"""Confirm that what this repository publishes is what is on record.

The protocol's central claim is that the procedure was fixed before it ran. Two
different things support that claim, and conflating them would be dishonest, so
this script keeps them apart:

**Verification.** The frozen configuration is committed, so its digest is
recomputed from the bytes on disk and compared against the digest committed
beside it. If they disagree the run fails. This is a real check and it is what
CI exercises on every push.

**Record consistency.** The market snapshot is licensed and is *not*
distributed with this repository. Its bytes therefore cannot be rehashed from a
public clone, and this script does not pretend otherwise. What it can do is
confirm that every place the repository writes the snapshot's identifier writes
the *same* identifier. That is a consistency check across independently read
files, not a verification of the original data, and it is reported as such.

If you hold a legally obtained copy of the snapshot and its manifest, drop both
into `data/` and this script upgrades to real byte verification automatically.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


from src.digest import sha256_bytes, sha256_of  # noqa: E402  (line-ending independent)

NOT_VERIFIED = (
    "NOT VERIFIED: the licensed market snapshot is not distributed in this "
    "repository.\nRecorded snapshot identifiers are checked for consistency only."
)

# The frozen pre-registration. Its expected digest is read from docs/freeze_record.md
# rather than recomputed from the document, so the comparison is between the file's
# bytes and an independently written constant. Regenerating the expectation from the
# file it is meant to check would make the check pass by construction.
FROZEN_PROTOCOL = "docs/research_protocol.md"

# Every file that writes the snapshot's identifier down. config/p1.yaml is the
# authoritative one: it is the frozen procedure, and the others describe it.
RECORD_FILES = (
    "config/p1.yaml",
    "docs/research_protocol.md",
    "docs/data_availability.md",
    "docs/feature_dictionary.md",
    "docs/freeze_record.md",
    "results/run_manifest.json",
)


def _snapshot_files(root: Path) -> tuple[list[Path], list[Path]]:
    """Snapshot CSVs and manifests actually present under data/.

    Restricted to `data/` and to the `market_inputs_` prefix. The synthetic
    fixture lives under `tests/fixtures/` and is deliberately unreachable from
    here: it is invented data, and treating it as the frozen input would let a
    run report a Sharpe ratio computed from a random walk.
    """
    csvs = [p for p in sorted(root.glob("data/market_inputs_*.csv"))
            if "synthetic" not in p.name]
    manifests = sorted(root.glob("data/market_inputs_*.manifest.json"))
    return csvs, manifests


def _recorded_snapshot_digest(root: Path) -> str | None:
    """The snapshot digest as the frozen configuration states it."""
    text = (root / "config" / "p1.yaml").read_text(encoding="utf-8")
    match = re.search(r"snapshot_sha256:\s*([0-9a-f]{64})", text)
    return match.group(1) if match else None


def _check_configuration(root: Path, failures: list[str]) -> str:
    """Real verification: recompute the configuration digest and compare."""
    config = root / "config" / "p1.yaml"
    recorded = (root / "config" / "p1.sha256").read_text(encoding="utf-8").split()[0]
    actual = sha256_of(config)
    ok = actual == recorded
    print(f"{'ok  ' if ok else 'FAIL'} {config.name}  {actual}  (recomputed and compared)")
    if not ok:
        failures.append(f"p1.yaml: recorded {recorded}, actual {actual}")
    return actual


def _verify_snapshot_bytes(csvs: list[Path], manifests: list[Path],
                           recorded: str | None, failures: list[str]) -> None:
    """Both halves present: rehash the data and compare against both records."""
    for manifest_path in manifests:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        csv_path = manifest_path.parent / manifest["snapshot_file"]
        if not csv_path.exists():
            failures.append(f"{manifest_path.name} names {manifest['snapshot_file']}, "
                            "which is not present")
            continue
        actual = sha256_of(csv_path)
        ok = actual == manifest["sha256"]
        print(f"{'ok  ' if ok else 'FAIL'} {csv_path.name}  {actual}  "
              "(recomputed and compared against its manifest)")
        if not ok:
            failures.append(
                f"{csv_path.name}: manifest records {manifest['sha256']}, actual {actual}")
        # The manifest travels with the CSV, so agreeing with it is necessary but
        # not sufficient: a matched pair could still be a different vintage than
        # the one the frozen procedure names. config/p1.yaml is the independent
        # record, so the frozen snapshot is also checked against that.
        if recorded and csv_path.name == "market_inputs_2026-08-21.csv":
            if actual != recorded:
                failures.append(
                    f"{csv_path.name}: config/p1.yaml records {recorded}, actual {actual}")
            else:
                print("ok   frozen snapshot matches the digest in config/p1.yaml")


def _check_record_consistency(root: Path, recorded: str | None,
                              failures: list[str]) -> None:
    """Snapshot absent: confirm every file writes the same identifier.

    This compares independently read files against the digest parsed from the
    frozen configuration. It says nothing about the original bytes, and the
    output says so.
    """
    if recorded is None:
        failures.append("config/p1.yaml records no snapshot_sha256")
        return
    for name in RECORD_FILES:
        path = root / name
        if not path.exists():
            failures.append(f"{name} is missing; the snapshot record cannot be cross-checked")
            continue
        if name == "config/p1.yaml":
            continue  # the source of the value; comparing it with itself proves nothing
        text = path.read_text(encoding="utf-8", errors="replace")
        if recorded in text:
            print(f"ok   {name} records the same snapshot identifier")
        else:
            failures.append(
                f"{name} does not record the snapshot identifier {recorded} "
                "that config/p1.yaml states")


def _recorded_protocol_digest(root: Path) -> str | None:
    """The frozen protocol's digest, as docs/freeze_record.md states it."""
    record = root / "docs" / "freeze_record.md"
    if not record.exists():
        return None
    text = record.read_text(encoding="utf-8")
    match = re.search(r"docs/research_protocol\.md\s+([0-9a-f]{64})", text)
    return match.group(1) if match else None


