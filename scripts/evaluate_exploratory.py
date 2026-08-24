"""Score every completed exploratory run on comparable terms, and report all of them.

Three things this deliberately does not do.

It does not rank and promote. The table comes out in specification order, not in
score order, because a table sorted by Sharpe invites reading the top row as a
result. The best row here is the maximum of two dozen draws and has no interval
that accounts for having been selected as a maximum.

It does not compare across execution specifications. A close-to-close run and an
open-to-close run hold different assets over different intervals with different
cost functions; each is scored against its own always-long benchmark, and the
Sharpe difference against P1 is only computed for runs that share P1's
specification.

It does not silently align mismatched windows. E14 and E15 produce shorter
out-of-sample series, so their paired comparison runs on the intersection with P1
and the number of shared sessions is printed alongside.
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
from src.stats import (ann_mean, bootstrap_difference, expected_max_sharpe,  # noqa: E402
                       sharpe)

BLOCK, REPS = 20, 10_000
BASE_COST = 2.0


def load_run(directory: Path):
    """Rebuild the specification the run actually used, parameters included.

    Scoring a run with a different borrow charge from the one it traded under would
    be the same defect that produced E24 in the first place, one level down.
    """
    manifest = json.loads((directory / "run_manifest.json").read_text(encoding="utf-8"))
    oos = pd.read_csv(directory / "oos_predictions.csv", index_col="date", parse_dates=True)
    spec = get_spec(manifest.get("execution_specification", "primary_open_to_close"),
                    **(manifest.get("execution_parameters") or {}))
    return manifest, oos, spec


def always_long(spec, index, r, carry, cost_bps):
    """The same benchmark the confirmatory report uses, on this run's own rows."""
    return spec.net(pd.Series(1.0, index=index), r, carry, cost_bps)


def score(eid, manifest, oos, spec, snapshot, p1_net):
    r = oos[spec.return_column]
    carry = oos[spec.carry_column]
    cost = float(manifest.get("cost_bps_per_side", BASE_COST))
    w = oos.position.astype(float)
    net = spec.net(w, r, carry, cost)
    cash = cash_return(snapshot).reindex(oos.index).fillna(0.0)
    al = always_long(spec, oos.index, r, carry, cost)

    row = {
        "id": eid,
        "spec": "O2C" if spec.name.startswith("primary") else "C2C",
        "oos_sessions": len(oos),
        "ann_mean_excess": ann_mean(net.to_numpy()),
        "sharpe": sharpe(net.to_numpy()),
        "participation": float((w != 0).mean()),
        "n_active": int((w != 0).sum()),
        "terminal_wealth": float((1.0 + net + cash).prod()),
        "sharpe_vs_always_long": sharpe(net.to_numpy()) - sharpe(al.to_numpy()),
        "models_selected": oos.model.nunique(),
    }

    # Against P1, only where that comparison means anything: same execution
    # specification, and only on the sessions the two actually share.
    if spec.name.startswith("primary") and p1_net is not None:
        shared = net.index.intersection(p1_net.index)
        row["shared_with_p1"] = len(shared)
        if len(shared) > 250:
            d = bootstrap_difference(net.loc[shared], p1_net.loc[shared], sharpe, BLOCK, REPS)
            row["sharpe_minus_p1"] = d["point"]
            row["diff_lo"], row["diff_hi"] = d["ci_low"], d["ci_high"]
    return row


def main() -> int:
    snapshot, _ = load_snapshot()

    p1_dir = ROOT / "results"
    _, p1_oos, p1_spec = load_run(p1_dir)
    p1_net = p1_spec.net(p1_oos.position.astype(float), p1_oos[p1_spec.return_column],
                         p1_oos[p1_spec.carry_column], BASE_COST)

    rows = [score("P1", {"execution_specification": p1_spec.name}, p1_oos, p1_spec,
                  snapshot, None)]
    rows[0]["id"] = "P1 (confirmatory)"

    base = ROOT / "results" / "exploratory"
    directories = sorted(
        (d for d in base.glob("E*") if (d / "run_manifest.json").exists()),
        key=lambda d: (int("".join(ch for ch in d.name if ch.isdigit()) or 0), d.name),
    )
    if not directories:
        print("no completed exploratory runs found under results/exploratory/")
        return 1

    for d in directories:
        manifest, oos, spec = load_run(d)
        rows.append(score(d.name, manifest, oos, spec, snapshot, p1_net))

    out = pd.DataFrame(rows)
    dest = ROOT / "results" / "exploratory_summary.csv"
    out.to_csv(dest, index=False, float_format="%.6g")

    show = out.copy()
    for col in ("ann_mean_excess", "participation"):
        show[col] = (show[col] * 100).round(2)
    pd.set_option("display.width", 220, "display.max_columns", 30)
    print(show.to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    print(f"\nwritten to {dest.relative_to(ROOT)}")

    n_pos = int((out.sharpe > 0).sum())
    print(f"\n{n_pos} of {len(out)} specifications have a positive Sharpe ratio.")
    print("The table is in specification order, not score order, and the highest row")
    print("is not the finding. It is the maximum of a set of draws, and the interval")
    print("beside it is an ordinary paired interval that does not account for having")
    print("been chosen as a maximum. Protocol 7.2 rules out reading it as a result.")

    # Protocol 6.4. Every realised path counts, not every E number: E10, E11, E12
    # and E12b each produced several, and a reference computed on 19 when 33 were
    # looked at understates exactly the thing it exists to measure.
    paths = out[out.id != "P1 (confirmatory)"].sharpe.to_numpy(dtype=float)
    rules = ROOT / "results" / "exploratory_position_rules.csv"
    if rules.exists():
        extra = pd.read_csv(rules)
        paths = np.concatenate([paths, extra.loc[extra.kind == "exploratory",
                                                 "sharpe"].to_numpy(dtype=float)])
    paths = paths[np.isfinite(paths)]
    if len(paths) >= 2:
        reference = expected_max_sharpe(paths)
        best = float(np.nanmax(paths))
        spread = float(np.nanstd(paths, ddof=1))
        print("")
        print(f"Multiple-testing reference (protocol 6.4), on {len(paths)} realised paths")
        print("  covering the retraining specifications and the position rules, all on the")
        print("  same 1,865 out-of-sample sessions. The 10 section 9.1 news arms are counted")
        print("  in the registry but excluded here: they run on a 1,247-session overlap, and")
        print("  pooling a spread across two different windows compares unlike quantities.")
        print(f"  spread of path Sharpe ratios, sd   {spread:+.3f}")
        print(f"  best observed                      {best:+.3f}")
        print(f"  independence-based E[max] at N={len(paths)}  {reference:+.3f}")
        print("")
        print(f"  The observed best is {best:+.3f} against an independence-based expected")
        print(f"  maximum of {reference:+.3f}. This is a statement of SCALE, not a test. The",)
        print("  paths are strongly correlated -- many share a training window, a feature")
        print("  screen and most of their positions -- so they are nowhere near independent")
        print("  draws, and the expression assumes exactly the independence they lack. It")
        print("  adjusts no interval and licenses no claim that the best row is noise.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
