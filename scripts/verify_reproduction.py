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

ORIGINAL_COMMIT = "120f3e9"          # the commit that recorded the first execution
PRESERVED = ROOT / "results" / "p1_original"
COST_BPS = 2.0


def from_git(path: str) -> str:
    return subprocess.run(["git", "show", f"{ORIGINAL_COMMIT}:{path}"],
                          cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8").stdout


def preserve() -> list[str]:
    """Write the first execution's artefacts to results/p1_original/.

    The reproduction wrote over results/, so without this the original exists only
    in git history. A reader should not have to reconstruct the primary result from
    a commit hash.
    """
    PRESERVED.mkdir(parents=True, exist_ok=True)
    saved = []
    for name in ("oos_predictions.csv", "selection_log.csv", "feature_stability.csv",
                 "candidate_diagnostics.csv", "run_manifest.json"):
        body = from_git(f"results/{name}")
        if body:
            (PRESERVED / name).write_text(body, encoding="utf-8", newline="")
            saved.append(name)
    (PRESERVED / "README.md").write_text(
        "# First execution of P1\n\n"
        f"Recovered from commit `{ORIGINAL_COMMIT}`. This is the **primary** result.\n\n"
        "P1 was executed a second time to emit `calibration_diagnostics.csv`, which the\n"
        "configuration promised and the first execution did not write. That second\n"
        "execution changed no data, no rule, no model selection and no reported figure,\n"
        "and is registered as `run_type=reproduction_output_regeneration` with\n"
        "`counts_toward_trial_budget=false`.\n\n"
        "`scripts/verify_reproduction.py` compares the two field by field and writes\n"
        "`results/reproduction_equivalence.json`. Neither run was chosen over the other\n"
        "on the basis of what it produced.\n",
        encoding="utf-8")
    return saved


def with_pnl(frame: pd.DataFrame) -> pd.DataFrame:
    """Add the components a selection log would not reveal."""
    out = frame.copy()
    c = COST_BPS / 1e4
    w = out.position.astype(float)
    out["gross"] = w * out.realised_o2c
    out["execution_cost"] = 2 * c * w.abs()
    out["financing_cost"] = out.financing * w.abs()
    out["net"] = out.gross - out.execution_cost - out.financing_cost
    return out


def main() -> int:
    saved = preserve()
    print(f"preserved the first execution: {', '.join(saved)}\n")

    a = with_pnl(pd.read_csv(PRESERVED / "oos_predictions.csv",
                             index_col="date", parse_dates=True))
    b = with_pnl(pd.read_csv(ROOT / "results" / "oos_predictions.csv",
                             index_col="date", parse_dates=True))

    report: dict = {"original_commit": ORIGINAL_COMMIT, "fields": {}}
    ok = True

    if not a.index.equals(b.index):
        print("FAIL  the two runs do not cover the same dates")
        return 1
    report["sessions"] = len(a)
    print(f"dates                        identical, {len(a)} sessions")

    for col in ("model", "params", "delta", "calibration_skipped"):
        same = bool((a[col].astype(str) == b[col].astype(str)).all())
        ok &= same
        report["fields"][col] = {"identical": same}
        print(f"{col:<28} {'identical' if same else 'DIFFERS'}")

    for col in ("p_short", "p_flat", "p_long", "mu_hat", "position", "financing",
                "realised_o2c", "gross", "execution_cost", "financing_cost", "net"):
        d = (a[col].to_numpy(dtype=float) - b[col].to_numpy(dtype=float))
        worst = float(np.nanmax(np.abs(d))) if len(d) else 0.0
        exact = bool(worst == 0.0)
        ok &= exact
        report["fields"][col] = {"identical": exact, "max_abs_difference": worst}
        print(f"{col:<28} {'identical' if exact else f'max |diff| = {worst:.3e}'}")

    # The reported figures themselves, not just their inputs.
    from src.stats import ann_mean, sharpe
    metrics = {}
    for name, frame in (("original", a), ("reproduction", b)):
        metrics[name] = {
            "sharpe": sharpe(frame.net.to_numpy()),
            "ann_mean_excess": ann_mean(frame.net.to_numpy()),
            "active_sessions": int((frame.position != 0).sum()),
            "long": int((frame.position > 0).sum()),
            "flat": int((frame.position == 0).sum()),
            "short": int((frame.position < 0).sum()),
        }
    same_metrics = metrics["original"] == metrics["reproduction"]
    ok &= same_metrics
    report["metrics"] = metrics
    report["metrics_identical"] = same_metrics
    print(f"{'reported metrics':<28} {'identical' if same_metrics else 'DIFFER'}")
    for k, v in metrics["original"].items():
        print(f"    {k:<24} {v}")

    for name in ("selection_log.csv", "feature_stability.csv"):
        x = (PRESERVED / name).read_text(encoding="utf-8").replace("\r\n", "\n")
        y = (ROOT / "results" / name).read_text(encoding="utf-8").replace("\r\n", "\n")
        same = x == y
        ok &= same
        report["fields"][name] = {"identical": same}
        print(f"{name:<28} {'identical' if same else 'DIFFERS'}")

    for name in ("original", "reproduction"):
        path = (PRESERVED if name == "original" else ROOT / "results") / "run_manifest.json"
        m = json.loads(path.read_text(encoding="utf-8"))
        report[f"manifest_{name}"] = {k: m.get(k) for k in
                                      ("config_sha256", "snapshot_sha256", "code_commit",
                                       "seconds", "packages")}

    same_inputs = (report["manifest_original"]["config_sha256"]
                   == report["manifest_reproduction"]["config_sha256"]
                   and report["manifest_original"]["snapshot_sha256"]
                   == report["manifest_reproduction"]["snapshot_sha256"]
                   and report["manifest_original"]["packages"]
                   == report["manifest_reproduction"]["packages"])
    report["same_config_snapshot_and_packages"] = same_inputs
    print(f"{'config, snapshot, packages':<28} {'identical' if same_inputs else 'DIFFER'}")

    report["verdict"] = ("bit_identical" if ok and same_inputs else "investigate")
    report["disposition"] = (
        "The reproduction is a supplementary artefact. The first execution stands as the "
        "primary result, is preserved under results/p1_original/, and neither run was "
        "chosen over the other on the basis of what it produced."
        if report["verdict"] == "bit_identical" else
        "STOP. A difference was found. Both runs are retained, the better one must not be "
        "selected, and the cause must be established before anything is published."
    )
    dest = ROOT / "results" / "reproduction_equivalence.json"
    dest.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    print(f"\nverdict: {report['verdict']}")
    print(report["disposition"])
    print(f"\nwritten to {dest.relative_to(ROOT)}")
    return 0 if ok and same_inputs else 1


if __name__ == "__main__":
    raise SystemExit(main())
