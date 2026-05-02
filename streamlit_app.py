from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import streamlit as st


ROOT = Path(__file__).resolve().parent
DATASET_VERSION = "dataset_modeling_v0.2"
DATA_DIR = ROOT / "data" / "processed" / "modeling_v0.2"
MODEL_PATH = ROOT / "reports" / "modeling_v0.2" / "selected_model.joblib"
SUMMARY_PATH = ROOT / "reports" / "modeling_v0.2" / "modeling_summary.json"
MANIFEST_PATH = DATA_DIR / f"{DATASET_VERSION}.feature_manifest.json"


@st.cache_resource
def load_model() -> dict[str, Any]:
    return joblib.load(MODEL_PATH)


@st.cache_data
def load_manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text())


@st.cache_data
def load_summary() -> dict[str, Any]:
    return json.loads(SUMMARY_PATH.read_text())


@st.cache_data
def load_split(split: str) -> pd.DataFrame:
    return pd.read_parquet(DATA_DIR / f"{DATASET_VERSION}.{split}.parquet")


def predict_probability(model_payload: dict[str, Any], row: pd.Series) -> float:
    feature_names = list(model_payload["feature_names"])
    x = row[feature_names].to_numpy(dtype=np.float32).reshape(1, -1)
    estimator = model_payload["estimator"]
    if hasattr(estimator, "predict_proba"):
        return float(estimator.predict_proba(x)[0, 1])
    decision = float(estimator.decision_function(x)[0])
    return float(1.0 / (1.0 + np.exp(-decision)))


def score_dataframe(model_payload: dict[str, Any], dataframe: pd.DataFrame) -> pd.DataFrame:
    feature_names = list(model_payload["feature_names"])
    x = dataframe[feature_names].to_numpy(dtype=np.float32)
    scores = model_payload["estimator"].predict_proba(x)[:, 1]
    scored = dataframe.copy()
    scored["pred_probability"] = scores.astype(float)
    scored["pred_label"] = (scored["pred_probability"] >= float(model_payload["threshold"])).astype(int)
    return scored


def display_label(value: float | int | None) -> str:
    if pd.isna(value):
        return "unknown"
    return "concern" if int(value) == 1 else "no concern"


def format_row(row: pd.Series) -> str:
    return (
        f"{row['repo']} #{int(row['pr_number'])} | "
        f"p={row['pred_probability']:.3f} | true={display_label(row['review_concern'])}"
    )


def top_feature_importance(model_payload: dict[str, Any], limit: int = 15) -> pd.DataFrame:
    estimator = model_payload["estimator"]
    if not hasattr(estimator, "feature_importances_"):
        return pd.DataFrame()
    values = np.asarray(estimator.feature_importances_, dtype=float)
    names = np.asarray(model_payload["feature_names"])
    order = np.argsort(values)[-limit:][::-1]
    return pd.DataFrame(
        {
            "feature": names[order],
            "importance": values[order],
        }
    )


st.set_page_config(page_title="Review Concern Demo", layout="wide")

model_payload = load_model()
manifest = load_manifest()
summary = load_summary()
threshold = float(model_payload["threshold"])

st.title("Review Concern Demo")

left, middle, right = st.columns(3)
left.metric("Model", str(model_payload["model_name"]))
middle.metric("Threshold", f"{threshold:.3f}")
right.metric("Features", f"{len(model_payload['feature_names']):,}")

with st.sidebar:
    split = st.selectbox("Split", ["test", "val", "train"], index=0)
    label_filter = st.selectbox("Observed label", ["all", "concern", "no concern"], index=0)
    accepted_filter = st.selectbox("Quality flag", ["all", "accepted", "rejected"], index=0)
    search = st.text_input("Repository search", "")
    sort_by = st.selectbox("Sort", ["highest probability", "lowest probability", "repository"], index=0)

df = load_split(split)
scored_df = score_dataframe(model_payload, df)

languages = ["all"] + sorted(str(value) for value in scored_df["top_language"].dropna().unique())
with st.sidebar:
    language_filter = st.selectbox("Top language", languages, index=0)

filtered = scored_df
if label_filter == "concern":
    filtered = filtered[filtered["review_concern"] == 1]
elif label_filter == "no concern":
    filtered = filtered[filtered["review_concern"] == 0]

if accepted_filter == "accepted":
    filtered = filtered[filtered["accepted_quality"] == 1]
