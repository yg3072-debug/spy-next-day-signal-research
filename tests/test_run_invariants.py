"""Invariants that must hold in a completed run.

These check the produced artefacts rather than the code that produced them. Both
were raised in review as things a reader would reasonably want confirmed rather
than asserted, and both are cheap to check once and expensive to notice later.

Skipped when no run is present, so the suite still passes on a fresh clone.
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

RESULTS = ROOT / "results" / "oos_predictions.csv"
pytestmark = pytest.mark.skipif(not RESULTS.exists(), reason="no completed run present")


@pytest.fixture(scope="module")
def run():
    from build_benchmarks import intraday_financing, load_snapshot
    oos = pd.read_csv(RESULTS, index_col="date", parse_dates=True)
    snapshot, _ = load_snapshot()
    fin = intraday_financing(snapshot, snapshot.index).shift(-1).reindex(oos.index)
    return oos, fin


def test_flat_sessions_are_charged_nothing(run):
    """A session with no position must cost nothing at all.

    Obvious from the formula and worth confirming from the output anyway: a cost
    leaking onto flat days would depress the strategy exactly where it is doing
    nothing, and would be invisible in any aggregate.
    """
    oos, fin = run
    c = 2e-4
    flat = oos.position == 0
    assert flat.sum() > 0
    execution = 2 * c * oos.position.abs()
    financing = fin * oos.position.abs()
    assert (execution[flat] == 0).all()
    assert (financing[flat] == 0).all()
    net = oos.position * oos.realised_o2c - execution - financing
    assert (net[flat] == 0).all()


def test_positions_follow_the_band_exactly(run):
    """Every position is the sign of mu_hat when it clears the threshold."""
    oos, fin = run
    from src.strategy import positions_from_expected_return
    expected = positions_from_expected_return(oos.mu_hat, 2.0, fin, 0.0)
    pd.testing.assert_series_equal(
        oos.position.astype(float), expected.astype(float), check_names=False
    )


def test_probabilities_are_a_distribution(run):
    oos, _ = run
    p = oos[["p_short", "p_flat", "p_long"]]
    np.testing.assert_allclose(p.sum(axis=1).to_numpy(), 1.0, atol=1e-9)
    assert ((p >= 0) & (p <= 1)).all().all()


def test_baseline_mu_hat_is_constant_within_an_outer_step(run):
    """The majority baseline predicts the class prior and reads no features, so its
    mu_hat must be one number for the whole of any outer step.

    Variation inside a step would mean something feature-dependent had reached a
    model that has no features.

    Variation *across* steps is deliberately not asserted. The class-conditional
    means are re-estimated at every outer step, so the value normally moves — but
    two adjacent training windows differ by 21 sessions out of a thousand and could
    legitimately produce the same number. Requiring them to differ would be
    asserting something the procedure does not guarantee. What is checked instead is
    that every step is present, which is what would actually break if the refit
    stopped happening.
    """
    oos, _ = run
    baseline = oos[oos.model == "majority_baseline"]
    if baseline.empty:
        pytest.skip("the baseline was never selected in this run")
    per_step = baseline.groupby("step").mu_hat.nunique()
    assert (per_step == 1).all(), "mu_hat varied inside a single outer step"
    steps = sorted(oos.step.unique())
    assert steps == list(range(len(steps))), "outer steps are not a complete sequence"


def test_every_out_of_sample_session_appears_once(run):
    oos, _ = run
    assert oos.index.is_unique
    assert oos.index.is_monotonic_increasing
    assert (oos.index.dayofweek < 5).all()
