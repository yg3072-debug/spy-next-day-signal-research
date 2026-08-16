"""Run a controlled chronological ablation for the Trump NLP extension.

This experiment compares the same Logistic Regression specification with and
without the frozen lagged text features. It is separate from the canonical
LightGBM holdout result reported for the main project.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

os.environ.setdefault(
    "MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "spy-signal-matplotlib")
)

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.feature_selection import VarianceThreshold
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[2]
MODEL_TABLE = ROOT / "data" / "nlp" / "trump_nlp_modeling_table.csv"
SELECTED_FEATURES = ROOT / "results" / "selected_features.csv"
CV_OUTPUT = ROOT / "results" / "trump_nlp_cv_metrics.csv"
HOLDOUT_OUTPUT = ROOT / "results" / "trump_nlp_holdout_metrics.csv"
FIGURE_OUTPUT = ROOT / "assets" / "trump_nlp_cv_comparison.png"

COVERAGE_START = pd.Timestamp("2024-07-15")
COVERAGE_END = pd.Timestamp("2026-04-23")
N_SPLITS = 5
GAP = 1
RANDOM_STATE = 42


def estimator() -> Pipeline:
    return Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("nonconstant", VarianceThreshold()),
            ("scale", StandardScaler()),
            (
                "model",
                LogisticRegression(
                    class_weight="balanced",
                    max_iter=3000,
                    random_state=RANDOM_STATE,
                ),
            ),
        ]
    )


def score(y_true: pd.Series, y_pred: np.ndarray) -> dict[str, float]:
    return {
        "accuracy": accuracy_score(y_true, y_pred),
        "balanced_accuracy": balanced_accuracy_score(y_true, y_pred),
        "macro_f1": f1_score(y_true, y_pred, average="macro"),
    }


def model_columns(data: pd.DataFrame) -> dict[str, list[str]]:
    base = pd.read_csv(SELECTED_FEATURES)["feature"].tolist()
    nlp = [column for column in data.columns if column.endswith("_lag1")]
    nlp.append("has_trump_nlp")
    return {
        "Market only": base,
        "Market + Trump NLP": base + nlp,
    }


def chronological_cv(data: pd.DataFrame, columns: dict[str, list[str]]) -> pd.DataFrame:
    rows: list[dict[str, float | int | str]] = []
    splitter = TimeSeriesSplit(n_splits=N_SPLITS, gap=GAP)
    for model_name, features in columns.items():
        fold_rows: list[dict[str, float | int | str]] = []
        for fold, (train_index, test_index) in enumerate(splitter.split(data), start=1):
            model = estimator()
            model.fit(data.iloc[train_index][features], data.iloc[train_index]["label"])
            prediction = model.predict(data.iloc[test_index][features])
            fold_score = {
                "model": model_name,
                "split": f"fold_{fold}",
                "train_rows": len(train_index),
                "test_rows": len(test_index),
                **score(data.iloc[test_index]["label"], prediction),
            }
            fold_rows.append(fold_score)
            rows.append(fold_score)

        metric_frame = pd.DataFrame(fold_rows)
        for summary, function in (("mean", "mean"), ("std", "std")):
            values = getattr(
                metric_frame[["accuracy", "balanced_accuracy", "macro_f1"]], function
            )()
            rows.append(
                {
                    "model": model_name,
                    "split": summary,
                    "train_rows": "",
                    "test_rows": "",
                    **values.to_dict(),
                }
            )
    return pd.DataFrame(rows)


def chronological_holdout(
    data: pd.DataFrame, columns: dict[str, list[str]]
) -> pd.DataFrame:
    cutoff = int(len(data) * 0.80)
    train_index = np.arange(cutoff - GAP)
    test_index = np.arange(cutoff, len(data))
    rows = []
    for model_name, features in columns.items():
        model = estimator()
        model.fit(data.iloc[train_index][features], data.iloc[train_index]["label"])
        prediction = model.predict(data.iloc[test_index][features])
        rows.append(
            {
                "model": model_name,
                "train_start": data.iloc[train_index[0]]["Date"].date().isoformat(),
                "train_end": data.iloc[train_index[-1]]["Date"].date().isoformat(),
                "test_start": data.iloc[test_index[0]]["Date"].date().isoformat(),
                "test_end": data.iloc[test_index[-1]]["Date"].date().isoformat(),
                "train_rows": len(train_index),
                "test_rows": len(test_index),
                **score(data.iloc[test_index]["label"], prediction),
            }
        )
    return pd.DataFrame(rows)


def plot_cv(cv_results: pd.DataFrame) -> None:
    means = cv_results[cv_results["split"] == "mean"].set_index("model")
    stds = cv_results[cv_results["split"] == "std"].set_index("model")
    metrics = ["balanced_accuracy", "macro_f1", "accuracy"]
    labels = ["Balanced accuracy", "Macro F1", "Accuracy"]
    models = means.index.tolist()
    x = np.arange(len(metrics))
    width = 0.34

    fig, axis = plt.subplots(figsize=(8.4, 4.8))
    colors = ["#7F8C8D", "#2F75B5"]
    for index, model_name in enumerate(models):
        values = means.loc[model_name, metrics].astype(float).to_numpy()
        errors = stds.loc[model_name, metrics].astype(float).to_numpy()
        axis.bar(
            x + (index - 0.5) * width,
            values,
            width,
            yerr=errors,
            capsize=4,
            label=model_name,
            color=colors[index],
        )
    axis.set_xticks(x, labels)
    axis.set_ylim(0.20, 0.55)
    axis.set_ylabel("Five-fold expanding-window score")
    axis.set_title("Exploratory Trump NLP ablation")
    axis.grid(axis="y", alpha=0.25)
    axis.legend(frameon=False, loc="upper left")
    fig.tight_layout()
    FIGURE_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURE_OUTPUT, dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    data = pd.read_csv(MODEL_TABLE, parse_dates=["Date"]).sort_values("Date")
    data = data[data["Date"].between(COVERAGE_START, COVERAGE_END)].reset_index(
        drop=True
    )
    if len(data) != 446:
        raise AssertionError(
            f"Expected 446 covered trading sessions, found {len(data)}"
        )

    columns = model_columns(data)
    missing = sorted(
        {item for values in columns.values() for item in values} - set(data.columns)
    )
    if missing:
        raise ValueError(f"Missing model columns: {missing}")

    cv_results = chronological_cv(data, columns)
    holdout_results = chronological_holdout(data, columns)
    CV_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    cv_results.to_csv(CV_OUTPUT, index=False)
    holdout_results.to_csv(HOLDOUT_OUTPUT, index=False)
    plot_cv(cv_results)

    print(cv_results[cv_results["split"] == "mean"].to_string(index=False))
    print(holdout_results.to_string(index=False))


if __name__ == "__main__":
    main()
