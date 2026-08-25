"""Generate a schema-identical synthetic market snapshot for the test suite.

The real snapshot is derived from a vendor whose terms restrict redistribution, so
it is not published with this repository. Most of the test suite does not need the
real data: a test that the feature matrix contains no look-ahead, or that an active
session pays a full round trip, is a statement about the code and holds on any input
with the right shape.

This produces that input. It is **obviously synthetic** — a seeded random walk on
round numbers — so nobody can mistake it for market data, and it is small enough to
commit.

**It is never a substitute for the real snapshot in a research run.** `load_snapshot`
refuses to fall back to it: a procedure that silently ran on invented prices and
reported a Sharpe ratio would be far worse than one that failed to start.

    python scripts/make_synthetic_snapshot.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pandas_market_calendars as mcal

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "tests" / "fixtures" / "market_inputs_synthetic.csv"
SEED = 20260825
START, END = "2015-01-02", "2026-08-21"

LF = chr(10)


def main() -> int:
    cal = mcal.get_calendar("NYSE")
    sched = cal.schedule(start_date=START, end_date=END)
    index = pd.DatetimeIndex(sched.index).normalize()
    index.name = "Date"
    n = len(index)

    rng = np.random.default_rng(SEED)
    # A random walk that starts at exactly 100 and moves in visibly round steps.
    # Real prices do not look like this, which is the point.
    # Six decimals, not two. Rounding a ~100 price to a cent leaves only 1e-4 of
    # relative precision, and a test that rescales the whole history and demands
    # bit-identical ratios then fails on the rounding rather than on the feature.
    close = 100.0 * np.exp(np.cumsum(rng.normal(0.0002, 0.01, n)))
    intraday = rng.normal(0.0, 0.004, n)
    open_ = close / (1.0 + intraday)
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.003, n)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.003, n)))

    # Session length from the calendar itself. An earlier version compared a
    # UTC hour against 15 and therefore found no early closes at all, which meant
    # the fixture silently failed to cover the case it was built to cover.
    minutes = ((sched["market_close"] - sched["market_open"])
               .dt.total_seconds().div(60).round().astype(int).to_numpy())

    frame = pd.DataFrame(index=index)
    frame["Open"], frame["High"] = open_, high
    frame["Low"], frame["Close"] = low, close
    frame["Volume"] = rng.integers(4e7, 1.2e8, n)
    for name, base, scale in (("VIX", 18.0, 4.0), ("DXY", 98.0, 3.0),
                              ("TNX", 3.0, 0.4), ("OIL", 75.0, 8.0),
                              ("OIL_WTI", 71.0, 8.0)):
        frame[name] = np.round(base + np.cumsum(rng.normal(0, scale / 60, n)), 3)
    for name, base in (("QQQ_Close", 300.0), ("IWM_Close", 190.0), ("DIA_Close", 340.0)):
        frame[name] = np.round(base * np.exp(np.cumsum(rng.normal(0.0002, 0.01, n))), 2)
    # A rate path that visits both a near-zero regime and a high one, because the
    # trading band's dependence on the short rate is only testable if the fixture
    # actually contains both. A narrow path silently made that test vacuous.
    cycle = 2.6 + 2.6 * np.sin(np.linspace(0, 2.4 * np.pi, n))
    for name, offset in (("DGS3MO", 0.0), ("DTB3", -0.1),
                         ("DGS2", 0.3), ("DGS10", 0.6)):
        frame[name] = np.round(
            np.clip(cycle + offset + np.cumsum(rng.normal(0, 0.004, n)), 0.0, None), 2)
    frame["session_minutes"] = minutes
    frame["is_half_day"] = minutes < 390

    # A negative settlement, so the fixture exercises the case that makes a log
    # return undefined. The value is invented -- -12.34, not the figure the real
    # contract printed -- because a fixture that reproduced a real settlement would
    # be copying the vendor series it exists to avoid, however small the excerpt.
    shock = pd.Timestamp("2020-04-20")
    if shock in frame.index:
        frame.loc[shock, "OIL_WTI"] = -12.34

    # A gap in a rate series on a session the exchange is open, which is what
    # Columbus Day and Veterans Day do to the H.15 release.
    for gap in ("2019-10-14", "2019-11-11"):
        ts = pd.Timestamp(gap)
        if ts in frame.index:
            frame.loc[ts, ["DGS3MO", "DTB3", "DGS2", "DGS10"]] = np.nan

    DEST.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(DEST, float_format="%.10g", lineterminator=LF)

    print(f"{len(frame)} synthetic sessions, {frame.index.min().date()} to "
          f"{frame.index.max().date()}")
    print(f"columns: {list(frame.columns)}")
    print(f"written to {DEST.relative_to(ROOT)}")
    print("\nSynthetic. Not market data. Never used for a research run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
