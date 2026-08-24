"""Confirm that the committed data and configuration are the ones on record.

The protocol's central claim is that the procedure was fixed before it ran. That
claim rests on two hashes, so both are checked here rather than trusted: the data
snapshot against its manifest, and the frozen configuration against the digest
committed beside it. CI runs this on every push, which is what turns "the config
has not changed" from an assertion into something a reader can see.
"""

from __future__ import annotations

import glob
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    failures = []

    for manifest_path in sorted(ROOT.glob("data/market_inputs_*.manifest.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        csv_path = manifest_path.parent / manifest["snapshot_file"]
        actual = sha256_of(csv_path)
        ok = actual == manifest["sha256"]
        print(f"{'ok  ' if ok else 'FAIL'} {csv_path.name}  {actual}")
        if not ok:
            failures.append(f"{csv_path.name}: recorded {manifest['sha256']}, actual {actual}")

    config = ROOT / "config" / "p1.yaml"
    recorded = (ROOT / "config" / "p1.sha256").read_text(encoding="utf-8").split()[0]
    actual = sha256_of(config)
    ok = actual == recorded
    print(f"{'ok  ' if ok else 'FAIL'} {config.name}  {actual}")
    if not ok:
        failures.append(f"p1.yaml: recorded {recorded}, actual {actual}")

    # The protocol quotes both hashes; a mismatch there is the same defect.
    protocol = (ROOT / "docs" / "research_protocol.md").read_text(encoding="utf-8")
    for label, digest in (("configuration", actual), ("snapshot", sha256_of(
            sorted(ROOT.glob("data/market_inputs_*.csv"))[-1]))):
        if digest not in protocol:
            failures.append(f"docs/research_protocol.md does not quote the {label} hash {digest}")
        else:
            print(f"ok   protocol quotes the {label} hash")

    if failures:
        print("\n" + "\n".join(failures), file=sys.stderr)
        return 1
    print("\nAll recorded hashes match.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
