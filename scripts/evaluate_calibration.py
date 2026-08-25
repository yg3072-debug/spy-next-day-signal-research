"""Calibration evidence, with each number labelled by what it is out-of-sample for.

`config/p1.yaml` requires four calibration diagnostics. Three of them are measured
on the calibrator's own fitting sample and one is not, and reporting them together
without saying which is which would flatter the calibration step.

    inner diagnostics      out-of-sample for the base model
                           IN-SAMPLE for the calibrator
                           the calibrator is fitted on exactly those out-of-fold
                           points, so applying it back to them cannot be evidence
                           that calibrating helped

    outer diagnostics      out-of-sample for both
                           the outer-validation rows were never seen by the model
                           or by the calibrator, so the before/after comparison
                           here is the one that answers "did calibrating help?"

The inner file is therefore stamped `eligible_as_confirmatory_evidence=false` and
the outer file carries the comparison that is eligible.

    python scripts/evaluate_calibration.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.pipeline import CLASSES  # noqa: E402

RESULTS = ROOT / "results"
BINS = np.linspace(0.0, 1.0, 11)


def brier(proba: np.ndarray, y: np.ndarray) -> float:
    onehot = np.zeros_like(proba)
    for i, c in enumerate(CLASSES):
        onehot[y == c, i] = 1.0
    return float(((proba - onehot) ** 2).sum(axis=1).mean())


def reliability(p: np.ndarray, hit: np.ndarray) -> pd.DataFrame:
    """Predicted probability against realised frequency, in ten bins.

    The count column matters as much as the frequency: a bin holding nine
    observations says nothing, and a reliability curve drawn without it invites
    reading noise as miscalibration.
    """
    idx = np.clip(np.digitize(p, BINS) - 1, 0, len(BINS) - 2)
    rows = []
    for b in range(len(BINS) - 1):
        m = idx == b
        rows.append({
            "bin_low": BINS[b], "bin_high": BINS[b + 1], "n": int(m.sum()),
            "mean_predicted": float(p[m].mean()) if m.any() else np.nan,
            "realised_frequency": float(hit[m].mean()) if m.any() else np.nan,
        })
    return pd.DataFrame(rows)


def main() -> int:
    inner_path = RESULTS / "calibration_diagnostics.csv"
    outer_path = RESULTS / "outer_calibration.csv"
    if not outer_path.exists():
        print("outer_calibration.csv is absent; run scripts/run_p1.py first")
        return 1

    # ---- stamp the inner file with its scope --------------------------------
    inner = pd.read_csv(inner_path)
    for column, value in (
        ("evaluation_scope", "calibrator_fit_sample"),
        ("out_of_sample_for_base_model", "true"),
        ("out_of_sample_for_calibrator", "false"),
        ("eligible_as_confirmatory_evidence", "false"),
    ):
        inner[column] = value
    inner.to_csv(inner_path, index=False, float_format="%.8g")
    print(f"stamped {inner_path.name} with its evaluation scope ({len(inner)} rows)")

    # ---- the comparison that is out-of-sample for both ----------------------
    outer = pd.read_csv(outer_path, parse_dates=["date"])
    y = outer.label.to_numpy()
    raw = outer[["raw_short", "raw_flat", "raw_long"]].to_numpy(float)
    cal = outer[["cal_short", "cal_flat", "cal_long"]].to_numpy(float)

    b_raw, b_cal = brier(raw, y), brier(cal, y)
    # The reference is the training base rate the protocol names, taken here as the
    # label frequencies of the outer-train quantile scheme: 25/50/25 by construction.
    ref = np.tile(np.array([0.25, 0.50, 0.25]), (len(y), 1))
    b_ref = brier(ref, y)

    summary = {
        "sessions": int(len(outer)),
        "scope": "outer_validation",
        "out_of_sample_for_base_model": True,
        "out_of_sample_for_calibrator": True,
        "eligible_as_confirmatory_evidence": True,
        "brier_uncalibrated": b_raw,
        "brier_calibrated": b_cal,
        "difference_calibrated_minus_uncalibrated": b_cal - b_raw,
        "brier_reference_25_50_25": b_ref,
        "skill_uncalibrated_vs_reference": 1 - b_raw / b_ref,
        "skill_calibrated_vs_reference": 1 - b_cal / b_ref,
        "rows_where_calibration_was_skipped": int(outer.calibration_skipped.sum()),
    }

    print("\nOUTER VALIDATION — out-of-sample for the model AND the calibrator")
    print(f"  Brier, uncalibrated                 {b_raw:.5f}")
    print(f"  Brier, calibrated                   {b_cal:.5f}")
    print(f"  difference (negative = better)      {b_cal - b_raw:+.5f}")
    print(f"  Brier of a fixed 25/50/25 forecast  {b_ref:.5f}")
    print(f"  skill, uncalibrated                 {summary['skill_uncalibrated_vs_reference']:+.5f}")
    print(f"  skill, calibrated                   {summary['skill_calibrated_vs_reference']:+.5f}")

    curves = []
    for i, c in enumerate(CLASSES):
        name = {-1: "short", 0: "flat", 1: "long"}[c]
        for label, p in (("uncalibrated", raw[:, i]), ("calibrated", cal[:, i])):
            curve = reliability(p, (y == c).astype(float))
            curve.insert(0, "class", name)
            curve.insert(1, "probabilities", label)
            curves.append(curve)
    table = pd.concat(curves, ignore_index=True)
    table.to_csv(RESULTS / "outer_reliability_curve.csv", index=False, float_format="%.6g")

    print("\n  reliability, calibrated, long class (bins with at least 30 observations)")
    show = table[(table["class"] == "long") & (table.probabilities == "calibrated")
                 & (table.n >= 30)]
    for row in show.itertuples():
        print(f"    predicted {row.mean_predicted:.3f}   realised {row.realised_frequency:.3f}"
              f"   n = {row.n}")

    (RESULTS / "outer_calibration_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nwritten to results/outer_calibration_summary.json and "
          f"results/outer_reliability_curve.csv")
    print("\nThe inner diagnostics are in-sample for the calibrator and are stamped as")
    print("ineligible confirmatory evidence. Only the outer comparison above answers")
    print("whether calibrating helped, and it is reported whichever way it comes out.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
