"""Prove the history rewrite changed no research value.

Rewriting history changes commit hashes. It must change nothing else. This compares
every research artefact between a reference commit and the working tree, field by
field rather than by digest, because a digest cannot distinguish "the numbers moved"
from "the file was checked out with different line endings" — and the second is what
actually happened here, on six files, which is exactly the sort of thing that looks
alarming until it is measured.

What is compared:

* the confirmatory run's daily rows: date, model, calibrated probabilities, expected
  return, position, realised return, financing
* the derived P&L components: gross, execution cost, financing cost, net
* the reported metrics: Sharpe, annualised mean, long/flat/short counts
* every summary table: exploratory, news arms, position rules, statistical tests

What is allowed to differ: commit hashes, and nothing else.

    python scripts/verify_sanitization.py --before v2-research
"""

from __future__ import annotations

import argparse
import io
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.stats import ann_mean, sharpe  # noqa: E402

COST_BPS = 2.0

DAILY = "results/oos_predictions.csv"
TABLES = [
    "results/trade_ledger.csv",
    "results/statistical_tests.csv",
    "results/exploratory_summary.csv",
    "results/news_increment_summary.csv",
    "results/exploratory_position_rules.csv",
    "results/p1_original/oos_predictions.csv",
    "results/p1_original/selection_log.csv",
    "config/p1.yaml",
    "data/market_inputs_2026-08-21.csv",
]


def from_commit(ref: str, path: str) -> bytes | None:
    r = subprocess.run(["git", "show", f"{ref}:{path}"], cwd=ROOT,
                       capture_output=True)
    return r.stdout if r.returncode == 0 else None


def frame(raw: bytes) -> pd.DataFrame:
    return pd.read_csv(io.BytesIO(raw))


def compare_daily(ref: str, report: dict) -> bool:
    old = from_commit(ref, DAILY)
    if old is None:
        report[DAILY] = {"status": "absent in the reference commit"}
        return False
    a, b = frame(old), pd.read_csv(ROOT / DAILY)

    detail: dict = {"rows_before": len(a), "rows_after": len(b)}
    if len(a) != len(b):
        detail["status"] = "row count differs"
        report[DAILY] = detail
        return False

    ok = True
    for col in ("date", "model", "params", "calibration_skipped"):
        same = bool((a[col].astype(str) == b[col].astype(str)).all())
        detail[col] = "identical" if same else "DIFFERS"
        ok &= same

    for col in ("p_short", "p_flat", "p_long", "mu_hat", "position",
                "realised_o2c", "financing"):
        diff = float(np.nanmax(np.abs(a[col].to_numpy(float) - b[col].to_numpy(float))))
        detail[col] = {"identical": diff == 0.0, "max_abs_difference": diff}
        ok &= diff == 0.0

    # The P&L a reader would reconstruct, not just its inputs.
    c = COST_BPS / 1e4
    for name, f in (("before", a), ("after", b)):
        w = f.position.astype(float)
        f["_gross"] = w * f.realised_o2c
        f["_exec"] = 2 * c * w.abs()
        f["_fin"] = f.financing * w.abs()
        f["_net"] = f._gross - f._exec - f._fin
    for col in ("_gross", "_exec", "_fin", "_net"):
        diff = float(np.nanmax(np.abs(a[col].to_numpy(float) - b[col].to_numpy(float))))
        detail[col.lstrip("_")] = {"identical": diff == 0.0, "max_abs_difference": diff}
        ok &= diff == 0.0

    metrics = {}
    for name, f in (("before", a), ("after", b)):
        metrics[name] = {
            "sharpe": sharpe(f._net.to_numpy()),
            "ann_mean_excess": ann_mean(f._net.to_numpy()),
            "long": int((f.position > 0).sum()),
            "flat": int((f.position == 0).sum()),
            "short": int((f.position < 0).sum()),
        }
    same_metrics = metrics["before"] == metrics["after"]
    detail["reported_metrics"] = metrics
    detail["metrics_identical"] = same_metrics
    ok &= same_metrics
    detail["status"] = "identical" if ok else "DIFFERS"
    report[DAILY] = detail
    return ok


def compare_table(ref: str, path: str, report: dict) -> bool:
    old = from_commit(ref, path)
    if old is None:
        report[path] = {"status": "absent in the reference commit"}
        return False
    new = (ROOT / path).read_bytes()

    if old == new:
        report[path] = {"status": "byte-identical"}
        return True

    # Line endings are presentation, not content. Say so explicitly rather than
    # letting a digest mismatch masquerade as a changed number.
    if old.replace(b"\x0d\x0a", b"\x0a") == new.replace(b"\x0d\x0a", b"\x0a"):
        report[path] = {"status": "identical apart from line endings",
                        "crlf_before": old.count(bytes([13, 10])),
                        "crlf_after": new.count(bytes([13, 10]))}
        return True

    if path.endswith(".csv"):
        a, b = frame(old), pd.read_csv(io.BytesIO(new))
        if a.shape != b.shape or list(a.columns) != list(b.columns):
            report[path] = {"status": "shape or columns differ",
                            "before": list(a.shape), "after": list(b.shape)}
            return False
        worst = {}
        for col in a.columns:
            if pd.api.types.is_numeric_dtype(a[col]):
                d = float(np.nanmax(np.abs(a[col].to_numpy(float)
                                           - b[col].to_numpy(float))))
                if d:
                    worst[col] = d
            elif not (a[col].astype(str) == b[col].astype(str)).all():
                worst[col] = "text differs"
        report[path] = {"status": "identical by value" if not worst else "DIFFERS",
                        "differing_columns": worst}
        return not worst

    report[path] = {"status": "DIFFERS"}
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--before", default="v2-research",
                    help="the reference to compare against")
    args = ap.parse_args()

    report: dict = {"reference": args.before,
                    "reference_commit": subprocess.run(
                        ["git", "rev-parse", args.before], cwd=ROOT,
                        capture_output=True, text=True).stdout.strip(),
                    "current_commit": subprocess.run(
                        ["git", "rev-parse", "HEAD"], cwd=ROOT,
                        capture_output=True, text=True).stdout.strip(),
                    "files": {}}

    ok = compare_daily(args.before, report["files"])
    for path in TABLES:
        ok &= compare_table(args.before, path, report["files"])

    report["verdict"] = "no research value changed" if ok else "STOP: a value changed"
    dest = ROOT / "results" / "sanitization_equivalence.json"
    dest.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    for path, detail in report["files"].items():
        status = detail.get("status", "?")
        print(f"  {'ok  ' if 'DIFFER' not in str(status) and 'STOP' not in str(status) else 'FAIL'} "
              f"{path:<48} {status}")
    d = report["files"].get(DAILY, {})
    if "reported_metrics" in d:
        print("\n  reported metrics, before and after:")
        for k, v in d["reported_metrics"]["before"].items():
            print(f"    {k:<18} {v}")
    print(f"\nverdict: {report['verdict']}")
    print(f"written to {dest.relative_to(ROOT)}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
