"""Compute every benchmark the strategy must be measured against.

Benchmarks are evaluated under the same execution specification, the same cost
model, and the same window as the strategy, and reported on returns in excess of
cash. Nothing here depends on a model, so these numbers are fixed before any
strategy exists and cannot be adjusted after seeing a result.

Return accounting
-----------------
Cash.  A flat position earns the short Treasury bill rate. Interest accrues on
settled end-of-day balances over actual calendar days, so a Friday-to-Monday gap
earns three days. The rate dated t is published by H.15 on the following business
day, so accrual for session t uses the rate dated t-1.

Primary specification (intraday, Open to Close).  Figures are excess returns on
unit notional: the active trading P&L of the position, stated against cash.

    excess = w * R_o2c - 2c|w| - f|w|

Cost is 2c on every active day because entry at the open and exit at the close are
a complete round trip, not a rebalance. The financing term f is the interest given
up while capital sits in equity rather than in bills, built from session length so
that a weekend is not double-counted and an early close is charged less. Charging
it is the default: a zero-cost collateral overlay is a financing structure that
would have to be specified, not a natural baseline for a study of an ETF.

Alternative specification (overnight, Close to Close).  Positions are held over
the close, so the capital is deployed and earns no cash return, and borrow accrues
over the calendar days the short is actually carried:

    excess = w * (R_c2c - rf) - c|dw| - b * (calendar days / 365) * max(-w, 0)

Sharpe ratios use excess returns throughout. Cash has zero excess return and zero
excess volatility, so its Sharpe is undefined and is reported as such rather than
as zero.
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.features import build_features  # noqa: E402
from src.stats import (  # noqa: E402
    ann_mean, bootstrap_difference, bootstrap_statistic,
    jobson_korkie_memmel, politis_white_block, sharpe,
)

ROOT = Path(__file__).resolve().parents[1]
INITIAL_TRAIN_SESSIONS = 1000          # sessions reserved before out-of-sample begins
COST_BPS_PER_SIDE = 2.0                # base case; c per side, 2c per round trip
COST_SCENARIOS_BPS = [0.0, 1.0, 2.0, 5.0, 10.0]
BORROW_ANNUAL = 0.0025                 # 25 bp/yr, SPY general collateral
TRADING_DAYS = 252


# --------------------------------------------------------------------------- data

def load_snapshot() -> tuple[pd.DataFrame, dict]:
    csv = sorted(glob.glob(str(ROOT / "data" / "market_inputs_*.csv")))[-1]
    manifest = json.loads(Path(csv.replace(".csv", ".manifest.json")).read_text("utf-8"))
    frame = pd.read_csv(csv, index_col="Date", parse_dates=True)
    return frame, manifest


def cash_return(frame: pd.DataFrame, column: str = "DGS3MO") -> pd.Series:
    """Daily cash return, accrued simply over actual calendar days on a 365 basis.

    DGS3MO is a constant-maturity coupon-equivalent yield, which for a bill under
    six months carries no intra-period compounding. It is therefore a *simple*
    annualised rate, not an effective annual rate, and must not be compounded as
    one: treating it as an APY understates the cash leg by about 4 bp a year over
    this sample, which flatters every excess return computed against it.

        rf_t = y_{t-1} / 100 * (calendar days since the previous session) / 365

    The one-session shift reflects the H.15 publication lag: the rate dated t is
    not known until the following business day. Calendar-day accrual means a
    Friday-to-Monday gap earns three days.
    """
    annual = frame[column].shift(1) / 100.0
    days = frame.index.to_series().diff().dt.days
    return (annual * days / 365.0).fillna(0.0)


# ------------------------------------------------------------------- performance

def performance(excess: pd.Series, total: pd.Series, weights: pd.Series) -> dict:
    """Metrics from a realised excess-return series and its total-return twin."""
    n = len(excess)
    years = n / TRADING_DAYS
    equity = (1.0 + total).cumprod()
    drawdown = equity / equity.cummax() - 1.0
    excess_vol = excess.std(ddof=1) * np.sqrt(TRADING_DAYS)

    downside = excess[excess < 0]
    sortino = (
        excess.mean() * TRADING_DAYS / (downside.std(ddof=1) * np.sqrt(TRADING_DAYS))
        if len(downside) > 1 and downside.std(ddof=1) > 0
        else np.nan
    )
    cagr = equity.iloc[-1] ** (1.0 / years) - 1.0
    max_dd = drawdown.min()

    return {
        "sessions": n,
        "years": round(years, 2),
        "ann_mean_excess": excess.mean() * TRADING_DAYS,
        "ann_mean_total": total.mean() * TRADING_DAYS,
        "cagr_total": cagr,
        "ann_vol_excess": excess_vol,
        "sharpe_excess": excess.mean() * TRADING_DAYS / excess_vol if excess_vol > 0 else np.nan,
        "sortino_excess": sortino,
        "max_drawdown": max_dd,
        "calmar": cagr / abs(max_dd) if max_dd < 0 else np.nan,
        "terminal_wealth": equity.iloc[-1],
        "participation_rate": (weights != 0).mean(),
        "avg_net_exposure": weights.mean(),
        "avg_gross_exposure": weights.abs().mean(),
        "turnover_per_year": weights.diff().abs().fillna(0).mean() * TRADING_DAYS,
        "hit_rate_active": np.nan,
    }


def breakeven_cost_o2c(weights: pd.Series, r_o2c: pd.Series) -> float:
    """One-side cost in bp at which the intraday specification's excess return is zero.

    Closed form: mean(w*r) - 2c*mean(|w|) = 0  =>  c* = mean(w*r) / (2*mean(|w|)).
    """
    gross = (weights * r_o2c).mean()
    exposure = weights.abs().mean()
    return np.nan if exposure == 0 else gross / (2.0 * exposure) * 1e4


def intraday_financing(frame: pd.DataFrame, index: pd.Index) -> pd.Series:
    """Interest forgone while capital sits in equity rather than in bills.

        f_t = (y_{t-1} / 100) * session_minutes_t / (365 * 24 * 60)

    Charging a fraction of the *daily* cash return would double-count weekends,
    because that return already spans three calendar days after a Friday. The
    position is open for one session, not for a fraction of the gap since the
    previous one. Using session_minutes also handles early closes without a
    special case: a 210-minute session forgoes proportionally less.
    """
    annual = frame.loc[index, "DGS3MO"].shift(1) / 100.0
    minutes = frame.loc[index, "session_minutes"]
    return (annual * minutes / (365.0 * 24.0 * 60.0)).fillna(0.0)


def run_o2c(
    weights: pd.Series, r_o2c: pd.Series, rf: pd.Series, cost_bps: float,
    financing: pd.Series | None = None,
) -> dict:
    """Intraday specification: full round trip on every active day.

    Reported quantities are excess returns on unit notional: the active trading
    P&L of the position, stated against cash.

    Pass `financing` to charge the interest given up while capital is in equity
    rather than in bills; see `intraday_financing`. That is the conservative
    default and the one used throughout, because a zero-cost collateral overlay is
    a financing structure that would have to be specified and justified, not a
    natural baseline for a study of an ETF. On this sample the charge is about
    0.53% a year at full participation, roughly 0.10 bp per side. Omitting it is
    the pre-declared sensitivity, not the default.
    """
    c = cost_bps / 1e4
    excess = weights * r_o2c - 2.0 * c * weights.abs()
    if financing is not None:
        excess = excess - financing * weights.abs()
    total = rf + excess
    stats = performance(excess, total, weights)
    stats["breakeven_cost_bps_per_side"] = breakeven_cost_o2c(weights, r_o2c)
    active = weights != 0
    if active.any():
        stats["hit_rate_active"] = (np.sign(weights[active]) == np.sign(r_o2c[active])).mean()
    return stats


def run_c2c(weights: pd.Series, r_c2c: pd.Series, rf: pd.Series, cost_bps: float) -> dict:
    """Overnight specification: cost on position changes, borrow on shorts."""
    c = cost_bps / 1e4
    dw = weights.diff()
    dw.iloc[0] = weights.iloc[0]                       # opening the initial position costs too
    # Borrow accrues over calendar days held, so a position carried across a
    # weekend is charged three days, not one.
    held_days = weights.index.to_series().diff().dt.days.fillna(1.0)
    borrow = BORROW_ANNUAL * (held_days / 365.0) * np.maximum(-weights, 0.0)
    excess = weights * (r_c2c - rf) - c * dw.abs() - borrow
    total = rf + excess
    stats = performance(excess, total, weights)
    active = weights != 0
    if active.any():
        stats["hit_rate_active"] = (np.sign(weights[active]) == np.sign(r_c2c[active])).mean()
    return stats


# -------------------------------------------------------------------- benchmarks

def o2c_benchmarks(d: pd.DataFrame) -> dict[str, pd.Series]:
    """Weight series for every intraday benchmark. All inputs are lagged."""
    r_o2c = np.log(d.Close / d.Open)                   # sign only, used for direction rules
    r_c2c = np.log(d.Close / d.Close.shift(1))
    one = pd.Series(1.0, index=d.index)
    return {
        "Cash": one * 0.0,
        "Always-long O2C": one,
        "Always-short O2C": -one,
        "Prior-day O2C direction": np.sign(r_o2c.shift(1)).fillna(0.0),
        "Prior-day C2C direction": np.sign(r_c2c.shift(1)).fillna(0.0),
        "5-day momentum": np.sign(r_c2c.rolling(5).sum().shift(1)).fillna(0.0),
        "5-day reversal": -np.sign(r_c2c.rolling(5).sum().shift(1)).fillna(0.0),
    }


def c2c_benchmarks(d: pd.DataFrame) -> dict[str, pd.Series]:
    r_c2c = np.log(d.Close / d.Close.shift(1))
    one = pd.Series(1.0, index=d.index)
    return {
        "SPY buy-and-hold": one,
        "Prior-day C2C direction (C2C spec)": np.sign(r_c2c.shift(1)).fillna(0.0),
        "5-day momentum (C2C spec)": np.sign(r_c2c.rolling(5).sum().shift(1)).fillna(0.0),
        "5-day reversal (C2C spec)": -np.sign(r_c2c.rolling(5).sum().shift(1)).fillna(0.0),
    }


def decompose_vs_always_long(
    weights: pd.Series, r_o2c: pd.Series, cost_bps: float,
    financing: pd.Series | None = None,
) -> dict:
    """Split the excess over always-long O2C into what the direction calls earned
    and what was saved by not being in the market.

        R_strategy - R_always_long
            = (w - 1) * R_o2c  +  2c * (1 - |w|)  +  f * (1 - |w|)
              └ timing ─┘        └ cost saving ┘    └ financing saving ┘

    Only the first term is evidence of predictive ability. The other two accrue to
    anything that trades less, so a strategy with no skill at all can beat a
    loss-making always-on benchmark on the sum. Reporting them apart is what stops
    that from being read as alpha.
    """
    c = cost_bps / 1e4
    timing = (weights - 1.0) * r_o2c
    saving = 2.0 * c * (1.0 - weights.abs())
    fin_saving = (
        financing * (1.0 - weights.abs())
        if financing is not None
        else pd.Series(0.0, index=weights.index)
    )
    total = timing + saving + fin_saving
    return {
        "ann_gross_timing": timing.mean() * TRADING_DAYS,
        "ann_cost_saving": saving.mean() * TRADING_DAYS,
        "ann_financing_saving": fin_saving.mean() * TRADING_DAYS,
        "ann_net_excess_vs_always_long": total.mean() * TRADING_DAYS,
    }


def volatility_matched(returns: pd.Series, target_ann_vol: float) -> pd.Series:
    """Scale a return series to a target annualised volatility.

    Sharpe is invariant to this scaling, so a volatility-matched benchmark answers a
    question about return and drawdown levels, not about risk-adjusted ranking. The
    target is the strategy's realised volatility and is therefore supplied once a
    strategy exists; the always-long O2C volatility is used here as a placeholder.
    """
    realised = returns.std(ddof=1) * np.sqrt(TRADING_DAYS)
    return returns * (target_ann_vol / realised) if realised > 0 else returns


# -------------------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--reps", type=int, default=10_000, help="bootstrap resamples; 0 to skip")
    ap.add_argument("--block", type=float, default=20.0, help="mean block length in sessions")
    args = ap.parse_args()
    reps, block = args.reps, args.block

    d, manifest = load_snapshot()
    rf_all = cash_return(d)
    fin_all = intraday_financing(d, d.index)   # charged by default; parity with P1

    r_o2c = pd.Series(d.Close.values / d.Open.values - 1.0, index=d.index)   # simple
    r_c2c = d.Close.pct_change().fillna(0.0)

    # The out-of-sample window must be identical to the strategy's. Features need a
    # warm-up before any row is complete, so the initial training block is counted
    # from the first complete feature row, not from the first session in the file.
    features, _ = build_features(d)
    modelling_index = features.dropna().index
    oos_index = modelling_index[INITIAL_TRAIN_SESSIONS:]
    windows = {"full": d.index, "oos": oos_index}

    rows = []
    for wname, idx in windows.items():
        for cost in COST_SCENARIOS_BPS:
            for name, w in o2c_benchmarks(d).items():
                stats = run_o2c(w.loc[idx], r_o2c.loc[idx], rf_all.loc[idx], cost,
                                financing=fin_all.loc[idx])
                rows.append({"window": wname, "spec": "O2C", "benchmark": name,
                             "cost_bps_per_side": cost, **stats})
            for name, w in c2c_benchmarks(d).items():
                stats = run_c2c(w.loc[idx], r_c2c.loc[idx], rf_all.loc[idx], cost)
                rows.append({"window": wname, "spec": "C2C", "benchmark": name,
                             "cost_bps_per_side": cost, **stats})

    table = pd.DataFrame(rows)
    outdir = ROOT / "results"
    outdir.mkdir(exist_ok=True)
    table.to_csv(outdir / "benchmark_comparison.csv", index=False, float_format="%.8g")

    # Cash context, for the write-up.
    oos = windows["oos"]
    cash_meta = {
        "snapshot_sha256": manifest["sha256"],
        "initial_train_sessions": INITIAL_TRAIN_SESSIONS,
        "oos_first_session": str(oos.min().date()),
        "oos_last_session": str(oos.max().date()),
        "oos_sessions": int(len(oos)),
        "base_cost_bps_per_side": COST_BPS_PER_SIDE,
        "base_cost_bps_round_trip": 2 * COST_BPS_PER_SIDE,
        "rf_series": "DGS3MO, bond-equivalent yield, actual/365 calendar-day accrual, lagged one session",
        "rf_mean_annual_pct_full": float(d.DGS3MO.mean()),
        "rf_mean_annual_pct_oos": float(d.loc[oos, "DGS3MO"].mean()),
        "cash_cumulative_return_oos": float((1 + rf_all.loc[oos]).prod() - 1),
    }
    (outdir / "benchmark_context.json").write_text(json.dumps(cash_meta, indent=2), "utf-8")

    # ------------------------------------------------------------------ report
    pd.set_option("display.width", 200, "display.max_columns", 50)
    base = table[(table.window == "oos") & (table.cost_bps_per_side == COST_BPS_PER_SIDE)]
    cols = ["spec", "benchmark", "ann_mean_excess", "cagr_total", "ann_vol_excess",
            "sharpe_excess", "max_drawdown", "calmar", "participation_rate",
            "hit_rate_active", "breakeven_cost_bps_per_side"]

    print(f"OOS window        {cash_meta['oos_first_session']} .. {cash_meta['oos_last_session']}"
          f"  ({cash_meta['oos_sessions']} sessions)")
    print(f"Base cost         {COST_BPS_PER_SIDE:g} bp per side = {2*COST_BPS_PER_SIDE:g} bp round trip")
    print(f"Cash rate (OOS)   {cash_meta['rf_mean_annual_pct_oos']:.2f}% mean annual, "
          f"cumulative {cash_meta['cash_cumulative_return_oos']:.2%}")
    print(f"\n{'='*150}\nBENCHMARKS at base cost, out-of-sample window\n{'='*150}")
    print(base[cols].to_string(index=False, float_format=lambda v: f"{v:9.4f}"))

    print(f"\n{'='*150}\nAlways-long O2C across cost scenarios (out-of-sample)\n{'='*150}")
    al = table[(table.window == "oos") & (table.benchmark == "Always-long O2C")]
    print(al[["cost_bps_per_side", "ann_mean_excess", "cagr_total", "ann_vol_excess",
              "sharpe_excess", "max_drawdown"]].to_string(index=False,
              float_format=lambda v: f"{v:10.4f}"))

    print(f"\n{'='*150}\nDecomposition check: what a no-skill flat strategy earns against always-long O2C\n{'='*150}")
    print("A strategy that never trades has w = 0 everywhere. Its entire advantage over the")
    print("always-long benchmark is cost saving, with zero timing contribution.\n")
    zero = pd.Series(0.0, index=oos)
    for cost in (1.0, 2.0, 5.0):
        dec = decompose_vs_always_long(zero, r_o2c.loc[oos], cost, fin_all.loc[oos])
        print(f"  c={cost:g} bp/side   gross timing {dec['ann_gross_timing']:+.2%}"
              f"   cost saving {dec['ann_cost_saving']:+.2%}"
              f"   financing saving {dec['ann_financing_saving']:+.2%}"
              f"   net {dec['ann_net_excess_vs_always_long']:+.2%}")

    # ------------------------------------------------------------------ intervals
    if reps:
        print(f"\n{'='*150}")
        print(f"Stationary bootstrap, {reps:,} resamples, mean block {block:g} sessions")
        print(f"{'='*150}")
        c = COST_BPS_PER_SIDE / 1e4
        excess = {
            name: (w.loc[oos] * r_o2c.loc[oos] - 2 * c * w.loc[oos].abs()
                   - fin_all.loc[oos] * w.loc[oos].abs())
            for name, w in o2c_benchmarks(d).items()
        }
        excess["SPY buy-and-hold"] = r_c2c.loc[oos] - rf_all.loc[oos]

        ref_long = excess["Always-long O2C"]
        ref_cash = excess["Cash"]
        irows = []
        for name, e in excess.items():
            flat = e.std(ddof=1) == 0
            row = {
                "benchmark": name,
                "politis_white_block": np.nan if flat else politis_white_block(e),
                "sharpe": np.nan if flat else sharpe(e.to_numpy()),
            }
            if not flat:
                sr = bootstrap_statistic(e, sharpe, block, reps)
                row["sharpe_ci_low"], row["sharpe_ci_high"] = sr["ci_low"], sr["ci_high"]
            am = bootstrap_statistic(e, ann_mean, block, reps)
            row["ann_mean_excess"] = am["point"]
            row["ann_mean_ci_low"], row["ann_mean_ci_high"] = am["ci_low"], am["ci_high"]

            if name not in ("Always-long O2C", "Cash") and not flat:
                dl = bootstrap_difference(e, ref_long, sharpe, block, reps)
                row["d_sharpe_vs_long"] = dl["point"]
                row["d_sharpe_vs_long_ci_low"] = dl["ci_low"]
                row["d_sharpe_vs_long_frac_le_0"] = dl["fraction_le_zero"]
                row["jk_memmel_p"] = jobson_korkie_memmel(e, ref_long)["p_two_sided"]
            if name != "Cash":
                dc = bootstrap_difference(e, ref_cash, ann_mean, block, reps)
                row["d_annmean_vs_cash_ci_low"] = dc["ci_low"]
                row["d_annmean_vs_cash_frac_le_0"] = dc["fraction_le_zero"]
            irows.append(row)

        intervals = pd.DataFrame(irows)
        intervals.to_csv(outdir / "benchmark_intervals.csv", index=False, float_format="%.8g")
        show = [
            "benchmark", "politis_white_block", "sharpe", "sharpe_ci_low", "sharpe_ci_high",
            "d_sharpe_vs_long", "d_sharpe_vs_long_ci_low", "d_sharpe_vs_long_frac_le_0",
            "d_annmean_vs_cash_ci_low",
        ]
        print(intervals[show].to_string(index=False, float_format=lambda v: f"{v:8.3f}"))
        print(f"\nWrote {outdir/'benchmark_intervals.csv'}")

    print(f"\nWrote {outdir/'benchmark_comparison.csv'}  ({len(table)} rows)")
    print(f"Wrote {outdir/'benchmark_context.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
