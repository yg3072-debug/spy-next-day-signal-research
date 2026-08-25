"""Alternative-data construction: session mapping, aggregation, and no look-ahead.

The mapping is where look-ahead would enter this layer, so it is checked directly
rather than through the features that depend on it.
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from freeze_alt_data import assign_to_bucket, session_closes  # noqa: E402
from src.altdata import (TOPICS, aggregate_by_session, score_documents,  # noqa: E402
                         tokenise)

ALT = ROOT / "data" / "alt"
TZ = "America/New_York"


@pytest.fixture(scope="module")
def closes():
    return session_closes("2024-01-01", "2024-12-31")


def et(text):
    return pd.Timestamp(text, tz=TZ)


def test_a_post_before_the_close_belongs_to_that_session(closes):
    stamps = pd.Series([et("2024-03-11 08:00"), et("2024-03-11 15:59")])
    got = assign_to_bucket(stamps, closes)
    assert (got == pd.Timestamp("2024-03-11")).all()


def test_a_post_exactly_at_the_close_belongs_to_that_session(closes):
    """Right-closed, as §9.3 states. Off by one here moves a whole batch."""
    got = assign_to_bucket(pd.Series([et("2024-03-11 16:00")]), closes)
    assert got.iloc[0] == pd.Timestamp("2024-03-11")


def test_a_post_after_the_close_belongs_to_the_next_session(closes):
    got = assign_to_bucket(pd.Series([et("2024-03-11 16:01")]), closes)
    assert got.iloc[0] == pd.Timestamp("2024-03-12")


def test_weekend_and_holiday_posts_roll_forward_and_are_never_dropped(closes):
    stamps = pd.Series([
        et("2024-03-16 12:00"),   # Saturday
        et("2024-03-17 23:00"),   # Sunday
        et("2024-03-29 10:00"),   # Good Friday, market closed
        et("2024-07-04 11:00"),   # Independence Day
    ])
    got = assign_to_bucket(stamps, closes)
    assert got.isna().sum() == 0
    assert got.iloc[0] == pd.Timestamp("2024-03-18")
    assert got.iloc[1] == pd.Timestamp("2024-03-18")
    assert got.iloc[2] == pd.Timestamp("2024-04-01")
    assert got.iloc[3] == pd.Timestamp("2024-07-05")


def test_a_half_day_closes_at_1300(closes):
    """2024-07-03 closes at 13:00. A 14:00 post is after it, not before."""
    assert closes.loc[pd.Timestamp("2024-07-03")].hour == 13
    before = assign_to_bucket(pd.Series([et("2024-07-03 12:59")]), closes)
    after = assign_to_bucket(pd.Series([et("2024-07-03 14:00")]), closes)
    assert before.iloc[0] == pd.Timestamp("2024-07-03")
    assert after.iloc[0] == pd.Timestamp("2024-07-05")   # the 4th is a holiday


def test_daylight_saving_boundary_is_handled(closes):
    """DST starts 2024-03-10. Both sides must land in the right session."""
    assert closes.loc[pd.Timestamp("2024-03-08")].utcoffset() == dt.timedelta(hours=-5)
    assert closes.loc[pd.Timestamp("2024-03-11")].utcoffset() == dt.timedelta(hours=-4)
    got = assign_to_bucket(pd.Series([et("2024-03-08 15:00"), et("2024-03-11 15:00")]), closes)
    assert list(got) == [pd.Timestamp("2024-03-08"), pd.Timestamp("2024-03-11")]


# ------------------------------------------------------------------- scoring

def test_tokenise_lowercases_and_keeps_only_words():
    assert tokenise("Tariffs: UP 25%!! (again)") == ["tariffs", "up", "again"]


def test_score_counts_lm_categories_and_topics():
    lex = {"Negative": {"loss", "decline"}, "Positive": {"gain"}, "Uncertainty": set(),
           "Litigious": set(), "Strong_Modal": set(), "Weak_Modal": set(),
           "Constraining": set()}
    got = score_documents(pd.Series(["Big loss and decline", "A gain on tariffs"]), lex)
    assert got.Negative.tolist() == [2, 0]
    assert got.Positive.tolist() == [0, 1]
    assert got.topic_trade_tariff.tolist() == [0, 1]


def test_tone_is_neutral_when_nothing_sentiment_bearing_was_published():
    """Zero is the neutral point of the scale, not a missing value."""
    sessions = pd.DatetimeIndex(["2024-03-11", "2024-03-12"])
    frame = pd.DataFrame({"session": [pd.Timestamp("2024-03-11")]})
    scores = pd.DataFrame({"n_tokens": [3], **{c: [0] for c in
                          ["Negative", "Positive", "Uncertainty", "Litigious",
                           "Strong_Modal", "Weak_Modal", "Constraining"]},
                          **{f"topic_{t}": [0] for t in TOPICS}})
    out = aggregate_by_session(frame, scores, "x", sessions)
    assert out.x_tone.tolist() == [0.0, 0.0]
    assert out.x_doc_count.tolist() == [1.0, 0.0]


def test_a_session_with_no_documents_is_kept_with_zero_counts():
    """Dropping them would make the alt sample a non-random subset of the market one."""
    sessions = pd.DatetimeIndex(["2024-03-11", "2024-03-12", "2024-03-13"])
    frame = pd.DataFrame({"session": [pd.Timestamp("2024-03-12")]})
    scores = pd.DataFrame({"n_tokens": [10], **{c: [1] for c in
                          ["Negative", "Positive", "Uncertainty", "Litigious",
                           "Strong_Modal", "Weak_Modal", "Constraining"]},
                          **{f"topic_{t}": [0] for t in TOPICS}})
    out = aggregate_by_session(frame, scores, "x", sessions)
    assert len(out) == 3
    assert out.x_doc_count.tolist() == [0.0, 1.0, 0.0]
    assert out.notna().all().all()


# ------------------------------------------- the corpus, when a user supplies it

@pytest.mark.skipif(not (ALT / "truth_social_sessions.csv").exists(),
                    reason="alternative-data corpus not present; it is not "
                           "distributed with this repository")
def test_supplied_corpus_has_no_text_dated_after_its_session_close():
    """The invariant the whole mapping exists to guarantee.

    Every post must have been published at or before the close of the session it is
    attached to. A single violation is a look-ahead: it would put text into a
    feature row that did not exist when that row's decision was made.
    """
    posts = pd.read_csv(ALT / "truth_social_sessions.csv", parse_dates=["session"])
    published = pd.to_datetime(posts.published_et, utc=True).dt.tz_convert(TZ)
    grid = session_closes("2024-01-01", "2026-12-31")
    close_of = posts.session.map(grid)
    late = published > close_of
    assert late.sum() == 0, f"{late.sum()} posts are dated after their session's close"


@pytest.mark.skipif(not (ALT / "news_headlines_sessions.csv").exists(),
                    reason="alternative-data snapshot not built")
def test_committed_headlines_are_never_attached_to_an_earlier_session():
    heads = pd.read_csv(ALT / "news_headlines_sessions.csv",
                        parse_dates=["date_stated", "session"])
    assert (heads.session >= heads.date_stated).all()
