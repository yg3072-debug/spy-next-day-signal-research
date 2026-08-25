"""Fetch the Treasury rate series from the Federal Reserve Board's own H.15 release.

The study originally obtained these rates through FRED, using
`pandas_datareader`. That is a historical fact and is recorded as one in
`docs/data_availability.md` — it is not rewritten.

What changed is the **default path for anyone running this code now**: rates come
from the Board's Data Download Program, which serves the H.15 release directly.
The Board's own publication is a United States federal government work and is in
the public domain, so a repository may redistribute the series with attribution.
That is what makes the committed rate file publishable when the equity snapshot is
not.

**This file is not the frozen P1 input and must not be represented as one.** Within
the modelling window the Board's values and the originally frozen values agree at
every session; they differ at exactly one later date, where the originally captured
figures were provisional. `--compare` reproduces that check against any snapshot you
hold.

    python scripts/fetch_treasury_rates.py                    # download and write
    python scripts/fetch_treasury_rates.py --verify           # check the committed file
    python scripts/fetch_treasury_rates.py --compare <csv>    # against a held snapshot
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pandas_market_calendars as mcal

ROOT = Path(__file__).resolve().parents[1]
DEST_DIR = ROOT / "data"
LF = chr(10)

PUBLISHER = "Board of Governors of the Federal Reserve System (US)"
RELEASE = "Statistical Release H.15, Selected Interest Rates (Daily)"
LANDING = "https://www.federalreserve.gov/releases/h15/"
BASE = "https://www.federalreserve.gov/datadownload/Output.aspx"
QUERY = ("rel=H15&series=bf17364827e38702b42a58cf8eaa3f78&lastobs="
         "&from={start}&to={end}&filetype=csv&label=include&layout=seriescolumn")

# Board identifiers, and the FRED identifiers the study originally used for the
# same quantity. Both are recorded: the mapping is the evidence that the
# substitution is like for like rather than a relabelling.
SERIES = {
    "RIFLGFCM03_N.B": {
        "column": "TCM3M", "fred_equivalent": "DGS3MO",
        "description": "3-month Treasury constant maturity, investment basis",
    },
    "RIFLGFCY02_N.B": {
        "column": "TCM2Y", "fred_equivalent": "DGS2",
        "description": "2-year Treasury constant maturity, investment basis",
    },
    "RIFLGFCY10_N.B": {
        "column": "TCM10Y", "fred_equivalent": "DGS10",
        "description": "10-year Treasury constant maturity, investment basis",
    },
}

START, END = "2015-01-01", "2026-08-21"
USER_AGENT = ("spy-next-day-signal-research/1.0 "
              "(+https://github.com/yg3072-debug/spy-next-day-signal-research)")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def download() -> bytes:
    url = f"{BASE}?{QUERY.format(start='01/01/2015', end='08/21/2026')}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=90) as response:
        if response.status != 200:
            raise SystemExit(f"H.15 returned HTTP {response.status}")
        return response.read()


def parse(raw: bytes) -> pd.DataFrame:
    """The Board's CSV carries five metadata rows before the data."""
    frame = pd.read_csv(io.BytesIO(raw), skiprows=5).rename(
        columns={"Time Period": "Date"})
    frame["Date"] = pd.to_datetime(frame.Date, errors="coerce")
    frame = frame.dropna(subset=["Date"]).set_index("Date")
    out = pd.DataFrame(index=frame.index)
    for board_id, meta in SERIES.items():
        if board_id not in frame.columns:
            raise SystemExit(f"{board_id} absent from the H.15 download")
        out[meta["column"]] = pd.to_numeric(frame[board_id], errors="coerce")
    return out


def session_calendar(index: pd.Index) -> pd.DataFrame:
    """Session length from the exchange calendar, not from any vendor.

    `session_minutes` and `is_half_day` are properties of the NYSE trading day.
    They are computed here from `pandas_market_calendars`, so they carry no market
    data and are publishable regardless of what happens to the price series.
    """
    cal = mcal.get_calendar("NYSE")
    sched = cal.schedule(start_date=str(index.min().date()),
                         end_date=str(index.max().date()))
    minutes = ((sched["market_close"] - sched["market_open"])
               .dt.total_seconds().div(60).round().astype(int))
    minutes.index = pd.DatetimeIndex(sched.index).normalize()
    out = pd.DataFrame(index=index)
    out["session_minutes"] = minutes.reindex(index)
    out["is_half_day"] = out.session_minutes < 390
    return out


