"""Run every retraining exploratory specification, in one batch, to completion.

The batch is deliberately not selective. It runs all of them, records all of them,
and reports all of them — including the ones that come out ahead of P1, which is
where the discipline actually costs something. Picking the best row of this table
and presenting it as the result is the winner's curse in its most ordinary form,
and §7.2 of the protocol rules it out in advance.

A failure does not stop the batch. It is recorded as a failure and the next
specification runs, because a batch that halts on the first error produces a table
whose gaps are invisible.

    python scripts/run_exploratory_batch.py                 # all of them
    python scripts/run_exploratory_batch.py --only E1 E22    # a subset
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OVERLAYS = ROOT / "config" / "exploratory"
DEST = ROOT / "results" / "exploratory"


def sort_key(path: Path) -> tuple:
    stem = path.stem
    digits = "".join(ch for ch in stem if ch.isdigit())
    return (int(digits or 0), stem)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", nargs="*", default=None, help="run only these ids")
    ap.add_argument("--skip-existing", action="store_true",
                    help="leave a specification alone if its manifest is already there")
    args = ap.parse_args()

    overlays = sorted(OVERLAYS.glob("E*.yaml"), key=sort_key)
    if args.only:
        wanted = set(args.only)
        overlays = [o for o in overlays if o.stem in wanted]
        missing = wanted - {o.stem for o in overlays}
        if missing:
            raise SystemExit(f"no overlay for {sorted(missing)}")
    DEST.mkdir(parents=True, exist_ok=True)

    print(f"{len(overlays)} specifications to run\n")
    log = []
    batch_start = time.perf_counter()

    for i, overlay in enumerate(overlays, 1):
        eid = overlay.stem
        outdir = DEST / eid
        if args.skip_existing and (outdir / "run_manifest.json").exists():
            print(f"[{i}/{len(overlays)}] {eid}  already present, skipped")
            log.append({"id": eid, "status": "skipped"})
            continue

        outdir.mkdir(parents=True, exist_ok=True)
        started = time.perf_counter()
        print(f"[{i}/{len(overlays)}] {eid}  started", flush=True)
        proc = subprocess.run(
            [sys.executable, "-u", str(ROOT / "scripts" / "run_p1.py"),
             "--overlay", f"config/exploratory/{eid}.yaml",
             "--outdir", f"results/exploratory/{eid}"],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        elapsed = time.perf_counter() - started
        (outdir / "run.log").write_text(
            (proc.stdout or "") + ("\n--- stderr ---\n" + proc.stderr if proc.stderr else ""),
            encoding="utf-8",
        )
        status = "ok" if proc.returncode == 0 else f"failed rc={proc.returncode}"
        print(f"[{i}/{len(overlays)}] {eid}  {status} in {elapsed / 60:.1f} min", flush=True)
        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-4:]
            for line in tail:
                print(f"        {line}", flush=True)
        log.append({"id": eid, "status": status, "minutes": round(elapsed / 60, 2)})
        (DEST / "batch_log.json").write_text(json.dumps(log, indent=2), encoding="utf-8")

    total = (time.perf_counter() - batch_start) / 60
    ok = sum(1 for row in log if row["status"] == "ok")
    print(f"\nbatch complete in {total:.1f} min: {ok}/{len(log)} succeeded")
    for row in log:
        if row["status"] not in ("ok", "skipped"):
            print(f"  {row['id']}: {row['status']}  (see results/exploratory/{row['id']}/run.log)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
