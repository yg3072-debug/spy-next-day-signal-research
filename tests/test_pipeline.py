"""Checks on the confirmatory pipeline.

Two things are worth pinning here that a reading of the code will not settle.
One is that every estimator learns only from the slice it is handed — the
protocol's whole claim rests on it and it is invisible at a glance. The other is
the alignment between a decision and the session it is acted on, which is the
kind of off-by-one that produces a plausible-looking result and no error.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.model_selection import TimeSeriesSplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from build_benchmarks import intraday_financing, load_snapshot  # noqa: E402
from src.features import build_features, build_target  # noqa: E402
from src.pipeline import (  # noqa: E402
    CLASSES, SigmoidCalibrator, apply_labels, calibration_is_viable,
    class_conditional_means, crossfit_out_of_fold, estimate_quantiles,
    expected_return, information_coefficients, make_estimator, select_features,
    vol_adjusted_target, _rolling_spearman,
)


@pytest.fixture(scope="module")
def data(market_frame):
    # The snapshot is not distributed; `market_frame` supplies a real one when the
    # user has obtained it and the synthetic fixture otherwise. What this file
    # asserts holds on either, because it is about the code.
    snapshot = market_frame
    features, registry = build_features(snapshot)
    target = build_target(snapshot)
    idx = features.dropna().index.intersection(target.dropna().index)
    groups = {f.name: f.group for f in registry}
    return snapshot, features.loc[idx], target.loc[idx], groups


# --------------------------------------------------------------------- alignment

def test_financing_is_charged_for_the_session_the_position_is_held(data):
    """A decision taken at the close of t is acted on during t+1.

    The row is indexed by the decision date and already carries t+1's return, so
    it must also carry t+1's financing. Charging f_t instead would misprice every
    row, and on a Friday it would misprice by a factor of the weekend.
    """
    snapshot, features, target, _ = data
    fin = intraday_financing(snapshot, snapshot.index)
    held = fin.shift(-1).reindex(features.index)

    sessions = list(snapshot.index)
    for date in features.index[100:105]:
        nxt = sessions[sessions.index(date) + 1]
        assert held.loc[date] == pytest.approx(fin.loc[nxt]), (
            "the row must carry the financing of the session the position is held in"
        )
        # And the target on the same row is that session's return.
        assert target.loc[date] == pytest.approx(
            snapshot.Close.loc[nxt] / snapshot.Open.loc[nxt] - 1.0
        )


# ------------------------------------------------------------------ containment

def test_quantiles_depend_only_on_the_slice_they_are_given(data):
    _, features, target, _ = data
    z = vol_adjusted_target(np.log1p(target), features["Volatility_20"], 1e-8)
    a = estimate_quantiles(z.iloc[:600], (0.25, 0.75))
    b = estimate_quantiles(z.iloc[:600].copy(), (0.25, 0.75))
    assert a == b
    # Changing data after the slice must not move them.
    perturbed = z.copy()
    perturbed.iloc[600:] *= 5.0
    assert estimate_quantiles(perturbed.iloc[:600], (0.25, 0.75)) == a


def test_feature_selection_depends_only_on_the_slice(data):
    """Selection run on a slice must not change when later data is altered."""
    _, features, target, groups = data
    z = vol_adjusted_target(np.log1p(target), features["Volatility_20"], 1e-8)
    cfg = {
        "drop_zero_variance": True,
        "ic": {"method": "spearman", "rolling_window_sessions": 60, "statistic": "abs_mean"},
        "per_group_top_k": 3,
        "correlation_pruning": {"linkage": "average",
                                "metric": "one_minus_abs_correlation",
                                "cut_distance": 0.20, "keep": "highest_abs_ic"},
        "max_features": 25,
    }
    cut = 800
    chosen_a, _ = select_features(features.iloc[:cut], z.iloc[:cut], groups, cfg)

    tampered = features.copy()
    tampered.iloc[cut:] = tampered.iloc[cut:] * 3.0 + 1.0
    chosen_b, _ = select_features(tampered.iloc[:cut], z.iloc[:cut], groups, cfg)

    assert chosen_a == chosen_b
    assert 0 < len(chosen_a) <= cfg["max_features"]


def test_class_conditional_means_use_the_slice_not_the_whole_sample(data):
    """The distinction that matters: scoring an inner fold must not reach forward.

    Outer-train contains every inner-validation, so means taken from it would let
    an inner score see the returns it is being graded on.
    """
    _, features, target, _ = data
    z = vol_adjusted_target(np.log1p(target), features["Volatility_20"], 1e-8)
    cut = 700
    q = estimate_quantiles(z.iloc[:cut], (0.25, 0.75))
    labels_slice = apply_labels(z.iloc[:cut], *q)

    inner = class_conditional_means(target.iloc[:cut], labels_slice)
    whole = class_conditional_means(target, apply_labels(z, *q))
    assert inner != whole, "the two slices should not coincidentally agree"
    assert set(inner) == set(CLASSES)


# -------------------------------------------------------------------- mechanics

def test_rolling_spearman_matches_scipy_on_a_window():
    from scipy.stats import spearmanr
    rng = np.random.default_rng(0)
    x, y = rng.normal(size=300), rng.normal(size=300)
    got = _rolling_spearman(x, y, 60)
    assert len(got) == 300 - 59
    for i in (0, 50, 240):
        expected = spearmanr(x[i:i + 60], y[i:i + 60]).statistic
        assert got[i] == pytest.approx(expected, abs=1e-12)


def test_rolling_spearman_handles_ties(data):
    """Binary features are all ties; average ranks must not blow up."""
    rng = np.random.default_rng(1)
    binary = rng.integers(0, 2, size=300).astype(float)
    y = rng.normal(size=300)
    got = _rolling_spearman(binary, y, 60)
    assert np.isfinite(got).mean() > 0.9


def test_information_coefficients_are_non_negative(data):
    _, features, target, _ = data
    z = vol_adjusted_target(np.log1p(target), features["Volatility_20"], 1e-8)
    ic = information_coefficients(features.iloc[:500], z.iloc[:500], 60)
    assert len(ic) == features.shape[1]
    assert (ic >= 0).all() and (ic <= 1).all()


def test_calibrator_is_a_no_op_shape_wise_and_renormalises(data):
    rng = np.random.default_rng(2)
    raw = pd.DataFrame(rng.dirichlet(np.ones(3), size=400), columns=CLASSES)
    y = pd.Series(rng.choice(CLASSES, size=400))
    cal = SigmoidCalibrator.fit(raw, y)
    out = cal.transform(raw)
    assert list(out.columns) == list(CLASSES)
    assert out.shape == raw.shape
    np.testing.assert_allclose(out.sum(axis=1).to_numpy(), 1.0, atol=1e-10)
    assert ((out >= 0) & (out <= 1)).all().all()


def test_calibration_viability_gate():
    plenty = pd.Series([-1] * 100 + [0] * 100 + [1] * 100)
    assert calibration_is_viable(plenty, 200, 30)
    assert not calibration_is_viable(plenty.iloc[:150], 200, 30)     # too few in total
    thin = pd.Series([-1] * 5 + [0] * 200 + [1] * 200)
    assert not calibration_is_viable(thin, 200, 30)                  # one class too thin


def test_crossfit_never_predicts_a_row_its_model_was_fitted_on(data):
    """Out-of-fold means out of fold. Overlap here would poison the calibrator."""
    _, features, target, _ = data
    z = vol_adjusted_target(np.log1p(target), features["Volatility_20"], 1e-8)
    X = features.iloc[:600, :8]
    y = apply_labels(z.iloc[:600], *estimate_quantiles(z.iloc[:600], (0.25, 0.75)))
    splitter = TimeSeriesSplit(n_splits=3, test_size=100, gap=1)

    fitted_on, predicted_on = [], []
    for tr, te in splitter.split(X):
        if len(tr) < 180:
            continue
        fitted_on.append(set(X.index[tr]))
        predicted_on.append(set(X.index[te]))
    for f, p in zip(fitted_on, predicted_on):
        assert not (f & p), "a fold predicted rows it had trained on"

    build = lambda: make_estimator(  # noqa: E731
        "logistic", {"C": 0.1}, {"fixed": {"max_iter": 1000}}, 0
    )
    proba, y_oof = crossfit_out_of_fold(X, y, build, splitter, 180)
    assert len(proba) == len(y_oof) > 0
    assert list(proba.columns) == list(CLASSES)


def test_expected_return_is_a_probability_weighted_mean(data):
    proba = pd.DataFrame({-1: [0.2, 0.5], 0: [0.5, 0.2], 1: [0.3, 0.3]})
    proba.columns = CLASSES
    means = {-1: -0.01, 0: 0.0, 1: 0.012}
    mu = expected_return(proba, means)
    assert mu.iloc[0] == pytest.approx(0.2 * -0.01 + 0.5 * 0.0 + 0.3 * 0.012)
    assert mu.iloc[1] == pytest.approx(0.5 * -0.01 + 0.2 * 0.0 + 0.3 * 0.012)
