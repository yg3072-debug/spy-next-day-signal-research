"""The two execution specifications, pinned against hand-computed cases.

The primary one is additionally pinned against `run_p1.py`'s own arithmetic on the
committed run, so the refactor into objects is verified rather than assumed.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.execution import CloseToClose, OpenToClose, get_spec  # noqa: E402


def _dates(n):
    return pd.bdate_range("2024-01-01", periods=n)


def test_o2c_charges_a_full_round_trip_on_every_active_session():
    idx = _dates(3)
    w = pd.Series([1.0, 1.0, 0.0], index=idx)
    r = pd.Series([0.01, 0.01, 0.01], index=idx)
    carry = pd.Series(0.0, index=idx)
    net = OpenToClose().net(w, r, carry, cost_bps=2.0)
    # Two consecutive longs are two separate day trades: 4 bp each, not netted.
    assert net.iloc[0] == pytest.approx(0.01 - 4e-4)
    assert net.iloc[1] == pytest.approx(0.01 - 4e-4)
    assert net.iloc[2] == 0.0


def test_c2c_nets_a_held_position_and_charges_both_ends():
    idx = _dates(3)
    w = pd.Series([1.0, 1.0, 1.0], index=idx)
    r = pd.Series([0.01, 0.01, 0.01], index=idx)
    carry = pd.Series(0.0, index=idx)
    days = pd.Series(1.0, index=idx)
    net = CloseToClose().net(w, r, carry, cost_bps=2.0, calendar_days=days)
    # Entry on the first row, nothing in the middle, close-out on the last.
    assert net.iloc[0] == pytest.approx(0.01 - 2e-4)
    assert net.iloc[1] == pytest.approx(0.01)
    assert net.iloc[2] == pytest.approx(0.01 - 2e-4)


def test_c2c_reversal_costs_two_sides():
    idx = _dates(2)
    w = pd.Series([1.0, -1.0], index=idx)
    r = pd.Series([0.0, 0.0], index=idx)
    carry = pd.Series(0.0, index=idx)
    days = pd.Series(1.0, index=idx)
    net = CloseToClose().net(w, r, carry, cost_bps=2.0, calendar_days=days)
    assert net.iloc[0] == pytest.approx(-2e-4)            # flat -> long
    assert net.iloc[1] == pytest.approx(-4e-4 - 2e-4 - 25e-4 / 365)  # long -> short, then closed


def test_c2c_borrow_is_charged_over_calendar_days_and_only_when_short():
    idx = _dates(2)
    carry = pd.Series(0.0, index=idx)
    r = pd.Series(0.0, index=idx)
    days = pd.Series([3.0, 1.0], index=idx)               # a weekend
    short = CloseToClose().net(pd.Series([-1.0, 0.0], index=idx), r, carry, 0.0, days)
    long_ = CloseToClose().net(pd.Series([1.0, 0.0], index=idx), r, carry, 0.0, days)
    assert short.iloc[0] == pytest.approx(-(25e-4) * 3.0 / 365.0)
    assert long_.iloc[0] == 0.0


def test_c2c_carries_one_extra_session_of_feature_lag():
    """The signal must exist before the close it is executed at."""
    assert OpenToClose().extra_feature_lag == 0
    assert CloseToClose().extra_feature_lag == 1


def test_c2c_band_is_on_the_excess_over_the_risk_free_rate():
    idx = _dates(3)
    mu = pd.Series([3e-4, 3e-4, -3e-4], index=idx)
    carry = pd.Series([0.0, 2e-4, 0.0], index=idx)
    w = CloseToClose().positions(mu, cost_bps=2.0, carry=carry, delta=0.0)
    assert w.iloc[0] == 1.0     # 3 bp edge clears a 2 bp entry
    assert w.iloc[1] == 0.0     # 1 bp edge after the rate does not
    assert w.iloc[2] == -1.0


def test_targets_are_the_next_session_and_differ_from_each_other():
    idx = _dates(3)
    snap = pd.DataFrame(
        {"Open": [100.0, 101.0, 102.0], "Close": [101.0, 100.0, 104.0]}, index=idx
    )
    o2c, c2c = OpenToClose().target(snap), CloseToClose().target(snap)
    assert o2c.iloc[0] == pytest.approx(100.0 / 101.0 - 1.0)     # session 1's own bar
    assert c2c.iloc[0] == pytest.approx(100.0 / 101.0 - 1.0)     # close 1 over close 0
    assert o2c.iloc[1] == pytest.approx(104.0 / 102.0 - 1.0)
    assert c2c.iloc[1] == pytest.approx(104.0 / 100.0 - 1.0)     # not the same quantity
    assert np.isnan(o2c.iloc[-1]) and np.isnan(c2c.iloc[-1])


def test_registry_round_trips():
    assert get_spec("primary_open_to_close").name == "primary_open_to_close"
    assert get_spec("alternative_close_to_close").name == "alternative_close_to_close"
    with pytest.raises(KeyError):
        get_spec("something_else")


RESULTS = ROOT / "results" / "oos_predictions.csv"


@pytest.mark.skipif(not RESULTS.exists(), reason="no completed run present")
def test_o2c_object_reproduces_the_committed_run_exactly():
    """The refactor must not have changed the primary specification by a basis point."""
    sys.path.insert(0, str(ROOT / "scripts"))
    from build_benchmarks import intraday_financing, load_snapshot
    oos = pd.read_csv(RESULTS, index_col="date", parse_dates=True)
    snapshot, _ = load_snapshot()
    fin = intraday_financing(snapshot, snapshot.index).shift(-1).reindex(oos.index)
    spec = OpenToClose()
    w = spec.positions(oos.mu_hat, 2.0, fin, 0.0)
    assert (w - oos.position.astype(float)).abs().max() == 0.0
    net = spec.net(w, oos.realised_o2c, fin, 2.0)
    direct = oos.position * oos.realised_o2c - 4e-4 * oos.position.abs() - fin * oos.position.abs()
    assert (net - direct).abs().max() < 1e-15
