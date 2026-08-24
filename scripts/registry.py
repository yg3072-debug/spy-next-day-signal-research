"""Append a row to the experiment registry.

Every run that produces out-of-sample predictions gets a row, whether it succeeded,
failed, or was never meant to be a research result at all. The registry is the
input to any multiple-testing statement, so a run that is left out of it silently
weakens every such statement made later.

Not every row counts against the trial budget. An engineering smoke test, for
instance, uses an informal cadence and computes no performance figure; recording it
as a failed experiment would be as inaccurate as leaving it out. It is recorded
with `run_type=engineering_smoke` and `excluded_from_trial_budget=true`, so the
distinction is in the file rather than in someone's memory.

    python scripts/registry.py --show
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "results" / "experiment_registry.csv"

FIELDS = [
    "run_id",
    "date",
    "run_type",                      # confirmatory | exploratory | sensitivity | engineering_smoke
    "excluded_from_trial_budget",
    "performance_metrics_computed",
    "protocol_version",
    "config_sha256",
    "snapshot_sha256",
    "code_commit",
    "n_candidates",
    "delta_multiple",
    "training_window",
    "outer_steps",
    "oos_sessions",
    "oos_net_sharpe",
    "delta_sharpe_vs_always_long",
    "delta_annmean_vs_cash",
    "notes",
]


def git_commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True
    ).stdout.strip()


def append(row: dict) -> None:
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    new = not REGISTRY.exists()
    with REGISTRY.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        if new:
            writer.writeheader()
        writer.writerow({k: row.get(k, "") for k in FIELDS})


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--seed-smoke", action="store_true",
                    help="record the v5 engineering smoke run")
    args = ap.parse_args()

    if args.seed_smoke:
        manifest = json.loads((ROOT / "results" / "smoke" / "run_manifest.json")
                              .read_text(encoding="utf-8"))
        append({
            "run_id": "SMOKE-02",
            "date": date.today().isoformat(),
            "run_type": "engineering_smoke",
            "excluded_from_trial_budget": "true",
            "performance_metrics_computed": "false",
            "protocol_version": "v6",
            "config_sha256": manifest["config_sha256"],
            "snapshot_sha256": manifest["snapshot_sha256"],
            "code_commit": manifest["code_commit"],
            "n_candidates": 23,
            "delta_multiple": "0.0 fixed",
            "training_window": "expanding, initial 1000",
            "outer_steps": manifest["outer_steps"],
            "oos_sessions": manifest["oos_sessions"],
            "notes": (
                "Verification smoke test for protocol v6 on the same truncated window. "
                "Confirmed that fixing delta at zero restores the one-standard-error rule: "
                "12 and 8 eligible candidates of 23 at the two reselections, against 1 of "
                "92 under v5. Confirmed no defect in the degeneracy guard. Inspected "
                "structural outputs only; no returns or performance statistics were "
                "computed or inspected. Excluded from the research trial budget."
            ),
        })
        append({
            "run_id": "SMOKE-01",
            "date": date.today().isoformat(),
            "run_type": "engineering_smoke",
            "excluded_from_trial_budget": "true",
            "performance_metrics_computed": "false",
            "protocol_version": "v5",
            "config_sha256": "e6c1776df8dd3b16f8fe0b3192cd417a6bd4c192648298fc444bae1c5529277d",
            "snapshot_sha256": manifest["snapshot_sha256"],
            "code_commit": manifest["code_commit"],
            "n_candidates": 92,
            "delta_multiple": "grid {0, 0.5, 1, 2}",
            "training_window": "expanding, initial 1000",
            "outer_steps": manifest["outer_steps"],
            "oos_sessions": manifest["oos_sessions"],
            "notes": (
                "Engineering smoke test on a truncated window with an informal retune "
                "cadence. Inspected structural outputs only, including schema, "
                "probability normalisation and position participation, over 63 realised "
                "out-of-sample dates. No returns or performance statistics were computed "
                "or inspected. Surfaced that selecting over delta let the inner "
                "cross-validation choose a trading frequency alongside a model, which is "
                "what protocol v6 fixes by holding delta at zero. Excluded from the "
                "research trial budget."
            ),
        })
        print(f"recorded SMOKE-01 and SMOKE-02 in {REGISTRY}")

    if REGISTRY.exists():
        rows = list(csv.DictReader(REGISTRY.open(encoding="utf-8")))
        print(f"\n{len(rows)} row(s) in the registry")
        counted = [r for r in rows if r["excluded_from_trial_budget"] != "true"]
        print(f"{len(counted)} counting against the trial budget\n")
        for r in rows:
            print(f"  {r['run_id']:<10} {r['date']}  {r['run_type']:<19}"
                  f" budget={'no ' if r['excluded_from_trial_budget'] == 'true' else 'yes'}"
                  f"  perf={'no' if r['performance_metrics_computed'] == 'false' else 'yes'}")
    else:
        print("registry does not exist yet")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
