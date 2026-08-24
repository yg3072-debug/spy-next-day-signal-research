"""Position sizing: turning a predicted return into a position.

The rule is that a trade is only worth taking when its expected return covers
everything the trade costs. That is the whole content of the no-trade band, and
getting the cost side of it complete is the point: a band built from execution
cost alone lets through trades that clear the spread but not the financing, and
those lose money in expectation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def no_trade_band(
    cost_bps_per_side: float,
    financing: pd.Series,
    delta_multiple: float = 0.0,
) -> pd.Series:
    """Per-session threshold a predicted return must clear before trading.

        h_t = (1 + delta) * (2c + f_t)

    Both terms belong inside. `2c` is the round trip, since the intraday
    specification enters at the open and exits at the close every active day.
    `f_t` is the interest given up while the capital sits in equity, which the
    position pays whether or not it also pays a spread. The threshold is
    therefore time-varying: it moves with the short rate and shrinks on an early
    close, exactly as the costs it has to cover do.

    `delta_multiple` is a safety margin expressed as a multiple of the total
    cost, so it keeps its meaning when the cost scenario changes.
    """
    c = cost_bps_per_side / 1e4
    return (1.0 + delta_multiple) * (2.0 * c + financing)


def positions_from_expected_return(
    mu_hat: pd.Series,
    cost_bps_per_side: float,
    financing: pd.Series,
    delta_multiple: float = 0.0,
) -> pd.Series:
    """Map predicted returns to positions in {-1, 0, +1}.

    `mu_hat` must be a simple return, in the same units as the costs. Flat means
    the prediction does not cover the cost of acting on it, not that the
    prediction is near a quantile of its own distribution.
    """
    h = no_trade_band(cost_bps_per_side, financing, delta_multiple)
    w = pd.Series(0.0, index=mu_hat.index)
    w[mu_hat > h] = 1.0
    w[mu_hat < -h] = -1.0
    return w
