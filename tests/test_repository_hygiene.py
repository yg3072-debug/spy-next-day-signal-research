"""Repository hygiene: no tracked file may carry environment-specific or personal data.

A research repository is read and re-run by people on other machines. Anything that
only makes sense on the machine that produced it -- an absolute user directory, a
contact address baked into a script -- is noise at best and a disclosure at worst, and
neither kind fails loudly on its own. These checks make them fail.

The rules enforced here:

* no absolute user directory from any platform, in any tracked file
* no email address beyond those a cited third party publishes for itself
* no credentials, private keys or `.env` files
* a crawler identifies itself from the environment at run time, not from a value
  committed to the repository

Identifying a crawler to the site it visits is good practice, so the mechanism stays;
what does not stay is the value. `scripts/collect_truth_social.py` and
`scripts/diagnose_empty_posts.py` read `SCRAPER_CONTACT` when they run.

Third-party document text and vendor market data are governed separately, in
`tests/test_no_raw_corpus.py`.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BACKSLASH = chr(92)

# A user directory in any interpreter or file path, on either platform.
MACHINE_PATH = re.compile(
    r"[A-Za-z]:" + re.escape(BACKSLASH) + r"Users" + re.escape(BACKSLASH)
    + r"|/home/[a-z][a-z0-9_-]*/|/Users/[a-z][a-z0-9_-]*/",
    re.IGNORECASE,
)

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

# Addresses that belong in the repository. The dictionary's licence names its own
# contact, and citing it is the point of recording the licence at all.
ALLOWED_EMAILS = {
    "loughranmcdonald@gmail.com",
    "noreply@github.com",
}

# RFC 2606 reserves these domains so documentation can show an address that can
# never belong to anyone. A usage example needs one; exempting the reserved domains
# is narrower and more durable than exempting whichever file happens to contain it.
RESERVED_DOMAINS = ("example.com", "example.org", "example.net", "invalid", "test")

SKIP_SUFFIXES = {".png", ".pdf", ".jpg", ".jpeg", ".gz", ".zip", ".parquet"}

# Documents that state these rules have to be able to name what they forbid. An
# explicit, reasoned allowlist -- not a relaxed pattern, which would stop the check
# working everywhere it matters.
POLICY_DOCUMENTS = {
    "DATA_POLICY.md": "states the redistribution rules and cites the dictionary "
                      "licence's own contact address",
    "docs/errata.md": "records what was corrected, which requires describing it",
    "tests/test_repository_hygiene.py": "the rules themselves",
    "tests/test_no_raw_corpus.py": "the rules themselves",
}


def tracked_files() -> list[Path]:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                         text=True).stdout
    return [ROOT / f for f in out.split("\n") if f]


def readable_text(path: Path) -> str | None:
    if path.suffix.lower() in SKIP_SUFFIXES or not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8", errors="strict")
    except (UnicodeDecodeError, OSError):
        return None


@pytest.fixture(scope="module")
def corpus():
    return [(p, t) for p in tracked_files() if (t := readable_text(p)) is not None]


def test_no_tracked_file_contains_a_machine_user_directory(corpus):
    """A local interpreter path says whose laptop built the artefact and nothing else.

    It reached the repository through a library warning captured in a run log, which
    is exactly the route nobody inspects.
    """
    offenders = {
        rel: sorted(set(MACHINE_PATH.findall(t)))[:3]
        for p, t in corpus
        if (rel := str(p.relative_to(ROOT)).replace("\\", "/")) not in POLICY_DOCUMENTS
        and MACHINE_PATH.search(t)
    }
    assert not offenders, f"machine paths in tracked files: {offenders}"


def test_no_tracked_file_contains_an_unexpected_email_address(corpus):
    """Only addresses that belong to a cited third party may appear."""
    found: dict[str, set[str]] = {}
    for p, text in corpus:
        rel = str(p.relative_to(ROOT)).replace("\\", "/")
        if rel in POLICY_DOCUMENTS:
            continue
        addresses = {
            a for a in EMAIL.findall(text)
            if a.lower() not in ALLOWED_EMAILS
            and not a.lower().endswith(RESERVED_DOMAINS)
        }
        if addresses:
            found[rel] = addresses
    assert not found, (
        f"unexpected email addresses in tracked files: {found}. "
        "A crawler's contact address belongs in SCRAPER_CONTACT at run time, not here."
    )


def test_the_scraper_takes_its_contact_from_the_environment():
    source = (ROOT / "scripts" / "diagnose_empty_posts.py").read_text(encoding="utf-8")
    assert "SCRAPER_CONTACT" in source
    assert not EMAIL.search(source), "the scraper has a hard-coded address again"


def test_no_tracked_file_redistributes_scraped_document_text(corpus):
    """The diagnostic sample must store lengths, not words.

    `results/empty_post_diagnosis.csv` originally kept the post bodies and video
    transcripts it fetched -- 49 bodies and 151 transcripts, up to 4,101 characters
    -- which redistributes exactly the third-party content the rest of this project
    withholds. Whether a body exists is answerable from a count, so the words were
    never needed.
    """
    path = ROOT / "results" / "empty_post_diagnosis.csv"
    if not path.exists():
        pytest.skip("no diagnostic sample present")
    header = path.read_text(encoding="utf-8").splitlines()[0].split(",")
    for column in ("body", "card_title", "card_description", "video_transcript"):
        assert column not in header, (
            f"{column} holds fetched text; store {column}_chars instead"
        )
    assert "body_chars" in header
