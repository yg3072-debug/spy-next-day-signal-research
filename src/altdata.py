"""Alternative-data features, built from text already mapped onto trading sessions.

Everything here consumes `data/alt/*.csv`, whose rows carry the session their text
belongs to under protocol §9.3. The session mapping is the part that could
introduce look-ahead, and it is done once, in `scripts/freeze_alt_data.py`, with
its own checksum. This module only aggregates.

Sentiment is **Loughran–McDonald** (Loughran and McDonald 2011, *Journal of
Finance*), as §9.4 requires — a citable, versioned, financial-domain word list
rather than a list assembled for this project. A general-purpose lexicon scores
"liability", "tax" and "restructuring" as negative in a financial text where they
are ordinary vocabulary, which is the whole reason LM exists.

The dictionary is **not committed to this repository.** Its licence covers academic
use and requires a separate licence for commercial use, so redistributing it here
would be careless. `scripts/fetch_lexicon.py` retrieves it and verifies the
SHA-256 recorded in `docs/scraping_notes.md`, which is what reproducibility
actually requires.

Topic features are keyword counts, and they are **not** claimed to be a lexicon:
they are declared here, in code, with their word lists visible, and they are
counted rather than scored. Calling them "topic exposure" and LM "sentiment" keeps
the citable part separable from the bespoke part.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

# The dictionary is not committed (see the module docstring), so its location is a
# local matter. It defaults to `vendor/` inside the repository, which .gitignore
# excludes, and `LM_DICTIONARY` overrides that for anyone who keeps it elsewhere.
LEXICON = Path(os.environ.get("LM_DICTIONARY", ROOT / "vendor" / "LM_MasterDictionary.csv"))
LEXICON_SHA256 = "e2d1328682bab7d2187684fb9f5420bb730401c9eefc00daf835edd203f4859d"

LM_CATEGORIES = ["Negative", "Positive", "Uncertainty", "Litigious",
                 "Strong_Modal", "Weak_Modal", "Constraining"]

TOKEN = re.compile(r"[A-Za-z']+")

# Declared here rather than loaded from anywhere, so a reader can see exactly what
# each topic is and object to it. Lower case; matched on whole tokens after the
# same tokenisation the sentiment scoring uses.
TOPICS: dict[str, tuple[str, ...]] = {
    "trade_tariff": ("tariff", "tariffs", "trade", "import", "imports", "export",
                     "exports", "customs", "duty", "duties", "quota"),
    "rates_fed": ("fed", "federal", "reserve", "powell", "rate", "rates",
                  "interest", "hike", "cut", "cuts", "basis", "fomc"),
    "inflation": ("inflation", "inflationary", "prices", "price", "cpi",
                  "deflation", "cost", "costs", "expensive"),
    "geopolitics": ("china", "russia", "ukraine", "iran", "israel", "nato",
                    "war", "sanctions", "military", "border"),
    "energy": ("oil", "gas", "gasoline", "energy", "opec", "barrel", "drilling",
               "pipeline", "crude"),
    "economy_market": ("economy", "economic", "market", "markets", "stock",
                       "stocks", "gdp", "recession", "jobs", "unemployment"),
    "legal_regulation": ("court", "judge", "lawsuit", "indictment", "trial",
                         "regulation", "regulatory", "sec", "doj", "appeal"),
    "election_policy": ("election", "vote", "voters", "campaign", "poll", "polls",
                        "congress", "senate", "house", "bill", "policy"),
}


@dataclass
class AltFeature:
    name: str
    group: str
    formula: str
    rationale: str
    notes: str = ""


REGISTRY: list[AltFeature] = []


def register(**kwargs) -> AltFeature:
    f = AltFeature(**kwargs)
    REGISTRY.append(f)
    return f


# ------------------------------------------------------------------- lexicon

def load_lexicon(path: Path = LEXICON, verify: bool = True) -> dict[str, set[str]]:
    """The LM categories as lower-case word sets.

    A word carries a non-zero value in a category column when it belongs to that
    category; the value is the year it was added, which is metadata rather than a
    weight, so it is read as a flag and not as a score.
    """
    import hashlib
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run scripts/fetch_lexicon.py first — the dictionary "
            "is deliberately not committed to this repository, because its licence "
            "restricts commercial use."
        )
    if verify:
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        if h.hexdigest() != LEXICON_SHA256:
            raise ValueError(
                f"lexicon checksum mismatch: expected {LEXICON_SHA256}, got "
                f"{h.hexdigest()}. A different dictionary version produces different "
                "sentiment and is a different study."
            )
    raw = pd.read_csv(path, usecols=["Word"] + LM_CATEGORIES)
    words = raw.Word.astype(str).str.lower()
    return {cat: set(words[raw[cat] != 0]) for cat in LM_CATEGORIES}


def tokenise(text: str) -> list[str]:
    return TOKEN.findall(str(text).lower())


# ------------------------------------------------------------------ scoring

def score_documents(texts: pd.Series, lexicon: dict[str, set[str]]) -> pd.DataFrame:
    """Per-document word counts by LM category, plus a total token count."""
    rows = []
    for text in texts:
        tokens = tokenise(text)
        row = {"n_tokens": len(tokens)}
        for cat, vocab in lexicon.items():
            row[cat] = sum(1 for t in tokens if t in vocab)
        for topic, keys in TOPICS.items():
            keyset = set(keys)
            row[f"topic_{topic}"] = sum(1 for t in tokens if t in keyset)
        rows.append(row)
    return pd.DataFrame(rows, index=texts.index)


def aggregate_by_session(
    frame: pd.DataFrame, scores: pd.DataFrame, prefix: str, sessions: pd.Index
) -> pd.DataFrame:
    """One row per session, reindexed onto the full session grid.

    Sessions with no documents get zero counts and a neutral tone rather than being
    dropped. That is the honest encoding: "nothing was published" is information
    the model is entitled to see, and dropping those rows would silently make the
    alternative-data sample a non-random subset of the market sample.
    """
    joined = pd.concat([frame[["session"]].reset_index(drop=True),
                        scores.reset_index(drop=True)], axis=1)
    g = joined.groupby("session")

    out = pd.DataFrame(index=sessions)
    out[f"{prefix}_doc_count"] = g.size().reindex(sessions).fillna(0.0)
    register(name=f"{prefix}_doc_count", group=f"alt_{prefix}",
             formula="documents in the session's close batch",
             rationale="Volume of coverage. A quiet session and a loud one are "
                       "different states regardless of what was said.")

    out[f"{prefix}_token_count"] = g.n_tokens.sum().reindex(sessions).fillna(0.0)
    register(name=f"{prefix}_token_count", group=f"alt_{prefix}",
             formula="sum of tokens over the session's documents",
             rationale="Length-weighted coverage; separates many short documents "
                       "from few long ones.")

    totals = {cat: g[cat].sum().reindex(sessions).fillna(0.0) for cat in LM_CATEGORIES}
    pos, neg = totals["Positive"], totals["Negative"]

    # Tone is undefined when nothing sentiment-bearing was published. Zero is the
    # right fill: it is the neutral point of the scale, not a missing value.
    denom = (pos + neg).replace(0.0, np.nan)
    out[f"{prefix}_tone"] = ((pos - neg) / denom).fillna(0.0)
    register(name=f"{prefix}_tone", group=f"alt_{prefix}",
             formula="(positive - negative) / (positive + negative), LM word counts",
             rationale="The standard LM tone measure. Scale-free, so a busy session "
                       "and a quiet one are comparable.",
             notes="Zero when no sentiment-bearing word appeared: that is the "
                   "neutral point of the scale, not a missing observation.")

    tokens = out[f"{prefix}_token_count"].replace(0.0, np.nan)
    for cat in LM_CATEGORIES:
        name = f"{prefix}_{cat.lower()}_rate"
        out[name] = (totals[cat] / tokens).fillna(0.0)
        register(name=name, group=f"alt_{prefix}",
                 formula=f"LM {cat} words / total tokens in the session",
                 rationale=f"Intensity of {cat.lower()} language, normalised by "
                           "length so it does not simply track volume.")

    for topic in TOPICS:
        col = f"topic_{topic}"
        name = f"{prefix}_{topic}_rate"
        out[name] = (g[col].sum().reindex(sessions).fillna(0.0) / tokens).fillna(0.0)
        register(name=name, group=f"alt_{prefix}_topic",
                 formula=f"{topic} keyword hits / total tokens in the session",
                 rationale=f"Attention to {topic.replace('_', '/')}.",
                 notes="A declared keyword count, not a validated lexicon. The word "
                       "list is visible in src/altdata.py and is bespoke to this "
                       "project, unlike the LM categories.")
    return out


ALT = ROOT / "data" / "alt"


def _committed(name: str, sessions: pd.Index) -> pd.DataFrame | None:
    """The session-level aggregate, if it is present.

    The per-document text is not committed -- it is third-party content and
    redistributing it is the publisher's decision, not this project's, exactly as
    with the dictionary. The aggregate the study actually consumes is committed, so
    a fresh clone can reproduce everything downstream of the text without holding
    the text. Rebuilding from raw needs the sources named in docs/scraping_notes.md.
    """
    path = ALT / f"{name}_session_features.csv"
    if not path.exists():
        return None
    frame = pd.read_csv(path, index_col=0, parse_dates=[0])
    frame.index.name = sessions.name
    return frame.reindex(sessions)


def build_news_features(sessions: pd.Index, lexicon=None) -> pd.DataFrame:
    raw = ALT / "news_headlines_sessions.csv"
    if not raw.exists():
        cached = _committed("news", sessions)
        if cached is not None:
            return cached
        raise FileNotFoundError(f"neither {raw} nor the committed aggregate is present")
    frame = pd.read_csv(raw, parse_dates=["session"])
    lexicon = lexicon or load_lexicon()
    scores = score_documents(frame.title, lexicon)
    return aggregate_by_session(frame, scores, "news", sessions)


def build_truth_social_features(sessions: pd.Index, lexicon=None) -> pd.DataFrame:
    """Truth Social, with empty posts counted rather than scored.

    §9.4 insists that "image or repost with no text" and "scrape failure" are
    different things. This archive distinguishes them only partly, and the limit is
    worth stating here rather than in the docs alone. Every empty row was fetched
    successfully -- it carries a status id, both URLs and a timestamp -- so none of
    them is a network failure. But the collector extracts the body by regular
    expression and writes nothing when no pattern matches, so an empty field is
    either a genuinely text-free post or an extraction miss, and the two cannot be
    separated from the archive alone. 26.5% is an upper bound on the first.

    They are excluded from the token and sentiment aggregates -- scoring an empty
    string would drag every tone toward zero in proportion to how many such rows a
    session had -- and carried as their own feature, because posting without text is
    itself a state. That reasoning holds under either cause.
    """
    raw = ALT / "truth_social_sessions.csv"
    if not raw.exists():
        cached = _committed("truth_social", sessions)
        if cached is not None:
            return cached
        raise FileNotFoundError(f"neither {raw} nor the committed aggregate is present")
    frame = pd.read_csv(raw, parse_dates=["session"])
    lexicon = lexicon or load_lexicon()
    empty = frame.is_empty.astype(bool)

    scored = frame.loc[~empty].reset_index(drop=True)
    out = aggregate_by_session(scored, score_documents(scored.text, lexicon),
                               "truth", sessions)

    counts = frame.loc[empty].groupby("session").size().reindex(sessions).fillna(0.0)
    out["truth_empty_post_count"] = counts
    register(name="truth_empty_post_count", group="alt_truth",
             formula="posts in the session's batch with no text at all",
             rationale="An image or a repost carries no text to score but is still "
                       "an act of posting.",
             notes="Held separate from scored posts on purpose. Feeding empty "
                   "strings through the tokeniser would pull every tone estimate "
                   "toward zero in proportion to how many images were posted, "
                   "which would look like sentiment and would not be.")
    return out
