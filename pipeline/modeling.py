from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    roc_auc_score,
    roc_curve,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.utils.class_weight import compute_sample_weight

try:
    from xgboost import XGBClassifier
except ImportError:  # pragma: no cover - depends on local environment
    XGBClassifier = None


DEFAULT_DATA_DIR = "data/processed/modeling_v0.2"
DEFAULT_DATASET_VERSION = "dataset_modeling_v0.2"
DEFAULT_REPORT_DIR = "reports/modeling_v0.2"
DEFAULT_FIGURE_DIR = "figures/modeling"
RANDOM_STATE = 42


@dataclass(frozen=True)
class DatasetBundle:
    x_train: np.ndarray
    y_train: np.ndarray
    x_val: np.ndarray
    y_val: np.ndarray
    x_test: np.ndarray
    y_test: np.ndarray
    feature_names: np.ndarray
    manifest: dict[str, Any]
    tabular_idx: np.ndarray
    all_idx: np.ndarray


@dataclass
class FitResult:
    name: str
    feature_set: str
    estimator: Any
    feature_idx: np.ndarray
    val_scores: np.ndarray
    threshold: float
    fit_seconds: float
    metrics: dict[str, Any]


def _load_npz(path: Path) -> tuple[np.ndarray, np.ndarray]:
    with np.load(path, allow_pickle=False) as data:
        return data["X"].astype(np.float32), data["y"].astype(np.int8)


def load_dataset(data_dir: str | Path, dataset_version: str) -> DatasetBundle:
    data_dir = Path(data_dir)
    manifest = json.loads((data_dir / f"{dataset_version}.feature_manifest.json").read_text())
    x_train, y_train = _load_npz(data_dir / f"{dataset_version}.train.npz")
    x_val, y_val = _load_npz(data_dir / f"{dataset_version}.val.npz")
    x_test, y_test = _load_npz(data_dir / f"{dataset_version}.test.npz")

    feature_names = np.asarray(manifest["feature_columns"])
    tabular_names = set(manifest["numeric_columns"]) | set(manifest["one_hot_columns"])
    tabular_idx = np.asarray(
        [index for index, name in enumerate(feature_names) if name in tabular_names],
        dtype=np.int64,
    )
    return DatasetBundle(
        x_train=x_train,
        y_train=y_train,
        x_val=x_val,
        y_val=y_val,
        x_test=x_test,
        y_test=y_test,
        feature_names=feature_names,
        manifest=manifest,
        tabular_idx=tabular_idx,
        all_idx=np.arange(len(feature_names), dtype=np.int64),
    )


def _balanced_sample_weight(y: np.ndarray) -> np.ndarray:
    return compute_sample_weight(class_weight="balanced", y=y).astype(np.float32)


def _make_models(y_train: np.ndarray) -> list[tuple[str, str, Any, bool]]:
    models: list[tuple[str, str, Any, bool]] = [
        (
            "majority_baseline",
            "none",
            DummyClassifier(strategy="most_frequent"),
            False,
        ),
        (
            "logistic_tabular",
            "tabular",
            Pipeline(
                [
                    ("scaler", StandardScaler()),
                    (
                        "classifier",
                        LogisticRegression(
                            max_iter=2000,
                            class_weight="balanced",
                            random_state=RANDOM_STATE,
                        ),
                    ),
                ]
            ),
            False,
        ),
        (
            "logistic_all_features",
            "all",
            Pipeline(
                [
                    ("scaler", StandardScaler()),
                    (
                        "classifier",
                        LogisticRegression(
                            max_iter=2000,
                            class_weight="balanced",
                            random_state=RANDOM_STATE,
                        ),
                    ),
                ]
            ),
            False,
        ),
    ]

    if XGBClassifier is not None:
        xgb_params = {
            "n_estimators": 250,
            "max_depth": 3,
            "learning_rate": 0.05,
            "subsample": 0.85,
            "colsample_bytree": 0.85,
            "reg_lambda": 2.0,
            "objective": "binary:logistic",
            "eval_metric": "auc",
            "tree_method": "hist",
            "random_state": RANDOM_STATE,
            "n_jobs": 4,
        }
        models.extend(
            [
                (
                    "xgboost_tabular",
                    "tabular",
                    XGBClassifier(**xgb_params),
                    True,
                ),
                (
                    "xgboost_all_features",
                    "all",
                    XGBClassifier(**xgb_params),
                    True,
                ),
            ]
        )
    return models


