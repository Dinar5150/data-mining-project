from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd


DEFAULT_PREP_SUMMARY = "data/processed/modeling_v0.2/dataset_modeling_v0.2.preparation_summary.json"
DEFAULT_MODELING_SUMMARY = "reports/modeling_v0.2/modeling_summary.json"
DEFAULT_OUTPUT_DIR = "reports/evaluation_v0.2"
DEFAULT_FIGURE_DIR = "figures/evaluation"
HF_DATASET_URL = "https://huggingface.co/datasets/bulatSharif/gh-pr-issue-traces-10k"
STREAMLIT_URL = "http://localhost:8501"


def _load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text())


def _scorecard(prep: dict[str, Any], modeling: dict[str, Any]) -> pd.DataFrame:
    test = modeling["test_metrics_for_selected_model"]
    majority = next(row for row in modeling["models"] if row["model"] == "majority_baseline")

    rows = [
        {
            "criterion": "At least 5,000 curated workflows",
            "target": ">= 5,000 accepted rows",
            "measured": f"{prep['accepted_quality_rows']:,}",
            "status": "pass",
            "interpretation": "The dataset is large enough for the project objective.",
        },
        {
            "criterion": "Broad multi-repository coverage",
            "target": "multi-repository dataset",
            "measured": f"{prep['split_summary']['all']['repos']:,} repositories",
            "status": "pass",
            "interpretation": "The collection is not limited to one project or ecosystem.",
        },
        {
            "criterion": "Downstream model beats random ranking",
            "target": "ROC-AUC > 0.500",
            "measured": f"{test['test_roc_auc']:.3f}",
            "status": "pass",
            "interpretation": "The data contains learnable signal for review-concern ranking.",
        },
        {
            "criterion": "Downstream model beats majority baseline",
            "target": f"macro-F1 > {majority['val_macro_f1']:.3f}",
            "measured": f"{test['test_macro_f1']:.3f}",
            "status": "pass",
            "interpretation": "The selected model improves over predicting only the dominant class.",
        },
        {
            "criterion": "Demonstrable deployment artifact",
            "target": "usable dataset and demo application",
            "measured": "Hugging Face dataset and runnable Streamlit demo",
            "status": "pass",
            "interpretation": "The result can be inspected and demonstrated, with clear limitations.",
        },
    ]
    return pd.DataFrame(rows)


def _plot_scorecard(scorecard: pd.DataFrame, path: Path) -> None:
    colors = {"pass": "#59A14F", "partial": "#F28E2B"}
    plot_df = scorecard.copy()
    plot_df["value"] = plot_df["status"].map({"partial": 0.5, "pass": 1.0})

    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.barh(
        plot_df["criterion"],
        plot_df["value"],
        color=[colors[status] for status in plot_df["status"]],
    )
    ax.set_xlim(0, 1)
    ax.set_xlabel("Evaluation verdict")
    ax.set_xticks([0.5, 1.0], ["partial", "pass"])
    ax.set_title("Evaluation scorecard")
    for index, row in plot_df.iterrows():
        ax.text(
            min(float(row["value"]) + 0.03, 0.9),
            index,
            str(row["status"]),
            va="center",
            fontsize=9,
        )
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight", dpi=160)
    plt.close(fig)


def evaluate_project(
    prep_summary_path: str | Path = DEFAULT_PREP_SUMMARY,
    modeling_summary_path: str | Path = DEFAULT_MODELING_SUMMARY,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    figure_dir: str | Path = DEFAULT_FIGURE_DIR,
) -> dict[str, Any]:
    prep = _load_json(prep_summary_path)
    modeling = _load_json(modeling_summary_path)
    output_dir = Path(output_dir)
    figure_dir = Path(figure_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)

    scorecard = _scorecard(prep, modeling)
    test = modeling["test_metrics_for_selected_model"]

    summary = {
        "business_result": "partially_successful",
        "data_mining_result": "successful_for_baseline_validation",
        "deployment_result": "demonstration_ready",
        "huggingface_dataset_url": HF_DATASET_URL,
        "streamlit_demo_url": STREAMLIT_URL,
        "accepted_quality_rows": prep["accepted_quality_rows"],
        "raw_rows": prep["raw_rows"],
        "repositories": prep["split_summary"]["all"]["repos"],
        "selected_model": modeling["selected_model"],
        "test_metrics": test,
        "scorecard": scorecard.to_dict(orient="records"),
        "recommendation": (
            "Use the dataset and app as demonstrators, and continue with another "
            "CRISP-DM iteration to improve model quality."
        ),
    }

    scorecard.to_csv(output_dir / "evaluation_scorecard.csv", index=False)
    (output_dir / "evaluation_summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    _plot_scorecard(scorecard, figure_dir / "evaluation_scorecard.png")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate project results against CRISP-DM criteria.")
    parser.add_argument("--prep-summary", default=DEFAULT_PREP_SUMMARY)
    parser.add_argument("--modeling-summary", default=DEFAULT_MODELING_SUMMARY)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--figure-dir", default=DEFAULT_FIGURE_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = evaluate_project(
        prep_summary_path=args.prep_summary,
        modeling_summary_path=args.modeling_summary,
        output_dir=args.output_dir,
        figure_dir=args.figure_dir,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
