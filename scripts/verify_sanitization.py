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
import hashlib
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
CRLF, LF = bytes([13, 10]), bytes([10])

# A text column may be corrected without a value changing, but only where the
# correction is registered here with its reason. Everything else that differs is a
# failure. The alternative -- ignoring text columns generally -- would let a real
# change hide behind a label edit.
REGISTERED_LABEL_CORRECTIONS = {
    ("results/news_increment_summary.csv", "kind"):
        "the negative-shift arms were described as positive controls, which "
        "docs/errata.md A8 retracts: a positive control injects a variable known to "
        "carry the answer, and future headlines are not that. Relabelled leakage "
        "stress tests. No number changed.",
}

# The last commit of the pre-sanitization branch, recorded as a hash rather than a
# branch name. `--before v2-research` looked right and was worthless: the branch was
# force-updated to the sanitized history, so the script compared the current tree
# with itself and reported that nothing had changed. A moving name cannot anchor a
# before-and-after claim.
PRE_SANITIZATION = "190c97f9258c1fe892d7ff63b36cd4ca01916074"

# Recorded so the comparison survives the reference becoming unfetchable: GitHub is
# being asked to purge the closed pull request that currently serves it.
BASELINE = "results/pre_sanitization_baseline.json"

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
        registered = {c: REGISTERED_LABEL_CORRECTIONS[(path, c)]
                      for c in list(worst)
                      if worst[c] == "text differs"
                      and (path, c) in REGISTERED_LABEL_CORRECTIONS}
        for c in registered:
            del worst[c]
        detail = {"status": "identical by value" if not worst else "DIFFERS",
                  "differing_columns": worst}
        if registered:
            detail["registered_label_corrections"] = registered
            detail["numeric_content"] = "identical"
        report[path] = detail
        return not worst

    report[path] = {"status": "DIFFERS"}
    return False


def write_baseline(ref: str) -> int:
    """Record the pre-sanitization digests, so the proof outlives the reference.

    GitHub is being asked to purge the closed pull request that currently serves
    the pre-sanitization commit. Once it does, `git show <ref>:...` stops working
    and the comparison above becomes unrunnable. These digests are what remains
    checkable afterwards, and they are written before the purge, not after it.
    """
    out = {"pre_sanitization_commit": ref, "recorded_utc": _now(), "sha256": {}}
    for path in [DAILY] + TABLES:
        raw = from_commit(ref, path)
        if raw is not None:
            out["sha256"][path] = hashlib.sha256(raw.replace(CRLF, LF)).hexdigest()
    out["note"] = (
        "SHA-256 over line-ending-normalised bytes, so a digest does not change "
        "with a checkout setting. Compare against the same normalisation."
    )
    (ROOT / BASELINE).write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"recorded {len(out['sha256'])} pre-sanitization digests to {BASELINE}")
    return 0


def compare_to_baseline() -> int:
    """Used when the pre-sanitization commit is no longer fetchable."""
    path = ROOT / BASELINE
    if not path.exists():
        print("the pre-sanitization commit is unfetchable and no baseline was "
              f"recorded in {BASELINE}; the equivalence claim cannot be checked",
              file=sys.stderr)
        return 1
    recorded = json.loads(path.read_text(encoding="utf-8"))
    bad = []
    for name, want in recorded["sha256"].items():
        f = ROOT / name
        got = (hashlib.sha256(f.read_bytes().replace(CRLF, LF)).hexdigest()
               if f.exists() else "MISSING")
        ok = got == want
        if not ok:
            bad.append(name)
        print(f"  {'ok  ' if ok else 'FAIL'} {name}")
    print("")
    print("compared against the recorded baseline for "
          f"{recorded['pre_sanitization_commit'][:8]}, which this repository "
          "cannot reach.")
    print("That is expected in a fresh clone: the commit is served only through a "
          "closed")
    print("pull request reference, which cloning does not fetch. It is also what "
          "will")
    print("remain true permanently once GitHub purges that reference, which is why "
          "the")
    print("digests were recorded before asking.")
    return 0 if not bad else 1


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--before", default=PRE_SANITIZATION,
                    help="the pre-sanitization commit; defaults to the recorded one")
    ap.add_argument("--baseline", action="store_true",
                    help="write the digest baseline instead of comparing")
    args = ap.parse_args()

    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True).stdout.strip()
    ref = subprocess.run(["git", "rev-parse", args.before], cwd=ROOT,
                         capture_output=True, text=True).stdout.strip()
    # rev-parse echoes an unknown 40-character hash back rather than failing, so
    # existence has to be asked separately. Without this the script "compares"
    # against a commit that is not there, finds every file absent, and reports that
    # a value changed -- alarming, and about nothing.
    exists = subprocess.run(["git", "cat-file", "-e", f"{ref}^{{commit}}"],
                            cwd=ROOT, capture_output=True).returncode == 0
    if not ref or not exists:
        # The reference may be gone once GitHub purges the closed pull request.
        # Fall back to the recorded digests rather than silently comparing nothing.
        return compare_to_baseline()
    if args.baseline:
        return write_baseline(ref)
    if ref == head:
        raise SystemExit(
            f"refusing to compare {args.before} with itself: both resolve to "
            f"{head[:8]}. A before-and-after proof that compares a commit with "
            "itself proves nothing, which is exactly what this script did once."
        )

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
