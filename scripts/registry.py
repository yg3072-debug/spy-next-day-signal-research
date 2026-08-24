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

**A specification is not a strategy path.** E10 supplies three quantiles, E11 two
volatility targets, E12 five cost levels and E12b three margins, so a registry
keyed only on the E number would record four rows where thirteen out-of-sample
return series were actually produced and looked at. Any descriptive multiple-testing
statement has to use the number of realised paths, not the number of E numbers, or
it understates its own N. Every path therefore carries a `subrun_id` alongside the
`family_id` it belongs to.

Three further flags exist because "pre-registered" is not one property. A
specification can be fixed before the confirmatory run, or merely before its own
results are seen — the second is much weaker than the first and still worth
something, but only if the registry distinguishes them rather than letting a reader
assume the stronger one.

    python scripts/registry.py --show
    python scripts/registry.py --register-position-rules
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
    "subrun_id",                     # one realised out-of-sample path
    "family_id",                     # the specification it belongs to
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
    "active_sessions",
    "active_rate",
    # What "pre-registered" means for this row, stated in three separate parts
    # rather than compressed into one word that would overstate the weakest case.
    "specified_before_p1",           # fixed before the confirmatory run
    "specified_before_own_results",  # fixed before this row's own returns were seen
    "cannot_modify_p1_headline",     # always true for anything outside P1
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
    ap.add_argument("--register-position-rules", action="store_true",
                    help="one row per realised path in exploratory_position_rules.csv")
    ap.add_argument("--register-runs", action="store_true",
                    help="one row per completed run under results/exploratory and results/altdata")
    args = ap.parse_args()

    if args.register_runs:
        import pandas as pd
        n = 0
        for base, kind in ((ROOT / "results" / "exploratory", "exploratory"),
                           (ROOT / "results" / "altdata", "exploratory")):
            if not base.exists():
                continue
            for d in sorted(base.iterdir()):
                manifest_path = d / "run_manifest.json"
                if not manifest_path.is_dir() and manifest_path.exists():
                    m = json.loads(manifest_path.read_text(encoding="utf-8"))
                    overlay = (m.get("overlay") or "")
                    # C2C inherits its position rule from an addendum written after
                    # P1, so it cannot claim the stronger pre-registration.
                    c2c = m.get("execution_specification") == "alternative_close_to_close"
                    append({
                        "run_id": d.name,
                        "subrun_id": d.name,
                        "family_id": d.name,
                        "date": date.today().isoformat(),
                        "run_type": kind,
                        "excluded_from_trial_budget": "false",
                        "performance_metrics_computed": "true",
                        "protocol_version": "v6 + c2c addendum" if c2c else "v6",
                        "config_sha256": m.get("config_sha256", ""),
                        "snapshot_sha256": m.get("snapshot_sha256", ""),
                        "code_commit": m.get("code_commit", ""),
                        "n_candidates": "",
                        "delta_multiple": "0.0 fixed",
                        "training_window": overlay,
                        "outer_steps": m.get("outer_steps", ""),
                        "oos_sessions": m.get("oos_sessions", ""),
                        "specified_before_p1": "false" if c2c else "true",
                        "specified_before_own_results": "true",
                        "cannot_modify_p1_headline": "true",
                        "notes": (
                            f"Overlay {overlay} merged over the frozen config/p1.yaml, which is "
                            f"unedited. Execution specification "
                            f"{m.get('execution_specification', 'primary_open_to_close')}, "
                            f"parameters {m.get('execution_parameters') or {}}. "
                            + ("Position rule from docs/c2c_exploratory_addendum.md, fixed "
                               "after P1 and before any close-to-close return was computed."
                               if c2c else "")
                        ),
                    })
                    n += 1
        print(f"registered {n} completed runs")
        return 0

    if args.register_position_rules:
        import pandas as pd
        table = pd.read_csv(ROOT / "results" / "exploratory_position_rules.csv")
        manifest = json.loads((ROOT / "results" / "run_manifest.json")
                              .read_text(encoding="utf-8"))
        n = 0
        for row in table.itertuples():
            if row.kind != "exploratory":
                continue
            family = row.id.split()[0]
            append({
                "run_id": f"{family}",
                "subrun_id": row.id.replace(" ", "_"),
                "family_id": family,
                "date": date.today().isoformat(),
                "run_type": "exploratory",
                "excluded_from_trial_budget": "false",
                "performance_metrics_computed": "true",
                "protocol_version": "v6",
                "config_sha256": manifest["config_sha256"],
                "snapshot_sha256": manifest["snapshot_sha256"],
                "code_commit": git_commit(),
                "n_candidates": 0,
                "delta_multiple": "n/a - trading rule only, no refit",
                "training_window": "P1 frozen predictions",
                "outer_steps": manifest["outer_steps"],
                "oos_sessions": int(manifest["oos_sessions"]),
                "oos_net_sharpe": round(float(row.sharpe), 6),
                "delta_sharpe_vs_always_long": "",
                "delta_annmean_vs_cash": round(float(row.ann_mean_excess), 6),
                "active_sessions": int(row.n_active),
                "active_rate": round(float(row.active_rate), 6),
                "specified_before_p1": "true",
                "specified_before_own_results": "true",
                "cannot_modify_p1_headline": "true",
                "notes": (
                    "Position rule applied to P1's frozen mu_hat; no model was refitted "
                    "and no new search was performed. One of several realised paths from "
                    f"family {family}. Reported in full and not promoted."
                ),
            })
            n += 1
        print(f"registered {n} realised strategy paths")
        return 0

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
