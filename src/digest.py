"""One way of hashing an artefact, so the answer does not depend on the platform.

The frozen configuration's SHA-256 is the whole basis of the claim that the method
was fixed before it ran. That claim failed on a fresh clone.

`.gitattributes` normalises text to LF in the repository. On Windows the working
copy is checked out with CRLF, so `config/p1.yaml` was 15,689 bytes locally and
15,359 bytes after a clone — the same 15,359 characters of content either way, and
two different digests. The recorded hash was the Windows one, so anyone cloning the
repository and running `verify_hashes.py` got **FAIL** on the most important check
in the study, for a reason that has nothing to do with the configuration.

Pinning line endings would fix it for this repository and break again the moment
someone's editor or git configuration disagreed. Hashing the canonical form fixes
it everywhere: text artefacts are hashed with CRLF collapsed to LF, so the digest
is a function of the content and nothing else.

Binary artefacts are hashed verbatim. Normalising a CSV would be wrong if it ever
contained a literal CR inside a quoted field, so the committed data files are
written with explicit LF terminators at source and hashed byte for byte.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

# Artefacts whose digest must survive a line-ending conversion. Anything not listed
# is hashed verbatim, which is the safe default.
TEXT_SUFFIXES = {".yaml", ".yml", ".md", ".txt", ".json", ".py", ".cfg", ".toml"}


def sha256_bytes(data: bytes, *, normalise: bool) -> str:
    if normalise:
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def sha256_of(path: str | Path, *, normalise: bool | None = None) -> str:
    """Digest of a file, line-ending independent for text artefacts.

    `normalise` defaults to whether the suffix is a known text format. Pass it
    explicitly when the caller knows better than the extension does.
    """
    path = Path(path)
    if normalise is None:
        normalise = path.suffix.lower() in TEXT_SUFFIXES
    return sha256_bytes(path.read_bytes(), normalise=normalise)
