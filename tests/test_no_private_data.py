"""No tracked file may carry a machine identifier or a personal address.

This is a public repository. Two things leaked into it before this test existed: a
Windows user directory, captured in a run log from a library warning, and a
personal email address that a script had been putting into a scraper's User-Agent.
Neither failed anything. Both were found by reading, which is not a method.

Identifying a crawler to the site it visits is good practice, so the mechanism
stays and the value comes from `SCRAPER_CONTACT` at run time instead of sitting in
the repository.
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

SKIP_SUFFIXES = {".png", ".pdf", ".jpg", ".jpeg", ".gz", ".zip", ".parquet"}


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
        str(p.relative_to(ROOT)): sorted(set(MACHINE_PATH.findall(t)))[:3]
        for p, t in corpus if MACHINE_PATH.search(t)
    }
    assert not offenders, f"machine paths in tracked files: {offenders}"


def test_no_tracked_file_contains_an_unexpected_email_address(corpus):
    """Only addresses that belong to a cited third party may appear."""
    found: dict[str, set[str]] = {}
    for p, text in corpus:
        addresses = {a for a in EMAIL.findall(text) if a.lower() not in ALLOWED_EMAILS}
        if addresses:
            found[str(p.relative_to(ROOT))] = addresses
    assert not found, (
        f"unexpected email addresses in tracked files: {found}. "
        "A crawler's contact address belongs in SCRAPER_CONTACT at run time, not here."
    )


def test_the_scraper_takes_its_contact_from_the_environment():
    source = (ROOT / "scripts" / "diagnose_empty_posts.py").read_text(encoding="utf-8")
    assert "SCRAPER_CONTACT" in source
    assert not EMAIL.search(source), "the scraper has a hard-coded address again"
