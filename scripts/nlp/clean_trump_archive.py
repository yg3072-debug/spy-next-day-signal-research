"""Normalize a raw Trump Truth archive export for downstream text analysis."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd
from ftfy import fix_text

TEXT_COLUMNS = ("created_at_raw", "text_raw")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_csv", type=Path)
    parser.add_argument("output_csv", type=Path)
    return parser.parse_args()


def normalize_text(value: object) -> str | None:
    if pd.isna(value):
        return None
    text = fix_text(str(value))
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(
        r"\s+Donald J\. Trump @realDonaldTrump · .*? Original Post(?: Share:.*)?$",
        "",
        text,
    ).strip()
    return text or None


def parse_archive_timestamp(series: pd.Series) -> pd.Series:
    cleaned = series.astype("string").str.replace(r"\s+(EDT|EST)$", "", regex=True)
    parsed = pd.to_datetime(
        cleaned,
        format="%A, %B %d, %Y, %I:%M %p",
        errors="coerce",
    )
    return parsed.dt.tz_localize(
        "America/New_York",
        ambiguous="NaT",
        nonexistent="shift_forward",
    )


def main() -> None:
    args = parse_args()
    data = pd.read_csv(args.input_csv, dtype={"status_id": "string"}, low_memory=False)
    required = {"status_id", "archive_url", "created_at_raw", "text_raw"}
    missing = sorted(required - set(data.columns))
    if missing:
        raise ValueError(f"Missing archive columns: {missing}")

    for column in TEXT_COLUMNS:
        data[column] = data[column].map(normalize_text)
    data["text"] = data["text_raw"]
    created_at = parse_archive_timestamp(data["created_at_raw"])
    data["created_at"] = created_at.map(
        lambda value: value.isoformat() if pd.notna(value) else None
    )
    data["date"] = created_at.dt.strftime("%Y-%m-%d")
    data = data.drop_duplicates(subset=["status_id", "archive_url"], keep="first")
    data = data.sort_values(
        ["created_at", "status_id"], na_position="last"
    ).reset_index(drop=True)

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(args.output_csv, index=False, encoding="utf-8")
    usable = int(data["text"].notna().sum())
    print(
        f"saved {len(data):,} rows ({usable:,} with usable text) to {args.output_csv}"
    )


if __name__ == "__main__":
    main()
