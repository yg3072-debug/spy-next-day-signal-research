"""Feature construction.

Every feature is a function of information available at or before the close of
session t. The target it predicts is the next session's open-to-close return, so
a feature that peeks even one session ahead invalidates the whole study. Two
things enforce that here: every transform is causal by construction, and
`tests/test_features.py` verifies it empirically by rebuilding the whole frame on
truncated history and requiring the overlapping values to be identical.

Each feature carries metadata — group, formula, economic rationale, availability,
and whether it survives a revision to the price adjustment factor. The metadata is
the single source of truth: `docs/feature_dictionary.md` is generated from it, so
the documentation cannot drift from the code.

Publication lag.  Treasury yields from H.15 are published the business day after
the date they carry, so features derived from DGS2 and DGS10 are shifted one extra
session. Everything else is available at the close of the session it is dated.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import pandas_market_calendars as mcal

MACRO_LAGS = [1, 2, 3, 5, 10, 20]
STYLE_LAGS = [1, 2, 3, 5, 10]
SMA_WINDOWS = [5, 10, 20, 50]
VOL_WINDOWS = [5, 10, 20, 60]
Z_WINDOWS = [20, 60]


@dataclass
class Feature:
    """One column, with everything needed to defend it in review."""

    name: str
    group: str
    formula: str
    rationale: str
    adjustment_invariant: bool
    extra_lag_sessions: int = 0
    notes: str = ""


REGISTRY: list[Feature] = []


def register(**kwargs) -> Feature:
    f = Feature(**kwargs)
    REGISTRY.append(f)
    return f


# --------------------------------------------------------------------------- 1

def _lagged_returns(d: pd.DataFrame, out: pd.DataFrame) -> None:
    """Recent realised returns. Short-horizon index returns mean-revert weakly."""
    close = d["Close"]
    out["log_ret"] = np.log(close / close.shift(1))
    register(name="log_ret", group="lagged_return",
             formula="log(Close_t / Close_{t-1})",
             rationale="Yesterday's move. The base term for short-horizon reversal.",
             adjustment_invariant=True)
    for lag in [2, 3, 5, 10]:
        out[f"ret_lag_{lag}"] = np.log(close / close.shift(lag))
        register(name=f"ret_lag_{lag}", group="lagged_return",
                 formula=f"log(Close_t / Close_{{t-{lag}}})",
                 rationale=f"Cumulative {lag}-session move; separates reversal from momentum by horizon.",
                 adjustment_invariant=True)


def _trend(d: pd.DataFrame, out: pd.DataFrame) -> None:
    """Distance from a moving average, as a fraction. Trend-following proxy."""
    close = d["Close"]
    for w in SMA_WINDOWS:
        sma = close.rolling(w).mean()
        out[f"SMA_gap_{w}"] = (close - sma) / sma
        register(name=f"SMA_gap_{w}", group="trend",
                 formula=f"(Close_t - SMA{w}_t) / SMA{w}_t",
                 rationale=f"Stretch above or below the {w}-session average. Expressed as a "
                           "ratio so it is comparable across price levels.",
                 adjustment_invariant=True)


def _momentum(d: pd.DataFrame, out: pd.DataFrame) -> None:
    close = d["Close"]
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    out["RSI_14"] = 100 - 100 / (1 + avg_gain / avg_loss)
    register(name="RSI_14", group="momentum",
             formula="100 - 100/(1 + EWM(gain,14)/EWM(loss,14))",
             rationale="Bounded overbought/oversold gauge. Extreme readings are the "
                       "classic short-horizon reversal signal.",
             adjustment_invariant=True,
             notes="Wilder smoothing via EWM with adjust=False, which is causal.")

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    out["MACD_hist"] = macd - macd.ewm(span=9, adjust=False).mean()
    register(name="MACD_hist", group="momentum",
             formula="(EMA12 - EMA26) - EMA9(EMA12 - EMA26)",
             rationale="Acceleration of trend. Sign changes mark momentum turning points.",
             adjustment_invariant=False,
             notes="A difference of price levels, not a ratio, so it scales with the "
                   "adjustment factor. Sign and relative magnitude survive; the level does not.")


def _volatility(d: pd.DataFrame, out: pd.DataFrame) -> None:
    log_ret = np.log(d["Close"] / d["Close"].shift(1))
    for w in VOL_WINDOWS:
        out[f"Volatility_{w}"] = log_ret.rolling(w).std()
        register(name=f"Volatility_{w}", group="volatility",
                 formula=f"std(log return, {w} sessions)",
                 rationale=f"Realised volatility over {w} sessions. Conditions the strength "
                           "of any reversal effect and scales the label.",
                 adjustment_invariant=True)


def _bollinger(d: pd.DataFrame, out: pd.DataFrame) -> None:
    close = d["Close"]
    mean20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    upper, lower = mean20 + 2 * std20, mean20 - 2 * std20
    out["BB_width"] = (upper - lower) / mean20
    out["BB_percent_b"] = (close - lower) / (upper - lower)
    register(name="BB_width", group="bollinger",
             formula="(upper - lower) / SMA20,  bands at +/- 2 sd",
             rationale="Band width is realised volatility in price-relative form; "
                       "narrow bands often precede expansion.",
             adjustment_invariant=True)
    register(name="BB_percent_b", group="bollinger",
             formula="(Close - lower) / (upper - lower)",
             rationale="Position within the band. Near 0 or 1 marks a stretched price.",
             adjustment_invariant=True)


def _macro_changes(d: pd.DataFrame, out: pd.DataFrame) -> None:
    out["VIX"] = d["VIX"]
    register(name="VIX", group="macro_change", formula="VIX close",
             rationale="Level of implied volatility. The primary risk-appetite state variable.",
             adjustment_invariant=True)
    specs = [("VIX", "log", "implied volatility"),
             ("DXY", "log", "the dollar"),
             ("TNX", "diff", "the 10-year yield"),
             ("OIL", "log", "Brent crude")]
    for col, kind, label in specs:
        for lag in MACRO_LAGS:
            if kind == "log":
                name = f"{col}_ret_{lag}"
                out[name] = np.log(d[col] / d[col].shift(lag))
                formula = f"log({col}_t / {col}_{{t-{lag}}})"
            else:
                name = f"{col}_change_{lag}"
                out[name] = d[col] - d[col].shift(lag)
                formula = f"{col}_t - {col}_{{t-{lag}}}"
            register(name=name, group="macro_change", formula=formula,
                     rationale=f"{lag}-session move in {label}; cross-asset risk-off transmission.",
                     adjustment_invariant=True,
                     notes="Differences, not ratios: TNX is already a yield level."
                           if kind == "diff" else "")


def _macro_zscores(d: pd.DataFrame, out: pd.DataFrame) -> None:
    for col in ["VIX", "DXY", "TNX", "OIL"]:
        for w in Z_WINDOWS:
            roll = d[col].rolling(w)
            out[f"{col}_z_{w}"] = (d[col] - roll.mean()) / roll.std()
            register(name=f"{col}_z_{w}", group="macro_zscore",
                     formula=f"({col}_t - mean_{w}) / sd_{w},  trailing window",
                     rationale=f"Where {col} sits relative to its own recent range, which "
                               "matters more than its absolute level.",
                     adjustment_invariant=True)


def _yield_curve(d: pd.DataFrame, out: pd.DataFrame) -> None:
    """Term spread. Shifted one extra session for the H.15 publication delay."""
    spread = (d["DGS10"] - d["DGS2"]).shift(1)
    out["YC_2Y10Y_change_1"] = spread.diff(1)
    register(name="YC_2Y10Y_change_1", group="yield_curve",
             formula="(DGS10 - DGS2)_{t-1} - (DGS10 - DGS2)_{t-2}",
             rationale="Daily change in the term spread; a fast read on growth and "
                       "policy expectations.",
             adjustment_invariant=True, extra_lag_sessions=1,
             notes="H.15 publishes the value dated t on the next business day.")
    for w in Z_WINDOWS:
        roll = spread.rolling(w)
        out[f"YC_2Y10Y_z_{w}"] = (spread - roll.mean()) / roll.std()
        register(name=f"YC_2Y10Y_z_{w}", group="yield_curve",
                 formula=f"z-score of the lagged term spread over {w} sessions",
                 rationale="Term-spread position relative to its recent range.",
                 adjustment_invariant=True, extra_lag_sessions=1)


def _intraday(d: pd.DataFrame, out: pd.DataFrame) -> None:
    close, open_, high, low = d["Close"], d["Open"], d["High"], d["Low"]
    out["intraday_ret"] = np.log(close / open_)
    register(name="intraday_ret", group="intraday",
             formula="log(Close_t / Open_t)",
             rationale="The previous session's open-to-close return, which is the lag-1 "
                       "of the prediction target itself. Any autocorrelation in intraday "
                       "returns shows up here first.",
             adjustment_invariant=True,
             notes="Same-session ratio, so the adjustment factor cancels exactly.")
    out["overnight_gap"] = np.log(open_ / close.shift(1))
    register(name="overnight_gap", group="intraday",
             formula="log(Open_t / Close_{t-1})",
             rationale="The overnight move, which the target deliberately excludes. "
                       "Whether a gap is faded or extended during the session is the "
                       "central question this specification can answer.",
             adjustment_invariant=True)
    out["high_low_range"] = (high - low) / close
    register(name="high_low_range", group="intraday",
             formula="(High_t - Low_t) / Close_t",
             rationale="Realised intraday range; a volatility measure that does not need "
                       "a rolling window.",
             adjustment_invariant=True,
             notes="Mechanically compressed on early-close sessions.")
    spread = high - low
    out["close_location_value"] = np.where(spread != 0, (close - low) / spread, np.nan)
    register(name="close_location_value", group="intraday",
             formula="(Close - Low) / (High - Low),  undefined when High == Low",
             rationale="Where the session closed inside its range. Near 1 is a strong "
                       "close, near 0 a weak one.",
             adjustment_invariant=True)


def _volume(d: pd.DataFrame, out: pd.DataFrame) -> None:
    vol = d["Volume"]
    mean20, std20 = vol.rolling(20).mean(), vol.rolling(20).std()
    out["relative_volume_20"] = vol / mean20
    register(name="relative_volume_20", group="volume",
             formula="Volume_t / mean(Volume, 20)",
             rationale="Participation relative to the recent norm. Moves on heavy volume "
                       "are held to persist more often than moves on light volume.",
             adjustment_invariant=True,
             notes="A ratio of raw volumes, so the missing volume adjustment cancels.")
    out["volume_z_20"] = (vol - mean20) / std20
    register(name="volume_z_20", group="volume",
             formula="(Volume_t - mean_20) / sd_20",
             rationale="Standardised abnormal volume.",
             adjustment_invariant=True)
    out["volume_ret_interaction"] = out["volume_z_20"] * np.log(d["Close"] / d["Close"].shift(1))
    register(name="volume_ret_interaction", group="volume",
             formula="volume_z_20 * log(Close_t / Close_{t-1})",
             rationale="A large move on abnormal volume is treated differently from the "
                       "same move on quiet volume.",
             adjustment_invariant=True,
             notes="Invariant to dividend adjustment, which rescales the whole price "
                   "history by one factor that cancels inside the log ratio. It is the "
                   "only feature exposed to a *split*, which changes Volume without "
                   "changing the adjusted price and so distorts the 20-session volume "
                   "window around the split date. Verified: SPY, QQQ, IWM and DIA have no "
                   "split in this sample, the most recent being IWM in June 2005.")


def _calendar(d: pd.DataFrame, out: pd.DataFrame) -> None:
    """Deterministic and known years ahead, so there is no availability question."""
    idx = d.index
    out["is_monday"] = (idx.dayofweek == 0).astype(int)
    out["is_friday"] = (idx.dayofweek == 4).astype(int)
    register(name="is_monday", group="calendar", formula="1 if the session is a Monday",
             rationale="Day-of-week effects are weak and mostly historical; carried as a control.",
             adjustment_invariant=True)
    register(name="is_friday", group="calendar", formula="1 if the session is a Friday",
             rationale="Pre-weekend positioning; carried as a control.",
             adjustment_invariant=True)

    # Month boundaries come from the exchange calendar over whole months, so that a
    # partial final month cannot mislabel its last available row as the month end.
    cal = mcal.get_calendar("NYSE")
    sched = cal.schedule(
        start_date=idx.min().to_period("M").start_time.date(),
        end_date=idx.max().to_period("M").end_time.date(),
    )
    sessions = pd.DatetimeIndex(sched.index).tz_localize(None).normalize()
    by_month = pd.Series(sessions, index=sessions).groupby(sessions.to_period("M"))
    firsts = set(by_month.first().dt.normalize())
    lasts = set(by_month.last().dt.normalize())
    out["is_month_start"] = idx.normalize().isin(firsts).astype(int)
    out["is_month_end"] = idx.normalize().isin(lasts).astype(int)
    register(name="is_month_start", group="calendar",
             formula="1 on the first NYSE session of the month",
             rationale="Month-turn flows from index rebalancing and retirement contributions.",
             adjustment_invariant=True)
    register(name="is_month_end", group="calendar",
             formula="1 on the last NYSE session of the month",
             rationale="Month-end rebalancing flows.",
             adjustment_invariant=True)


def _regime(d: pd.DataFrame, out: pd.DataFrame) -> None:
    roll = d["VIX"].rolling(252, min_periods=60)
    out["vix_regime_high"] = (d["VIX"] > roll.quantile(0.75)).astype(int)
    out["vix_regime_low"] = (d["VIX"] < roll.quantile(0.25)).astype(int)
    for name, side in (("vix_regime_high", "above"), ("vix_regime_low", "below")):
        register(name=name, group="regime",
                 formula=f"1 if VIX_t is {side} its trailing 252-session "
                         f"{'75th' if side == 'above' else '25th'} percentile",
                 rationale="Reversal strength is widely held to depend on the volatility "
                           "state. These flags let a model condition on it.",
                 adjustment_invariant=True,
                 notes="Trailing quantiles only; min_periods=60 keeps the early sample honest.")


def _cross_market(d: pd.DataFrame, out: pd.DataFrame) -> None:
    labels = {"QQQ": "Nasdaq growth", "IWM": "small caps", "DIA": "blue chips"}
    for tk, label in labels.items():
        price = d[f"{tk}_Close"]
        for lag in STYLE_LAGS:
            out[f"{tk}_ret_{lag}"] = np.log(price / price.shift(lag))
            register(name=f"{tk}_ret_{lag}", group="cross_market",
                     formula=f"log({tk}_t / {tk}_{{t-{lag}}})",
                     rationale=f"{lag}-session return of {label}. Its spread against SPY "
                               "carries the risk-appetite rotation the index alone hides.",
                     adjustment_invariant=True)


BUILDERS = [
    _lagged_returns, _trend, _momentum, _volatility, _bollinger,
    _macro_changes, _macro_zscores, _yield_curve, _intraday,
    _volume, _calendar, _regime, _cross_market,
]


def build_features(snapshot: pd.DataFrame) -> tuple[pd.DataFrame, list[Feature]]:
    """Build every candidate feature from a frozen snapshot.

    The study's own snapshot is licensed and is not distributed with this
    repository; this function takes whatever frame it is handed.

    Returns the feature frame and the metadata registry, in registration order.
    """
    REGISTRY.clear()
    out = pd.DataFrame(index=snapshot.index)
    for builder in BUILDERS:
        builder(snapshot, out)
    names = [f.name for f in REGISTRY]
    if len(names) != len(set(names)):
        dupes = sorted({n for n in names if names.count(n) > 1})
        raise RuntimeError(f"duplicate feature names: {dupes}")
    missing = sorted(set(names) - set(out.columns))
    extra = sorted(set(out.columns) - set(names))
    if missing or extra:
        raise RuntimeError(f"registry and frame disagree; missing {missing}, unregistered {extra}")
    return out[names], list(REGISTRY)


def build_target(snapshot: pd.DataFrame) -> pd.Series:
    """Next session's open-to-close simple return, the primary specification's target.

    Simple rather than log because the backtest compounds it and subtracts costs in
    the same units. It is shifted back to session t so that row t holds the value a
    decision taken after t's close is trying to predict.
    """
    r = snapshot["Close"] / snapshot["Open"] - 1.0
    return r.shift(-1).rename("target_o2c_next")
