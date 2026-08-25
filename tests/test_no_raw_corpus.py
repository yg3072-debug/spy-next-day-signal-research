"""No tracked file may carry per-record third-party text or its reconstruction keys.

The repository distributes session-level aggregates. It does not distribute the
corpora they were computed from: whether to redistribute third-party content is the
publisher's decision, not this project's, and public accessibility does not make
redistribution so.

That rule was stated in the decision log and then broken three times, each time
silently — the per-post archive, the per-headline file, and a diagnostic that kept
bodies and transcripts. Nothing failed. The files were simply there.

Two things are forbidden and the distinction matters:

**Text.** A column holding document text redistributes the corpus directly.

**Identifiers.** A column of status ids or source URLs redistributes a *key* to it.
Anyone holding the list can refetch every record, so a file that dropped the text
but kept the ids would still hand over the corpus, one request at a time.
"""

from __future__ import annotations

import csv
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# Columns that hold document text, or a key for refetching it.
FORBIDDEN_COLUMNS = {
    "text", "text_raw", "body", "body_text", "headline", "title",
    "transcript", "video_transcript", "card_title", "card_description",
    "archive_url", "original_truthsocial_url", "status_url", "status_id",
}

# Files permitted to use one of those names, each for a stated reason. A file-level
# allowlist rather than a relaxed global rule: `title` is a common column name and
# widening the rule for it would disable the check everywhere it matters.
# Two allowlists, deliberately separate. Exempting a file from one check must not
# exempt it from the other, and a single list would do exactly that.
ALLOWED_COLUMN_NAMES: dict[str, str] = {
    # Nothing yet. A file needing one of those column names for a legitimate reason
    # goes here with the reason, rather than the global rule being widened -- `title`
    # is a common name and relaxing it would disable the check everywhere.
}

ALLOWED_LONG_TEXT = {
    "results/experiment_registry.csv":
        "the notes column is this project's own provenance prose -- why a run was "
        "voided, what a flag means -- written here, not fetched from anywhere. It is "
        "still subject to the column-name check.",
}

MAX_FREE_TEXT_CHARS = 200


def tracked_csvs() -> list[Path]:
    out = subprocess.run(["git", "ls-files", "*.csv"], cwd=ROOT,
                         capture_output=True, text=True).stdout
    return [ROOT / f for f in out.split("\n") if f]


@pytest.mark.parametrize("path", tracked_csvs(), ids=lambda p: str(p.name))
def test_tracked_csv_has_no_document_text_or_identifier_column(path):
    rel = str(path.relative_to(ROOT)).replace("\\", "/")
    if rel in ALLOWED_COLUMN_NAMES:
        pytest.skip(f"{rel}: {ALLOWED_COLUMN_NAMES[rel]}")
    with path.open(encoding="utf-8", errors="replace", newline="") as fh:
        header = next(csv.reader(fh), [])
    offending = {c for c in header if c.strip().lower() in FORBIDDEN_COLUMNS}
    assert not offending, (
        f"{rel} carries {sorted(offending)}. Document text redistributes the corpus; "
        "an identifier column redistributes a key to it. Store aggregates, or "
        "lengths, or counts."
    )


@pytest.mark.parametrize("path", tracked_csvs(), ids=lambda p: str(p.name))
def test_tracked_csv_holds_no_long_free_text(path):
    """A long string in a committed CSV is document text under a different name.

    The column-name rule catches what it knows to look for. This catches the rest,
    by measuring rather than by matching a vocabulary.
    """
    rel = str(path.relative_to(ROOT)).replace("\\", "/")
    if rel in ALLOWED_LONG_TEXT:
        pytest.skip(f"{rel}: {ALLOWED_LONG_TEXT[rel]}")
    longest, where = 0, ""
    with path.open(encoding="utf-8", errors="replace", newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader, [])
        for row_no, row in enumerate(reader):
            if row_no > 5000:
                break
            for i, cell in enumerate(row):
                if len(cell) > longest:
                    longest = len(cell)
                    where = header[i] if i < len(header) else f"column {i}"
    assert longest <= MAX_FREE_TEXT_CHARS, (
        f"{rel} has a {longest}-character cell in '{where}', over the "
        f"{MAX_FREE_TEXT_CHARS} limit. Free text of that length in a committed "
        "result file is document text under another name."
    )


def test_the_forbidden_corpus_paths_are_ignored():
    """The paths that were committed before must now be impossible to commit."""
    for candidate in ("data/alt/truth_social_sessions.csv",
                      "data/alt/news_headlines_sessions.csv",
                      "results/empty_post_diagnosis.csv",
                      "data/raw/anything.csv",
                      "vendor/anything.csv"):
        assert subprocess.run(["git", "check-ignore", "-q", candidate],
                              cwd=ROOT).returncode == 0, f"{candidate} is not ignored"


def test_the_aggregates_the_study_needs_remain_committable():
    """The ignore rules must not be so broad they exclude the deliverables."""
    for candidate in ("data/alt/truth_social_session_features.csv",
                      "data/alt/news_session_features.csv",
                      "results/oos_predictions.csv"):
        assert subprocess.run(["git", "check-ignore", "-q", candidate],
                              cwd=ROOT).returncode != 0, f"{candidate} is ignored"


def test_gitignore_uses_unix_line_endings():
    """A CR at the end of a pattern makes git match a filename that ends in CR.

    The rules silently stop working and nothing reports it. This repository's
    .gitignore had exactly that until it was found by testing the rules rather than
    reading them.
    """
    raw = (ROOT / ".gitignore").read_bytes()
    assert bytes([13, 10]) not in raw, (
        ".gitignore contains CRLF; patterns will not match as written"
    )


DOC_SUFFIXES = {".md", ".txt", ".json", ".yaml", ".yml"}
# A record identifier in the archive's numbering, which is five digits. Requiring
# five rules out four-digit years, which an earlier version matched -- it flagged
# "2024" in a sentence about dates, and a guard that cries wolf gets switched off.
RECORD_ID = re.compile(
    r"\b(?:status[ _]?id[s]?|post[s]? )\D{0,12}(\d{5,6})\b",
    re.IGNORECASE,
)


def tracked_docs() -> list[Path]:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                         text=True).stdout
    return [ROOT / f for f in out.splitlines()
            if f and Path(f).suffix.lower() in DOC_SUFFIXES]


def test_documentation_does_not_quote_record_identifiers():
    """Prose is in scope too.

    The scan started on CSVs, so scraping_notes.md kept a status-id range and two
    identifiers in ordinary sentences -- forbidden data in a permitted file type,
    which is exactly the gap a file-type-scoped rule leaves open.
    """
    offenders = {}
    for path in tracked_docs():
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        if rel in ("tests/test_no_raw_corpus.py",):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        hits = RECORD_ID.findall(text)
        if hits:
            offenders[rel] = sorted(set(hits))[:5]
    assert not offenders, (
        f"documentation quotes record identifiers: {offenders}. Describe the "
        "handling rule; do not reproduce the identifiers."
    )