def _check_frozen_protocol(root: Path, failures: list[str]) -> None:
    """Real verification: the pre-registration must not have moved.

    A pre-registration revised after seeing results is not evidence of anything, so
    this is the check that the document is the one that was frozen. It is compared
    against the digest written in docs/freeze_record.md, not against itself.
    """
    path = root / FROZEN_PROTOCOL
    recorded = _recorded_protocol_digest(root)
    if recorded is None:
        failures.append("docs/freeze_record.md records no digest for "
                        f"{FROZEN_PROTOCOL}")
        return
    actual = sha256_of(path)
    ok = actual == recorded
    print(f"{'ok  ' if ok else 'FAIL'} {FROZEN_PROTOCOL}  {actual}  "
          "(recomputed and compared against the freeze record)")
    if not ok:
        failures.append(f"{FROZEN_PROTOCOL}: freeze record states {recorded}, "
                        f"actual {actual}")


def _historical_identifiers(root: Path) -> set[str]:
    """Digests the freeze record documents as superseded.

    Read from docs/freeze_record.md rather than hard-coded, so admitting one is a
    documented act rather than a quiet exception in a script. A stale hash that
    nobody wrote down is still rejected.
    """
    record = root / "docs" / "freeze_record.md"
    if not record.exists():
        return set()
    text = record.read_text(encoding="utf-8")
    section = text.split("## Historical identifiers", 1)
    if len(section) < 2:
        return set()
    body = section[1].split("## ", 1)[0]
    return set(re.findall("[0-9a-f]{64}", body))


