"""Checks on the feature layer.

The important one is `test_no_lookahead`: features are rebuilt on truncated
history and every overlapping value must be bit-identical. A feature that reads
even one session ahead cannot survive that, whatever its formula looks like.
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

from build_benchmarks import load_snapshot  # noqa: E402
from src.features import build_features, build_target  # noqa: E402

EXPECTED_FEATURE_COUNT = 81


@pytest.fixture(scope="module")
def snapshot(market_frame):
    # The snapshot is not distributed; `market_frame` supplies a real one when the
    # user has obtained it and the synthetic fixture otherwise. What this file
    # asserts holds on either, because it is about the code.
    return market_frame


@pytest.fixture(scope="module")
def built(snapshot):
    return build_features(snapshot)


# --------------------------------------------------------------------- shape

def test_feature_count_matches_the_declared_set(built):
    features, registry = built
    assert features.shape[1] == EXPECTED_FEATURE_COUNT
    assert len(registry) == EXPECTED_FEATURE_COUNT


def test_every_feature_is_documented(built):
    _, registry = built
    for f in registry:
        assert f.formula.strip(), f"{f.name} has no formula"
        assert f.rationale.strip(), f"{f.name} has no rationale"
        assert f.group.strip(), f"{f.name} has no group"


def test_index_is_preserved(snapshot, built):
    features, _ = built
    assert features.index.equals(snapshot.index)


# ----------------------------------------------------------------- causality

@pytest.mark.parametrize("cut", [400, 1200, 2400])
def test_no_lookahead(snapshot, built, cut):
    """Rebuilding on truncated history must not change any earlier value.

    This is the definitive test. Any transform that reads forward — a centred
    window, a backward fill, a full-sample statistic — changes values before the
    cut when later data is removed.
    """
    full, _ = built
    truncated, _ = build_features(snapshot.iloc[:cut])
    assert list(truncated.columns) == list(full.columns)

    a = full.iloc[:cut]
    b = truncated
    for col in full.columns:
        x, y = a[col].to_numpy(dtype=float), b[col].to_numpy(dtype=float)
        both_nan = np.isnan(x) & np.isnan(y)
        assert np.array_equal(np.isnan(x), np.isnan(y)), f"{col}: NaN pattern changed at cut {cut}"
        np.testing.assert_allclose(
            x[~both_nan], y[~both_nan], rtol=0, atol=0,
            err_msg=f"{col} changed when future data was removed (cut {cut})",
        )


def test_target_is_the_next_session_open_to_close(snapshot):
    target = build_target(snapshot)
    expected = (snapshot["Close"] / snapshot["Open"] - 1.0).shift(-1)
    pd.testing.assert_series_equal(target, expected.rename("target_o2c_next"))
    assert np.isnan(target.iloc[-1]), "the final session has no next session"


def test_target_is_not_among_the_features(built):
    features, _ = built
    assert "target_o2c_next" not in features.columns


def test_no_feature_is_a_copy_of_the_target(snapshot, built):
    """A leak would show up as a near-perfect contemporaneous correlation."""
    features, _ = built
    target = build_target(snapshot)
    valid = target.notna()
    for col in features.columns:
        s = features[col]
        ok = valid & s.notna()
        if ok.sum() < 100 or s[ok].std() == 0:
            continue
        rho = abs(np.corrcoef(s[ok], target[ok])[0, 1])
        assert rho < 0.5, f"{col} correlates {rho:.3f} with the target it is meant to predict"


def test_intraday_ret_is_the_lagged_target(snapshot, built):
    """A useful sanity anchor: today's O2C return is yesterday's target."""
    features, _ = built
    target = build_target(snapshot)
    lagged = np.log1p(target.shift(1))
    ok = features["intraday_ret"].notna() & lagged.notna()
    np.testing.assert_allclose(
        features["intraday_ret"][ok].to_numpy(), lagged[ok].to_numpy(), rtol=1e-12
    )


# -------------------------------------------------------------- publication lag

def test_yield_curve_features_carry_the_extra_publication_lag():
    """A jump in the term spread dated t must not move a feature dated t."""
    idx = pd.bdate_range("2015-01-05", periods=260)
    base = pd.DataFrame(
        {
            "Open": 100.0, "High": 101.0, "Low": 99.0, "Close": 100.0, "Volume": 1e6,
            "VIX": 15.0, "DXY": 95.0, "TNX": 2.0, "OIL": 60.0,
            "QQQ_Close": 100.0, "IWM_Close": 100.0, "DIA_Close": 100.0,
            "DGS3MO": 1.0, "DGS2": 1.0, "DGS10": 2.0, "is_half_day": 0,
        },
        index=idx,
    )
    bumped = base.copy()
    bump_at = 200
    bumped.iloc[bump_at, bumped.columns.get_loc("DGS10")] = 3.0

    a, _ = build_features(base)
    b, _ = build_features(bumped)
    col = "YC_2Y10Y_change_1"
    assert a[col].iloc[bump_at] == pytest.approx(b[col].iloc[bump_at]), \
        "the value dated t moved a feature dated t; the publication lag is missing"
    assert a[col].iloc[bump_at + 1] != pytest.approx(b[col].iloc[bump_at + 1]), \
        "the value dated t never reached the feature dated t+1"


# ------------------------------------------------------- adjustment invariance

def test_declared_adjustment_invariance_holds(snapshot, built):
    """Rescaling every price by a constant must leave the flagged features alone.

    A dividend revision multiplies the whole adjusted history by one factor, so
    anything built from price ratios cannot notice it. Features declared
    non-invariant must actually move, otherwise the flag is wrong in the other
    direction and the documentation overstates the risk.
    """
    features, registry = built
    scaled_snapshot = snapshot.copy()
    for col in ["Open", "High", "Low", "Close", "QQQ_Close", "IWM_Close", "DIA_Close"]:
        scaled_snapshot[col] = scaled_snapshot[col] * 1.37
    scaled, _ = build_features(scaled_snapshot)

    for f in registry:
        x = features[f.name].to_numpy(dtype=float)
        y = scaled[f.name].to_numpy(dtype=float)
        ok = np.isfinite(x) & np.isfinite(y)
        if ok.sum() == 0:
            continue
        # atol is 1e-10, not 1e-12. Several of these features are dimensionless
        # ratios that pass through zero, and at zero the relative term vanishes
        # and the absolute tolerance is the whole budget. Rescaling a price
        # history and recomputing a rolling standard deviation moves such a value
        # by about 1e-12 in float64: that is arithmetic, not a broken invariance.
        # A feature that genuinely is not invariant moves by tens of percent, and
        # test_invariance_check_catches_a_mislabelled_feature holds that line.
        same = np.allclose(x[ok], y[ok], rtol=1e-9, atol=1e-10)
        if f.adjustment_invariant:
            assert same, f"{f.name} is declared adjustment-invariant but changed"
        else:
            assert not same, f"{f.name} is declared non-invariant but did not change"


# --------------------------------------------------------------- data quality

def test_no_infinities(built):
    features, _ = built
    bad = [c for c in features.columns if np.isinf(features[c].to_numpy(dtype=float)).any()]
    assert not bad, f"infinite values in {bad}"


def test_warmup_is_bounded(built):
    """The longest trailing window is 252 sessions, so nothing should need more."""
    features, _ = built
    first_complete = features.dropna().index.min()
    assert features.index.get_loc(first_complete) <= 252


def test_binary_features_are_binary(built):
    features, registry = built
    for f in registry:
        if f.group in ("calendar", "regime"):
            assert set(features[f.name].dropna().unique()) <= {0, 1}, f"{f.name} is not binary"


def test_invariance_check_catches_a_mislabelled_feature(snapshot):
    """The counter-example for the loosened tolerance.

    Raising atol from 1e-12 to 1e-10 is only defensible if the check still fails on
    a feature that is genuinely not adjustment-invariant. A raw price level is the
    clearest such case: rescaling the history moves it by the scale factor, which is
    thirty-seven percent here and eight orders of magnitude above the tolerance.

    This test exists because loosening a tolerance to make a suite pass is a way of
    deleting a check while appearing to keep it.
    """
    scaled = snapshot.copy()
    for col in ["Open", "High", "Low", "Close"]:
        scaled[col] = scaled[col] * 1.37

    level = snapshot["Close"].to_numpy(dtype=float)
    level_scaled = scaled["Close"].to_numpy(dtype=float)
    ok = np.isfinite(level) & np.isfinite(level_scaled)

    assert not np.allclose(level[ok], level_scaled[ok], rtol=1e-9, atol=1e-10), (
        "a raw price level survived the invariance check; the tolerance is too loose"
    )
    ratio = np.abs(level_scaled[ok] / level[ok] - 1.0).mean()
    assert ratio > 0.3, f"the counter-example should move by ~37%, moved by {ratio:.1%}"
