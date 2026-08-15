"""Download, validate, and freeze the market inputs used by the notebook.

The canonical repository notebook reads the committed CSV snapshot by default.
Run this module explicitly only when intentionally refreshing that snapshot.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote as url_quote, urlencode
from urllib.request import Request, urlopen

import pandas as pd
import yfinance as yf
from pandas_datareader import data as pdr


START_DATE = "2022-01-01"
END_DATE = "2026-05-06"  # yfinance end is exclusive; last observation is 2026-05-05.
EXPECTED_FIRST_DATE = "2022-01-03"
EXPECTED_LAST_DATE = "2026-05-05"
EXPECTED_ROWS = 1088

REQUIRED_COLUMNS = [
    "Open",
    "High",
    "Low",
    "Price",
    "Volume",
    "VIX",
    "DXY",
    "TNX",
    "OIL",
    "DGS2",
    "DGS10",
    "QQQ_Price",
    "IWM_Price",
    "DIA_Price",
]


def _download_one(ticker: str, fields: list[str]) -> pd.DataFrame:
    # The chart endpoint returns the same quote and adjusted-close fields that
    # yfinance uses, while avoiding cookie/crumb rate-limit failures in CI.
    period1 = int(pd.Timestamp(START_DATE, tz="UTC").timestamp())
    period2 = int(pd.Timestamp(END_DATE, tz="UTC").timestamp())
    query = urlencode(
        {
            "period1": period1,
            "period2": period2,
            "interval": "1d",
            "events": "div,splits",
        }
    )
    encoded_ticker = url_quote(ticker, safe="")
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded_ticker}?{query}"
    chart = None
    last_error = None
    for attempt in range(3):
        try:
            request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(request, timeout=30) as response:
                payload = json.load(response)
            result = payload.get("chart", {}).get("result")
            candidate = result[0] if result else None
            if candidate and candidate.get("timestamp"):
                chart = candidate
                break
            last_error = payload.get("chart", {}).get("error") or "missing timestamp"
        except Exception as exc:  # Retry transient network/provider responses.
            last_error = repr(exc)
        time.sleep(attempt + 1)

    if chart is None:
        raise RuntimeError(f"No Yahoo Finance data returned for {ticker}: {last_error}")
    timestamps = chart["timestamp"]
    quote = chart["indicators"]["quote"][0]
    adjusted = chart["indicators"].get("adjclose", [{}])[0].get("adjclose", quote["close"])
    timezone_name = chart.get("meta", {}).get("exchangeTimezoneName", "America/New_York")

    index = (
        pd.to_datetime(timestamps, unit="s", utc=True)
        .tz_convert(timezone_name)
        .normalize()
        .tz_localize(None)
    )
    raw_close = pd.Series(quote["close"], index=index, dtype="float64")
    adj_close = pd.Series(adjusted, index=index, dtype="float64")
    adjustment = adj_close / raw_close

    frame = pd.DataFrame(index=index)
    frame["Open"] = pd.Series(quote["open"], index=index, dtype="float64") * adjustment
    frame["High"] = pd.Series(quote["high"], index=index, dtype="float64") * adjustment
    frame["Low"] = pd.Series(quote["low"], index=index, dtype="float64") * adjustment
    frame["Close"] = adj_close
    frame["Volume"] = pd.Series(quote["volume"], index=index, dtype="float64")
    frame = frame.dropna(how="all")

    missing = sorted(set(fields).difference(frame.columns))
    if missing:
        raise RuntimeError(f"{ticker} is missing columns: {missing}")

    result = frame[fields].copy()
    result.index = pd.to_datetime(result.index).tz_localize(None)
    result.index.name = "Date"
    return result


def validate_snapshot(frame: pd.DataFrame, strict: bool = True) -> None:
    """Fail fast when a snapshot does not match the published research window."""
    missing = sorted(set(REQUIRED_COLUMNS).difference(frame.columns))
    if missing:
        raise ValueError(f"Snapshot is missing columns: {missing}")
    if frame.index.has_duplicates:
        raise ValueError("Snapshot contains duplicate dates.")
    if not frame.index.is_monotonic_increasing:
        raise ValueError("Snapshot dates must be sorted ascending.")
    if frame[REQUIRED_COLUMNS].isna().any().any():
        bad = frame[REQUIRED_COLUMNS].columns[
            frame[REQUIRED_COLUMNS].isna().any()
        ].tolist()
        raise ValueError(f"Snapshot contains missing values in: {bad}")

    if strict:
        actual = (len(frame), frame.index.min().date().isoformat(), frame.index.max().date().isoformat())
        expected = (EXPECTED_ROWS, EXPECTED_FIRST_DATE, EXPECTED_LAST_DATE)
        if actual != expected:
            raise ValueError(
                "Snapshot window changed. "
                f"Expected rows/first/last={expected}, received={actual}."
            )


def snapshot_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_market_inputs() -> pd.DataFrame:
    """Recreate the exact pre-feature-engineering input table."""
    spy = _download_one("SPY", ["Open", "High", "Low", "Close", "Volume"])
    spy = spy.rename(columns={"Close": "Price"})

    macro_specs = {
        "VIX": ("^VIX", "Close"),
        "DXY": ("DX-Y.NYB", "Close"),
        "TNX": ("^TNX", "Close"),
        "OIL": ("CL=F", "Close"),
    }
    macro_frames = []
    for output_name, (ticker, field) in macro_specs.items():
        macro_frames.append(_download_one(ticker, [field]).rename(columns={field: output_name}))

    # Match the original research logic: an inner join across the five core sources.
    inputs = spy.join(macro_frames, how="inner").sort_index()

    # FRED observations are aligned to SPY dates and carried forward across holidays.
    yields = pdr.DataReader(["DGS2", "DGS10"], "fred", START_DATE, END_DATE)
    yields.index = pd.to_datetime(yields.index).tz_localize(None)
    yields = yields.reindex(inputs.index).ffill()
    inputs = inputs.join(yields[["DGS2", "DGS10"]], how="left")

    # Cross-market ETFs are aligned to the core input calendar, as in the notebook.
    for name in ["QQQ", "IWM", "DIA"]:
        close = _download_one(name, ["Close"]).rename(columns={"Close": f"{name}_Price"})
        inputs[f"{name}_Price"] = close.reindex(inputs.index).ffill()[f"{name}_Price"]

    inputs = inputs[REQUIRED_COLUMNS].copy()
    validate_snapshot(inputs, strict=True)
    return inputs


def build_snapshot(output_path: str | Path, manifest_path: str | Path | None = None) -> pd.DataFrame:
    output_path = Path(output_path)
    manifest_path = Path(manifest_path) if manifest_path else output_path.with_suffix(".manifest.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    inputs = download_market_inputs()
    inputs.to_csv(output_path, index_label="Date", float_format="%.10f")

    manifest = {
        "snapshot_file": output_path.name,
        "sha256": snapshot_sha256(output_path),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_window": {"start_inclusive": START_DATE, "end_exclusive": END_DATE},
        "first_observation": EXPECTED_FIRST_DATE,
        "last_observation": EXPECTED_LAST_DATE,
        "rows": len(inputs),
        "columns": list(inputs.columns),
        "sources": {
            "Yahoo Finance": ["SPY", "^VIX", "DX-Y.NYB", "^TNX", "CL=F", "QQQ", "IWM", "DIA"],
            "FRED": ["DGS2", "DGS10"],
        },
        "yfinance_version": yf.__version__,
        "yahoo_download_method": "v8 chart endpoint with auto-adjust equivalent",
        "pandas_version": pd.__version__,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return inputs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default="data/market_inputs_2026-05-05.csv",
        help="Destination CSV path.",
    )
    parser.add_argument(
        "--manifest",
        default="data/market_inputs_2026-05-05.manifest.json",
        help="Destination manifest path.",
    )
    args = parser.parse_args()
    frame = build_snapshot(args.output, args.manifest)
    print(
        f"Saved {len(frame)} rows from {frame.index.min().date()} "
        f"through {frame.index.max().date()} to {args.output}."
    )


if __name__ == "__main__":
    main()
