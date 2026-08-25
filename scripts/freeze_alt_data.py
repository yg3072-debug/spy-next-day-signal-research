"""Freeze the alternative-data sources onto trading sessions, once, with a checksum.

Protocol §9.3 fixes the mapping:

    bucket_t = ( kappa_{t-1}, kappa_t ]      kappa_t = the official close of session t

A post at 08:00 on Monday belongs to Monday's close batch and is acted on at
Tuesday's open. Weekend and holiday posts roll into the next complete close batch
and are never dropped. Boundaries are left-open and right-closed, the timezone is
America/New_York with daylight saving handled, and the timestamp used is the
original publication time.

Two things here are load-bearing and easy to get wrong.

**The timezone label is in the raw string, not in the parsed column.** The archive
carries `created_at_raw` ending in "EDT" or "EST" and a separate naive
`created_at`. Reading the naive column as UTC shifts every post four or five hours
earlier -- and 882 posts sit in the 16:00 hour, right against the close, so that
error silently moves posts into the previous session's bucket. The raw field is
parsed with its own offset and the two are reconciled here rather than trusted.

**Headlines carry a date and no time.** They cannot be bucketed by timestamp at
all. §9.4 fixes the conservative reading: a headline dated D is treated as fully
known only after D's close, so it lands in bucket D and is acted on at D+1's open.
That is an assumption about availability, it is stated rather than inferred from
the data, and it costs intraday timeliness on purpose.

    python scripts/freeze_alt_data.py            # build and write
    python scripts/freeze_alt_data.py --verify   # check the committed checksums
"""

from __future__ import annotations

import argparse
import hashlib
import os
import json
import re
import sys
from datetime import datetime, time, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pandas_market_calendars as mcal

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "data" / "alt"
# The per-document text is third-party content and is not committed, so where it
# lives is a local matter. `ALT_DATA_SOURCE` points at the directory holding the two
# raw files; `data/raw/` inside the repository is the default and is gitignored.
# docs/scraping_notes.md names both sources and their checksums.
SOURCE = Path(os.environ.get("ALT_DATA_SOURCE", ROOT / "data" / "raw"))

HEADLINES = SOURCE / "sp500_headlines_2008_2024.csv"
POSTS = SOURCE / "trump_archive_full_cleaned.csv"

LF = chr(10)
TZ = "America/New_York"
RAW_FORMAT = "%A, %B %d, %Y, %I:%M %p"
OFFSETS = {"EDT": -4, "EST": -5}


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def session_closes(start: str, end: str) -> pd.Series:
    """Official NYSE close, per session, tz-aware. Half days close at 13:00."""
    cal = mcal.get_calendar("NYSE")
    sched = cal.schedule(start_date=start, end_date=end)
    closes = sched["market_close"].dt.tz_convert(TZ)
    closes.index = pd.DatetimeIndex(sched.index).normalize()
    return closes


def session_opens(start: str, end: str) -> pd.Series:
    cal = mcal.get_calendar("NYSE")
    sched = cal.schedule(start_date=start, end_date=end)
    opens = sched["market_open"].dt.tz_convert(TZ)
    opens.index = pd.DatetimeIndex(sched.index).normalize()
    return opens


def assign_to_bucket(stamps: pd.Series, closes: pd.Series) -> pd.Series:
    """The session whose close batch a timestamp falls into.

    `searchsorted(side="left")` gives the first close at or after the stamp, which
    is the right-closed boundary §9.3 asks for: a post exactly at the close belongs
    to that session, not the next one. A weekend post finds the next session's close
    on its own, with no special case, because the closes are the only grid.
    """
    order = closes.sort_values()
    # Compare as UTC nanoseconds. Mixing a tz-aware index with a tz-aware series
    # through numpy silently produces object arrays that do not compare, and the
    # whole point of this function is that the comparison is exact.
    grid = order.dt.tz_convert("UTC").astype("int64").to_numpy()
    when = stamps.dt.tz_convert("UTC").astype("int64").to_numpy()
    idx = np.searchsorted(grid, when, side="left")
    out = pd.Series(pd.NaT, index=stamps.index, dtype="datetime64[ns]")
    inside = idx < len(order)
    out.loc[inside] = order.index.to_numpy()[idx[inside]]
    return out


# ------------------------------------------------------------------ truth social

