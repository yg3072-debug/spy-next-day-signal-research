"""Prove that a reproduction run is the same trial, field by field.

P1 was executed a second time to emit `calibration_diagnostics.csv`, which
`config/p1.yaml` promises in its `outputs` list and which the first execution did
not write. Re-executing a procedure is a **computation run**, not a research
trial: nothing about the data, the rules, the model selection or the reported
figures was changed, and neither execution was chosen over the other on the basis
of what it produced.

That claim is only worth what it can be checked against, so this checks it. Not
"the eight selections matched" — every field, including the ones a selection log
would not show: probabilities, expected returns, the trading threshold, positions,
and the gross, cost and net components of the daily return.

The disposition rules were fixed before the comparison was run:

    identical to the bit
        the reproduction is a supplementary artefact; the original stands as the
        primary result and both manifests are retained

    differences at machine epsilon only, with identical positions and identical
        reported figures
        a numerical determinism issue: quantify it, disclose it, and keep P1

    any difference in selected model, position, or return
        stop. Retain both runs, investigate, and do NOT choose the better one

    a code defect found that affected trading output
        the original is void for a technical reason and the corrected run becomes
        the result, whether it looks better or worse

    python scripts/verify_reproduction.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

# The commit under which the first execution's artefacts were first recorded. It is a
# historical label only. The artefacts themselves live in results/p1_original/ and are
# read from there: a verification step that required checking out a commit nobody can
# fetch would not be a verification step.
HISTORICAL_COMMIT = "120f3e9"
PRESERVED = ROOT / "results" / "p1_original"
MANIFEST = PRESERVED / "manifest.sha256.json"
COST_BPS = 2.0

# Columns published for both executions. `gross` and `net` are absent from both,
# because reconstructing them needs the licensed snapshot's daily returns, which this
# repository does not distribute. That limit is stated in the output rather than
# worked around -- everything below is a comparison of values actually present.
SHARED_LABELS = ("model", "params", "delta", "calibration_skipped")
SHARED_NUMERIC = ("p_short", "p_flat", "p_long", "mu_hat", "position", "financing")


def file_digests(directory: Path) -> dict:
    """SHA-256 of every artefact, so the directory has a stable identity."""
    from src.digest import sha256_of
    return {p.name: sha256_of(p) for p in sorted(directory.iterdir())
            if p.is_file() and p.name != MANIFEST.name}


def with_costs(frame: pd.DataFrame) -> pd.DataFrame:
    """Add the cost components the position and the short rate determine.

    Execution cost and financing cost are functions of the position and the
    financing rate alone, so they are comparable without any market data. The gross
    and net return are not: they need the realised session return, which comes from
    the undistributed snapshot.
    """
    out = frame.copy()
    c = COST_BPS / 1e4
    w = out.position.astype(float)
    out["execution_cost"] = 2 * c * w.abs()
    out["financing_cost"] = out.financing * w.abs()
    return out


def main() -> int:
    print("comparing the primary execution in results/p1_original/ with the current "
          "results/")

    a = with_costs(pd.read_csv(PRESERVED / "oos_predictions.csv",
                               index_col="date", parse_dates=True))
    b = with_costs(pd.read_csv(ROOT / "results" / "oos_predictions.csv",
                               index_col="date", parse_dates=True))

    report: dict = {
        "primary": "results/p1_original/",
        "comparison": "results/",
        "historical_commit_label": HISTORICAL_COMMIT,
        "verification_requires_git_history": False,
        "fields": {},
    }
    ok = True

    if not a.index.equals(b.index):
        print("FAIL  the two executions do not cover the same dates")
        return 1
    report["sessions"] = len(a)
    print(f"dates                        identical, {len(a)} sessions")

    for col in SHARED_LABELS:
        same = bool((a[col].astype(str) == b[col].astype(str)).all())
        ok &= same
        report["fields"][col] = {"identical": same}
        print(f"{col:<28} {'identical' if same else 'DIFFERS'}")

    for col in SHARED_NUMERIC + ("execution_cost", "financing_cost"):
        d = a[col].to_numpy(dtype=float) - b[col].to_numpy(dtype=float)
        worst = float(np.nanmax(np.abs(d))) if len(d) else 0.0
        exact = bool(worst == 0.0)
        ok &= exact
        report["fields"][col] = {"identical": exact, "max_abs_difference": worst}
        print(f"{col:<28} {'identical' if exact else f'max |diff| = {worst:.3e}'}")

    # Position counts are the reported figures that survive without the snapshot.
    counts = {}
    for name, frame in (("primary", a), ("comparison", b)):
        counts[name] = {
            "active_sessions": int((frame.position != 0).sum()),
            "long": int((frame.position > 0).sum()),
            "flat": int((frame.position == 0).sum()),
            "short": int((frame.position < 0).sum()),
            "total_execution_cost": float(frame.execution_cost.sum()),
            "total_financing_cost": float(frame.financing_cost.sum()),
        }
    same_counts = counts["primary"] == counts["comparison"]
    ok &= same_counts
    report["position_and_cost_totals"] = counts
    report["position_and_cost_totals_identical"] = same_counts
    print(f"{'position and cost totals':<28} {'identical' if same_counts else 'DIFFER'}")
    for k, v in counts["primary"].items():
        print(f"    {k:<24} {v}")

    for name in ("selection_log.csv", "feature_stability.csv",
                 "candidate_diagnostics.csv"):
        x = (PRESERVED / name).read_text(encoding="utf-8").replace(chr(13) + chr(10), chr(10))
        y = (ROOT / "results" / name).read_text(encoding="utf-8").replace(chr(13) + chr(10), chr(10))
        same = x == y
        ok &= same
        report["fields"][name] = {"identical": same}
        print(f"{name:<28} {'identical' if same else 'DIFFERS'}")

    for label, path in (("primary", PRESERVED / "run_manifest.json"),
                        ("comparison", ROOT / "results" / "run_manifest.json")):
        m = json.loads(path.read_text(encoding="utf-8"))
        report[f"manifest_{label}"] = {k: m.get(k) for k in
                                       ("config_sha256", "snapshot_sha256",
                                        "code_commit", "seconds", "packages")}

    same_inputs = (report["manifest_primary"]["config_sha256"]
                   == report["manifest_comparison"]["config_sha256"]
                   and report["manifest_primary"]["snapshot_sha256"]
                   == report["manifest_comparison"]["snapshot_sha256"]
                   and report["manifest_primary"]["packages"]
                   == report["manifest_comparison"]["packages"])
    report["same_config_snapshot_and_packages"] = same_inputs
    print(f"{'config, snapshot, packages':<28} "
          f"{'identical' if same_inputs else 'DIFFER'}")

    # A stable file-level identity for the preserved directory.
    digests = file_digests(PRESERVED)
    MANIFEST.write_text(json.dumps({
        "directory": "results/p1_original/",
        "description": "SHA-256 of each artefact of the primary P1 execution, "
                       "LF-normalised for text.",
        "files": digests,
    }, indent=2), encoding="utf-8")
    report["primary_file_digests"] = digests
    print(f"{'file-level manifest':<28} written, {len(digests)} artefacts")

    report["not_compared"] = {
        "fields": ["gross", "net", "realised_o2c"],
        "reason": "reconstructing the realised session return requires the licensed "
                  "market snapshot, which this repository does not distribute. Every "
                  "field either execution actually publishes is compared above.",
    }

    report["verdict"] = "bit_identical" if ok and same_inputs else "investigate"
    report["disposition"] = (
        "Only one confirmatory decision path was evaluated. The deterministic "
        "procedure was later re-executed solely to persist diagnostics the "
        "configuration had promised but the first execution omitted. Every shared "
        "field is bit-identical, and no result was used to select a replacement "
        "procedure. The first execution stands as the primary result and is preserved "
        "under results/p1_original/."
        if report["verdict"] == "bit_identical" else
        "STOP. A difference was found. Both executions are retained, the better one "
        "must not be selected, and the cause must be established before anything is "
        "published."
    )
    dest = ROOT / "results" / "reproduction_equivalence.json"
    dest.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    print()
    print(f"verdict: {report['verdict']}")
    print(report["disposition"])
    print()
    print(f"written to {dest.relative_to(ROOT)}")
    return 0 if ok and same_inputs else 1


if __name__ == "__main__":
    raise SystemExit(main())
