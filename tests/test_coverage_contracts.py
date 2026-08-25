"""Contracts that would have caught the two gaps found only by hand-checking.

Both were silent. `config/p1.yaml` promised `calibration_diagnostics.csv` in its
`outputs` list and the run never wrote it; §7.2 registered E21 and the exploratory
overlays never included it. Neither failed anything — they were simply absent, and
absence is what no assertion was watching for.

These two tests watch for it.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CONFIG = yaml.safe_load((ROOT / "config" / "p1.yaml").read_bytes())
PROTOCOL = (ROOT / "docs" / "research_protocol.md").read_text(encoding="utf-8")
REGISTRY = ROOT / "results" / "experiment_registry.csv"

EXPECTED_COLUMNS = {
    "oos_predictions.csv": {"date", "step", "model", "mu_hat", "position"},
    "selection_log.csv": {"step", "date", "chosen_id", "n_candidates"},
    "feature_stability.csv": {"feature", "steps_selected"},
    "candidate_diagnostics.csv": {"step", "id", "score", "chosen"},
    "calibration_diagnostics.csv": {"step", "inner_fold", "family", "inner_oos_brier",
                                    "inner_oos_brier_skill_vs_train_base_rate"},
    "trade_ledger.csv": set(),
}


@pytest.mark.parametrize("declared", CONFIG["outputs"])
def test_every_declared_output_exists_and_is_not_empty(declared):
    """A configuration that promises a file and does not write it is a silent gap.

    calibration_diagnostics.csv was promised and absent through the whole first
    execution. Nothing failed; it simply was not there.
    """
    path = ROOT / declared
    assert path.exists(), (
        f"config/p1.yaml declares {declared} in outputs but it does not exist. "
        "Either the run must write it or the configuration must stop promising it."
    )
    assert path.stat().st_size > 0, f"{declared} exists but is empty"


@pytest.mark.parametrize("declared", [o for o in CONFIG["outputs"] if o.endswith(".csv")])
def test_declared_csv_outputs_carry_their_expected_columns(declared):
    name = Path(declared).name
    expected = EXPECTED_COLUMNS.get(name)
    if not expected:
        pytest.skip(f"no column contract declared for {name}")
    frame = pd.read_csv(ROOT / declared, nrows=5)
    columns = set(frame.columns) | ({frame.index.name} if frame.index.name else set())
    missing = expected - columns
    assert not missing, f"{name} is missing {sorted(missing)}; has {sorted(columns)}"


ROW = re.compile(r"^\|\s*\*{0,2}\s*(P1|E\d+b?(?:\s*[–—-]\s*E\d+b?)?)\s*\*{0,2}\s*\|")


def protocol_trial_ids() -> set[str]:
    """Every P/E identifier the protocol's trial registry declares.

    The table writes ranges: "E1-E4" means four trials, not one. Expanding them is
    the whole point -- a range is exactly where an identifier disappears without
    anyone noticing, which is what happened to E21.
    """
    ids: set[str] = set()
    for line in PROTOCOL.splitlines():
        m = ROW.match(line)
        if not m:
            continue
        token = m.group(1)
        if token == "P1":
            ids.add("P1")
            continue
        parts = re.findall(r"E(\d+)(b?)", token)
        if len(parts) == 2 and not parts[0][1] and not parts[1][1]:
            ids.update(f"E{n}" for n in range(int(parts[0][0]), int(parts[1][0]) + 1))
        else:
            ids.update(f"E{n}{suffix}" for n, suffix in parts)
    return ids


@pytest.mark.skipif(not REGISTRY.exists(), reason="no registry yet")
def test_every_protocol_trial_id_has_a_registry_status():
    """A pre-registered identifier must be accounted for, one way or another.

    E21 was registered in §7.2, omitted when the overlays were written, and its
    absence was declared nowhere. Running it, failing it, or declaring it not run
    are all acceptable. Silence is not.
    """
    declared = protocol_trial_ids()
    assert len(declared) > 20, f"parsed only {sorted(declared)} from the protocol"

    rows = pd.read_csv(REGISTRY, dtype=str).fillna("")
    accounted = set(rows.family_id) | set(rows.run_id)
    accounted |= {r.split("-")[0] for r in rows.run_id}

    missing = sorted(declared - accounted, key=lambda s: (len(s), s))
    assert not missing, (
        f"pre-registered but absent from results/experiment_registry.csv: {missing}. "
        "Every declared trial needs a row saying it completed, failed, or was not run."
    )


@pytest.mark.skipif(not REGISTRY.exists(), reason="no registry yet")
def test_registry_distinguishes_the_two_preregistration_claims():
    """"Pre-registered" is not one property, and compressing it overstates the weak case."""
    rows = pd.read_csv(REGISTRY, dtype=str).fillna("")
    for column in ("specified_before_p1", "specified_before_own_results",
                   "cannot_modify_p1_headline"):
        assert column in rows.columns, f"the registry has no {column} column"
    research = rows[~rows.run_type.isin(["engineering_smoke", ""])]
    assert (research.cannot_modify_p1_headline == "true").any()
    # The close-to-close rule postdates P1 and must not claim otherwise.
    c2c = rows[rows.family_id.isin(["E22", "E23", "E24"])]
    if len(c2c):
        assert (c2c.specified_before_p1 == "false").all(), (
            "close-to-close rows claim pre-P1 specification; their position rule "
            "was fixed in an addendum written after P1."
        )


@pytest.mark.skipif(not (ROOT / "results" / "reproduction_equivalence.json").exists(),
                    reason="no reproduction has been verified")
def test_the_reproduction_run_is_recorded_as_equivalent():
    report = json.loads((ROOT / "results" / "reproduction_equivalence.json")
                        .read_text(encoding="utf-8"))
    assert report["verdict"] == "bit_identical", report["disposition"]
    assert report["same_config_snapshot_and_packages"]
    for field in ("position", "mu_hat", "net", "p_long"):
        assert report["fields"][field]["identical"], f"{field} differs between runs"


@pytest.mark.skipif(not REGISTRY.exists(), reason="no registry yet")
def test_documents_quote_the_registrys_actual_path_count():
    """Hand-copied counts drift. This one already did.

    The reports quoted 45 paths across 35 families while the registry held 46 and
    36, because E21 landed after the sentences were written. Nothing failed -- the
    numbers were simply stale, which is the same silent failure as the two gaps
    this file exists for.
    """
    rows = pd.read_csv(REGISTRY, dtype=str).fillna("")
    counted = rows[(rows.performance_metrics_computed == "true")
                   & (rows.excluded_from_trial_budget != "true")]
    paths, families = len(counted), counted.family_id.nunique()

    quoted = re.compile(r"(\d+) realised\s+strategy paths (?:across|from) (\d+)")
    seen = 0
    for name in ("README.md", "reports/p1_confirmatory_result.md",
                 "reports/exploratory_results.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        for p, f in quoted.findall(text.replace("\n", " ")):
            seen += 1
            assert int(p) == paths, (
                f"{name} says {p} realised paths; the registry has {paths}"
            )
            assert int(f) == families, (
                f"{name} says {f} families; the registry has {families}"
            )
    assert seen >= 3, f"expected the count to be quoted in each report, found {seen}"


# ---------------------------------------------------------------------------
# Data-availability honesty
# ---------------------------------------------------------------------------

# Phrases that assert the licensed market snapshot ships with this repository.
# It does not, and it will not: the prices come from a vendor whose terms forbid
# redistribution. A document that says otherwise sends a reader looking for a file
# that is not there and misstates what the repository can prove about its own
# inputs. The workflow comment "The snapshot is committed, so nothing here touches
# the network" survived the removal by weeks and is what this guard exists to stop
# recurring.
FORBIDDEN_AVAILABILITY_CLAIMS = (
    r"snapshot is committed",
    r"committed snapshot",
    r"snapshot,? (?:is |which is )?(?:committed|included|shipped|bundled)",
    r"the snapshot ships",
)

# "frozen study snapshot" is legitimate history -- the study did run on a real
# snapshot and saying so is a fact, not a distortion. It is admissible only where
# the same document also states the file is not distributed, so a reader is never
# left with the identifier and no notice of its absence.
HISTORICAL_PHRASE = re.compile(r"frozen (?:study )?snapshot", re.I)
# \s+ rather than a literal space: these documents wrap, and "not\ndistributed"
# is the same statement as "not distributed". Requiring one space made the guard
# report a compliant file as an offender.
NOT_DISTRIBUTED = re.compile(
    r"not\s+(?:distributed|redistributed|published|committed|present|included)"
    r"|NOT\s+DISTRIBUTED|does\s+not\s+(?:ship|include)", re.I)

PUBLIC_TEXT_SUFFIXES = (".md", ".yml", ".yaml", ".py")
SKIP_DIRS = {".git", "_archive", "node_modules", "__pycache__"}

# This file states the forbidden phrases in order to forbid them, and asserts on
# one of them to prove the guard fires. Excluding it is not a loophole in the
# rule: it is the one file whose job is to contain the string.
SELF = Path(__file__).name


def _public_text_files():
    # Skip directories are matched against the path RELATIVE to the repository
    # root. Matching absolute parts made this scan zero files whenever the
    # checkout happened to sit under a directory that shared one of these names,
    # which is exactly how a guard ends up passing while watching nothing.
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path.suffix not in PUBLIC_TEXT_SUFFIXES:
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        if path.name == SELF:
            continue
        yield path


def test_the_public_text_scan_is_not_empty():
    """The scan above is only meaningful if it reaches the documents."""
    files = list(_public_text_files())
    assert len(files) > 20, f"expected the repository's documents, found {len(files)}"
    names = {p.name for p in files}
    assert "README.md" in names


@pytest.mark.parametrize("pattern", FORBIDDEN_AVAILABILITY_CLAIMS)
def test_no_document_claims_the_market_snapshot_is_distributed(pattern):
    regex = re.compile(pattern, re.I)
    offenders = []
    for path in _public_text_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in regex.finditer(text):
            line = text[:match.start()].count("\n") + 1
            offenders.append(f"{path.relative_to(ROOT)}:{line}  {match.group(0)!r}")
    assert not offenders, (
        "these claim the licensed market snapshot is distributed with this "
        "repository:\n  " + "\n  ".join(offenders))


def test_the_guard_would_catch_the_claim_it_was_written_for(tmp_path):
    """A guard that matches nothing is worse than no guard.

    An earlier regex in this suite contained a `\b` that Python read as a
    backspace, so it silently matched nothing and passed for months. This asserts
    the patterns actually fire on the exact sentence that was in the workflow.
    """
    offending = ("# The snapshot is committed, so nothing here touches the "
                 "network.")
    assert any(re.search(p, offending, re.I) for p in FORBIDDEN_AVAILABILITY_CLAIMS)


def test_historical_snapshot_references_say_it_is_not_distributed():
    """`frozen snapshot` may be written, but not without the caveat nearby."""
    offenders = []
    for path in _public_text_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        if not HISTORICAL_PHRASE.search(text):
            continue
        if not NOT_DISTRIBUTED.search(text):
            offenders.append(str(path.relative_to(ROOT)))
    assert not offenders, (
        "these refer to the frozen snapshot without stating anywhere that it is "
        "not distributed:\n  " + "\n  ".join(offenders))
