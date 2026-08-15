"""Lightweight repository checks that do not require model training."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data" / "market_inputs_2026-05-05.csv"
MANIFEST = ROOT / "data" / "market_inputs_2026-05-05.manifest.json"
NOTEBOOK = ROOT / "notebooks" / "spy_next_day_signal_research.ipynb"
RUN_MANIFEST = ROOT / "results" / "run_manifest.json"
FEATURES = ROOT / "results" / "selected_features.csv"
CONFUSION = ROOT / "results" / "final_test_confusion_matrix.csv"
REQUIRED_ASSETS = [
    ROOT / "assets" / "core_model_cv_metrics.png",
    ROOT / "assets" / "feature_importance_top15.png",
    ROOT / "assets" / "final_holdout_confusion_matrix.png",
    ROOT / "assets" / "final_holdout_cumulative_return.png",
    ROOT / "assets" / "final_signal_distribution.png",
]


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    digest = hashlib.sha256(SNAPSHOT.read_bytes()).hexdigest()
    if digest != manifest["sha256"]:
        raise AssertionError("Snapshot SHA-256 does not match its manifest.")

    with SNAPSHOT.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    if len(rows) != manifest["rows"]:
        raise AssertionError("Snapshot row count does not match its manifest.")
    if rows[0]["Date"] != manifest["first_observation"]:
        raise AssertionError("Unexpected first snapshot date.")
    if rows[-1]["Date"] != manifest["last_observation"]:
        raise AssertionError("Unexpected last snapshot date.")

    run_manifest = json.loads(RUN_MANIFEST.read_text(encoding="utf-8"))
    if run_manifest["data_sha256"] != digest:
        raise AssertionError("Run manifest points to a different data snapshot.")
    if run_manifest["raw_input_rows"] != len(rows):
        raise AssertionError("Run manifest raw row count is inconsistent.")

    with FEATURES.open(newline="", encoding="utf-8") as handle:
        selected_features = list(csv.DictReader(handle))
    if len(selected_features) != run_manifest["selected_feature_count"]:
        raise AssertionError("Selected feature count is inconsistent.")

    with CONFUSION.open(newline="", encoding="utf-8") as handle:
        confusion_rows = list(csv.DictReader(handle))
    holdout_total = sum(int(row["total"]) for row in confusion_rows)
    if holdout_total != run_manifest["test_rows"]:
        raise AssertionError("Confusion matrix does not match the holdout size.")
    missing_assets = [str(path.relative_to(ROOT)) for path in REQUIRED_ASSETS if not path.is_file()]
    if missing_assets:
        raise AssertionError(f"Missing result assets: {missing_assets}")

    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    code = "\n".join(
        "".join(cell.get("source", []))
        for cell in notebook["cells"]
        if cell.get("cell_type") == "code"
    )
    for token in [
        "REFRESH_DATA = False",
        "FULL_TUNING = False",
        "N_JOBS = 1",
        "EXPECTED_MODEL_ROWS = 1027",
    ]:
        if token not in code:
            raise AssertionError(f"Notebook is missing reproducibility setting: {token}")
    if any(cell.get("outputs") for cell in notebook["cells"] if cell.get("cell_type") == "code"):
        raise AssertionError("Canonical notebook must not contain execution outputs.")

    print("Repository validation passed.")
    print(f"Snapshot rows: {len(rows)}")
    print(f"Snapshot SHA-256: {digest}")
    print(f"Selected features: {len(selected_features)}")
    print(f"Holdout observations: {holdout_total}")


if __name__ == "__main__":
    main()
