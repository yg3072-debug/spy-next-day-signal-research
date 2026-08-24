"""Evaluate P1 against the two conditions.

Written before the run finished, on purpose: the protocol already says what to
compute, so there is nothing here that seeing a result could have shaped. Every
quantity below is section 5, 6 or 8 of `docs/research_protocol.md`, and nothing
else is computed.

    python scripts/evaluate_p1.py

Outputs trade_ledger.csv, statistical_tests.csv and regime_performance.csv, and
prints the verdict on Conditions A and B. It does not decide anything: if the
conditions fail, that is the finding.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from build_benchmarks import (  # noqa: E402
    BORROW_ANNUAL, COST_BPS_PER_SIDE, COST_SCENARIOS_BPS, TRADING_DAYS,
    breakeven_cost_o2c, cash_return, intraday_financing, load_snapshot,
    o2c_benchmarks, performance,
)
from src.features import build_features, build_target  # noqa: E402
from src.pipeline import (  # noqa: E402
    CLASSES, apply_labels, estimate_quantiles, vol_adjusted_target,
)
from src.stats import (  # noqa: E402
    ann_mean, bootstrap_difference, bootstrap_joint, bootstrap_statistic,
    jobson_korkie_memmel, ols_slope, politis_white_block, sharpe,
)


def load_run(outdir: Path):
    oos = pd.read_csv(outdir / "oos_predictions.csv", index_col="date", parse_dates=True)
    manifest = json.loads((outdir / "run_manifest.json").read_text(encoding="utf-8"))
    selection = pd.read_csv(outdir / "selection_log.csv")
    return oos, manifest, selection


def reconstruct_labels(snapshot, oos, cfg_quantiles, initial, step):
    """Realised labels for the out-of-sample rows, as each step defined them.

    The thresholds are a deterministic function of the outer-train slice, so they
    can be recovered without refitting anything. Reconstructing them beats storing
    them, because a mismatch would show up here rather than being carried silently.
    """
    features, _ = build_features(snapshot)
    target = build_target(snapshot)
    idx = features.dropna().index.intersection(target.dropna().index)
    z = vol_adjusted_target(np.log1p(target.loc[idx]), features.loc[idx, "Volatility_20"], 1e-8)

    labels, base_rates = {}, {}
    starts = list(range(initial, len(idx), step))
    for start in starts:
        stop = min(start + step, len(idx))
        train, val = idx[:start], idx[start:stop]
        q_low, q_high = estimate_quantiles(z.loc[train], tuple(cfg_quantiles))
        for d in val:
            labels[d] = apply_labels(z.loc[[d]], q_low, q_high).iloc[0]
        train_labels = apply_labels(z.loc[train], q_low, q_high)
        rates = train_labels.value_counts(normalize=True)
        for d in val:
            base_rates[d] = {c: float(rates.get(c, 0.0)) for c in CLASSES}
    y = pd.Series(labels).reindex(oos.index)
    br = pd.DataFrame(base_rates).T.reindex(oos.index)
    return y, br


def multiclass_brier(proba: pd.DataFrame, y: pd.Series) -> float:
    onehot = pd.DataFrame(0.0, index=y.index, columns=CLASSES)
    for c in CLASSES:
        onehot.loc[y == c, c] = 1.0
    return float(((proba[CLASSES].to_numpy() - onehot.to_numpy()) ** 2).sum(axis=1).mean())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", default="results")
    ap.add_argument("--reps", type=int, default=10_000)
    ap.add_argument("--block", type=float, default=20.0)
    args = ap.parse_args()

    outdir = ROOT / args.dir
    oos, manifest, selection = load_run(outdir)
    snapshot, snap_manifest = load_snapshot()
    idx = oos.index

    c = COST_BPS_PER_SIDE / 1e4
    fin = oos["financing"]
    w = oos["position"]
    realised = oos["realised_o2c"]

    # ---------------------------------------------------------------- P&L
    gross = w * realised
    execution = 2 * c * w.abs()
    financing = fin * w.abs()
    net = gross - execution - financing
    rf = cash_return(snapshot).reindex(idx)

    stats = performance(net, rf + net, w)
    stats["breakeven_cost_bps_per_side"] = breakeven_cost_o2c(w, realised, fin)

    # ------------------------------------------------------- benchmark legs
    bench_w = o2c_benchmarks(snapshot)
    always_long = pd.Series(1.0, index=idx)
    fin_all = intraday_financing(snapshot, snapshot.index).shift(-1).reindex(idx)
    al_net = always_long * realised - 2 * c * always_long - fin_all * always_long
    cash_net = pd.Series(0.0, index=idx)

    # ------------------------------------------------------- Condition A
    # A strategy that never takes a position has zero excess variance, so its
    # Sharpe is undefined and so is any difference of Sharpe ratios involving it.
    # That is a real outcome and it fails Condition A, but it fails it for a
    # reason worth naming rather than by producing a silent NaN.
    took_positions = net.std(ddof=1) > 0
    if took_positions:
        cond_a = bootstrap_difference(net, al_net, sharpe, args.block, args.reps)
        jk = jobson_korkie_memmel(net, al_net)
    else:
        cond_a = {"point": np.nan, "ci_low": np.nan, "ci_high": np.nan,
                  "fraction_le_zero": np.nan, "se": np.nan}
        jk = {"p_two_sided": np.nan, "correlation": np.nan}

    # decomposition, the three terms reported apart
    timing = (w - 1.0) * realised
    cost_saving = 2 * c * (1.0 - w.abs())
    fin_saving = fin_all * (1.0 - w.abs())

    # ------------------------------------------------------- Condition B
    cond_b = bootstrap_difference(net, cash_net, ann_mean, args.block, args.reps)

    passes_a = bool(cond_a["ci_low"] > 0)
    passes_b = bool(cond_b["ci_low"] > 0)
    if not took_positions:
        verdict = ("insufficient evidence of a stable incremental value "
                   "(the procedure took no position on any out-of-sample session)")
    elif passes_a and passes_b:
        verdict = "supported"
    else:
        verdict = "insufficient evidence of a stable incremental value"

    # ------------------------------------------------- predictive evidence
    y, base_rates = reconstruct_labels(
        snapshot, oos, [0.25, 0.75],
        int(manifest["modelling_sessions"]) - int(manifest["oos_sessions"]),
        21,
    )
    proba = oos.rename(columns={"p_short": -1, "p_flat": 0, "p_long": 1})
    bs = multiclass_brier(proba, y)
    bs_ref = multiclass_brier(base_rates, y)
    brier_skill = 1.0 - bs / bs_ref if bs_ref > 0 else np.nan

    # The slope of realised return on predicted return, with a paired interval.
    # Resampling the two series independently would destroy the relationship the
    # slope exists to measure, so both are drawn with the same block indices.
    ok = oos.mu_hat.notna() & realised.notna()
    slope_boot = bootstrap_joint(
        oos.mu_hat[ok], realised[ok], ols_slope, args.block, args.reps,
    )
    slope = slope_boot["point"]

    # ------------------------------------------------------------ outputs
    ledger = pd.DataFrame({
        "position": w, "open": snapshot.Open.shift(-1).reindex(idx),
        "close": snapshot.Close.shift(-1).reindex(idx),
        "gross": gross, "execution_cost": execution, "financing_cost": financing,
        "net": net, "model": oos["model"],
    })
    ledger[ledger.position != 0].to_csv(outdir / "trade_ledger.csv", float_format="%.10g")

    regime = pd.DataFrame({"net": net, "w": w})
    regime["year"] = regime.index.year
    vix = snapshot.VIX.reindex(idx)
    regime["vix_tercile"] = pd.qcut(vix, 3, labels=["low", "mid", "high"])
    rows = []
    for key, group in list(regime.groupby("year")) + list(regime.groupby("vix_tercile", observed=True)):
        rows.append({
            "bucket": str(key), "sessions": len(group),
            "participation": float((group.w != 0).mean()),
            "ann_mean_excess": float(group.net.mean() * TRADING_DAYS),
            "sharpe_excess": sharpe(group.net.to_numpy()),
        })
    pd.DataFrame(rows).to_csv(outdir / "regime_performance.csv", index=False, float_format="%.8g")

    cost_rows = []
    for bps in COST_SCENARIOS_BPS:
        cc = bps / 1e4
        n = gross - 2 * cc * w.abs() - financing
        cost_rows.append({
            "cost_bps_per_side": bps, "positions_frozen_at_base_cost": True,
            "ann_mean_excess": float(n.mean() * TRADING_DAYS),
            "sharpe_excess": sharpe(n.to_numpy()),
        })
    pd.DataFrame(cost_rows).to_csv(outdir / "cost_sensitivity.csv", index=False, float_format="%.8g")

    tests = {
        "oos_sessions": len(idx),
        "participation_rate": float((w != 0).mean()),
        "block_sessions": args.block, "reps": args.reps,
        "politis_white_block": politis_white_block(net) if net.std() > 0 else np.nan,
        "net_sharpe": stats["sharpe_excess"],
        "net_ann_mean_excess": stats["ann_mean_excess"],
        "cagr_total": stats["cagr_total"], "max_drawdown": stats["max_drawdown"],
        "breakeven_cost_bps_per_side": stats["breakeven_cost_bps_per_side"],
        "condition_a_d_sharpe": cond_a["point"], "condition_a_ci_low": cond_a["ci_low"],
        "condition_a_ci_high": cond_a["ci_high"],
        "condition_a_bootstrap_fraction_le_zero": cond_a["fraction_le_zero"],
        "condition_a_passes": passes_a,
        "took_any_position": bool(took_positions),
        "jobson_korkie_memmel_p": jk["p_two_sided"], "strategy_benchmark_correlation": jk["correlation"],
        "condition_b_d_annmean": cond_b["point"], "condition_b_ci_low": cond_b["ci_low"],
        "condition_b_ci_high": cond_b["ci_high"],
        "condition_b_bootstrap_fraction_le_zero": cond_b["fraction_le_zero"],
        "condition_b_passes": bool(passes_b),
        "ann_gross_timing": float(timing.mean() * TRADING_DAYS),
        "ann_cost_saving": float(cost_saving.mean() * TRADING_DAYS),
        "ann_financing_saving": float(fin_saving.mean() * TRADING_DAYS),
        "brier_score": bs, "brier_reference": bs_ref, "brier_skill": brier_skill,
        "mu_hat_slope_on_realised": float(slope),
        "mu_hat_slope_ci_low": slope_boot["ci_low"],
        "mu_hat_slope_ci_high": slope_boot["ci_high"],
        "mu_hat_slope_bootstrap_fraction_le_zero": slope_boot["fraction_le_zero"],
        "steps_with_baseline_selected": int(selection.get(
            "baseline_selected", pd.Series(dtype=bool)).sum()) if "baseline_selected" in selection else None,
        "verdict": verdict,
    }
    pd.Series(tests).to_csv(outdir / "statistical_tests.csv", header=False)

    # ------------------------------------------------------------- report
    def pct(x): return f"{x:+.2%}"
    print(f"P1  {len(idx)} out-of-sample sessions, {idx.min().date()} to {idx.max().date()}")
    print(f"config {manifest['config_sha256'][:16]}...  snapshot {manifest['snapshot_sha256'][:16]}...")
    print(f"participation {tests['participation_rate']:.1%}"
          f"   baseline selected at {tests['steps_with_baseline_selected']} of {len(selection)} reselections")
    print()
    print(f"{'':<34}{'point':>10}{'95% CI low':>13}{'passes':>9}")
    if took_positions:
        print(f"{'Condition A  d Sharpe vs always-long':<34}{cond_a['point']:>10.3f}"
              f"{cond_a['ci_low']:>13.3f}{str(passes_a):>9}")
    else:
        print(f"{'Condition A  d Sharpe vs always-long':<34}{'undefined':>10}"
              f"{'-':>13}{'False':>9}   no position was ever taken")
    print(f"{'Condition B  d ann mean vs cash':<34}{cond_b['point']:>10.4f}"
          f"{cond_b['ci_low']:>13.4f}{str(passes_b):>9}")
    print()
    print(f"VERDICT  {verdict}")
    print()
    print("decomposition of the excess over always-long")
    print(f"  gross timing      {pct(tests['ann_gross_timing'])}"
          "   <- the only term that is evidence of prediction")
    print(f"  cost saving       {pct(tests['ann_cost_saving'])}")
    print(f"  financing saving  {pct(tests['ann_financing_saving'])}")
    print()
    print("predictive evidence, independent of P&L")
    print(f"  Brier skill vs training base rate  {brier_skill:+.4f}")
    print(f"  slope of realised on mu_hat        {slope:+.4f}"
          f"   95% CI [{slope_boot['ci_low']:+.3f}, {slope_boot['ci_high']:+.3f}]")
    print()
    print(f"wrote trade_ledger.csv, statistical_tests.csv, regime_performance.csv,"
          f" cost_sensitivity.csv to {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
