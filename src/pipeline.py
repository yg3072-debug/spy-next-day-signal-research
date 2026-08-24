"""The confirmatory procedure, built out of pieces that each see only one slice.

Every function here takes the slice it is allowed to learn from and returns
something that can be applied elsewhere. That shape is deliberate: it is what
makes the nesting order in the protocol checkable by reading the call site rather
than by trusting a comment. Nothing in this module reaches for data outside the
frame it was handed.

The pieces exist because neither `GridSearchCV` nor `CalibratedClassifierCV` can
be used. Both assume a single fixed `y`, and here the label thresholds are
re-estimated inside every fold, so the same historical session can carry
different labels in different folds.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform
from scipy.stats import rankdata
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

CLASSES = np.array([-1, 0, 1])


# ------------------------------------------------------------------------ labels

def vol_adjusted_target(target_log: pd.Series, vol: pd.Series, eps: float) -> pd.Series:
    """The quantity labels are cut from: next-session log return over its scale."""
    return target_log / (vol + eps)


def estimate_quantiles(z: pd.Series, quantiles: tuple[float, float]) -> tuple[float, float]:
    """Label thresholds. Only ever called on a training slice."""
    lo, hi = z.quantile(list(quantiles))
    return float(lo), float(hi)


def apply_labels(z: pd.Series, q_low: float, q_high: float) -> pd.Series:
    out = pd.Series(0, index=z.index, dtype=int)
    out[z <= q_low] = -1
    out[z >= q_high] = 1
    return out


# --------------------------------------------------------------- feature selection

def _rolling_spearman(x: np.ndarray, y: np.ndarray, window: int) -> np.ndarray:
    """Spearman correlation in each trailing window, vectorised.

    Ranks are taken inside the window, not globally, which is what makes it
    Spearman rather than a Pearson correlation of global ranks. Average ranks
    handle the binary features, where ties are the norm rather than the exception.
    """
    if len(x) < window:
        return np.array([])
    xw = sliding_window_view(x, window)
    yw = sliding_window_view(y, window)
    xr = rankdata(xw, axis=1)
    yr = rankdata(yw, axis=1)
    xr = xr - xr.mean(axis=1, keepdims=True)
    yr = yr - yr.mean(axis=1, keepdims=True)
    num = (xr * yr).sum(axis=1)
    den = np.sqrt((xr**2).sum(axis=1) * (yr**2).sum(axis=1))
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(den > 0, num / den, np.nan)


def information_coefficients(X: pd.DataFrame, z: pd.Series, window: int) -> pd.Series:
    """Absolute mean rolling rank correlation of each feature with the target."""
    zv = z.to_numpy(dtype=float)
    out = {}
    for col in X.columns:
        ic = _rolling_spearman(X[col].to_numpy(dtype=float), zv, window)
        out[col] = abs(np.nanmean(ic)) if ic.size and not np.isnan(ic).all() else 0.0
    return pd.Series(out)


def select_features(
    X: pd.DataFrame,
    z: pd.Series,
    groups: dict[str, str],
    cfg: dict,
) -> tuple[list[str], pd.Series]:
    """The five screening steps, run entirely inside the slice it is given.

    Returns the chosen columns and the information coefficients behind the choice,
    so that a selection can be explained after the fact rather than only observed.
    """
    ic_cfg = cfg["ic"]
    alive = X.columns[X.std(ddof=0) > 0] if cfg["drop_zero_variance"] else X.columns
    if len(alive) == 0:
        return [], pd.Series(dtype=float)

    ic = information_coefficients(X[alive], z, ic_cfg["rolling_window_sessions"])

    # Top k inside each hypothesis group, so one crowded group cannot take the slate.
    kept: list[str] = []
    for group in sorted({groups[c] for c in alive}):
        members = [c for c in alive if groups[c] == group]
        kept += list(ic[members].sort_values(ascending=False).head(cfg["per_group_top_k"]).index)

    if len(kept) > 1:
        prune = cfg["correlation_pruning"]
        corr = X[kept].corr().abs().fillna(0.0).to_numpy()
        np.fill_diagonal(corr, 1.0)
        dist = np.clip(1.0 - corr, 0.0, None)
        np.fill_diagonal(dist, 0.0)
        dist = (dist + dist.T) / 2.0                       # squareform needs exact symmetry
        labels = fcluster(
            linkage(squareform(dist, checks=False), method=prune["linkage"]),
            t=prune["cut_distance"],
            criterion="distance",
        )
        representatives = []
        for cluster in np.unique(labels):
            members = [kept[i] for i in np.where(labels == cluster)[0]]
            representatives.append(ic[members].idxmax())
        kept = representatives

    kept = list(ic[kept].sort_values(ascending=False).head(cfg["max_features"]).index)
    return kept, ic


# ------------------------------------------------------------------------ models

def make_estimator(family: str, params: dict, spec: dict, seed: int):
    """Build one candidate. Scaling is part of the estimator so it is refit per slice."""
    fixed = dict(spec.get("fixed") or {})
    fixed.pop("multi_class", None)                # removed from sklearn's newer API
    merged = {**fixed, **params}

    if family == "majority_baseline":
        return DummyClassifier(strategy="prior")
    if family == "logistic":
        return Pipeline([
            ("scale", StandardScaler()),
            ("model", LogisticRegression(random_state=seed, **merged)),
        ])
    if family == "random_forest":
        return RandomForestClassifier(random_state=seed, **merged)
    if family == "lightgbm":
        from lightgbm import LGBMClassifier
        return LGBMClassifier(random_state=seed, **merged)
    if family == "xgboost":
        from xgboost import XGBClassifier
        return XGBClassifier(random_state=seed, **merged)
    raise ValueError(f"unknown model family: {family}")


def _proba_frame(estimator, X: pd.DataFrame) -> pd.DataFrame:
    """Predicted probabilities as a frame with one column per class in CLASSES.

    A slice can be missing a class entirely; the column is then zero rather than
    absent, so downstream code never has to ask which classes were present.
    """
    raw = estimator.predict_proba(X)
    seen = getattr(estimator, "classes_", None)
    if seen is None:                                        # pipelines expose it on the last step
        seen = estimator[-1].classes_
    out = pd.DataFrame(0.0, index=X.index, columns=CLASSES)
    for j, cls in enumerate(seen):
        out[cls] = raw[:, j]
    return out


def fit_and_predict_proba(estimator, X_fit, y_fit, X_pred) -> pd.DataFrame:
    labels = np.asarray(y_fit)
    if family_is_xgboost(estimator):
        estimator.fit(X_fit, labels + 1)                    # xgboost needs 0..K-1
        raw = estimator.predict_proba(X_pred)
        return pd.DataFrame(raw, index=X_pred.index, columns=CLASSES)
    estimator.fit(X_fit, labels)
    return _proba_frame(estimator, X_pred)


def family_is_xgboost(estimator) -> bool:
    return type(estimator).__name__ == "XGBClassifier"


# ------------------------------------------------------------------- calibration

@dataclass
class SigmoidCalibrator:
    """One-vs-rest Platt scaling, then renormalise.

    Two parameters per class. Isotonic would need far more calibration points
    than a 500-session inner out-of-sample provides once it is split three ways.
    """

    models: dict = field(default_factory=dict)

    @classmethod
    def fit(cls, proba: pd.DataFrame, y: pd.Series) -> "SigmoidCalibrator":
        models = {}
        for cls_value in CLASSES:
            target = (np.asarray(y) == cls_value).astype(int)
            if target.sum() == 0 or target.sum() == len(target):
                continue                                    # nothing to calibrate against
            p = np.clip(proba[cls_value].to_numpy(), 1e-9, 1 - 1e-9)
            logit = np.log(p / (1 - p)).reshape(-1, 1)
            models[cls_value] = LogisticRegression().fit(logit, target)
        return cls(models=models)

    def transform(self, proba: pd.DataFrame) -> pd.DataFrame:
        if not self.models:
            return proba
        out = pd.DataFrame(index=proba.index, columns=CLASSES, dtype=float)
        for cls_value in CLASSES:
            p = np.clip(proba[cls_value].to_numpy(), 1e-9, 1 - 1e-9)
            if cls_value in self.models:
                logit = np.log(p / (1 - p)).reshape(-1, 1)
                out[cls_value] = self.models[cls_value].predict_proba(logit)[:, 1]
            else:
                out[cls_value] = p
        total = out.sum(axis=1).replace(0.0, np.nan)
        return out.div(total, axis=0).fillna(1.0 / len(CLASSES))


@dataclass
class IsotonicCalibrator:
    """One-vs-rest isotonic regression, then renormalise. E16 only.

    Retained as the pre-registered alternative to Platt scaling, and expected to be
    worse here rather than better: with three classes over a 500-session inner
    out-of-sample split three ways for the cross-fit, isotonic sees on the order of
    a hundred points per class, well inside the range where a free-form monotone
    fit reproduces its own calibration set. Sigmoid spends two parameters per class
    instead. Running it is how that claim gets a number attached.
    """

    models: dict = field(default_factory=dict)

    @classmethod
    def fit(cls, proba: pd.DataFrame, y: pd.Series) -> "IsotonicCalibrator":
        from sklearn.isotonic import IsotonicRegression
        models = {}
        for cls_value in CLASSES:
            target = (np.asarray(y) == cls_value).astype(int)
            if target.sum() == 0 or target.sum() == len(target):
                continue
            iso = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
            models[cls_value] = iso.fit(proba[cls_value].to_numpy(), target)
        return cls(models=models)

    def transform(self, proba: pd.DataFrame) -> pd.DataFrame:
        if not self.models:
            return proba
        out = pd.DataFrame(index=proba.index, columns=CLASSES, dtype=float)
        for cls_value in CLASSES:
            p = proba[cls_value].to_numpy()
            out[cls_value] = self.models[cls_value].predict(p) \
                if cls_value in self.models else p
        total = out.sum(axis=1).replace(0.0, np.nan)
        return out.div(total, axis=0).fillna(1.0 / len(CLASSES))


CALIBRATORS = {"sigmoid": SigmoidCalibrator, "isotonic": IsotonicCalibrator}


def get_calibrator(method: str):
    if method not in CALIBRATORS:
        raise KeyError(f"unknown calibration method {method!r}; have {sorted(CALIBRATORS)}")
    return CALIBRATORS[method]


def crossfit_out_of_fold(
    X: pd.DataFrame,
    y: pd.Series,
    build_estimator,
    splitter,
    min_base_train: int,
) -> tuple[pd.DataFrame, pd.Series]:
    """Out-of-fold probabilities from inside one slice, for fitting a calibrator.

    The calibrator must never see a prediction the base estimator made on its own
    training rows, so the probabilities it learns from come from folds the model
    did not fit on. Sub-folds whose training block is too small are skipped rather
    than fitted badly.
    """
    chunks, targets = [], []
    for train_idx, test_idx in splitter.split(X):
        if len(train_idx) < min_base_train:
            continue
        est = build_estimator()
        proba = fit_and_predict_proba(
            est, X.iloc[train_idx], y.iloc[train_idx], X.iloc[test_idx]
        )
        chunks.append(proba)
        targets.append(y.iloc[test_idx])
    if not chunks:
        return pd.DataFrame(columns=CLASSES), pd.Series(dtype=int)
    return pd.concat(chunks), pd.concat(targets)


def calibration_is_viable(y_oof: pd.Series, min_total: int, min_per_class: int) -> bool:
    if len(y_oof) < min_total:
        return False
    counts = pd.Series(y_oof).value_counts()
    return all(counts.get(c, 0) >= min_per_class for c in CLASSES)


# -------------------------------------------------------------- expected return

def class_conditional_means(returns_simple: pd.Series, labels: pd.Series) -> dict:
    """Mean realised return within each label, estimated on one slice only.

    Which slice is the whole point: scoring an inner fold must use that fold's own
    training rows, because outer-train contains the inner-validation and would let
    the score see the returns it is being graded on.
    """
    means = {}
    for cls_value in CLASSES:
        subset = returns_simple[labels == cls_value]
        means[cls_value] = float(subset.mean()) if len(subset) else 0.0
    return means


def expected_return(proba: pd.DataFrame, means: dict) -> pd.Series:
    return sum(proba[c] * means[c] for c in CLASSES)
