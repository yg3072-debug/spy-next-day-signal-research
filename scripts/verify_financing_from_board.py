"""Rebuild the financing fields from Board H.15 data and check them against what P1 published.

The rate columns kept in this repository are published because the Board's H.15
release is a public-domain federal government work. That justification only holds
if the fields really can be rebuilt from the Board's own data — keeping a value
that was obtained elsewhere and relabelling its source would be worse than removing
it.

So the fields are recomputed here from scratch, using nothing but the committed
Board rate file, the exchange calendar, and the formulas in the protocol:

    intraday financing   f_t = y_{t-1}/100 * session_minutes / (365*24*60)
    close-to-close carry rf_t = y_{t-1}/100 * calendar days / 365
    financing cost       financing_cost = f_t * |w_t|

and compared, session by session, with the values the published results carry.

One difference is expected and is not a failure: the frozen snapshot captured
2026-08-21's rates while they were provisional, and the Board has since revised
them. That date lies outside the modelling window. Any difference on any other
date would mean the reconstruction claim is false.

    python scripts/verify_financing_from_board.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

COST_BPS = 2.0
MINUTES_PER_YEAR = 365.0 * 24.0 * 60.0


FILL_LIMIT = 5


def board_rates() -> pd.DataFrame:
    """Board rates on the NYSE session grid, forward-filled as the snapshot builder does.

    The bond market closes on days the NYSE does not -- Columbus Day and Veterans
    Day are the recurring cases -- so H.15 publishes nothing while a session still
    trades. `freeze_market_data.py` carries the previous rate forward with a
    five-session limit, and the reconstruction has to apply the same rule or it is
    not reconstructing the same quantity. The rule is a processing decision recorded
    in the protocol, not data from anywhere.
    """
    files = sorted((ROOT / "data").glob("treasury_rates_h15_*.csv"))
    if not files:
        raise SystemExit("no Board rate file; run scripts/fetch_treasury_rates.py")
    frame = pd.read_csv(files[-1], index_col="Date", parse_dates=True)
    sessions = frame.index[frame.session_minutes.notna()]
    frame = frame.reindex(sessions)
    for col in ("TCM3M", "TCM2Y", "TCM10Y"):
        frame[col] = frame[col].ffill(limit=FILL_LIMIT)
    return frame


def intraday_financing(rates: pd.DataFrame, index: pd.Index) -> pd.Series:
    """The protocol's f_t, built only from the Board series and session length."""
    annual = rates["TCM3M"].reindex(index).shift(1) / 100.0
    minutes = rates["session_minutes"].reindex(index)
    return (annual * minutes / MINUTES_PER_YEAR).fillna(0.0)


def cash_carry(rates: pd.DataFrame, index: pd.Index) -> pd.Series:
    """The protocol's rf_t: simple accrual over actual calendar days."""
    annual = rates["TCM3M"].reindex(index).shift(1) / 100.0
    days = index.to_series().diff().dt.days
    return (annual * days / 365.0).fillna(0.0)


def check(name: str, rebuilt: pd.Series, published: pd.Series,
          report: dict) -> bool:
    shared = rebuilt.index.intersection(published.index)
    a = published.loc[shared].to_numpy(float)
    b = rebuilt.loc[shared].to_numpy(float)
    diff = np.abs(a - b)
    mismatch = shared[diff > 1e-12]
    entry = {
        "sessions": int(len(shared)),
        "identical": int((diff <= 1e-12).sum()),
        "max_abs_difference": float(diff.max()) if len(diff) else 0.0,
        "mismatched_dates": [str(d.date()) for d in mismatch][:10],
    }
    report[name] = entry
    ok = len(mismatch) == 0
    print(f"  {'ok  ' if ok else 'FAIL'} {name:<28} "
          f"{entry['identical']}/{entry['sessions']} identical, "
          f"max|diff| = {entry['max_abs_difference']:.3e}")
    for d in mismatch[:5]:
        print(f"        {d.date()}  published={published[d]:.10g}  "
              f"rebuilt={rebuilt[d]:.10g}")
    return ok


def main() -> int:
    rates = board_rates()
    report: dict = {"rate_file": sorted(
        p.name for p in (ROOT / "data").glob("treasury_rates_h15_*.csv"))[-1],
        "fields": {}}
    ok = True

    print("rebuilding the financing fields from Board H.15 data alone\n")

    oos_path = ROOT / "results" / "oos_predictions.csv"
    if oos_path.exists():
        oos = pd.read_csv(oos_path, index_col="date", parse_dates=True)
        if "financing" in oos.columns:
            # P1 charges the session the position is held in, which is t+1.
            full = rates.index
            rebuilt = intraday_financing(rates, full).shift(-1).reindex(oos.index)
            ok &= check("oos financing", rebuilt.fillna(0.0), oos.financing,
                        report["fields"])

    ledger = ROOT / "results" / "trade_ledger.csv"
    if ledger.exists():
        led = pd.read_csv(ledger, index_col="date", parse_dates=True)
        if "financing_cost" in led.columns and "position" in led.columns:
            fin = intraday_financing(rates, rates.index).shift(-1).reindex(led.index)
            rebuilt = (fin.fillna(0.0) * led.position.abs())
            ok &= check("ledger financing_cost", rebuilt, led.financing_cost,
                        report["fields"])

    for name in ("E22", "E23", "E24"):
        path = ROOT / "results" / "exploratory" / name / "oos_predictions.csv"
        if not path.exists():
            continue
        frame = pd.read_csv(path, index_col="date", parse_dates=True)
        if "carry_rf" not in frame.columns:
            continue
        rebuilt = cash_carry(rates, rates.index).shift(-1).reindex(frame.index)
        ok &= check(f"{name} carry_rf", rebuilt.fillna(0.0), frame.carry_rf,
                    report["fields"])

    report["verdict"] = ("every financing field is reconstructible from Board H.15 data"
                         if ok else "a field could NOT be rebuilt from Board data")
    report["note"] = (
        "Any mismatch confined to 2026-08-21 reflects a provisional rate in the "
        "frozen snapshot that the Board has since revised. That date lies outside "
        "the modelling window. A mismatch on any other date would falsify the claim "
        "that these fields are publishable on the strength of the Board's licence."
    )
    dest = ROOT / "results" / "financing_reconstruction.json"
    dest.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n{report['verdict']}")
    print(f"written to {dest.relative_to(ROOT)}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