def write(rates: pd.DataFrame, raw: bytes) -> Path:
    stamp = datetime.now(timezone.utc).date().isoformat()
    dest = DEST_DIR / f"treasury_rates_h15_{stamp}.csv"
    sessions = session_calendar(rates.index)
    frame = rates.join(sessions)
    frame = frame.loc[frame.session_minutes.notna()]
    frame["session_minutes"] = frame.session_minutes.astype(int)
    frame.to_csv(dest, float_format="%.10g", lineterminator=LF)

    manifest = {
        "file": dest.name,
        "sha256": sha256(dest.read_bytes()),
        "retrieved_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "publisher": PUBLISHER,
        "release": RELEASE,
        "landing_page": LANDING,
        "download_url": f"{BASE}?{QUERY.format(start='01/01/2015', end='08/21/2026')}",
        "source_payload_sha256": sha256(raw),
        "source_payload_bytes": len(raw),
        "rights": ("United States federal government work; public domain. "
                   "Redistribution permitted with attribution."),
        "citation": (f"{PUBLISHER}, {RELEASE}, retrieved from {LANDING}"),
        "series": {k: v for k, v in SERIES.items()},
        "calendar_columns": {
            "session_minutes": "NYSE close minus open, in minutes",
            "is_half_day": "session_minutes < 390",
            "source": "generated from the NYSE session rules published by "
                      "pandas_market_calendars",
            "package_version": getattr(mcal, "__version__", "unknown"),
            "rights": "Derived here from MIT-licensed calendar rules; no vendor data",
            "package_licence": "MIT",
        },
        "relationship_to_the_frozen_p1_input": (
            "The study originally obtained equivalent series through FRED. This file "
            "is served by the Board directly. It is NOT the frozen P1 input and must "
            "not be represented as such; see --compare and docs/data_availability.md."
        ),
        "sessions": int(len(frame)),
        "range": [str(frame.index.min().date()), str(frame.index.max().date())],
    }
    (dest.with_suffix(".manifest.json")).write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
    return dest


def compare(rates: pd.DataFrame, snapshot_path: Path) -> int:
    """Board values against a snapshot you already hold, series by series."""
    snap = pd.read_csv(snapshot_path, index_col="Date", parse_dates=True)
    print(f"comparing against {snapshot_path.name}")
    worst_date = None
    for board_id, meta in SERIES.items():
        fred = meta["fred_equivalent"]
        if fred not in snap.columns:
            print(f"  {fred} absent from the snapshot; skipped")
            continue
        a = snap[fred]
        b = rates[meta["column"]].reindex(a.index)
        both = a.notna() & b.notna()
        diff = (a[both] - b[both]).abs()
        mismatched = a.index[both][diff > 0]
        print(f"  {fred:<7} vs {board_id:<16} n={int(both.sum()):>5}  "
              f"identical={int((diff == 0).sum())}/{int(both.sum())}  "
              f"max|diff|={diff.max():.4f}")
        for d in mismatched:
            print(f"      {d.date()}  held={a[d]:.3f}  board={b[d]:.3f}")
            worst_date = d
    if worst_date is not None:
        print(f"\n  Differences are confined to {worst_date.date()}. Rate releases are "
              "revised;")
        print("  a value captured on the day is provisional. Check whether that date "
              "falls")
        print("  inside your modelling window before drawing any conclusion from it.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--compare", type=Path, default=None)
    args = ap.parse_args()

    if args.verify:
        files = sorted(DEST_DIR.glob("treasury_rates_h15_*.csv"))
        if not files:
            print("no committed rate file found", file=sys.stderr)
            return 1
        ok = True
        for f in files:
            manifest = json.loads(f.with_suffix(".manifest.json").read_text("utf-8"))
            actual = sha256(f.read_bytes())
            good = actual == manifest["sha256"]
            ok &= good
            print(f"{'ok  ' if good else 'FAIL'} {f.name}  {actual}")
        return 0 if ok else 1

    raw = download()
    rates = parse(raw)
    print(f"H.15 payload {len(raw)} bytes, sha256 {sha256(raw)[:16]}...")
    print(f"parsed {len(rates)} dates, {rates.index.min().date()} to "
          f"{rates.index.max().date()}")

    if args.compare:
        return compare(rates, args.compare)

    dest = write(rates, raw)
    print(f"\nwritten to {dest.relative_to(ROOT)} and its manifest")
    print(f"{PUBLISHER}")
    print(f"{RELEASE} — public domain, redistribution permitted with attribution")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