def load_posts(closes: pd.Series) -> tuple[pd.DataFrame, dict]:
    raw = pd.read_csv(POSTS)
    audit: dict = {"rows_in_file": len(raw)}

    audit["exact_duplicate_rows"] = int(raw.duplicated().sum())
    audit["duplicate_status_ids"] = int(raw.status_id.duplicated().sum())
    raw = raw.drop_duplicates(subset="status_id", keep="first")

    label = raw.created_at_raw.astype(str).str.extract(r"\b([A-Z]{2,4})$")[0]
    audit["timezone_labels"] = {str(k): int(v) for k, v in
                                label.value_counts(dropna=False).items()}
    wall = pd.to_datetime(
        raw.created_at_raw.astype(str).str.replace(r"\s+[A-Z]{2,4}$", "", regex=True),
        format=RAW_FORMAT, errors="coerce",
    )
    audit["unparseable_timestamps"] = int(wall.isna().sum())

    # Rows whose label is missing are localised through the zone's own DST rule
    # rather than guessed at. They are counted, because an unlabelled timestamp is
    # a different kind of object from a labelled one.
    missing = label.isna()
    audit["timezone_label_missing"] = int(missing.sum())
    offset = label.map(OFFSETS)
    utc = pd.Series(pd.NaT, index=raw.index, dtype="datetime64[ns, UTC]")
    have = offset.notna() & wall.notna()
    utc.loc[have] = (wall[have] - pd.to_timedelta(offset[have], unit="h")).dt.tz_localize("UTC")
    if (~have & wall.notna()).any():
        inferred = wall[~have & wall.notna()].dt.tz_localize(
            TZ, ambiguous=True, nonexistent="shift_forward").dt.tz_convert("UTC")
        utc.loc[inferred.index] = inferred
    et = utc.dt.tz_convert(TZ)

    # The naive column read as UTC is what a careless pipeline would use. The size
    # of that error is recorded so the choice is visible rather than implicit.
    careless = pd.to_datetime(raw.created_at, errors="coerce").dt.tz_localize(
        "UTC").dt.tz_convert(TZ)
    shift = (et - careless).dt.total_seconds().div(3600)
    audit["hours_of_error_if_naive_column_used"] = {
        str(k): int(v) for k, v in shift.value_counts().items()}

    text = raw.text.fillna("").astype(str).str.strip()
    empty = (text == "") | (text.str.lower() == "nan")
    audit["empty_text"] = int(empty.sum())
    audit["empty_text_share"] = round(float(empty.mean()), 4)

    frame = pd.DataFrame({
        "status_id": raw.status_id.to_numpy(),
        "text": text.to_numpy(),
        "is_empty": empty.to_numpy(),
    })
    frame["published_et"] = et.reset_index(drop=True)
    frame["session"] = assign_to_bucket(frame.published_et, closes)

    audit["after_last_close"] = int(frame.session.isna().sum())
    frame = frame.dropna(subset=["session"]).reset_index(drop=True)

    same_day = (frame.published_et.dt.normalize().dt.tz_localize(None) == frame.session)
    audit["rolled_into_a_later_session"] = int((~same_day).sum())
    audit["rolled_share"] = round(float((~same_day).mean()), 4)

    # What the pre-open window would have bought, stated because §9.3 forgoes it.
    #
    # The condition is "published before the open of the session it is assigned to",
    # which is the general form of the claim. It is much broader than it first looks:
    # a post at 18:00 on Monday falls in Tuesday's close batch under §9.3 and is
    # therefore acted on at Wednesday's open, while a morning pipeline would have
    # acted on it at Tuesday's open. Evenings are most of this feed, so most posts
    # qualify.
    #
    # A narrower proxy -- posts timestamped before 09:30 on any calendar day -- gives
    # 18.75%, and that is the figure the frozen protocol quotes. It is recorded
    # alongside so the discrepancy is traceable rather than mysterious. See the
    # erratum in the protocol's version record.
    opens = session_opens("2007-12-01", "2026-08-21")
    open_of = frame.session.map(opens)
    earlier = frame.published_et < open_of
    audit["tradable_one_session_earlier_with_a_morning_pipeline"] = int(earlier.sum())
    audit["share_tradable_one_session_earlier_with_a_morning_pipeline"] = round(
        float(earlier.mean()), 4)
    before_0930 = frame.published_et.dt.time < time(9, 30)
    audit["proxy_posts_before_0930_any_calendar_day"] = int(before_0930.sum())
    audit["proxy_share_before_0930_any_calendar_day"] = round(float(before_0930.mean()), 4)
    return frame, audit


# ----------------------------------------------------------------------- news

