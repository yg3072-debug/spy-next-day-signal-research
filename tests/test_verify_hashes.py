"""The hash verifier is the check the freeze rests on, so it is itself tested.

This suite exists because the verifier already failed twice in ways that only a
fresh environment revealed: once when a CRLF checkout made the frozen digest
irreproducible, and once when removing the licensed snapshot from the public
repository left the verifier crashing on a glob that assumed the file was there.
Both times the failure was in the thing that was supposed to catch failures.

The distinction the tests enforce is between *verifying bytes* and *checking that
records agree*. When the snapshot is present the verifier must rehash it. When it
is absent the verifier must say `NOT VERIFIED` and must not claim otherwise —
a green check mark that means "two documents agree" is worse than no check mark
at all if a reader takes it for "the data is what it says".
"""

from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "verify_hashes", ROOT / "scripts" / "verify_hashes.py")
verify_hashes = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(verify_hashes)

from src.digest import sha256_bytes, sha256_of  # noqa: E402

SNAPSHOT_NAME = "market_inputs_2026-08-21.csv"
CSV_BODY = b"Date,Open,High,Low,Close\n2020-01-02,100,101,99,100.5\n"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A minimal repository with a coherent set of records and no snapshot.

    Built rather than copied so every digest in it is one this test computed and
    can therefore corrupt deliberately. A fixture that copied the real files
    could only test the passing case.
    """
    snapshot_digest = sha256_bytes(CSV_BODY, normalise=False)

    config = (
        "# minimal frozen configuration\n"
        "data:\n"
        f"  snapshot: data/{SNAPSHOT_NAME}\n"
        f"  snapshot_sha256: {snapshot_digest}\n"
    )
    _write(tmp_path / "config" / "p1.yaml", config)
    config_digest = sha256_of(tmp_path / "config" / "p1.yaml")
    _write(tmp_path / "config" / "p1.sha256", f"{config_digest}  p1.yaml\n")

    _write(tmp_path / "docs" / "research_protocol.md",
           "# Protocol\n\n"
           f"| Configuration SHA-256 | `{config_digest}` |\n"
           f"| Data snapshot SHA-256 | `{snapshot_digest}` |\n")
    for name in ("data_availability.md", "feature_dictionary.md", "freeze_record.md"):
        _write(tmp_path / "docs" / name, f"**SHA-256:** `{snapshot_digest}`\n")
    _write(tmp_path / "results" / "run_manifest.json",
           json.dumps({"snapshot_sha256": snapshot_digest}, indent=2) + "\n")
    return tmp_path


def _add_snapshot(repo: Path, body: bytes = CSV_BODY,
                  manifest_digest: str | None = None) -> None:
    """Place a snapshot CSV and its manifest into the repository."""
    csv_path = repo / "data" / SNAPSHOT_NAME
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.write_bytes(body)
    digest = manifest_digest or sha256_bytes(body, normalise=False)
    (repo / "data" / f"{Path(SNAPSHOT_NAME).stem}.manifest.json").write_text(
        json.dumps({"snapshot_file": SNAPSHOT_NAME, "sha256": digest}, indent=2),
        encoding="utf-8")


# --------------------------------------------------------------------------
# The state the public repository is actually in
# --------------------------------------------------------------------------

def test_absent_snapshot_reports_not_verified_and_succeeds(repo, capsys):
    """No CSV and no manifest is the expected public state, not an error."""
    assert verify_hashes.main(repo) == 0
    out = capsys.readouterr().out
    assert "NOT VERIFIED" in out
    assert "consistency only" in out


def test_absent_snapshot_never_claims_the_snapshot_was_verified(repo, capsys):
    """The wording matters more than the exit code.

    A reader who sees "All recorded hashes match" reasonably concludes the data
    was checked. With the snapshot undistributed that sentence would be false,
    so it must not appear.
    """
    verify_hashes.main(repo)
    out = capsys.readouterr().out
    assert "All recorded hashes match" not in out
    assert "snapshot verified" not in out.lower()


def test_absent_snapshot_still_verifies_the_configuration(repo, capsys):
    """Losing the snapshot must not weaken the configuration check."""
    (repo / "config" / "p1.yaml").write_text("tampered: true\n", encoding="utf-8",
                                             newline="\n")
    assert verify_hashes.main(repo) == 1


# --------------------------------------------------------------------------
# The state a user with a legally obtained copy is in
# --------------------------------------------------------------------------

def test_present_snapshot_is_verified_by_bytes(repo, capsys):
    _add_snapshot(repo)
    assert verify_hashes.main(repo) == 0
    out = capsys.readouterr().out
    assert "recomputed and compared against its manifest" in out
    assert "NOT VERIFIED" not in out
    assert "All recorded hashes match" in out


def test_corrupted_snapshot_content_fails(repo):
    """The manifest is honest, the data is not."""
    _add_snapshot(repo)
    (repo / "data" / SNAPSHOT_NAME).write_bytes(CSV_BODY + b"2020-01-03,1,1,1,1\n")
    assert verify_hashes.main(repo) == 1


def test_snapshot_disagreeing_with_the_frozen_configuration_fails(repo):
    """A self-consistent CSV/manifest pair from the wrong vintage.

    The pair agrees with itself, so checking only the manifest would pass it.
    config/p1.yaml is the independent record that catches it.
    """
    other = b"Date,Open,High,Low,Close\n2020-01-02,7,7,7,7\n"
    _add_snapshot(repo, body=other)
    assert verify_hashes.main(repo) == 1


# --------------------------------------------------------------------------
# Half-present states are broken, not supported
# --------------------------------------------------------------------------

def test_csv_without_manifest_fails(repo):
    (repo / "data").mkdir(parents=True, exist_ok=True)
    (repo / "data" / SNAPSHOT_NAME).write_bytes(CSV_BODY)
    assert verify_hashes.main(repo) == 1


def test_manifest_without_csv_fails(repo):
    (repo / "data").mkdir(parents=True, exist_ok=True)
    (repo / "data" / f"{Path(SNAPSHOT_NAME).stem}.manifest.json").write_text(
        json.dumps({"snapshot_file": SNAPSHOT_NAME, "sha256": "0" * 64}),
        encoding="utf-8")
    assert verify_hashes.main(repo) == 1


# --------------------------------------------------------------------------
# The configuration and the records
# --------------------------------------------------------------------------

def test_wrong_configuration_digest_fails(repo):
    (repo / "config" / "p1.sha256").write_text("f" * 64 + "  p1.yaml\n",
                                               encoding="utf-8", newline="\n")
    assert verify_hashes.main(repo) == 1


@pytest.mark.parametrize("name", [
    "docs/research_protocol.md",
    "docs/data_availability.md",
    "docs/feature_dictionary.md",
    "docs/freeze_record.md",
    "results/run_manifest.json",
])
def test_inconsistent_snapshot_record_fails(repo, name):
    """Every file that writes the identifier down has to write the same one."""
    path = repo / name
    path.write_text(path.read_text(encoding="utf-8").replace(
        sha256_bytes(CSV_BODY, normalise=False), "a" * 64), encoding="utf-8",
        newline="\n")
    assert verify_hashes.main(repo) == 1


@pytest.mark.parametrize("name", [
    "docs/data_availability.md",
    "docs/feature_dictionary.md",
    "docs/freeze_record.md",
    "results/run_manifest.json",
])
def test_missing_record_file_fails(repo, name):
    (repo / name).unlink()
    assert verify_hashes.main(repo) == 1


# --------------------------------------------------------------------------
# The synthetic fixture is not the frozen input
# --------------------------------------------------------------------------

def test_synthetic_fixture_is_never_treated_as_the_snapshot(repo, capsys):
    """A synthetic file in data/ must not satisfy the snapshot requirement.

    If it did, the verifier would report a byte check against invented prices,
    which is the specific confusion `load_snapshot` also refuses to allow.
    """
    (repo / "data").mkdir(parents=True, exist_ok=True)
    (repo / "data" / "market_inputs_synthetic.csv").write_bytes(
        b"Date,Open,High,Low,Close\n2020-01-02,1,1,1,1\n")
    assert verify_hashes.main(repo) == 0
    out = capsys.readouterr().out
    assert "NOT VERIFIED" in out
    assert "synthetic" not in out


def test_real_synthetic_fixture_is_outside_the_snapshot_glob():
    """The committed fixture must not live where the verifier looks."""
    fixture = ROOT / "tests" / "fixtures" / "market_inputs_synthetic.csv"
    if not fixture.exists():
        pytest.skip("synthetic fixture not present in this checkout")
    csvs, _ = verify_hashes._snapshot_files(ROOT)
    assert fixture not in csvs
