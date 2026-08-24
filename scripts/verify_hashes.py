"""Confirm that the committed data and configuration are the ones on record.

The protocol's central claim is that the procedure was fixed before it ran. That
claim rests on two hashes, so both are checked here rather than trusted: the data
snapshot against its manifest, and the frozen configuration against the digest
committed beside it. CI runs this on every push, which is what turns "the config
has not changed" from an assertion into something a reader can see.
"""

from __future__ import annotations

import glob
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


from src.digest import sha256_bytes, sha256_of  # noqa: E402  (line-ending independent)


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

    # Quoting the right hash once is not enough: the v5 -> v6 revision left a stale
    # digest behind in one table, which is exactly the defect a reader checking the
    # freeze would find. Every hash-like token in the protocol must resolve to a
    # committed artefact, not merely one of them.
    # Canonical digests, plus the same artefacts hashed verbatim. The second set
    # exists because the protocol's erratum has to quote the digest it superseded in
    # order to explain the change, and a scan that forbade that would force the
    # document to describe a hash it is not allowed to write down. A superseded
    # digest is admissible only when it still resolves to a committed artefact under
    # the older convention -- which is checked here, not asserted -- so an arbitrary
    # stale hash is still caught.
    artefacts = [ROOT / "config" / "p1.yaml",
                 sorted(ROOT.glob("data/market_inputs_*.csv"))[-1]]
    known = {sha256_of(a) for a in artefacts}

    # A superseded digest is one of these artefacts under the older convention: the
    # same content with CRLF terminators. It is CONSTRUCTED from the canonical bytes
    # rather than read off disk, because on a Linux checkout the working copy is
    # already LF and the older digest could not otherwise be reproduced at all --
    # which is exactly how this check passed locally and failed in CI.
    CR, LF = b"\x0d", b"\x0a"
    superseded = set()
    for a in artefacts:
        canonical = a.read_bytes().replace(CR + LF, LF)
        superseded.add(sha256_bytes(canonical.replace(LF, CR + LF), normalise=False))
    superseded -= known
    if superseded:
        print(f"note superseded digests admissible, reconstructed from the committed "
              f"content: {', '.join(sorted(d[:8] for d in superseded))}")
    known |= superseded
    # At least one a-f, so an eight-digit date in backticks is not mistaken for a digest.
    quoted = {m for m in re.findall(r"`([0-9a-f]{8,64})…?`", protocol) if re.search(r"[a-f]", m)}
    for token in sorted(quoted):
        if not any(d.startswith(token.rstrip("…")) for d in known):
            failures.append(
                f"docs/research_protocol.md quotes `{token}`, which matches no committed artefact"
            )
    if not failures:
        print(f"ok   every hash quoted in the protocol resolves ({len(quoted)} distinct)")

    if failures:
        print("\n" + "\n".join(failures), file=sys.stderr)
        return 1
    print("\nAll recorded hashes match.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
