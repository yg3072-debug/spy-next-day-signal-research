"""Freeze the market data snapshot used by the study.

Every input series is downloaded once, aligned to the NYSE trading calendar, and
written to a single CSV alongside a manifest recording provenance and a SHA-256
checksum. All downstream work reads the frozen CSV, never the network, so any
published number can be traced to an exact input.

Design notes
------------
Calendar spine.  Sessions come from the NYSE calendar rather than from the
intersection of the downloaded series. Taking an intersection silently drops
sessions whenever any one series is missing a day, and reports nothing.

Forward fill only.  Macro series that do not trade on every NYSE session are
carried forward from the last observed value. Backward filling would move future
information into the past. Every filled cell is counted and reported.

Adjustment.  Prices are split- and dividend-adjusted. Note that the primary
target, log(Close / Open) within a single session, is invariant to any
multiplicative adjustment factor, since the factor cancels in the ratio.

Usage
-----
    python scripts/freeze_market_data.py                 # write the snapshot
    python scripts/freeze_market_data.py --verify        # check an existing one
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pandas_market_calendars as mcal
import yfinance as yf
from pandas_datareader import data as pdr

START_DATE = "2015-01-01"

# ticker -> (output column name, source field)
YAHOO_SINGLE = {
    "^VIX": ("VIX", "Close"),
    "DX-Y.NYB": ("DXY", "Close"),
    "^TNX": ("TNX", "Close"),
    # Brent is the primary oil factor. Front-month WTI settled at -$37.63 on
    # 2020-04-20 during the Cushing storage crisis, which leaves any log-ratio
    # feature undefined. Brent is seaborne, never went negative, and its daily
    # log returns correlate 0.894 with WTI's over this sample. WTI is retained
    # alongside it so the choice can be revisited without re-downloading.
    "BZ=F": ("OIL", "Close"),
    "CL=F": ("OIL_WTI", "Close"),
    "QQQ": ("QQQ_Close", "Close"),
    "IWM": ("IWM_Close", "Close"),
    "DIA": ("DIA_Close", "Close"),
}
# DGS3MO is the cash / risk-free proxy. It is a constant-maturity bond-equivalent
# yield (investment basis, actual/365), so it can be compounded directly. DTB3 is
# the secondary-market bill rate on a 360-day DISCOUNT basis and needs converting
# before use; it is carried only as a sensitivity check on the cash series.
FRED_SERIES = ["DGS3MO", "DTB3", "DGS2", "DGS10"]

# Series that genuinely trade on a different calendar from NYSE equities and may
# therefore need carrying forward. SPY itself must be complete on every session.
FILL_LIMIT = 5

SNAPSHOT_DIR = Path(__file__).resolve().parents[1] / "data"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def nyse_sessions(start: str, end: str) -> pd.DataFrame:
    """One row per NYSE session, with its length and an early-close flag.

    Session length is carried explicitly because an early close is a real trading
    state, not a data defect: the same round-trip cost has to be recovered over a
    shorter session. Returns are never rescaled by it.
    """
    cal = mcal.get_calendar("NYSE")
    sched = cal.schedule(start_date=start, end_date=end)
    open_et = sched["market_open"].dt.tz_convert("America/New_York")
    close_et = sched["market_close"].dt.tz_convert("America/New_York")
    minutes = ((close_et - open_et).dt.total_seconds() / 60).to_numpy()
    sessions = pd.DatetimeIndex(sched.index).tz_localize(None).normalize()
    return pd.DataFrame(
        {"session_minutes": minutes.astype(int), "is_half_day": (minutes < 360).astype(int)},
        index=sessions,
    )


def fetch_yahoo(ticker: str, start: str, end: str) -> pd.DataFrame:
    """Download one ticker. One at a time keeps the columns flat."""
    frame = yf.Ticker(ticker).history(
        start=start, end=end, auto_adjust=True, actions=False
    )
    if frame.empty:
        raise RuntimeError(f"Yahoo returned no rows for {ticker}")
    frame.index = pd.DatetimeIndex(frame.index).tz_localize(None).normalize()
    return frame[~frame.index.duplicated(keep="last")].sort_index()


def build_snapshot(start: str, end: str) -> tuple[pd.DataFrame, dict]:
    spine = nyse_sessions(start, end)
    out = pd.DataFrame(index=spine.index)
    out.index.name = "Date"
    coverage: dict[str, dict] = {}

    spy = fetch_yahoo("SPY", start, end)

    # The calendar knows about sessions that have not traded yet. Cap the spine at
    # the last session SPY actually has, then require no interior gaps.
    last_traded = spy.index.max()
    trailing = int((out.index > last_traded).sum())
    out = out.loc[out.index <= last_traded]
    spine = spine.loc[spine.index <= last_traded]

    for field in ("Open", "High", "Low", "Close", "Volume"):
        out[field] = spy[field].reindex(out.index)
    missing_spy = int(out["Close"].isna().sum())
    if missing_spy:
        gaps = out.index[out["Close"].isna()]
        raise RuntimeError(
            f"SPY is missing {missing_spy} NYSE sessions inside the traded range, "
            f"first {gaps[0].date()}. The calendar spine and the price history "
            "disagree; investigate before freezing."
        )
    coverage["SPY"] = {"native_rows": int(len(spy)), "filled": 0}

    for ticker, (col, field) in YAHOO_SINGLE.items():
        raw = fetch_yahoo(ticker, start, end)[field]
        aligned = raw.reindex(out.index)
        n_missing = int(aligned.isna().sum())
        filled = aligned.ffill(limit=FILL_LIMIT)
        still_missing = int(filled.isna().sum())
        out[col] = filled
        coverage[ticker] = {
            "column": col,
            "native_rows": int(raw.notna().sum()),
            "missing_on_nyse_sessions": n_missing,
            "forward_filled": n_missing - still_missing,
            "unresolved": still_missing,
        }

    yields = pdr.DataReader(FRED_SERIES, "fred", start, end)
    yields.index = pd.DatetimeIndex(yields.index).tz_localize(None).normalize()
    for col in FRED_SERIES:
        aligned = yields[col].reindex(out.index)
        n_missing = int(aligned.isna().sum())
        filled = aligned.ffill(limit=FILL_LIMIT)
        out[col] = filled
        coverage[col] = {
            "column": col,
            "native_rows": int(yields[col].notna().sum()),
            "missing_on_nyse_sessions": n_missing,
            "forward_filled": n_missing - int(filled.isna().sum()),
            "unresolved": int(filled.isna().sum()),
        }

    out["session_minutes"] = spine["session_minutes"]
    out["is_half_day"] = spine["is_half_day"]

    # Leading rows can still be NaN where a series starts after START_DATE or a
    # gap exceeded FILL_LIMIT. Trim the leading block, then require completeness.
    first_complete = out.dropna().index.min()
    trimmed = int((out.index < first_complete).sum())
    out = out.loc[out.index >= first_complete]
    if out.isna().any().any():
        bad = out.columns[out.isna().any()].tolist()
        raise RuntimeError(f"Unresolved gaps remain in {bad} after the leading trim.")

    meta = {
        "coverage": coverage,
        "leading_rows_trimmed": trimmed,
        "trailing_untraded_sessions_dropped": trailing,
        "fill_limit_sessions": FILL_LIMIT,
    }
    return out, meta


def write_snapshot(frame: pd.DataFrame, meta: dict, outdir: Path) -> tuple[Path, Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    stamp = frame.index.max().date().isoformat()
    csv_path = outdir / f"market_inputs_{stamp}.csv"
    frame.to_csv(csv_path, float_format="%.10g", lineterminator="\n")

    manifest = {
        "snapshot_file": csv_path.name,
        "sha256": sha256_of(csv_path),
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "requested_window": {"start_inclusive": START_DATE, "end": stamp},
        "first_session": frame.index.min().date().isoformat(),
        "last_session": frame.index.max().date().isoformat(),
        "sessions": int(len(frame)),
        "half_day_sessions": int(frame["is_half_day"].sum()),
        "columns": list(frame.columns),
        "calendar": "NYSE via pandas_market_calendars",
        "adjustment": "yfinance auto_adjust=True (split and dividend adjusted OHLC; Volume unadjusted)",
        "sources": {
            "Yahoo Finance": ["SPY"] + list(YAHOO_SINGLE),
            "FRED": FRED_SERIES,
        },
        "alignment": {
            "spine": "NYSE session calendar, not the intersection of series",
            "gap_policy": f"forward fill only, limit {FILL_LIMIT} sessions; never backward fill",
        },
        "package_versions": {
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "yfinance": yf.__version__,
            "pandas_market_calendars": mcal.__version__,
        },
        **meta,
    }
    manifest_path = outdir / f"market_inputs_{stamp}.manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return csv_path, manifest_path


def verify(outdir: Path) -> int:
    manifests = sorted(outdir.glob("market_inputs_*.manifest.json"))
    if not manifests:
        print("No manifest found.")
        return 1
    ok = True
    for mpath in manifests:
        manifest = json.loads(mpath.read_text(encoding="utf-8"))
        csv_path = outdir / manifest["snapshot_file"]
        actual = sha256_of(csv_path)
        match = actual == manifest["sha256"]
        ok &= match
        print(f"{csv_path.name}: {'OK' if match else 'CHECKSUM MISMATCH'}")
        if not match:
            print(f"  expected {manifest['sha256']}\n  actual   {actual}")
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="check existing snapshots and exit")
    parser.add_argument("--end", default=None, help="end date (exclusive), defaults to today")
    args = parser.parse_args()

    if args.verify:
        return verify(SNAPSHOT_DIR)

    end = args.end or (pd.Timestamp.today().normalize() + pd.Timedelta(days=1)).date().isoformat()
    frame, meta = build_snapshot(START_DATE, end)
    csv_path, manifest_path = write_snapshot(frame, meta, SNAPSHOT_DIR)

    print(f"Sessions      {len(frame)}  ({frame.index.min().date()} to {frame.index.max().date()})")
    print(f"Half days     {int(frame['is_half_day'].sum())}")
    print(f"Leading trim  {meta['leading_rows_trimmed']} sessions")
    print(f"Snapshot      {csv_path}")
    print(f"SHA-256       {sha256_of(csv_path)}")
    print(f"Manifest      {manifest_path}")
    print("\nPer-series coverage on NYSE sessions:")
    for name, info in meta["coverage"].items():
        if name == "SPY":
            print(f"  {name:<10} complete, {info['native_rows']} native rows")
            continue
        print(
            f"  {name:<10} -> {info['column']:<10} native {info['native_rows']:>5}"
            f"   missing {info['missing_on_nyse_sessions']:>4}"
            f"   ffilled {info['forward_filled']:>4}"
            f"   unresolved {info['unresolved']:>3}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
