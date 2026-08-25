"""Checks on the benchmark layer.

These assert identities and invariants, not values. A test that pins a number
would have to be rewritten whenever the snapshot is refreshed, and would then be
testing nothing.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from build_benchmarks import (  # noqa: E402
    TRADING_DAYS,
    breakeven_cost_o2c,
    cash_return,
    decompose_vs_always_long,
    intraday_financing,
    load_snapshot,
    run_c2c,
    run_o2c,
    volatility_matched,
)
from src.stats import bootstrap_difference, sharpe  # noqa: E402


@pytest.fixture(scope="module")
def snapshot(market_frame):
    # The snapshot is not distributed; `market_frame` supplies a real one when the
    # user has obtained it and the synthetic fixture otherwise. What this file
    # asserts holds on either, because it is about the code.
    return market_frame


@pytest.fixture(scope="module")
def pieces(snapshot):
    d = snapshot
    r_o2c = pd.Series(d.Close.values / d.Open.values - 1.0, index=d.index)
    return d, r_o2c, cash_return(d)


# ------------------------------------------------------------------ identities

def test_decomposition_is_an_exact_identity(pieces):
    """(w-1)*r + 2c(1-|w|) must equal the strategy's excess minus the benchmark's.

    This is algebra, so it should hold to floating-point precision for any weight
    series, not just for the tidy ones.
    """
    _, r_o2c, _ = pieces
    rng = np.random.default_rng(0)
    for c_bps in (0.0, 2.0, 7.5):
        c = c_bps / 1e4
        for w in (
            pd.Series(0.0, index=r_o2c.index),
            pd.Series(1.0, index=r_o2c.index),
            pd.Series(rng.choice([-1.0, 0.0, 1.0], size=len(r_o2c)), index=r_o2c.index),
        ):
            strategy = w * r_o2c - 2 * c * w.abs()
            always_long = r_o2c - 2 * c
            direct = (strategy - always_long).mean() * TRADING_DAYS
            decomposed = decompose_vs_always_long(w, r_o2c, c_bps)
            assert decomposed["ann_net_excess_vs_always_long"] == pytest.approx(direct, abs=1e-12)
            assert (
                decomposed["ann_gross_timing"] + decomposed["ann_cost_saving"]
                == pytest.approx(direct, abs=1e-12)
            )


def test_flat_strategy_earns_only_cost_saving(pieces):
    """Doing nothing has zero timing contribution by construction."""
    _, r_o2c, _ = pieces
    flat = pd.Series(0.0, index=r_o2c.index)
    dec = decompose_vs_always_long(flat, r_o2c, 2.0)
    # The timing term is exactly the forgone drift; the saving term is exactly 2c.
    assert dec["ann_gross_timing"] == pytest.approx(-r_o2c.mean() * TRADING_DAYS, abs=1e-12)
    assert dec["ann_cost_saving"] == pytest.approx(2 * 2e-4 * TRADING_DAYS, abs=1e-12)


def test_breakeven_cost_zeroes_the_excess(pieces):
    """Running the backtest at c* must produce zero mean excess return."""
    _, r_o2c, rf = pieces
    rng = np.random.default_rng(1)
    for w in (
        pd.Series(1.0, index=r_o2c.index),
        pd.Series(rng.choice([-1.0, 0.0, 1.0], size=len(r_o2c)), index=r_o2c.index),
    ):
        c_star = breakeven_cost_o2c(w, r_o2c)
        stats = run_o2c(w, r_o2c, rf, c_star)
        assert stats["ann_mean_excess"] == pytest.approx(0.0, abs=1e-12)


def test_breakeven_accounts_for_financing(pieces, snapshot):
    """With financing charged, c* must fall: less execution cost can be absorbed."""
    _, r_o2c, rf = pieces
    w = pd.Series(1.0, index=r_o2c.index)
    f = intraday_financing(snapshot, r_o2c.index)
    c_free = breakeven_cost_o2c(w, r_o2c)
    c_charged = breakeven_cost_o2c(w, r_o2c, f)
    assert c_charged < c_free
    stats = run_o2c(w, r_o2c, rf, c_charged, financing=f)
    assert stats["ann_mean_excess"] == pytest.approx(0.0, abs=1e-12)


# --------------------------------------------------------------- accounting

def test_cash_has_zero_excess_return(pieces):
    _, r_o2c, rf = pieces
    flat = pd.Series(0.0, index=r_o2c.index)
    stats = run_o2c(flat, r_o2c, rf, 2.0)
    assert stats["ann_mean_excess"] == pytest.approx(0.0, abs=1e-15)
    assert stats["ann_vol_excess"] == pytest.approx(0.0, abs=1e-15)
    assert np.isnan(stats["sharpe_excess"])
    # Cash still earns something in total-return terms.
    assert stats["ann_mean_total"] > 0


def test_zero_cost_always_long_reproduces_the_raw_series(pieces):
    _, r_o2c, rf = pieces
    long_only = pd.Series(1.0, index=r_o2c.index)
    stats = run_o2c(long_only, r_o2c, rf, 0.0)
    assert stats["ann_mean_excess"] == pytest.approx(r_o2c.mean() * TRADING_DAYS, abs=1e-14)
    assert stats["sharpe_excess"] == pytest.approx(sharpe(r_o2c.to_numpy()), abs=1e-12)


def test_cost_is_a_round_trip_not_a_rebalance(pieces):
    """Holding the same position two days running still costs two round trips."""
    _, r_o2c, rf = pieces
    long_only = pd.Series(1.0, index=r_o2c.index)
    free = run_o2c(long_only, r_o2c, rf, 0.0)["ann_mean_excess"]
    charged = run_o2c(long_only, r_o2c, rf, 2.0)["ann_mean_excess"]
    expected_drag = 2 * 2e-4 * TRADING_DAYS
    assert free - charged == pytest.approx(expected_drag, abs=1e-12)


def test_cash_accrues_over_calendar_days(snapshot):
    """A Friday-to-Monday gap must earn three days of interest, not one."""
    rf = cash_return(snapshot)
    gaps = snapshot.index.to_series().diff().dt.days
    mondays = rf[(gaps == 3) & (snapshot.DGS3MO.shift(1) > 1.0)]
    singles = rf[(gaps == 1) & (snapshot.DGS3MO.shift(1) > 1.0)]
    assert mondays.mean() > 2.5 * singles.mean()


def test_cash_uses_the_lagged_publication():
    """The rate dated t must not be earned on session t.

    Correlation cannot show this: the three-month yield has autocorrelation near
    0.999, so a one-session shift is invisible to it. A synthetic series with a
    single non-zero rate pins the behaviour exactly.
    """
    idx = pd.bdate_range("2020-01-06", periods=5)
    rates = pd.Series(0.0, index=idx)
    rates.iloc[2] = 3.65                      # rate is published dated on the third session
    rf = cash_return(pd.DataFrame({"DGS3MO": rates}))

    assert rf.iloc[2] == pytest.approx(0.0, abs=1e-15), "rate dated t must not accrue on t"
    assert rf.iloc[3] > 0, "rate dated t must accrue on t+1"
    assert rf.iloc[4] == pytest.approx(0.0, abs=1e-15), "and only on t+1"
    # One calendar day of a 3.65% simple annualised yield: 0.0365 / 365 = 1 bp.
    assert rf.iloc[3] == pytest.approx(0.0365 / 365, rel=1e-12)


def test_cash_is_accrued_simply_not_as_an_effective_annual_rate():
    """DGS3MO is a coupon-equivalent yield on a sub-six-month bill, so it carries
    no intra-period compounding and must not be treated as an APY.

    Compounding it as `(1+y)^(d/365)-1` understates the cash leg, which in turn
    inflates every excess return measured against it.
    """
    idx = pd.bdate_range("2020-01-06", periods=3)
    rates = pd.Series(5.0, index=idx)
    rf = cash_return(pd.DataFrame({"DGS3MO": rates}))
    simple = 0.05 / 365
    compounded = 1.05 ** (1 / 365) - 1
    assert rf.iloc[2] == pytest.approx(simple, rel=1e-12)
    assert rf.iloc[2] > compounded, "simple accrual must exceed the compounded reading"


def test_intraday_financing_uses_session_length_not_a_share_of_the_daily_rate(snapshot, pieces):
    """Charging a fraction of the daily cash return double-counts weekends.

    The daily cash return after a Friday already spans three calendar days. A
    position is open for one session, so the charge must be built from session
    minutes, not scaled off that three-day accrual.
    """
    d = snapshot
    f = intraday_financing(d, d.index)

    # A Monday must not be charged three times a Tuesday at a comparable rate.
    gaps = d.index.to_series().diff().dt.days
    lit = d.DGS3MO.shift(1) > 1.0
    mondays = f[(gaps == 3) & lit & (d.session_minutes == 390)]
    singles = f[(gaps == 1) & lit & (d.session_minutes == 390)]
    assert mondays.mean() == pytest.approx(singles.mean(), rel=0.15)

    # A 210-minute session forgoes proportionally less than a 390-minute one.
    short = f[(d.session_minutes == 210) & lit]
    full = f[(d.session_minutes == 390) & lit]
    assert short.mean() < full.mean()

    # Scale check against the closed form.
    oos = d.index[1060:]
    annual_cost = f.loc[oos].mean() * TRADING_DAYS
    closed_form = (d.loc[oos, "DGS3MO"].mean() / 100) * (TRADING_DAYS * 6.5) / (365 * 24)
    assert annual_cost == pytest.approx(closed_form, rel=0.02)


def test_financing_is_charged_by_default_and_omitting_it_is_the_sensitivity(pieces, snapshot):
    _, r_o2c, rf = pieces
    long_only = pd.Series(1.0, index=r_o2c.index)
    f = intraday_financing(snapshot, r_o2c.index)
    charged = run_o2c(long_only, r_o2c, rf, 2.0, financing=f)["ann_mean_excess"]
    free = run_o2c(long_only, r_o2c, rf, 2.0)["ann_mean_excess"]
    assert free > charged
    assert free - charged == pytest.approx(f.mean() * TRADING_DAYS, rel=1e-12)


def test_borrow_accrues_over_calendar_days(pieces):
    """A short carried across a weekend is charged three days of borrow."""
    _, r_o2c, rf = pieces
    idx = r_o2c.index
    short = pd.Series(-1.0, index=idx)
    r_c2c = pd.Series(0.0, index=idx)
    flat_rf = pd.Series(0.0, index=idx)
    stats = run_c2c(short, r_c2c, flat_rf, 0.0)
    days = idx.to_series().diff().dt.days.fillna(1.0)
    expected = -(0.0025 * days / 365.0).mean() * TRADING_DAYS
    assert stats["ann_mean_excess"] == pytest.approx(expected, rel=1e-10)


# ------------------------------------------------------------------ invariance

def test_volatility_matching_preserves_sharpe(pieces):
    """Scaling is leverage; Sharpe is invariant to it. Only levels change."""
    _, r_o2c, _ = pieces
    scaled = volatility_matched(r_o2c, 0.10)
    assert scaled.std(ddof=1) * np.sqrt(TRADING_DAYS) == pytest.approx(0.10, abs=1e-12)
    assert sharpe(scaled.to_numpy()) == pytest.approx(sharpe(r_o2c.to_numpy()), abs=1e-10)
    assert scaled.mean() != pytest.approx(r_o2c.mean(), abs=1e-6)


def test_paired_bootstrap_is_tighter_than_unpaired(pieces):
    """Resampling two correlated series independently inflates the difference's error.

    This is the reason the protocol mandates paired resampling; the test pins the
    direction of the effect rather than a magnitude.
    """
    _, r_o2c, _ = pieces
    a = r_o2c.iloc[-750:]
    b = (a * 0.7).rename("scaled")               # perfectly correlated by construction
    paired = bootstrap_difference(a, b, reps=400, seed=7)
    rng = np.random.default_rng(7)
    unpaired = np.array(
        [
            sharpe(rng.choice(a.to_numpy(), len(a))) - sharpe(rng.choice(b.to_numpy(), len(b)))
            for _ in range(400)
        ]
    ).std(ddof=1)
    assert paired["se"] < unpaired


def test_bootstrap_difference_rejects_misaligned_indices(pieces):
    _, r_o2c, _ = pieces
    with pytest.raises(ValueError):
        bootstrap_difference(r_o2c.iloc[:100], r_o2c.iloc[1:101])
