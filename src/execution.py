"""The two execution specifications, as objects rather than as a flag.

Protocol §2.2 is emphatic that close-to-close is a different strategy and not a
robustness check on open-to-close: it changes the prediction target, the holding
interval, the overnight exposure, the cost function, and the dominant source of
return. Writing it as `if spec == "c2c"` scattered through the driver would make
it look like a variant. Writing it as a second object with the same interface
keeps the two honest about how little they share.

The primary specification is reproduced here exactly as `run_p1.py` computes it,
and a test pins the two implementations against each other on P1's own output.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.strategy import no_trade_band

BORROW_DEFAULT_BPS = 25.0


@dataclass(frozen=True)
class OpenToClose:
    """Enter at t+1's open, exit at t+1's close. A day trade, both ways.

    An active session pays a full round trip, `2c`, because the position does not
    persist: there is nothing to net against tomorrow. It also forgoes bill
    interest for the hours it is held, and no overnight borrow is due on a short
    that never crosses a close.
    """

    name: str = "primary_open_to_close"
    extra_feature_lag: int = 0
    return_column: str = "realised_o2c"
    carry_column: str = "financing"

    def target(self, snapshot: pd.DataFrame) -> pd.Series:
        r = snapshot["Close"] / snapshot["Open"] - 1.0
        return r.shift(-1).rename("target_o2c_next")

    def carry(self, snapshot: pd.DataFrame, index: pd.Index) -> pd.Series:
        """Intraday financing for the session the position is held in."""
        from build_benchmarks import intraday_financing
        return intraday_financing(snapshot, snapshot.index).shift(-1).reindex(index)

    def positions(self, mu, cost_bps, carry, delta=0.0) -> pd.Series:
        band = no_trade_band(cost_bps, carry.loc[mu.index], delta)
        return np.sign(mu).where(mu.abs() > band, 0.0)

    def net(self, w, r, carry, cost_bps, calendar_days=None) -> pd.Series:
        c = cost_bps / 1e4
        return w * r.loc[w.index] - 2 * c * w.abs() - carry.loc[w.index] * w.abs()


@dataclass(frozen=True)
class CloseToClose:
    """Signal before t's close, execute market-on-close at t, hold to t+1's close.

    Three consequences the primary specification does not have.

    Features come from t−1, not t: the signal has to exist before the close it is
    executed at, so the whole feature matrix carries one more session of lag. That
    is `extra_feature_lag`, and it is the reason this is not a cost variant.

    Cost is `c·|Δw|`, not `2c·|w|`. A position that persists is not re-paid for,
    so the cost depends on the path and cannot be computed row by row from `w`
    alone. Holding +1 for a month costs one side at each end.

    A short crosses the close, so it owes borrow — accrued over calendar days, so
    a short held over a weekend is charged three.

    **The position rule is specified after P1 and before any C2C return was
    computed.** §2.2 fixes the target, the information lag, the cost function, the
    borrow and this specification's exploratory status, but it does not say how
    `mu_hat` becomes a position. That gap is recorded rather than papered over:
    every C2C row in the registry carries `specified_before_p1=false` and
    `specified_before_own_results=true`, which is the weaker of the two claims and
    the only one that is true.

    A single fixed threshold cannot serve here, and the first implementation of
    this class got it wrong. With `c·|Δw|` costs the three transitions cost
    different amounts — holding a position costs nothing, flat to long costs `c`,
    long to short costs `2c` — so one number compared against `|mu_hat|` prices all
    three identically and is simply the wrong shape. The rule is instead the
    one-step optimum over the three admissible positions:

        w_t = argmax over w in {-1, 0, +1} of
                  w * (mu_hat_t - rf_t) - c * |w - w_{t-1}| - b_t * max(-w, 0)

    This has no free parameter to tune: no margin, no threshold, no `δ`. It prices
    each transition at what that transition actually costs, and it reduces to the
    primary band's logic in the special case where every position is closed daily.
    It remains greedy in the one-step sense — it does not look ahead to the cost a
    position saves tomorrow — and that is a stated property, not a tuned one.
    """

    name: str = "alternative_close_to_close"
    extra_feature_lag: int = 1
    return_column: str = "realised_c2c"
    carry_column: str = "carry_rf"
    borrow_annual_bps: float = BORROW_DEFAULT_BPS

    def target(self, snapshot: pd.DataFrame) -> pd.Series:
        r = snapshot["Close"] / snapshot["Close"].shift(1) - 1.0
        return r.shift(-1).rename("target_c2c_next")

    def carry(self, snapshot: pd.DataFrame, index: pd.Index) -> pd.Series:
        """The risk-free accrual over the holding period, one session ahead."""
        from build_benchmarks import cash_return
        return cash_return(snapshot).shift(-1).reindex(index).fillna(0.0)

    def positions(self, mu, cost_bps, carry, delta=0.0, calendar_days=None) -> pd.Series:
        """One-step optimal position, given yesterday's.

        Path-dependent by construction: what a position costs today depends on what
        was held yesterday, so this cannot be vectorised into a threshold and is not
        written as one.
        """
        if delta:
            raise ValueError(
                "the close-to-close rule takes no safety margin; delta must be 0. "
                "A margin here would be a search over the trading rule of a "
                "specification that is already exploratory."
            )
        c = cost_bps / 1e4
        b = self.borrow_annual_bps / 1e4
        edge = (mu - carry.loc[mu.index]).to_numpy(dtype=float)
        if calendar_days is None:
            calendar_days = self._calendar_days(mu.index)
        days = calendar_days.loc[mu.index].to_numpy(dtype=float)

        out = np.zeros(len(edge))
        prev = 0.0
        for i in range(len(edge)):
            best, best_value = 0.0, -np.inf
            for w in (-1.0, 0.0, 1.0):
                value = w * edge[i] - c * abs(w - prev) - b * (days[i] / 365.0) * max(-w, 0.0)
                if value > best_value:
                    best, best_value = w, value
            out[i] = best
            prev = best
        return pd.Series(out, index=mu.index)

    @staticmethod
    def _calendar_days(index) -> pd.Series:
        """Days a position opened at t's close is carried, i.e. t to t+1."""
        return index.to_series().diff().dt.days.shift(-1).fillna(1.0)

    def net(self, w, r, carry, cost_bps, calendar_days=None) -> pd.Series:
        c = cost_bps / 1e4
        w = w.astype(float)
        # Opening cost included: the position before the first row is flat, and the
        # final position is closed out, so both ends are charged.
        prev = w.shift(1).fillna(0.0)
        turnover = (w - prev).abs()
        turnover.iloc[-1] += abs(w.iloc[-1])
        if calendar_days is None:
            calendar_days = self._calendar_days(w.index)
        borrow = (self.borrow_annual_bps / 1e4) * (calendar_days.loc[w.index] / 365.0) \
            * np.maximum(-w, 0.0)
        return w * (r.loc[w.index] - carry.loc[w.index]) - c * turnover - borrow


SPECS = {
    "primary_open_to_close": OpenToClose(),
    "alternative_close_to_close": CloseToClose(),
}


def get_spec(name: str):
    if name not in SPECS:
        raise KeyError(f"unknown execution specification {name!r}; have {sorted(SPECS)}")
    return SPECS[name]
