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


def test_c2c_edge_is_measured_over_the_risk_free_rate():
    """A 3 bp raw prediction is a 1 bp edge once the bill it displaces is netted."""
    idx = _dates(2)
    spec = CloseToClose(borrow_annual_bps=0.0)
    days = pd.Series(1.0, index=idx)
    flat_entry = spec.positions(pd.Series([3e-4, 3e-4], index=idx), 2.0,
                                pd.Series([2e-4, 2e-4], index=idx), calendar_days=days)
    # 1 bp of edge does not pay for a 2 bp entry from flat.
    assert flat_entry.iloc[0] == 0.0
    clears = spec.positions(pd.Series([3e-4, 3e-4], index=idx), 2.0,
                            pd.Series([0.0, 0.0], index=idx), calendar_days=days)
    assert clears.iloc[0] == 1.0


def test_c2c_holds_a_position_that_would_not_be_worth_opening():
    """The whole reason a single threshold is the wrong shape here.

    Day 1 opens a long on a 3 bp edge. Day 2's edge is only 1 bp, which would not
    pay a 2 bp entry — but the position is already on, holding it costs nothing, and
    going flat would cost 2 bp to give up a positive expectation. A fixed band
    compares |mu_hat| to one number and exits; the one-step optimum holds.
    """
    idx = _dates(2)
    spec = CloseToClose(borrow_annual_bps=0.0)
    w = spec.positions(pd.Series([3e-4, 1e-4], index=idx), 2.0,
                       pd.Series([0.0, 0.0], index=idx),
                       calendar_days=pd.Series(1.0, index=idx))
    assert list(w) == [1.0, 1.0]


def test_c2c_never_exits_a_long_into_flat_when_borrow_is_free():
    """A property of the rule that is not obvious and is worth pinning.

    Holding a long against an adverse edge `e < 0` is worth `e`. Going flat costs
    `c`. Reversing costs `2c` and earns `|e|`. Flat beats holding only when
    `e < -c`, and reversing beats flat only when `|e| > c` -- the same condition.
    So with no borrow charge, flat is dominated from a long position: the rule
    either holds or goes all the way to short, never parks in between.

    This is exactly what a single fixed threshold cannot express, and it is why the
    first implementation of this rule was wrong rather than merely suboptimal.
    """
    idx = _dates(2)
    spec = CloseToClose(borrow_annual_bps=0.0)
    days = pd.Series(1.0, index=idx)
    zero = pd.Series([0.0, 0.0], index=idx)

    # A 1 bp adverse edge is cheaper to sit through than the 2 bp it costs to leave.
    held = spec.positions(pd.Series([3e-4, -1e-4], index=idx), 2.0, zero, calendar_days=days)
    assert list(held) == [1.0, 1.0]

    # A 3 bp adverse edge clears c, and the rule goes straight to short.
    flipped = spec.positions(pd.Series([3e-4, -3e-4], index=idx), 2.0, zero, calendar_days=days)
    assert list(flipped) == [1.0, -1.0]

    # Sweep it: from a long, with free borrow, flat is never chosen.
    for bp in range(-20, 21):
        w = spec.positions(pd.Series([3e-4, bp * 1e-5], index=idx), 2.0, zero,
                           calendar_days=days)
        assert w.iloc[1] != 0.0, f"flat was chosen from a long at edge {bp} x 1e-5"


def test_c2c_borrow_restores_flat_as_a_choice():
    """Charge the short and the middle option stops being dominated."""
    idx = _dates(2)
    days = pd.Series(1.0, index=idx)
    zero = pd.Series([0.0, 0.0], index=idx)
    spec = CloseToClose(borrow_annual_bps=2000.0)
    w = spec.positions(pd.Series([3e-4, -2.2e-4], index=idx), 2.0, zero, calendar_days=days)
    assert list(w) == [1.0, 0.0]


def test_c2c_rule_refuses_a_safety_margin():
    """delta is not a parameter of this rule and must not be silently ignored."""
    idx = _dates(2)
    with pytest.raises(ValueError, match="no safety margin"):
        CloseToClose().positions(pd.Series([1.0, 1.0], index=idx), 2.0,
                                 pd.Series([0.0, 0.0], index=idx), delta=1.0)


def test_c2c_borrow_makes_a_short_harder_to_justify_than_a_long():
    idx = _dates(2)
    days = pd.Series([3.0, 1.0], index=idx)          # opened into a weekend
    zero = pd.Series([0.0, 0.0], index=idx)
    edge = 2.1e-4
    charged = CloseToClose(borrow_annual_bps=500.0)
    free = CloseToClose(borrow_annual_bps=0.0)
    assert free.positions(pd.Series([-edge, 0.0], index=idx), 2.0, zero,
                          calendar_days=days).iloc[0] == -1.0
    assert charged.positions(pd.Series([-edge, 0.0], index=idx), 2.0, zero,
                             calendar_days=days).iloc[0] == 0.0
    # The same edge on the long side is unaffected by borrow.
    assert charged.positions(pd.Series([edge, 0.0], index=idx), 2.0, zero,
                             calendar_days=days).iloc[0] == 1.0


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


def test_get_spec_applies_configured_parameters():
    """The regression that produced E24.

    get_spec used to return module-level singletons built with their defaults, so a
    configuration setting borrow_annual_bps to 0 was accepted, written into the run
    manifest, and ignored. E24 ran with the 25 bp charge it existed to remove and
    came out bit-identical to E22.
    """
    default = get_spec("alternative_close_to_close")
    assert default.borrow_annual_bps == 25.0
    free = get_spec("alternative_close_to_close", borrow_annual_bps=0.0)
    assert free.borrow_annual_bps == 0.0
    assert default.borrow_annual_bps == 25.0, "overrides must not mutate a shared object"

    # And it must actually change the P&L, not merely the attribute.
    idx = _dates(2)
    w = pd.Series([-1.0, 0.0], index=idx)
    r = pd.Series([0.0, 0.0], index=idx)
    carry = pd.Series(0.0, index=idx)
    days = pd.Series([3.0, 1.0], index=idx)
    assert free.net(w, r, carry, 0.0, days).iloc[0] == 0.0
    assert default.net(w, r, carry, 0.0, days).iloc[0] < 0.0


def test_get_spec_rejects_a_parameter_it_does_not_have():
    """A misspelled parameter must fail loudly rather than be dropped."""
    with pytest.raises(KeyError, match="takes no parameter"):
        get_spec("alternative_close_to_close", borrow_bps=0.0)
    with pytest.raises(KeyError, match="takes no parameter"):
        get_spec("primary_open_to_close", borrow_annual_bps=0.0)