elif accepted_filter == "rejected":
    filtered = filtered[filtered["accepted_quality"] == 0]

if language_filter != "all":
    filtered = filtered[filtered["top_language"] == language_filter]

if search.strip():
    query = search.strip().lower()
    filtered = filtered[
        filtered["repo"].str.lower().str.contains(query, regex=False)
        | filtered["example_id"].str.lower().str.contains(query, regex=False)
    ]

if sort_by == "highest probability":
    filtered = filtered.sort_values("pred_probability", ascending=False)
elif sort_by == "lowest probability":
    filtered = filtered.sort_values("pred_probability", ascending=True)
else:
    filtered = filtered.sort_values(["repo", "pr_number"])

if filtered.empty:
    st.warning("No rows match the selected filters.")
    st.stop()

overview_columns = [
    "repo",
    "pr_number",
    "top_language",
    "changed_files",
    "diff_lines",
    "source_patch_token_count_capped",
    "pred_probability",
    "pred_label",
    "review_concern",
    "accepted_quality",
]

st.dataframe(
    filtered[overview_columns].head(100),
    use_container_width=True,
    hide_index=True,
    column_config={
        "pred_probability": st.column_config.ProgressColumn(
            "pred_probability",
            min_value=0.0,
            max_value=1.0,
            format="%.3f",
        )
    },
)

selected_index = st.selectbox(
    "Pull request",
    filtered.index.tolist(),
    format_func=lambda index: format_row(filtered.loc[index]),
)
selected = filtered.loc[selected_index].copy()

probability = predict_probability(model_payload, selected)
prediction = int(probability >= threshold)

st.subheader("Prediction")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Probability", f"{probability:.3f}")
c2.metric("Decision", display_label(prediction))
c3.metric("Observed", display_label(selected["review_concern"]))
c4.metric("Quality", "accepted" if int(selected["accepted_quality"]) else "rejected")

st.progress(min(max(probability, 0.0), 1.0))

meta_left, meta_right = st.columns(2)
with meta_left:
    st.write(
        pd.DataFrame(
            [
                ["Repository", selected["repo"]],
                ["Pull request", int(selected["pr_number"])],
                ["Language", selected["top_language"]],
                ["Author association", selected["author_association"]],
                ["Changed files", int(selected["changed_files"])],
                ["Changed lines", int(selected["diff_lines"])],
            ],
            columns=["Field", "Value"],
        )
    )

with meta_right:
    st.write(
        pd.DataFrame(
            [
                ["Source files", int(selected["source_file_count"])],
                ["Source patches", int(selected["source_patch_count"])],
                ["Patch tokens", int(selected["source_patch_token_count_capped"])],
                ["Title length", int(selected["pr_title_length"])],
                ["Body length", int(selected["pr_body_length"])],
                ["Commits", int(selected["commits"])],
            ],
            columns=["Field", "Value"],
        )
    )

with st.expander("Numeric what-if", expanded=False):
    edited = selected.copy()
    numeric_columns = list(manifest["numeric_columns"])
    cols = st.columns(2)
    for index, column in enumerate(numeric_columns):
        value = float(selected[column])
        kwargs: dict[str, Any] = {"key": f"num_{column}"}
        if column == "source_file_ratio":
            kwargs.update({"min_value": 0.0, "max_value": 1.0, "step": 0.01, "format": "%.2f"})
        else:
            kwargs.update({"min_value": 0.0, "step": 1.0, "format": "%.0f"})
        edited[column] = cols[index % 2].number_input(column, value=value, **kwargs)

    edited_probability = predict_probability(model_payload, edited)
    edited_prediction = int(edited_probability >= threshold)
    w1, w2 = st.columns(2)
    w1.metric("What-if probability", f"{edited_probability:.3f}", f"{edited_probability - probability:+.3f}")
    w2.metric("What-if decision", display_label(edited_prediction))

importance = top_feature_importance(model_payload)
if not importance.empty:
    st.subheader("Top Feature Importances")
    st.bar_chart(importance.set_index("feature"))

with st.expander("Current Run Summary", expanded=False):
    selected_metrics = summary["test_metrics_for_selected_model"]
    st.json(
        {
            "test_roc_auc": selected_metrics["test_roc_auc"],
            "test_macro_f1": selected_metrics["test_macro_f1"],
            "test_balanced_accuracy": selected_metrics["test_balanced_accuracy"],
            "test_confusion_matrix": selected_metrics["test_confusion_matrix"],
        }
    )
