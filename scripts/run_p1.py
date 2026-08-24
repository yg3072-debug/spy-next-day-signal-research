"""Run P1, the confirmatory procedure.

The order of operations is the protocol's, not a convenience: every quantity a
fold learns is estimated inside that fold's own training slice, and
outer-validation is predicted once and never looked at again. Reading the loop
below against protocol section 4.2 should show them to be the same thing.

    python scripts/run_p1.py --smoke     structure check, writes to results/smoke/
    python scripts/run_p1.py             the real run, writes to results/

Smoke mode reports shapes, columns and counts. It deliberately reports no
performance figure, because the point of a smoke test is to check the plumbing
without anyone forming an impression of the answer.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import itertools
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sklearn.model_selection import TimeSeriesSplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.features import build_features, build_target  # noqa: E402
from src.pipeline import (  # noqa: E402
    CLASSES, SigmoidCalibrator, apply_labels, calibration_is_viable,
    class_conditional_means, crossfit_out_of_fold, estimate_quantiles,
    expected_return, fit_and_predict_proba, make_estimator, select_features,
    vol_adjusted_target,
)
from src.stats import TRADING_DAYS, bootstrap_statistic, sharpe  # noqa: E402
from src.strategy import positions_from_expected_return  # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))
from build_benchmarks import cash_return, intraday_financing, load_snapshot  # noqa: E402


# ------------------------------------------------------------------- candidates

def build_candidates(cfg: dict) -> list[dict]:
    """The full cross product of model configuration and delta, in ordering order.

    Selected in one pass. Choosing delta per family first and then comparing
    families would be a two-stage selection, which is a second comparison hidden
    inside the first.
    """
    out = []
    for family, spec in cfg["models"].items():
        grid = spec.get("grid")
        combos = (
            [dict(zip(grid, values)) for values in itertools.product(*grid.values())]
            if isinstance(grid, dict) else list(grid)
        )
        for rank, params in enumerate(combos):
            for delta in cfg["position_rule"]["delta_multiple_grid"]:
                out.append({
                    "family": family,
                    "params": params,
                    "delta": float(delta),
                    "complexity_rank": spec["complexity_rank"],
                    "within_family_rank": rank,
                    "spec": spec,
                    "id": f"{family}|{params}|d{delta}",
                })
    # simplicity_key: (complexity_rank, within_family_rank, -delta)
    out.sort(key=lambda c: (c["complexity_rank"], c["within_family_rank"], -c["delta"]))
    return out


def model_configs(cfg: dict) -> list[dict]:
    """One entry per fitted model, i.e. candidates collapsed over delta.

    Delta is swept on mu_hat afterwards and needs no refit, so the loop fits each
    model once and reuses it across the delta grid.
    """
    seen, out = set(), []
    for c in build_candidates(cfg):
        key = (c["family"], repr(c["params"]))
        if key not in seen:
            seen.add(key)
            out.append(c)
    return out


# ------------------------------------------------------------------- one fold

def fit_slice(
    X_train, z_train, target_log_train, returns_train, X_pred,
    cfg, groups, seed, only=None,
):
    """Everything a slice is allowed to learn, learned from that slice alone.

    Returns calibrated probabilities on `X_pred`, the class-conditional means, the
    features chosen, and whether calibration was possible.
    """
    q_low, q_high = estimate_quantiles(z_train, tuple(cfg["target"]["quantiles"]))
    y_train = apply_labels(z_train, q_low, q_high)

    features, _ = select_features(X_train, z_train, groups, cfg["feature_selection"])
    if not features:
        return None
    Xt, Xp = X_train[features], X_pred[features]

    means = class_conditional_means(returns_train, y_train)

    cal_cfg = cfg["calibration"]
    ns = cal_cfg["nested_splitter"]
    splitter = TimeSeriesSplit(n_splits=ns["n_splits"], test_size=ns["test_size"], gap=ns["gap"])

    # A reselection needs every candidate; a monthly refit needs only the frozen
    # one, and fitting the rest would be work the protocol does not ask for.
    wanted = only if only is not None else model_configs(cfg)
    results = {}
    for candidate in wanted:
        build = lambda c=candidate: make_estimator(  # noqa: E731
            c["family"], c["params"], c["spec"], seed
        )
        oof_proba, oof_y = crossfit_out_of_fold(
            Xt, y_train, build, splitter, ns["min_base_train_samples"]
        )
        viable = calibration_is_viable(
            oof_y, cal_cfg["min_calibration_samples"], cal_cfg["min_samples_per_class"]
        )
        calibrator = SigmoidCalibrator.fit(oof_proba, oof_y) if viable else None

        raw = fit_and_predict_proba(build(), Xt, y_train, Xp)
        proba = calibrator.transform(raw) if calibrator else raw
        key = (candidate["family"], repr(candidate["params"]))
        results[key] = {
            "mu_hat": expected_return(proba, means),
            "proba": proba,
            "calibration_skipped": not viable,
        }

    return {
        "predictions": results,
        "features": features,
        "quantiles": (q_low, q_high),
        "class_means": means,
        "labels": y_train,
    }


# ------------------------------------------------------------------- selection

def score_candidates(
    inner: dict[tuple, pd.Series],
    realised: pd.Series,
    financing_held: pd.Series,
    cfg: dict,
    candidates: list[dict],
    seed: int,
) -> pd.DataFrame:
    """Net Sharpe of every candidate on the concatenated inner out-of-sample.

    Computed once on the concatenated series, never as an average of per-fold
    Sharpe ratios: the average of fold Sharpes is not the Sharpe of the series,
    and it hides drift between folds.
    """
    cost = cfg["selection"]["metric_cost_bps_per_side"]
    c = cost / 1e4
    rows = []
    for cand in candidates:
        key = (cand["family"], repr(cand["params"]))
        mu = inner.get(key)
        if mu is None or mu.empty:
            continue
        w = positions_from_expected_return(mu, cost, financing_held.loc[mu.index], cand["delta"])
        net = w * realised.loc[mu.index] - 2 * c * w.abs() - financing_held.loc[mu.index] * w.abs()
        active = int((w != 0).sum())
        s = sharpe(net.to_numpy())
        rows.append({
            "id": cand["id"], "family": cand["family"], "params": repr(cand["params"]),
            "delta": cand["delta"], "complexity_rank": cand["complexity_rank"],
            "within_family_rank": cand["within_family_rank"],
            "active_positions": active, "score": s,
            "degenerate": active < cfg["selection"]["constraints"]["min_active_positions_inner_oos"]
                          or not np.isfinite(s),
            "net": net,
        })
    return pd.DataFrame(rows)


def one_standard_error_choice(scored: pd.DataFrame, cfg: dict, seed: int) -> tuple[dict, dict]:
    """Best score, then the simplest candidate within one standard error of it.

    The band is one standard error *of the best candidate*, not of each candidate
    in turn, which would make eligibility depend on how noisy a rival happened to
    be.
    """
    live = scored[~scored.degenerate]
    if live.empty:
        fallback = scored.iloc[0].to_dict() if len(scored) else {}
        return fallback, {"reason": "all candidates degenerate", "se_best": np.nan,
                          "n_eligible": 0, "best_score": np.nan}

    best = live.loc[live.score.idxmax()]
    se_cfg = cfg["selection"]["standard_error"]
    se = bootstrap_statistic(
        best["net"], sharpe, se_cfg["block_sessions"], se_cfg["reps"],
        seed=seed + se_cfg["seed_offset"],
    )["se"]

    eligible = live[live.score >= best.score - se]
    chosen = eligible.sort_values(
        ["complexity_rank", "within_family_rank", "delta"],
        ascending=[True, True, False],
    ).iloc[0]
    return chosen.to_dict(), {
        "reason": "one-standard-error rule",
        "best_id": best["id"], "best_score": float(best.score),
        "se_best": float(se), "n_eligible": int(len(eligible)),
        "n_degenerate": int(scored.degenerate.sum()),
    }


# ------------------------------------------------------------------------ main

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--smoke", action="store_true", help="structure check on a short window")
    ap.add_argument("--config", default="config/p1.yaml")
    args = ap.parse_args()

    cfg = yaml.safe_load((ROOT / args.config).read_bytes())
    config_sha = hashlib.sha256((ROOT / args.config).read_bytes()).hexdigest()

    snapshot, manifest = load_snapshot()
    features_all, registry = build_features(snapshot)
    groups = {f.name: f.group for f in registry}
    target_log = np.log1p(build_target(snapshot)).rename("target_log")
    target_simple = build_target(snapshot)

    complete = features_all.dropna().index.intersection(target_simple.dropna().index)
    features_all, target_log = features_all.loc[complete], target_log.loc[complete]
    target_simple = target_simple.loc[complete]
    vol = snapshot.loc[complete, "Volatility_20"] if "Volatility_20" in snapshot else \
        features_all["Volatility_20"]
    z_all = vol_adjusted_target(target_log, vol, cfg["target"]["volatility_epsilon"])

    # A position decided at the close of t is held through session t+1, so it pays
    # that session's financing, not t's. Everything else on the row is already
    # indexed by the decision date.
    fin = intraday_financing(snapshot, snapshot.index)
    financing_held = fin.shift(-1).reindex(complete)

    initial = cfg["sample"]["initial_train_sessions"]
    step = cfg["walk_forward"]["outer_step_sessions"]
    retune_every = cfg["walk_forward"]["retune_every_outer_steps"]
    seed = cfg["seeds"]["base"]

    if args.smoke:
        complete = complete[: initial + 3 * step]
        features_all = features_all.loc[complete]
        z_all, target_simple = z_all.loc[complete], target_simple.loc[complete]
        target_log, financing_held = target_log.loc[complete], financing_held.loc[complete]
        retune_every = 2
        outdir = ROOT / "results" / "smoke"
    else:
        outdir = ROOT / "results"
    outdir.mkdir(parents=True, exist_ok=True)

    n = len(complete)
    starts = list(range(initial, n, step))
    candidates = build_candidates(cfg)
    inner_splitter = TimeSeriesSplit(
        n_splits=cfg["inner_cv"]["n_splits"],
        test_size=cfg["inner_cv"]["test_size"],
        gap=cfg["inner_cv"]["gap"],
    )

    print(f"config          {args.config}  {config_sha[:16]}...")
    print(f"modelling set   {n} sessions, {complete.min().date()} to {complete.max().date()}")
    print(f"initial train   {initial}")
    print(f"outer steps     {len(starts)}  (step {step}, retune every {retune_every})")
    print(f"candidates      {len(candidates)}  over {len(model_configs(cfg))} fitted models")
    print()

    frozen, oos_rows, selection_log, stability = None, [], [], []
    t0 = time.perf_counter()

    for step_i, start in enumerate(starts):
        stop = min(start + step, n)
        train_idx, val_idx = complete[:start], complete[start:stop]
        Xtr, Xva = features_all.loc[train_idx], features_all.loc[val_idx]

        if step_i % retune_every == 0:
            inner: dict[tuple, list] = {}
            for tr, va in inner_splitter.split(Xtr):
                itr, iva = train_idx[tr], train_idx[va]
                fold = fit_slice(
                    features_all.loc[itr], z_all.loc[itr], target_log.loc[itr],
                    target_simple.loc[itr], features_all.loc[iva],
                    cfg, groups, seed + step_i,
                )
                if fold is None:
                    continue
                for key, res in fold["predictions"].items():
                    inner.setdefault(key, []).append(res["mu_hat"])
            concatenated = {k: pd.concat(v) for k, v in inner.items() if v}
            scored = score_candidates(
                concatenated, target_simple, financing_held, cfg, candidates, seed + step_i
            )
            frozen, why = one_standard_error_choice(scored, cfg, seed + step_i)
            selection_log.append({
                "step": step_i, "date": str(train_idx[-1].date()),
                "chosen_id": frozen.get("id"), "chosen_score": frozen.get("score"),
                "n_candidates": len(scored), **why,
            })
            print(f"  step {step_i:>3}  retune  chose {frozen.get('id')}"
                  f"   eligible {why.get('n_eligible')}/{len(scored)}")

        frozen_config = next(
            c for c in model_configs(cfg)
            if c["family"] == frozen["family"] and repr(c["params"]) == frozen["params"]
        )
        fitted = fit_slice(
            Xtr, z_all.loc[train_idx], target_log.loc[train_idx],
            target_simple.loc[train_idx], Xva, cfg, groups, seed + step_i,
            only=[frozen_config],
        )
        if fitted is None:
            continue
        res = next(iter(fitted["predictions"].values()))
        mu = res["mu_hat"]
        w = positions_from_expected_return(
            mu, cfg["costs"]["base_bps_per_side"], financing_held.loc[mu.index], frozen["delta"]
        )
        for date in mu.index:
            oos_rows.append({
                "date": date, "step": step_i, "model": frozen["family"],
                "params": frozen["params"], "delta": frozen["delta"],
                "p_short": res["proba"].loc[date, -1], "p_flat": res["proba"].loc[date, 0],
                "p_long": res["proba"].loc[date, 1], "mu_hat": mu.loc[date],
                "position": w.loc[date], "realised_o2c": target_simple.loc[date],
                "financing": financing_held.loc[date],
                "calibration_skipped": res["calibration_skipped"],
            })
        for f in fitted["features"]:
            stability.append({"step": step_i, "feature": f})

    elapsed = time.perf_counter() - t0
    oos = pd.DataFrame(oos_rows).set_index("date")
    oos.to_csv(outdir / "oos_predictions.csv", float_format="%.10g")
    pd.DataFrame(selection_log).to_csv(outdir / "selection_log.csv", index=False)
    stab = pd.DataFrame(stability).groupby("feature").size().rename("steps_selected")
    stab.sort_values(ascending=False).to_csv(outdir / "feature_stability.csv")

    (outdir / "run_manifest.json").write_text(json.dumps({
        "mode": "smoke" if args.smoke else "confirmatory",
        "config": args.config, "config_sha256": config_sha,
        "snapshot_sha256": manifest["sha256"],
        "code_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True
        ).stdout.strip(),
        "modelling_sessions": int(n), "outer_steps": len(starts),
        "oos_sessions": int(len(oos)), "seconds": round(elapsed, 1),
        "packages": {"numpy": np.__version__, "pandas": pd.__version__},
    }, indent=2), encoding="utf-8")

    print(f"\n{'structure' if args.smoke else 'run'} complete in {elapsed:.1f}s")
    print(f"  oos_predictions.csv   {oos.shape[0]} rows x {oos.shape[1]} cols")
    print(f"    columns             {list(oos.columns)}")
    print(f"    dates               {oos.index.min().date()} to {oos.index.max().date()}")
    print(f"    positions           {dict(oos.position.value_counts().sort_index())}")
    print(f"    calibration skipped {int(oos.calibration_skipped.sum())} rows")
    print(f"  selection_log.csv     {len(selection_log)} retunes")
    print(f"  feature_stability.csv {len(stab)} distinct features selected")
    print(f"  run_manifest.json     written")
    if args.smoke:
        print("\nNo performance figure is reported in smoke mode, by design.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
