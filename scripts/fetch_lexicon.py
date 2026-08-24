"""Retrieve the Loughran–McDonald master dictionary and verify it.

The dictionary is **not committed to this repository**, deliberately. Its terms
make it free for academic research and require a separate licence for commercial
use, so redistributing it inside an MIT-licensed repository would misrepresent what
a user is allowed to do with it.

Reproducibility does not require redistribution. It requires that a third party can
obtain the same bytes and check that they are the same bytes, which is what the
recorded SHA-256 is for. A different dictionary version scores differently and is a
different study, so a mismatch is an error rather than a warning.

    python scripts/fetch_lexicon.py            # download, verify, report
    python scripts/fetch_lexicon.py --verify   # check an existing copy only
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

VERSION = "Loughran-McDonald_MasterDictionary_1993-2025.csv, updated March 2026"
PAGE = "https://sraf.nd.edu/loughranmcdonald-master-dictionary/"
DRIVE_ID = "1iq2RUf8qGFEAk1g8wQntP3habOnR3fXF"
URL = f"https://drive.usercontent.google.com/download?id={DRIVE_ID}&export=download&confirm=t"
SHA256 = "e2d1328682bab7d2187684fb9f5420bb730401c9eefc00daf835edd203f4859d"
DEFAULT = Path(r"D:\SPY Prediction\_vendor\LM_MasterDictionary.csv")

LICENCE = (
    "Free for use in academic research. Commercial applications require a licence "
    "from the authors (loughranmcdonald@gmail.com). Cite: Loughran, T. and "
    "McDonald, B. (2011), 'When Is a Liability Not a Liability? Textual Analysis, "
    "Dictionaries, and 10-Ks', Journal of Finance 66(1), 35-65."
)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--path", type=Path, default=DEFAULT)
    ap.add_argument("--verify", action="store_true", help="do not download")
    args = ap.parse_args()

    if not args.path.exists():
        if args.verify:
            print(f"{args.path} not present", file=sys.stderr)
            return 1
        import urllib.request
        args.path.parent.mkdir(parents=True, exist_ok=True)
        print(f"downloading {VERSION}\n  from {PAGE}")
        urllib.request.urlretrieve(URL, args.path)

    actual = digest(args.path)
    ok = actual == SHA256
    size_mb = args.path.stat().st_size / 1e6
    print(f"{'ok  ' if ok else 'FAIL'} {args.path.name}  {size_mb:.1f} MB  {actual}")
    if not ok:
        print(f"\nexpected {SHA256}\nA different dictionary version produces different "
              "sentiment scores and is a different study.", file=sys.stderr)
        return 1
    print(f"\n{VERSION}\n{LICENCE}")
    print("\nNot redistributed through this repository; see docs/scraping_notes.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
