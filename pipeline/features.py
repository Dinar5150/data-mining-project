from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

from pipeline.config import AppConfig, ensure_parent_dir
from pipeline.export_jsonl import iter_jsonl
from pipeline.filters import is_source_file, source_language_counts, top_source_language

FEATURE_COLUMNS = [
    "example_id",
    "repo",
    "pr_number",
    "accepted",
    "score",
    "changed_files",
    "additions",
    "deletions",
    "diff_lines",
    "num_reviews",
    "num_review_comments",
    "num_meaningful_review_comments",
    "discussion_count",
    "has_linked_issue",
    "pr_body_length",
    "issue_body_length",
    "source_file_count",
    "source_patch_count",
    "source_file_ratio",
    "has_changes_requested",
    "review_states_count_approved",
    "review_states_count_commented",
    "review_states_count_changes_requested",
    "top_language",
    "author_association",
]


def _split_paths(config: AppConfig) -> dict[str, tuple[str, str]]:
    return {
        "train": (
            config.output.train_features_csv_path,
            config.output.train_features_parquet_path,
        ),
        "val": (
            config.output.val_features_csv_path,
            config.output.val_features_parquet_path,
        ),
        "test": (
            config.output.test_features_csv_path,
            config.output.test_features_parquet_path,
        ),
    }


def _split_input_paths(config: AppConfig) -> dict[str, str]:
    return {
        "train": config.output.train_path,
        "val": config.output.val_path,
        "test": config.output.test_path,
    }


def _review_state_counts(reviews: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for review in reviews:
        state = (review.get("state") or "").upper()
        if state:
            counts[state] += 1
    return counts


def build_feature_row(example: dict[str, Any]) -> dict[str, Any]:
    pr = example.get("pr") or {}
    issue = example.get("issue") or {}
    review = example.get("review") or {}
    quality = example.get("quality") or {}
    files = (example.get("code_diff") or {}).get("files", [])
    reviews = review.get("reviews", [])
    filenames = [file_item.get("filename") for file_item in files if file_item.get("filename")]
    source_files = [path for path in filenames if is_source_file(path)]
    review_state_counts = _review_state_counts(reviews)
    changed_files = pr.get("changed_files") or 0

    return {
        "example_id": example.get("example_id"),
        "repo": example.get("repo"),
        "pr_number": example.get("pr_number"),
        "accepted": int(bool(quality.get("accepted"))),
        "score": quality.get("score", 0),
        "changed_files": changed_files,
        "additions": pr.get("additions") or 0,
        "deletions": pr.get("deletions") or 0,
        "diff_lines": quality.get("diff_lines", 0),
        "num_reviews": len(reviews),
        "num_review_comments": len(review.get("review_comments", [])),
        "num_meaningful_review_comments": quality.get("meaningful_review_comment_count", 0),
        "discussion_count": quality.get("discussion_count", 0),
        "has_linked_issue": int(example.get("linked_issue_number") is not None),
        "pr_body_length": len(pr.get("body") or ""),
        "issue_body_length": len(issue.get("body") or ""),
        "source_file_count": quality.get("source_file_count", 0),
        "source_patch_count": quality.get("source_patch_count", 0),
        "source_file_ratio": (
            float(len(source_files)) / float(changed_files)
            if changed_files
            else 0.0
        ),
        "has_changes_requested": int(review_state_counts.get("CHANGES_REQUESTED", 0) > 0),
        "review_states_count_approved": review_state_counts.get("APPROVED", 0),
        "review_states_count_commented": review_state_counts.get("COMMENTED", 0),
        "review_states_count_changes_requested": review_state_counts.get(
            "CHANGES_REQUESTED",
            0,
        ),
        "top_language": top_source_language(source_files),
        "author_association": pr.get("author_association") or "UNKNOWN",
    }


def _rows_to_dataframe(rows: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=FEATURE_COLUMNS)


def export_feature_tables(config: AppConfig) -> dict[str, int]:
    stats: dict[str, int] = {}
    input_paths = _split_input_paths(config)
    output_paths = _split_paths(config)

    for split_name, input_path in input_paths.items():
        rows = [build_feature_row(example) for example in iter_jsonl(input_path)]
        dataframe = _rows_to_dataframe(rows)
        csv_path, parquet_path = output_paths[split_name]
        ensure_parent_dir(csv_path)
        ensure_parent_dir(parquet_path)
        dataframe.to_csv(csv_path, index=False)
        dataframe.to_parquet(parquet_path, index=False)
        stats[f"{split_name}_rows"] = len(rows)

    return stats


def accepted_language_distribution(path: str | Path) -> Counter[str]:
    counts: Counter[str] = Counter()
    for example in iter_jsonl(path):
        files = (example.get("code_diff") or {}).get("files", [])
        filenames = [file_item.get("filename") for file_item in files if file_item.get("filename")]
        counts.update(source_language_counts(filenames))
    return counts
