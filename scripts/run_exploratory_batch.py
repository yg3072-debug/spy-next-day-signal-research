"""Run a directory of pre-registered specifications, in one batch, to completion.

The batch is deliberately not selective. It runs all of them, records all of them,
and reports all of them — including the ones that come out ahead of P1, which is
where the discipline actually costs something. Picking the best row of the
resulting table and presenting it as the result is the winner's curse in its most
ordinary form, and §7.2 of the protocol rules it out in advance.

A failure does not stop the batch. It is recorded as a failure and the next
specification runs, because a batch that halts on the first error produces a table
whose gaps are invisible.

    python scripts/run_exploratory_batch.py                      # all of them
    python scripts/run_exploratory_batch.py --only E1 E22        # a subset
    python scripts/run_exploratory_batch.py --workers 6          # in parallel
    python scripts/run_exploratory_batch.py --dir config/altdata --out results/altdata

Running them in parallel changes nothing about the results. Each specification is
an independent process with its own seed, every fit is single-threaded by
configuration, and none of them reads another's output. What it changes is whether
the batch finishes in an hour or in five.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sort_key(path: Path) -> tuple:
    stem = path.stem
    digits = "".join(ch for ch in stem if ch.isdigit())
    return (int(digits or 0), stem)


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", nargs="*", default=None, help="run only these ids")
    ap.add_argument("--skip-existing", action="store_true",
                    help="leave a specification alone if its manifest is already there")
    ap.add_argument("--workers", type=int, default=1,
                    help="specifications to run at once; results are unaffected")
    ap.add_argument("--dir", default="config/exploratory", help="directory of overlays")
    ap.add_argument("--out", default="results/exploratory", help="where output goes")
    args = ap.parse_args()

    overlays_dir = ROOT / args.dir
    dest = ROOT / args.out

    overlays = sorted(overlays_dir.glob("*.yaml"), key=sort_key)
    if args.only:
        wanted = set(args.only)
        overlays = [o for o in overlays if o.stem in wanted]
        missing = wanted - {o.stem for o in overlays}
        if missing:
            raise SystemExit(f"no overlay for {sorted(missing)}")
    if not overlays:
        raise SystemExit(f"no overlays found in {args.dir}")
    dest.mkdir(parents=True, exist_ok=True)

    print(f"{len(overlays)} specifications from {args.dir}, "
          f"{args.workers} at a time\n")
    log: list[dict] = []
    batch_start = time.perf_counter()

    def run_one(overlay: Path) -> dict:
        eid = overlay.stem
        outdir = dest / eid
        if args.skip_existing and (outdir / "run_manifest.json").exists():
            print(f"  {eid:<7} already present, skipped", flush=True)
            return {"id": eid, "status": "skipped"}

        outdir.mkdir(parents=True, exist_ok=True)
        started = time.perf_counter()
        print(f"  {eid:<7} started", flush=True)
        proc = subprocess.run(
            [sys.executable, "-u", str(ROOT / "scripts" / "run_p1.py"),
             "--overlay", rel(overlay), "--outdir", rel(outdir)],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        elapsed = time.perf_counter() - started
        body = proc.stdout or ""
        if proc.stderr:
            body += "\n--- stderr ---\n" + proc.stderr
        (outdir / "run.log").write_text(body, encoding="utf-8")

        status = "ok" if proc.returncode == 0 else f"failed rc={proc.returncode}"
        print(f"  {eid:<7} {status} in {elapsed / 60:.1f} min", flush=True)
        if proc.returncode != 0:
            for line in (proc.stderr or proc.stdout or "").strip().splitlines()[-4:]:
                print(f"          {line}", flush=True)
        return {"id": eid, "status": status, "minutes": round(elapsed / 60, 2)}

    def record() -> None:
        (dest / "batch_log.json").write_text(json.dumps(log, indent=2), encoding="utf-8")

    if args.workers > 1:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = [pool.submit(run_one, o) for o in overlays]
            for future in as_completed(futures):
                log.append(future.result())
                record()
    else:
        for overlay in overlays:
            log.append(run_one(overlay))
            record()

    total = (time.perf_counter() - batch_start) / 60
    ok = sum(1 for row in log if row["status"] == "ok")
    print(f"\nbatch complete in {total:.1f} min: {ok}/{len(log)} succeeded")
    for row in sorted(log, key=lambda r: r["id"]):
        if row["status"] not in ("ok", "skipped"):
            print(f"  {row['id']}: {row['status']}  (see {args.out}/{row['id']}/run.log)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