def _check_quoted_hashes(root: Path, config_digest: str, recorded: str | None,
                         artefacts: list[Path], failures: list[str]) -> None:
    """Every hash-like token in the protocol must resolve to something real.

    The v5 -> v6 revision once left a stale digest in one table, which is exactly
    the defect a reader checking the freeze would find. Quoting the right hash
    once is not enough.
    """
    protocol = (root / "docs" / "research_protocol.md").read_text(encoding="utf-8")

    # The configuration digest is accepted under either convention. The protocol is
    # frozen and quotes the CRLF-era value that was current when it was written;
    # editing a pre-registration so a later checker is happy would defeat the point
    # of freezing it. Both forms are derived from the committed bytes below, so an
    # arbitrary stale hash is still rejected.
    cr, lf = bytes([13]), bytes([10])
    canonical = (root / "config" / "p1.yaml").read_bytes().replace(cr + lf, lf)
    config_forms = {config_digest,
                    sha256_bytes(canonical.replace(lf, cr + lf), normalise=False)}
    if any(d in protocol for d in config_forms):
        print("ok   protocol quotes the configuration hash")
    else:
        failures.append("docs/research_protocol.md quotes no digest that resolves "
                        "to config/p1.yaml")
    if recorded is not None:
        if recorded in protocol:
            print("ok   protocol quotes the snapshot hash")
        else:
            failures.append(
                f"docs/research_protocol.md does not quote the snapshot hash {recorded}")

    known = {sha256_of(a) for a in artefacts}
    if recorded:
        known.add(recorded)
    known |= _historical_identifiers(root)

    # A superseded digest is a committed artefact under the older convention: the
    # same content with CRLF terminators. It is CONSTRUCTED from the canonical
    # bytes rather than read off disk, because on a Linux checkout the working
    # copy is already LF and the older digest could not otherwise be reproduced
    # at all -- which is exactly how this check once passed locally and failed in
    # CI. The protocol's erratum has to quote the digest it superseded in order to
    # explain the change; a scan that forbade that would force the document to
    # describe a hash it is not allowed to write down.
    CR, LF = b"\x0d", b"\x0a"
    superseded = set()
    for artefact in artefacts:
        canonical = artefact.read_bytes().replace(CR + LF, LF)
        superseded.add(sha256_bytes(canonical.replace(LF, CR + LF), normalise=False))
    superseded -= known
    if superseded:
        print(f"note superseded digests admissible, reconstructed from the committed "
              f"content: {', '.join(sorted(d[:8] for d in superseded))}")
    known |= superseded

    # At least one a-f, so an eight-digit date in backticks is not mistaken for a digest.
    quoted = {m for m in re.findall(r"`([0-9a-f]{8,64})…?`", protocol)
              if re.search(r"[a-f]", m)}
    unresolved = [t for t in sorted(quoted)
                  if not any(d.startswith(t.rstrip("…")) for d in known)]
    for token in unresolved:
        failures.append(
            f"docs/research_protocol.md quotes `{token}`, which matches no known artefact")
    if not unresolved:
        print(f"ok   every hash quoted in the protocol resolves ({len(quoted)} distinct)")


def main(root: Path = ROOT) -> int:
    failures: list[str] = []
    csvs, manifests = _snapshot_files(root)
    recorded = _recorded_snapshot_digest(root)

    # Exactly one half of the pair is a broken state, not a supported one. It
    # means either a manifest describing data that is gone or data with nothing
    # to check it against, and reporting either as success would be a lie.
    if bool(csvs) != bool(manifests):
        present = "CSV" if csvs else "manifest"
        missing = "manifest" if csvs else "CSV"
        print(f"FAIL snapshot {present} present without its {missing}", file=sys.stderr)
        print(f"\nsnapshot {present} found but the matching {missing} is absent. "
              "Provide both or neither.", file=sys.stderr)
        return 1

    distributed = bool(csvs) and bool(manifests)
    config_digest = _check_configuration(root, failures)
    _check_frozen_protocol(root, failures)

    if distributed:
        _verify_snapshot_bytes(csvs, manifests, recorded, failures)
    else:
        print()
        print(NOT_VERIFIED)
        print()
        _check_record_consistency(root, recorded, failures)

    artefacts = [root / "config" / "p1.yaml"] + csvs
    _check_quoted_hashes(root, config_digest, recorded, artefacts, failures)

    if failures:
        print("\n" + "\n".join(failures), file=sys.stderr)
        return 1

    if distributed:
        print("\nAll recorded hashes match.")
    else:
        print("\nConfiguration verified against its committed digest.")
        print("Snapshot NOT VERIFIED: identifiers are consistent across the "
              "repository, which is\na weaker statement than a byte check and is "
              "not a substitute for one.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
