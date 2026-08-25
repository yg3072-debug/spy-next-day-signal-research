"""Checks on the position rule.

The band exists to stop trades whose expected return does not cover their cost.
The case that matters is the one between the two cost components: a prediction
that clears the spread but not the financing must not trade.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from build_benchmarks import intraday_financing, load_snapshot  # noqa: E402
from src.strategy import no_trade_band, positions_from_expected_return  # noqa: E402

COST = 2.0
C = COST / 1e4


@pytest.fixture(scope="module")
def financing(market_frame):
    # Session length and the short rate; the band's behaviour is what is under
    # test, and it holds on synthetic input as well as real.
    frame = market_frame
    return frame, intraday_financing(frame, frame.index)


def test_band_covers_execution_and_financing(financing):
    frame, f = financing
    h = no_trade_band(COST, f)
    pd.testing.assert_series_equal(h, 2 * C + f, check_names=False)
    # Never below the round trip, and strictly above it whenever the short rate
    # is positive. It can equal it: financing is zero on the first session, which
    # has no prior rate, and on sessions where the rate itself was zero.
    assert (h >= 2 * C - 1e-15).all()
    assert (h[f > 0] > 2 * C).all()
    assert (f > 0).mean() > 0.9, "financing should be positive on most sessions"


def test_a_prediction_between_the_two_costs_does_not_trade(financing):
    """The case the reviewer flagged: 2c < mu_hat < 2c + f must stay flat.

    A band built from execution cost alone would take this trade, and it loses
    money in expectation because the financing is still owed.
    """
    frame, f = financing
    lit = frame.DGS3MO.shift(1) > 1.0        # a stretch where financing is not ~0
    idx = frame.index[lit][-500:]
    fin = f.loc[idx]
    assert (fin > 0).all()

    mu = 2 * C + fin / 2.0                   # clears the spread, not the financing
    w = positions_from_expected_return(mu, COST, fin)
    assert (w == 0).all(), "a trade that cannot cover financing was taken"

    # Sanity: the same prediction against an execution-only band would have traded.
    execution_only = pd.Series(2 * C, index=idx)
    assert (mu > execution_only).all()


def test_a_prediction_above_the_full_cost_trades(financing):
    frame, f = financing
    idx = frame.index[-500:]
    fin = f.loc[idx]
    mu = 2 * C + fin + 1e-5
    w = positions_from_expected_return(mu, COST, fin)
    assert (w == 1.0).all()
    assert (positions_from_expected_return(-mu, COST, fin) == -1.0).all()


def test_delta_scales_the_whole_cost_not_just_execution(financing):
    frame, f = financing
    fin = f.loc[frame.index[-200:]]
    base = no_trade_band(COST, fin, 0.0)
    wide = no_trade_band(COST, fin, 1.0)
    pd.testing.assert_series_equal(wide, 2 * base, check_names=False)


def test_band_shrinks_on_an_early_close(financing):
    """Financing scales with session length, so the band does too."""
    frame, f = financing
    lit = frame.DGS3MO.shift(1) > 1.0
    h = no_trade_band(COST, f)
    short = h[(frame.session_minutes == 210) & lit]
    full = h[(frame.session_minutes == 390) & lit]
    assert short.mean() < full.mean()


def test_band_is_time_varying_with_the_short_rate(financing):
    frame, f = financing
    h = no_trade_band(COST, f)
    high = h[frame.DGS3MO.shift(1) > 4.0]
    low = h[frame.DGS3MO.shift(1) < 0.5]
    assert len(high) > 0 and len(low) > 0
    assert high.mean() > low.mean()


def test_zero_financing_reduces_to_the_execution_band(financing):
    frame, _ = financing
    idx = frame.index[-100:]
    zero = pd.Series(0.0, index=idx)
    h = no_trade_band(COST, zero)
    assert h.to_numpy() == pytest.approx(2 * C)