def _feature_index(bundle: DatasetBundle, feature_set: str) -> np.ndarray:
    if feature_set == "tabular":
        return bundle.tabular_idx
    if feature_set == "all":
        return bundle.all_idx
    return np.asarray([], dtype=np.int64)


def _fit_estimator(
    estimator: Any,
    x_train: np.ndarray,
    y_train: np.ndarray,
    use_sample_weight: bool,
) -> Any:
    if x_train.shape[1] == 0:
        estimator.fit(np.zeros((len(y_train), 1), dtype=np.float32), y_train)
        return estimator
    if use_sample_weight:
        estimator.fit(x_train, y_train, sample_weight=_balanced_sample_weight(y_train))
    else:
        estimator.fit(x_train, y_train)
    return estimator


def _score_estimator(estimator: Any, x_eval: np.ndarray) -> np.ndarray:
    if x_eval.shape[1] == 0:
        x_eval = np.zeros((len(x_eval), 1), dtype=np.float32)
    if hasattr(estimator, "predict_proba"):
        return estimator.predict_proba(x_eval)[:, 1].astype(np.float32)
    decision = estimator.decision_function(x_eval)
    return (1.0 / (1.0 + np.exp(-decision))).astype(np.float32)


def _best_threshold(y_true: np.ndarray, scores: np.ndarray) -> float:
    unique_scores = np.unique(scores)
    if len(unique_scores) == 1:
        return 0.5
    thresholds = np.unique(np.quantile(scores, np.linspace(0.01, 0.99, 99)))
    best = 0.5
    best_score = -1.0
    for threshold in thresholds:
        pred = (scores >= threshold).astype(np.int8)
        score = f1_score(y_true, pred, average="macro", zero_division=0)
        if score > best_score:
            best = float(threshold)
            best_score = float(score)
    return best


def _safe_roc_auc(y_true: np.ndarray, scores: np.ndarray) -> float:
    if len(np.unique(scores)) == 1:
        return 0.5
    return float(roc_auc_score(y_true, scores))


def _metrics_for(
    y_true: np.ndarray,
    scores: np.ndarray,
    threshold: float,
    prefix: str,
) -> dict[str, Any]:
    pred = (scores >= threshold).astype(np.int8)
    return {
        f"{prefix}_roc_auc": _safe_roc_auc(y_true, scores),
        f"{prefix}_average_precision": float(average_precision_score(y_true, scores)),
        f"{prefix}_brier": float(brier_score_loss(y_true, scores)),
        f"{prefix}_threshold": float(threshold),
        f"{prefix}_macro_f1": float(f1_score(y_true, pred, average="macro", zero_division=0)),
        f"{prefix}_positive_f1": float(f1_score(y_true, pred, pos_label=1, zero_division=0)),
        f"{prefix}_balanced_accuracy": float(balanced_accuracy_score(y_true, pred)),
        f"{prefix}_confusion_matrix": confusion_matrix(y_true, pred).tolist(),
    }


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, np.ndarray):
        return _json_ready(value.tolist())
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        if not np.isfinite(value):
            return None
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def _classification_report_text(
    name: str,
    y_true: np.ndarray,
    scores: np.ndarray,
    threshold: float,
) -> str:
    pred = (scores >= threshold).astype(np.int8)
    return (
        f"{name}\n"
        f"threshold={threshold:.6f}\n"
        f"{classification_report(y_true, pred, digits=4, zero_division=0)}\n"
        f"confusion_matrix={confusion_matrix(y_true, pred).tolist()}\n"
    )