def load_headlines(closes: pd.Series) -> tuple[pd.DataFrame, dict]:
    raw = pd.read_csv(HEADLINES)
    audit: dict = {"rows_in_file": len(raw)}
    audit["exact_duplicate_rows"] = int(raw.duplicated().sum())
    raw = raw.drop_duplicates()
    audit["rows_after_dedup"] = len(raw)

    dates = pd.to_datetime(raw.Date, errors="coerce")
    audit["unparseable_dates"] = int(dates.isna().sum())
    title = raw.Title.fillna("").astype(str).str.strip()
    audit["empty_titles"] = int((title == "").sum())

    # No times in the file. §9.4 fixes the conservative reading: a headline dated D
    # is treated as fully known only after D's close. Where D is not a session --
    # a weekend or a holiday -- it rolls forward to the next close batch, exactly
    # as a post would.
    grid = closes.index
    idx = np.searchsorted(grid.to_numpy(), dates.dt.normalize().to_numpy(), side="left")
    session = pd.Series(pd.NaT, index=raw.index, dtype="datetime64[ns]")
    inside = idx < len(grid)
    session.loc[inside] = grid.to_numpy()[idx[inside]]

    frame = pd.DataFrame({"date_stated": dates.values, "title": title.values,
                          "session": session.values}).dropna(subset=["session"])
    audit["rolled_into_a_later_session"] = int((frame.date_stated != frame.session).sum())
    audit["assumption"] = (
        "The file carries dates without times. A headline dated D is treated as "
        "fully known only after D's close and acted on at D+1's open. This is an "
        "availability assumption that cannot be verified from the data, and it is "
        "conservative: a headline published before D's open is treated as if it "
        "arrived at D's close."
    )
    return frame, audit


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()

    DEST.mkdir(parents=True, exist_ok=True)
    manifest_path = DEST / "alt_data.manifest.json"

    if args.verify:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        failures = []
        # The per-document text is third-party content and is not committed, so a
        # fresh clone has the aggregates and not the sources. Verifying what is
        # absent by design would fail every clone; verifying only what is present
        # would let a missing aggregate pass silently. Both are reported.
        recorded_all = {**manifest.get("derived_features", {}), **manifest["sha256"]}
        for name, recorded in recorded_all.items():
            path = DEST / name
            if not path.exists():
                if name in manifest.get("derived_features", {}):
                    print(f"FAIL {name}  committed aggregate is missing")
                    failures.append(name)
                else:
                    print(f"skip {name}  per-document source, not redistributed")
                continue
            actual = sha256_of(path)
            ok = actual == recorded
            print(f"{'ok  ' if ok else 'FAIL'} {name}  {actual}")
            if not ok:
                failures.append(name)
        if failures:
            print("\nchecksum mismatch: " + ", ".join(failures), file=sys.stderr)
            return 1
        print("\nAlternative-data checksums match.")
        return 0

    closes = session_closes("2007-12-01", "2026-08-21")
    print(f"NYSE sessions on the spine: {len(closes)}  "
          f"{closes.index.min().date()} to {closes.index.max().date()}")

    posts, post_audit = load_posts(closes)
    heads, head_audit = load_headlines(closes)

    posts_out = DEST / "truth_social_sessions.csv"
    heads_out = DEST / "news_headlines_sessions.csv"
    # Explicit LF, as freeze_market_data.py does. Written CRLF on Windows and
    # checked out LF elsewhere, a file's recorded digest fails on every other
    # platform -- which is what CI caught on the aggregates below.
    posts.to_csv(posts_out, index=False, lineterminator=LF)
    heads.to_csv(heads_out, index=False, lineterminator=LF)

    # The aggregates are built here too, so their checksums are part of the same
    # manifest the build writes. Adding them afterwards from another script meant a
    # rebuild silently dropped them, and --verify then checked nothing on a clone
    # while still reporting success.
    sys.path.insert(0, str(ROOT))
    from src.altdata import build_news_features, build_truth_social_features, load_lexicon
    derived = {}
    try:
        lexicon = load_lexicon()
        sessions = pd.read_csv(sorted((ROOT / "data").glob("market_inputs_*.csv"))[-1],
                               index_col="Date", parse_dates=True).index
        for label, frame in (("news", build_news_features(sessions, lexicon)),
                             ("truth_social", build_truth_social_features(sessions, lexicon))):
            out = DEST / f"{label}_session_features.csv"
            frame.to_csv(out, float_format="%.10g", lineterminator=LF)
            derived[out.name] = sha256_of(out)
        print(f"derived features  {', '.join(derived)}")
    except FileNotFoundError as exc:
        print(f"derived features  skipped: {exc}")

    def relative(path: Path) -> str:
        """Paths in the manifest are relative to the repository, never absolute.

        An absolute path records whose machine built the file, which is neither
        useful to a reader nor appropriate in a public repository.
        """
        try:
            return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
        except ValueError:
            return path.name

    manifest = {
        "built_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "session_mapping": "bucket_t = (close_{t-1}, close_t], America/New_York, DST handled",
        "boundary": "left-open, right-closed",
        "calendar": "NYSE via pandas_market_calendars",
        "sources": {
            "truth_social": {"path": relative(POSTS), "sha256": sha256_of(POSTS)},
            "news_headlines": {"path": relative(HEADLINES), "sha256": sha256_of(HEADLINES)},
        },
        "derived_features": derived,
        "redistribution": (
            "The per-document text files are NOT committed. They are third-party "
            "content whose redistribution is the publisher's decision, not this "
            "project's, and the same reasoning applies to them as to the "
            "Loughran-McDonald dictionary. What is committed is the session-level "
            "aggregate the study consumes, plus the source checksums above, so a "
            "reader who obtains the same raw files can confirm they have the same "
            "bytes. Set ALT_DATA_SOURCE to point at them and rerun this script."
        ),
        "truth_social": post_audit,
        "news_headlines": head_audit,
        "sha256": {posts_out.name: sha256_of(posts_out), heads_out.name: sha256_of(heads_out)},
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"\ntruth social  {len(posts):,} posts -> {posts.session.nunique():,} sessions")
    for k, v in post_audit.items():
        print(f"    {k:<52} {v}")
    print(f"\nnews          {len(heads):,} headlines -> {heads.session.nunique():,} sessions")
    for k, v in head_audit.items():
        if k != "assumption":
            print(f"    {k:<52} {v}")
    print(f"\nwritten to {DEST.relative_to(ROOT)}/ with checksums")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
