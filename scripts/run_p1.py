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
    CLASSES, apply_labels, brier_skill, calibration_is_viable, get_calibrator,
    multiclass_brier,
    class_conditional_means, crossfit_out_of_fold, estimate_quantiles,
    expected_return, fit_and_predict_proba, make_estimator, select_features,
    vol_adjusted_target,
)
from src.stats import TRADING_DAYS, bootstrap_statistic, sharpe  # noqa: E402
from src.strategy import positions_from_expected_return  # noqa: E402
from src.execution import get_spec  # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))
from build_benchmarks import cash_return, intraday_financing, load_snapshot  # noqa: E402


# ------------------------------------------------------------------- candidates

def deep_merge(base: dict, over: dict) -> dict:
    """Overlay wins at the leaves; dictionaries merge, everything else replaces.

    A list replaces rather than extends, so an overlay that narrows a grid narrows
    it rather than adding to it. That is the behaviour the E-group needs: E5 fixes
    the model family by supplying one family, not by appending a fifth.
    """
    out = dict(base)
    for key, value in (over or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def build_candidates(cfg: dict) -> list[dict]:
    """Every model configuration, in the order the simplicity key ranks them.

    Delta is fixed, not selected. Selecting over it made the inner
    cross-validation choose a model and a trading frequency at the same time, and
    because delta drives the participation rate directly, the winner was reliably
    whichever candidate traded least — a Sharpe ranked first out of 92 while being
    estimated on about 30 non-zero observations. The margins are a declared
    sensitivity now, not a decision this procedure makes.
    """
    delta = float(cfg["position_rule"]["delta_multiple"])
    # E5-E8 hold the family fixed for the whole sample. Restricting here rather than
    # by overriding `models` in the overlay is deliberate: a dict overlay merges, so
    # supplying one family would silently leave the other four in place.
    keep = cfg["selection"].get("restrict_to_families")
    families = {k: v for k, v in cfg["models"].items() if k in keep} if keep         else cfg["models"]
    if keep and not families:
        raise KeyError(f"restrict_to_families={keep} matches no family in the grid")
    out = []
    for family, spec in families.items():
        grid = spec.get("grid")
        combos = (
            [dict(zip(grid, values)) for values in itertools.product(*grid.values())]
            if isinstance(grid, dict) else list(grid)
        )
        for rank, params in enumerate(combos):
            out.append({
                "family": family, "params": params, "delta": delta,
                "complexity_rank": spec["complexity_rank"],
                "within_family_rank": rank, "spec": spec,
                "id": f"{family}|{params}",
            })
    out.sort(key=lambda c: (c["complexity_rank"], c["within_family_rank"]))
    return out


def model_configs(cfg: dict) -> list[dict]:
    """One entry per fitted model. With delta fixed, this is the candidate list."""
    return build_candidates(cfg)


def _predict_only(estimator, X: pd.DataFrame) -> pd.DataFrame:
    """Probabilities from an already-fitted estimator, without refitting it."""
    from src.pipeline import _proba_frame, family_is_xgboost
    if family_is_xgboost(estimator):
        return pd.DataFrame(estimator.predict_proba(X), index=X.index, columns=CLASSES)
    return _proba_frame(estimator, X)


def net_returns(mu, realised, carry, cost_bps, delta, spec=None):
    """Positions from the band, and the net excess return they earn.

    `spec` decides both, because the two execution specifications disagree about
    what a position costs and about what the band has to clear.
    """
    spec = spec or get_spec("primary_open_to_close")
    w = spec.positions(mu, cost_bps, carry, delta)
    return w, spec.net(w, realised, carry, cost_bps)


# ------------------------------------------------------------------- one fold

def fit_slice(
    X_train, z_train, target_log_train, returns_train, X_pred,
    cfg, groups, seed, only=None, also_predict_train=False, calibration_log=None,
):
    """Everything a slice is allowed to learn, learned from that slice alone.

    Returns calibrated probabilities on `X_pred`, the class-conditional means, the
    features chosen, and whether calibration was possible. With
    `also_predict_train` it additionally returns in-sample predictions from the
    same fitted model, which feed the train-minus-validation gap reported in the
    diagnostics file.
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
        calibrator = get_calibrator(cfg["calibration"]["method"]).fit(oof_proba, oof_y) \
            if viable else None

        # The calibration diagnostics config/p1.yaml requires. The out-of-fold
        # probabilities are genuinely out-of-sample for the base estimator, so the
        # "before" Brier is an honest number.
        #
        # The "after" is not, and is labelled accordingly: the calibrator was fitted
        # on exactly these points, so applying it back to them is in-sample for the
        # calibrator and will flatter it. Reporting the pair without that label
        # would be the more comfortable choice and the wrong one. The genuinely
        # out-of-sample calibration evidence is the outer-OOS reliability curve,
        # which is built from results/oos_predictions.csv rather than from here.
        if calibration_log is not None and len(oof_y):
            base_rate = pd.Series(
                {c: float((np.asarray(y_train) == c).mean()) for c in CLASSES})
            after = calibrator.transform(oof_proba) if calibrator else oof_proba
            calibration_log.append({
                "family": candidate["family"], "params": repr(candidate["params"]),
                "n_oof": int(len(oof_y)),
                "calibration_skipped": not viable,
                "inner_oos_brier": multiclass_brier(oof_proba, oof_y),
                "inner_oos_brier_skill_vs_train_base_rate":
                    brier_skill(oof_proba, oof_y, base_rate),
                "brier_before_calibration": multiclass_brier(oof_proba, oof_y),
                "brier_after_calibration_in_sample_for_calibrator":
                    multiclass_brier(after, oof_y),
                **{f"base_rate_{c}": base_rate[c] for c in CLASSES},
            })

        estimator = build()
        raw = fit_and_predict_proba(estimator, Xt, y_train, Xp)
        proba = calibrator.transform(raw) if calibrator else raw
        key = (candidate["family"], repr(candidate["params"]))
        entry = {
            "mu_hat": expected_return(proba, means),
            "proba": proba,
            "proba_raw": raw,
            "calibration_skipped": not viable,
        }
        if also_predict_train:
            raw_in = _predict_only(estimator, Xt)
            proba_in = calibrator.transform(raw_in) if calibrator else raw_in
            entry["mu_hat_train"] = expected_return(proba_in, means)
        results[key] = entry

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
    train_scores: dict | None = None,
) -> pd.DataFrame:
    """Net Sharpe of every candidate on the concatenated inner out-of-sample.

    Computed once on the concatenated series, never as an average of per-fold
    Sharpe ratios: the average of fold Sharpes is not the Sharpe of the series,
    and it hides drift between folds.

    `train_scores` carries a mean in-sample score per candidate, averaged over
    folds. The protocol's objection to averaging across folds is about the metric
    that decides something; this one only ever appears in the diagnostics file.
    """
    train_scores = train_scores or {}
    cost = cfg["selection"]["metric_cost_bps_per_side"]
    min_active = cfg["selection"]["constraints"]["min_active_positions_inner_oos"]
    rows = []
    for cand in candidates:
        key = (cand["family"], repr(cand["params"]))
        mu = inner.get(key)
        if mu is None or mu.empty:
            continue
        w, net = net_returns(mu, realised, financing_held, cost, cand["delta"])
        active = int((w != 0).sum())
        s = sharpe(net.to_numpy())
        in_sample = train_scores.get(key, np.nan)
        rows.append({
            "id": cand["id"], "family": cand["family"], "params": repr(cand["params"]),
            "delta": cand["delta"], "complexity_rank": cand["complexity_rank"],
            "within_family_rank": cand["within_family_rank"],
            "active_positions": active,
            "turnover_per_year": float(w.diff().abs().fillna(0).mean() * TRADING_DAYS),
            "score": s,
            "in_sample_score": in_sample,
            "train_minus_oos_score": in_sample - s,
            "degenerate": active < min_active or not np.isfinite(s),
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
    ap.add_argument("--overlay", default=None,
                    help="YAML merged over --config; an exploratory specification")
    ap.add_argument("--outdir", default=None, help="where results go; defaults to results/")
    args = ap.parse_args()

    cfg = yaml.safe_load((ROOT / args.config).read_bytes())
    config_sha = hashlib.sha256((ROOT / args.config).read_bytes()).hexdigest()

    # An overlay never edits the frozen file. The P1 hash below is still the hash of
    # config/p1.yaml, and the overlay is recorded beside it with its own digest, so a
    # reader can tell an exploratory run from the confirmatory one at a glance.
    overlay_sha = None
    if args.overlay:
        raw = (ROOT / args.overlay).read_bytes()
        overlay_sha = hashlib.sha256(raw).hexdigest()
        cfg = deep_merge(cfg, yaml.safe_load(raw) or {})

    # Parameters the specification owns are passed to it, not left at their
    # defaults while the configuration quietly disagrees. See get_spec.
    spec_kwargs = {}
    if cfg["meta"]["execution_specification"] == "alternative_close_to_close":
        spec_kwargs["borrow_annual_bps"] = float(cfg["costs"]["borrow_annual_bps"])
    spec = get_spec(cfg["meta"]["execution_specification"], **spec_kwargs)
    snapshot, manifest = load_snapshot(cfg["sample"].get("snapshot_dir"))

    # E20 substitutes the oil factor at the snapshot, so every downstream feature
    # name is unchanged and the two runs stay comparable. The substitution is not
    # cosmetic: front-month WTI settled at -$37.63 on 2020-04-20, which makes
    # log(OIL_t / OIL_{t-k}) undefined for every lag k spanning that date. Those
    # rows leave the modelling set entirely, and the count is printed rather than
    # absorbed silently, because the shrunken sample is most of what E20 shows.
    oil = cfg.get("features", {}).get("oil_series", "OIL")
    if oil != "OIL":
        if oil not in snapshot.columns:
            raise KeyError(f"{oil} is not in the snapshot; have {sorted(snapshot.columns)}")
        n_nonpositive = int((snapshot[oil] <= 0).sum())
        snapshot = snapshot.assign(OIL=snapshot[oil])
        print(f"oil factor      {oil} substituted for Brent"
              f"  ({n_nonpositive} non-positive settlements)")

    features_all, registry = build_features(snapshot)
    groups = {f.name: f.group for f in registry}

    # E1-E4 drop a whole hypothesis group before selection ever sees it, which is
    # not the same as selection happening to leave it out.
    dropped = set(cfg["feature_selection"].get("exclude_groups") or [])
    if dropped:
        keep = [f.name for f in registry if f.group not in dropped]
        missing = dropped - {f.group for f in registry}
        if missing:
            raise KeyError(f"exclude_groups names groups that do not exist: {sorted(missing)}")
        features_all = features_all[keep]
        groups = {k: v for k, v in groups.items() if k in set(keep)}

    # The alternative specification generates its signal before the close it trades
    # at, so every feature carries one more session of lag. Shifting the matrix is
    # the whole of that change and it must happen before anything is selected.
    if spec.extra_feature_lag:
        features_all = features_all.shift(spec.extra_feature_lag)

    # §9.1's incremental test: the same procedure, the same folds, the same sample,
    # differing only in whether the alternative-data columns are present. The
    # market-only arm therefore also restricts to the overlap -- comparing a
    # market-only run on the full sample against a market-plus-news run on the
    # overlap would confound the feature set with the window.
    alt_cfg = cfg.get("alt_data") or {}
    alt_window = None
    if alt_cfg:
        from src.altdata import REGISTRY as ALT_REGISTRY
        from src.altdata import build_news_features, build_truth_social_features
        builders = {"news": build_news_features, "truth_social": build_truth_social_features}
        spans, blocks = [], []
        for source in alt_cfg["sources"]:
            built = builders[source](snapshot.index)
            per_doc = ROOT / "data" / "alt" / {
                "news": "news_headlines_sessions.csv",
                "truth_social": "truth_social_sessions.csv"}[source]
            if per_doc.exists():
                table = pd.read_csv(per_doc, usecols=["session"], parse_dates=["session"])
                spans.append((table.session.min(), table.session.max()))
            else:
                # Without the per-document file, the span is the range over which the
                # aggregate reports any document at all -- the same window.
                count = built[f"{'news' if source == 'news' else 'truth'}_doc_count"]
                live = count.index[count > 0]
                spans.append((live.min(), live.max()))
            blocks.append(built)
        alt = pd.concat(blocks, axis=1)

        # The placebo. A positive shift attaches session t-k's text to session t,
        # which is stale but legitimate information. A NEGATIVE shift attaches text
        # from the future, and is a positive control rather than a placebo: if
        # tomorrow's headlines do not improve the result either, the pipeline cannot
        # detect this kind of information at all, and a null from the real alignment
        # says less than it appears to.
        k = int(alt_cfg.get("placebo_shift_sessions", 0))
        if k:
            alt = alt.shift(k)

        if alt_cfg.get("include_columns", True):
            features_all = features_all.join(alt, how="left")
            groups.update({f.name: f.group for f in ALT_REGISTRY})
        alt_window = (max(a for a, _ in spans), min(b for _, b in spans))

    target_simple = spec.target(snapshot)
    target_log = np.log1p(target_simple).rename("target_log")

    complete = features_all.dropna().index.intersection(target_simple.dropna().index)
    if alt_window is not None:
        lo, hi = alt_window
        # A placebo shift moves the alternative data off the front or back of its own
        # span, so the usable window shrinks by |k| sessions on one side. Both arms of
        # a comparison must be run at the same shift to stay on identical rows.
        complete = complete[(complete >= lo) & (complete <= hi)]
    features_all, target_log = features_all.loc[complete], target_log.loc[complete]
    target_simple = target_simple.loc[complete]
    vol = snapshot.loc[complete, "Volatility_20"] if "Volatility_20" in snapshot else \
        features_all["Volatility_20"]
    z_all = vol_adjusted_target(target_log, vol, cfg["target"]["volatility_epsilon"])

    # A position decided at the close of t is held through session t+1, so it pays
    # that session's financing, not t's. Everything else on the row is already
    # indexed by the decision date.
    financing_held = spec.carry(snapshot, complete)

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
    if args.outdir:
        outdir = ROOT / args.outdir
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
    if args.overlay:
        print(f"overlay         {args.overlay}  {overlay_sha[:16]}...")
    print(f"execution       {spec.name}")
    if alt_cfg:
        shift = int(alt_cfg.get("placebo_shift_sessions", 0))
        arm = "market + alt" if alt_cfg.get("include_columns", True) else "market only"
        print(f"alternative     {alt_cfg['sources']}  arm={arm}  shift={shift:+d}")
    if dropped:
        print(f"excluded groups {sorted(dropped)}  -> {features_all.shape[1]} features remain")
    print(f"modelling set   {n} sessions, {complete.min().date()} to {complete.max().date()}")
    print(f"initial train   {initial}")
    print(f"outer steps     {len(starts)}  (step {step}, retune every {retune_every})")
    print(f"candidates      {len(candidates)}  over {len(model_configs(cfg))} fitted models")
    print()

    frozen, oos_rows, selection_log, stability = None, [], [], []
    candidate_diagnostics, calibration_rows, outer_calibration = [], [], []
    t0 = time.perf_counter()

    for step_i, start in enumerate(starts):
        stop = min(start + step, n)
        lo = 0
        if cfg["walk_forward"].get("window") == "rolling":
            lo = max(0, start - int(cfg["walk_forward"]["rolling_sessions"]))
        train_idx, val_idx = complete[lo:start], complete[start:stop]
        Xtr, Xva = features_all.loc[train_idx], features_all.loc[val_idx]

        if step_i % retune_every == 0:
            inner: dict[tuple, list] = {}
            fold_train: dict[tuple, list] = {}
            cost = cfg["selection"]["metric_cost_bps_per_side"]
            for fold_i, (tr, va) in enumerate(inner_splitter.split(Xtr)):
                itr, iva = train_idx[tr], train_idx[va]
                fold_cal: list[dict] = []
                fold = fit_slice(
                    features_all.loc[itr], z_all.loc[itr], target_log.loc[itr],
                    target_simple.loc[itr], features_all.loc[iva],
                    cfg, groups, seed + step_i, also_predict_train=True,
                    calibration_log=fold_cal,
                )
                for row in fold_cal:
                    calibration_rows.append({"step": step_i, "inner_fold": fold_i,
                                             "date": str(train_idx[-1].date()), **row})
                if fold is None:
                    continue
                for key, res in fold["predictions"].items():
                    inner.setdefault(key, []).append(res["mu_hat"])
                    _, net_in = net_returns(
                        res["mu_hat_train"], target_simple, financing_held,
                        cost, candidates[0]["delta"], spec,
                    )
                    fold_train.setdefault(key, []).append(sharpe(net_in.to_numpy()))
            concatenated = {k: pd.concat(v) for k, v in inner.items() if v}
            train_scores = {k: float(np.nanmean(v)) for k, v in fold_train.items()}
            scored = score_candidates(
                concatenated, target_simple, financing_held, cfg, candidates,
                seed + step_i, train_scores=train_scores,
            )
            frozen, why = one_standard_error_choice(scored, cfg, seed + step_i)

            # Every candidate, with the numbers behind the choice. Diagnostics, not
            # gates: a reader can see why the rule picked what it picked without
            # any of these becoming an extra threshold.
            se_cfg = cfg["selection"]["standard_error"]
            diag = scored.drop(columns=["net"]).copy()
            diag.insert(0, "step", step_i)
            diag.insert(1, "date", str(train_idx[-1].date()))
            diag["standard_error"] = [
                bootstrap_statistic(row.net, sharpe, se_cfg["block_sessions"],
                                    se_cfg["reps"], seed=seed + step_i + se_cfg["seed_offset"])["se"]
                if not row.degenerate else np.nan
                for row in scored.itertuples()
            ]
            diag["chosen"] = diag.id == frozen.get("id")
            candidate_diagnostics.append(diag)

            # Flagged, not corrected. When the baseline wins the one-standard-error
            # rule, the positions that follow compare an unconditional drift estimate
            # against the prevailing cost level and carry no feature-based signal.
            # Protocol A.4.1 says why no rule forces them flat.
            selection_log.append({
                "step": step_i, "date": str(train_idx[-1].date()),
                "chosen_id": frozen.get("id"), "chosen_score": frozen.get("score"),
                "baseline_selected": frozen.get("family") == "majority_baseline",
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
        w = spec.positions(
            mu, cfg["costs"]["base_bps_per_side"], financing_held, frozen["delta"]
        )
        for date in mu.index:
            oos_rows.append({
                "date": date, "step": step_i, "model": frozen["family"],
                "params": frozen["params"], "delta": frozen["delta"],
                "p_short": res["proba"].loc[date, -1], "p_flat": res["proba"].loc[date, 0],
                "p_long": res["proba"].loc[date, 1], "mu_hat": mu.loc[date],
                "position": w.loc[date],
                spec.return_column: target_simple.loc[date],
                spec.carry_column: financing_held.loc[date],
                "calibration_skipped": res["calibration_skipped"],
            })
        for f in fitted["features"]:
            stability.append({"step": step_i, "feature": f})

        # Outer-validation probabilities before and after calibration, with the
        # label the outer-train quantiles imply. This is the only calibration
        # evidence in the study that is out-of-sample for the calibrator as well as
        # for the model, which is what makes "did calibrating help?" answerable.
        q_low, q_high = fitted["quantiles"]
        z_val = z_all.loc[mu.index]
        y_val = apply_labels(z_val, q_low, q_high)
        for date in mu.index:
            outer_calibration.append({
                "date": date, "step": step_i, "label": int(y_val.loc[date]),
                "raw_short": res["proba_raw"].loc[date, -1],
                "raw_flat": res["proba_raw"].loc[date, 0],
                "raw_long": res["proba_raw"].loc[date, 1],
                "cal_short": res["proba"].loc[date, -1],
                "cal_flat": res["proba"].loc[date, 0],
                "cal_long": res["proba"].loc[date, 1],
                "calibration_skipped": res["calibration_skipped"],
            })

    elapsed = time.perf_counter() - t0
    oos = pd.DataFrame(oos_rows).set_index("date")
    oos.to_csv(outdir / "oos_predictions.csv", float_format="%.10g")
    pd.DataFrame(selection_log).to_csv(outdir / "selection_log.csv", index=False)
    stab = pd.DataFrame(stability).groupby("feature").size().rename("steps_selected")
    stab.sort_values(ascending=False).to_csv(outdir / "feature_stability.csv")
    if candidate_diagnostics:
        pd.concat(candidate_diagnostics).to_csv(
            outdir / "candidate_diagnostics.csv", index=False, float_format="%.8g"
        )
    if calibration_rows:
        pd.DataFrame(calibration_rows).to_csv(
            outdir / "calibration_diagnostics.csv", index=False, float_format="%.8g"
        )
    if outer_calibration:
        pd.DataFrame(outer_calibration).set_index("date").to_csv(
            outdir / "outer_calibration.csv", float_format="%.10g"
        )

    (outdir / "run_manifest.json").write_text(json.dumps({
        "mode": "smoke" if args.smoke else ("exploratory" if args.overlay else "confirmatory"),
        "config": args.config, "config_sha256": config_sha,
        "overlay": args.overlay, "overlay_sha256": overlay_sha,
        "execution_specification": spec.name,
        "execution_parameters": spec_kwargs,
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
    if candidate_diagnostics:
        nd = sum(len(d) for d in candidate_diagnostics)
        print(f"  candidate_diagnostics {nd} rows ({len(candidate_diagnostics)} retunes"
              f" x {len(candidate_diagnostics[0])} candidates)")
    print(f"  feature_stability.csv {len(stab)} distinct features selected")
    if calibration_rows:
        print(f"  calibration_diagnostics {len(calibration_rows)} rows "
              f"({len(set(r['step'] for r in calibration_rows))} retunes"
              f" x {cfg['inner_cv']['n_splits']} inner folds x candidates)")
    print(f"  run_manifest.json     written")
    if args.smoke:
        print("\nNo performance figure is reported in smoke mode, by design.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