def train_and_evaluate(
    data_dir: str | Path = DEFAULT_DATA_DIR,
    dataset_version: str = DEFAULT_DATASET_VERSION,
    report_dir: str | Path = DEFAULT_REPORT_DIR,
    figure_dir: str | Path = DEFAULT_FIGURE_DIR,
) -> dict[str, Any]:
    report_dir = Path(report_dir)
    figure_dir = Path(figure_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)

    bundle = load_dataset(data_dir, dataset_version)
    results: list[FitResult] = []
    report_blocks: list[str] = []

    for name, feature_set, estimator, use_sample_weight in _make_models(bundle.y_train):
        feature_idx = _feature_index(bundle, feature_set)
        x_train = bundle.x_train[:, feature_idx] if len(feature_idx) else np.empty((len(bundle.y_train), 0))
        x_val = bundle.x_val[:, feature_idx] if len(feature_idx) else np.empty((len(bundle.y_val), 0))
        start = time.perf_counter()
        estimator = _fit_estimator(estimator, x_train, bundle.y_train, use_sample_weight)
        fit_seconds = time.perf_counter() - start
        val_scores = _score_estimator(estimator, x_val)
        threshold = _best_threshold(bundle.y_val, val_scores)
        metrics = {
            "model": name,
            "feature_set": feature_set,
            "feature_count": int(len(feature_idx)),
            "fit_seconds": round(fit_seconds, 3),
        }
        metrics.update(_metrics_for(bundle.y_val, val_scores, threshold, "val"))
        results.append(
            FitResult(
                name=name,
                feature_set=feature_set,
                estimator=estimator,
                feature_idx=feature_idx,
                val_scores=val_scores,
                threshold=threshold,
                fit_seconds=fit_seconds,
                metrics=metrics,
            )
        )
        report_blocks.append(
            _classification_report_text(
                f"Validation: {name}",
                bundle.y_val,
                val_scores,
                threshold,
            )
        )

    metrics_df = pd.DataFrame([result.metrics for result in results]).sort_values(
        ["val_roc_auc", "val_macro_f1"],
        ascending=False,
    )
    selected_name = str(metrics_df.iloc[0]["model"])
    selected = next(result for result in results if result.name == selected_name)

    x_test = bundle.x_test[:, selected.feature_idx] if len(selected.feature_idx) else np.empty((len(bundle.y_test), 0))
    test_scores = _score_estimator(selected.estimator, x_test)
    test_metrics = _metrics_for(bundle.y_test, test_scores, selected.threshold, "test")
    selected_mask = metrics_df["model"] == selected.name
    for key in test_metrics:
        metrics_df[key] = pd.Series([None] * len(metrics_df), dtype="object")
    selected_index = metrics_df.index[selected_mask][0]
    for key, value in test_metrics.items():
        metrics_df.at[selected_index, key] = value

    metrics_df.to_csv(report_dir / "modeling_metrics.csv", index=False)
    (report_dir / "validation_classification_reports.txt").write_text(
        "\n".join(report_blocks),
        encoding="utf-8",
    )
    (report_dir / "selected_test_classification_report.txt").write_text(
        _classification_report_text(
            f"Selected test: {selected.name}",
            bundle.y_test,
            test_scores,
            selected.threshold,
        ),
        encoding="utf-8",
    )
    joblib.dump(
        {
            "model_name": selected.name,
            "feature_set": selected.feature_set,
            "feature_idx": selected.feature_idx,
            "feature_names": bundle.feature_names[selected.feature_idx],
            "threshold": selected.threshold,
            "estimator": selected.estimator,
        },
        report_dir / "selected_model.joblib",
    )

    _plot_metrics(metrics_df, figure_dir / "model_comparison_validation.png")
    _plot_curves(
        bundle.y_val,
        selected.val_scores,
        figure_dir / "selected_validation_curves.png",
        f"{selected.name} validation",
    )
    _plot_confusion(
        bundle.y_val,
        selected.val_scores,
        selected.threshold,
        figure_dir / "selected_validation_confusion.png",
        f"{selected.name} validation",
    )
    _plot_confusion(
        bundle.y_test,
        test_scores,
        selected.threshold,
        figure_dir / "selected_test_confusion.png",
        f"{selected.name} test",
    )
    _plot_importance(selected, bundle, figure_dir / "selected_feature_importance.png")

    summary = {
        "dataset_version": dataset_version,
        "data_dir": str(data_dir),
        "report_dir": str(report_dir),
        "figure_dir": str(figure_dir),
        "class_balance": {
            "train": np.bincount(bundle.y_train, minlength=2).tolist(),
            "val": np.bincount(bundle.y_val, minlength=2).tolist(),
            "test": np.bincount(bundle.y_test, minlength=2).tolist(),
        },
        "models": _json_ready(metrics_df.to_dict(orient="records")),
        "selected_model": selected.name,
        "selection_rule": "highest validation ROC-AUC, with validation macro-F1 used for thresholded sanity check",
        "selected_threshold": selected.threshold,
        "test_metrics_for_selected_model": test_metrics,
    }
    (report_dir / "modeling_summary.json").write_text(
        json.dumps(_json_ready(summary), indent=2, allow_nan=False),
        encoding="utf-8",
    )
    return summary


