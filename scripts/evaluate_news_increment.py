"""Score §9.1's incremental test: does adding news features change anything?

The comparison is paired and on identical rows. Every arm runs the same procedure
over the same 2,247-session overlap with the same folds and the same cost model,
and differs only in which columns exist. That is what makes a difference between
two arms attributable to the feature set rather than to the window.

Three things this reports that a simpler script would not.

**The placebo arms and the control arms are labelled differently**, because they
answer different questions. A positive shift feeds the model stale news and asks
whether an improvement survives it; a negative shift feeds the model news from the
future and asks whether the procedure could detect such an improvement at all.

**The number of realised strategy paths is printed**, not the number of
specifications, because that is the count any multiple-testing statement has to
use.

**Nothing is ranked.** The table comes out in specification order.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from build_benchmarks import cash_return, load_snapshot  # noqa: E402
from src.execution import get_spec  # noqa: E402
from src.stats import ann_mean, bootstrap_difference, sharpe  # noqa: E402

BASE = ROOT / "results" / "altdata"
BLOCK, REPS, COST = 20, 10_000, 2.0

ORDER = ["N0", "N1", "N1p5", "N1p10", "N1p20", "N1p60",
         "N1m5", "N1m10", "N1m20", "N1m60"]

KIND = {"N0": "control arm — market features only",
        "N1": "treatment arm — market + news, true alignment"}
for k in (5, 10, 20, 60):
    KIND[f"N1p{k}"] = f"placebo — news from t−{k}, stale but legitimate"
    KIND[f"N1m{k}"] = f"positive control — news from t+{k}, information it could not have had"


def load(aid: str):
    d = BASE / aid
    if not (d / "run_manifest.json").exists():
        return None
    oos = pd.read_csv(d / "oos_predictions.csv", index_col="date", parse_dates=True)
    spec = get_spec(json.loads((d / "run_manifest.json").read_text(encoding="utf-8"))
                    .get("execution_specification", "primary_open_to_close"))
    net = spec.net(oos.position.astype(float), oos[spec.return_column],
                   oos[spec.carry_column], COST)
    return oos, net


def main() -> int:
    snapshot, _ = load_snapshot()
    runs = {aid: load(aid) for aid in ORDER}
    have = {k: v for k, v in runs.items() if v is not None}
    if "N0" not in have:
        print("N0 has not completed; the incremental test has no control arm yet.")
        return 1
    missing = [a for a in ORDER if a not in have]
    if missing:
        print(f"not yet complete, omitted from the table: {missing}\n")

    _, base_net = have["N0"]
    rows = []
    for aid in ORDER:
        if aid not in have:
            continue
        oos, net = have[aid]
        cash = cash_return(snapshot).reindex(oos.index).fillna(0.0)
        row = {
            "id": aid, "kind": KIND[aid], "oos_sessions": len(oos),
            "n_active": int((oos.position != 0).sum()),
            "active_rate": float((oos.position != 0).mean()),
            "ann_mean_excess": ann_mean(net.to_numpy()),
            "sharpe": sharpe(net.to_numpy()),
            "terminal_wealth": float((1.0 + net + cash).prod()),
        }
        if aid != "N0":
            shared = net.index.intersection(base_net.index)
            row["shared_with_N0"] = len(shared)
            d = bootstrap_difference(net.loc[shared], base_net.loc[shared],
                                     sharpe, BLOCK, REPS)
            row["sharpe_minus_N0"] = d["point"]
            row["lo"], row["hi"] = d["ci_low"], d["ci_high"]
        rows.append(row)

    out = pd.DataFrame(rows)
    dest = ROOT / "results" / "news_increment_summary.csv"
    out.to_csv(dest, index=False, float_format="%.6g")

    show = out.drop(columns=["kind"]).copy()
    for col in ("ann_mean_excess", "active_rate"):
        show[col] = (show[col] * 100).round(2)
    pd.set_option("display.width", 200, "display.max_columns", 20)
    print(show.to_string(index=False, float_format=lambda v: f"{v:.3f}"))

    print(f"\nwritten to {dest.relative_to(ROOT)}\n")
    treated = out[out.id != "N0"]
    if not treated.empty:
        crosses = int(((treated.lo <= 0) & (treated.hi >= 0)).sum())
        print(f"{len(out)} realised strategy paths, one per arm. "
              f"{crosses} of {len(treated)} intervals against N0 include zero.")
        controls = treated[treated.id.str.contains("m")]
        if not controls.empty:
            print("\nRead the positive controls first. They were given news from the "
                  "future;\nif they do not separate from N0 either, then a null at the "
                  "true alignment\nis a statement about this procedure's sensitivity as "
                  "much as about the data.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