def _plot_metrics(metrics_df: pd.DataFrame, path: Path) -> None:
    plot_df = metrics_df[
        ["model", "val_roc_auc", "val_average_precision", "val_macro_f1", "val_balanced_accuracy"]
    ].melt(id_vars="model", var_name="metric", value_name="value")
    fig, ax = plt.subplots(figsize=(10, 5))
    for metric, group in plot_df.groupby("metric"):
        ax.plot(group["model"], group["value"], marker="o", label=metric.replace("val_", ""))
    ax.set_ylim(0, 1.03)
    ax.set_ylabel("Score")
    ax.set_xlabel("")
    ax.set_title("Validation model comparison")
    ax.tick_params(axis="x", rotation=25)
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight", dpi=160)
    plt.close(fig)


def _plot_curves(y_true: np.ndarray, scores: np.ndarray, path: Path, title: str) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    fpr, tpr, _ = roc_curve(y_true, scores)
    precision, recall, _ = precision_recall_curve(y_true, scores)
    axes[0].plot(fpr, tpr)
    axes[0].plot([0, 1], [0, 1], linestyle="--", color="gray")
    axes[0].set_title(f"ROC AUC={roc_auc_score(y_true, scores):.3f}")
    axes[0].set_xlabel("False positive rate")
    axes[0].set_ylabel("True positive rate")
    axes[1].plot(recall, precision)
    axes[1].set_title(f"PR AUC={average_precision_score(y_true, scores):.3f}")
    axes[1].set_xlabel("Recall")
    axes[1].set_ylabel("Precision")
    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight", dpi=160)
    plt.close(fig)


def _plot_confusion(
    y_true: np.ndarray,
    scores: np.ndarray,
    threshold: float,
    path: Path,
    title: str,
) -> None:
    pred = (scores >= threshold).astype(np.int8)
    matrix = confusion_matrix(y_true, pred)
    fig, ax = plt.subplots(figsize=(4.8, 4.2))
    image = ax.imshow(matrix, cmap="Blues")
    ax.set_xticks([0, 1], labels=["pred 0", "pred 1"])
    ax.set_yticks([0, 1], labels=["true 0", "true 1"])
    for row in range(2):
        for col in range(2):
            ax.text(col, row, str(matrix[row, col]), ha="center", va="center")
    ax.set_title(f"{title}\nthreshold={threshold:.3f}")
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight", dpi=160)
    plt.close(fig)


def _plot_importance(selected: FitResult, bundle: DatasetBundle, path: Path) -> None:
    names = bundle.feature_names[selected.feature_idx]
    estimator = selected.estimator
    values: np.ndarray | None = None
    if hasattr(estimator, "feature_importances_"):
        values = estimator.feature_importances_
    elif isinstance(estimator, Pipeline):
        classifier = estimator.named_steps.get("classifier")
        if hasattr(classifier, "coef_"):
            values = np.abs(classifier.coef_[0])
    if values is None or len(values) == 0:
        return
    top_idx = np.argsort(values)[-20:][::-1]
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.barh(np.arange(len(top_idx)), values[top_idx][::-1])
    ax.set_yticks(np.arange(len(top_idx)), labels=names[top_idx][::-1])
    ax.set_xlabel("Importance")
    ax.set_title(f"Top features: {selected.name}")
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight", dpi=160)
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train and evaluate review_concern models.")
    parser.add_argument("--data-dir", default=DEFAULT_DATA_DIR)
    parser.add_argument("--dataset-version", default=DEFAULT_DATASET_VERSION)
    parser.add_argument("--report-dir", default=DEFAULT_REPORT_DIR)
    parser.add_argument("--figure-dir", default=DEFAULT_FIGURE_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = train_and_evaluate(
        data_dir=args.data_dir,
        dataset_version=args.dataset_version,
        report_dir=args.report_dir,
        figure_dir=args.figure_dir,
    )
    print(json.dumps(_json_ready(summary), indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
