from __future__ import annotations

import argparse
import json
import random
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import mlx.core as mx
import numpy as np
import pandas as pd
from mlx_embeddings import generate, load

from pipeline.config import ensure_parent_dir, load_config
from pipeline.export_jsonl import iter_jsonl
from pipeline.filters import (
    LANGUAGE_BY_EXT,
    evaluate_example,
    is_meaningful_review_comment,
    is_source_file,
    top_source_language,
)

DEFAULT_RAW_PATH = "enriched_prs_raw_new.jsonl"
DEFAULT_OUTPUT_DIR = "data/processed/modeling_v0.2"
DEFAULT_DATASET_VERSION = "dataset_modeling_v0.2"
DEFAULT_EMBEDDING_MODEL = "mlx-community/nomicai-modernbert-embed-base-4bit"
DEFAULT_TOKEN_CAP = 1000
DEFAULT_BATCH_SIZE = 32
TARGET_COLUMN = "review_concern"


def _safe_name(value: str) -> str:
    value = value.lower().replace("+", "plus").replace("#", "sharp")
    value = re.sub(r"[^a-z0-9]+", "_", value).strip("_")
    return value or "unknown"


def example_id(row: dict[str, Any]) -> str:
    repo = row.get("repo_name") or "unknown_repo"
    pr_number = row.get("pr_number") or "unknown_pr"
    return f"{repo.replace('/', '__')}__pull_{pr_number}"


def source_patch_text(row: dict[str, Any]) -> str:
    parts: list[str] = []
    for file_item in row.get("files") or []:
        filename = file_item.get("filename") or ""
        patch = file_item.get("patch") or ""
        if filename and patch and is_source_file(filename):
            parts.append(f"diff -- {filename}\n{patch}")
    return "\n".join(parts)


def review_concern_label(row: dict[str, Any]) -> int | None:
    reviews = row.get("reviews") or []
    review_comments = row.get("review_comments") or []
    if not reviews and not review_comments:
        return None

    states = {(review.get("state") or "").upper() for review in reviews}
    meaningful_count = sum(
        1
        for comment in review_comments
        if is_meaningful_review_comment(comment.get("body"))
    )
    return int("CHANGES_REQUESTED" in states or meaningful_count >= 2)


def _base_row(
    row: dict[str, Any],
    quality: dict[str, Any],
    raw_token_count: int,
    token_cap: int,
) -> dict[str, Any]:
    pr = row.get("pr") or {}
    files = row.get("files") or []
    filenames = [item.get("filename") for item in files if item.get("filename")]
    source_files = [filename for filename in filenames if is_source_file(filename)]
    source_patches = [
        item
        for item in files
        if item.get("filename")
        and is_source_file(item["filename"])
        and item.get("patch")
    ]
    changed_files = pr.get("changed_files") or len(files)
    additions = pr.get("additions") or 0
    deletions = pr.get("deletions") or 0
    author_association = (pr.get("author_association") or "UNKNOWN").upper()

    return {
        "example_id": example_id(row),
        "repo": row.get("repo_name"),
        "pr_number": row.get("pr_number"),
        "split": "",
        TARGET_COLUMN: review_concern_label(row),
        "accepted_quality": int(bool(quality.get("accepted"))),
        "changed_files": int(changed_files or 0),
        "additions": int(additions),
        "deletions": int(deletions),
        "diff_lines": int(additions + deletions),
        "commits": int(pr.get("commits") or 0),
        "pr_title_length": len(pr.get("title") or ""),
        "pr_body_length": len(pr.get("body") or ""),
        "has_pr_body": int(bool(pr.get("body"))),
        "source_file_count": len(source_files),
        "source_patch_count": len(source_patches),
        "source_file_ratio": (
            float(len(source_files)) / float(changed_files) if changed_files else 0.0
        ),
        "source_patch_char_count": len(source_patch_text(row)),
        "source_patch_token_count_raw": int(raw_token_count),
        "source_patch_token_count_capped": int(min(raw_token_count, token_cap)),
        "top_language": top_source_language(source_files),
        "author_association": author_association,
    }


def _load_rows_and_texts(
    raw_path: Path,
    config_path: Path,
    token_cap: int,
    tokenizer: Any,
) -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
    config = load_config(config_path)
    rows: list[dict[str, Any]] = []
    texts: list[str] = []
    reject_reasons: Counter[str] = Counter()
    token_counts: list[int] = []
    label_counts: Counter[str] = Counter()
    accepted_count = 0
    empty_patch_count = 0

    start = time.perf_counter()
    for index, row in enumerate(iter_jsonl(raw_path), start=1):
        text = source_patch_text(row)
        token_count = len(tokenizer.encode(text, add_special_tokens=False))
        quality = evaluate_example(row, config.dataset, config.filters)
        reject_reasons.update(quality.get("reject_reasons") or [])
        accepted_count += int(bool(quality.get("accepted")))
        empty_patch_count += int(not text)

        feature_row = _base_row(row, quality, token_count, token_cap)
        label = feature_row[TARGET_COLUMN]
        label_counts["excluded"] += int(label is None)
        if label is not None:
            label_counts[str(label)] += 1

        rows.append(feature_row)
        texts.append(text)
        token_counts.append(token_count)

        if index % 1000 == 0:
            print(f"loaded {index} raw rows")

    elapsed = time.perf_counter() - start
    summary = {
        "raw_rows": len(rows),
        "accepted_quality_rows": accepted_count,
        "empty_source_patch_rows": empty_patch_count,
        "label_counts": dict(label_counts),
        "source_patch_tokens_raw_total": int(sum(token_counts)),
        "source_patch_tokens_capped_total": int(sum(min(t, token_cap) for t in token_counts)),
        "rows_over_token_cap": int(sum(t > token_cap for t in token_counts)),
        "top_reject_reasons": reject_reasons.most_common(10),
        "load_seconds": round(elapsed, 2),
    }
    return rows, texts, summary


def _embed_texts(
    texts: list[str],
    model: Any,
    tokenizer: Any,
    token_cap: int,
    batch_size: int,
) -> np.ndarray:
    batches: list[np.ndarray] = []
    max_length = token_cap + 2
    start = time.perf_counter()

    for start_index in range(0, len(texts), batch_size):
        batch_texts = texts[start_index : start_index + batch_size]
        outputs = generate(
            model,
            tokenizer,
            batch_texts,
            max_length=max_length,
            padding=True,
            truncation=True,
        )
        batch_embeddings = np.asarray(outputs.text_embeds, dtype=np.float32)
        batches.append(batch_embeddings)
        mx.eval(outputs.text_embeds)
        mx.synchronize()
        mx.clear_cache()

        done = start_index + len(batch_texts)
        if done % (batch_size * 10) == 0 or done == len(texts):
            elapsed = time.perf_counter() - start
            print(f"embedded {done}/{len(texts)} rows in {elapsed:.1f}s")

    return np.vstack(batches)


def _add_one_hot_columns(
    dataframe: pd.DataFrame,
) -> tuple[pd.DataFrame, list[str], dict[str, list[str]]]:
    language_values = sorted(set(LANGUAGE_BY_EXT.values()) | {"unknown"})
    association_values = sorted(
        str(value)
        for value in dataframe["author_association"].fillna("UNKNOWN").unique()
    )

    one_hot_columns: list[str] = []
    for language in language_values:
        column = f"lang_{_safe_name(language)}"
        dataframe[column] = (dataframe["top_language"] == language).astype("int8")
        one_hot_columns.append(column)

    for association in association_values:
        column = f"author_{_safe_name(association)}"
        dataframe[column] = (
            dataframe["author_association"].fillna("UNKNOWN") == association
        ).astype("int8")
        one_hot_columns.append(column)

    categories = {
        "top_language": language_values,
        "author_association": association_values,
    }
    return dataframe, one_hot_columns, categories


def _split_by_repo(
    dataframe: pd.DataFrame,
    train_ratio: float,
    val_ratio: float,
    seed: int,
) -> dict[str, pd.DataFrame]:
    labeled = dataframe[dataframe[TARGET_COLUMN].notna()].copy()
    repos = sorted(labeled["repo"].dropna().unique().tolist())
    random.Random(seed).shuffle(repos)

    train_count = int(len(repos) * train_ratio)
    val_count = int(len(repos) * val_ratio)
    train_repos = set(repos[:train_count])
    val_repos = set(repos[train_count : train_count + val_count])
    test_repos = set(repos[train_count + val_count :])

    split_for_repo = {
        **{repo: "train" for repo in train_repos},
        **{repo: "val" for repo in val_repos},
        **{repo: "test" for repo in test_repos},
    }
    dataframe["split"] = dataframe["repo"].map(split_for_repo).fillna("excluded")

    labeled_mask = dataframe[TARGET_COLUMN].notna()
    return {
        "all": dataframe.copy(),
        "train": dataframe[(dataframe["split"] == "train") & labeled_mask].copy(),
        "val": dataframe[(dataframe["split"] == "val") & labeled_mask].copy(),
        "test": dataframe[(dataframe["split"] == "test") & labeled_mask].copy(),
    }


def _write_npz(
    path: Path,
    dataframe: pd.DataFrame,
    feature_columns: list[str],
    target_column: str,
) -> None:
    ensure_parent_dir(path)
    x = dataframe[feature_columns].to_numpy(dtype=np.float32)
    y = dataframe[target_column].to_numpy(dtype=np.int8)
    np.savez_compressed(
        path,
        X=x,
        y=y,
        feature_names=np.asarray(feature_columns),
        example_id=dataframe["example_id"].to_numpy(dtype=str),
        repo=dataframe["repo"].to_numpy(dtype=str),
        pr_number=dataframe["pr_number"].to_numpy(dtype=np.int64),
    )


def _write_outputs(
    splits: dict[str, pd.DataFrame],
    output_dir: Path,
    dataset_version: str,
    feature_columns: list[str],
    summary: dict[str, Any],
    manifest: dict[str, Any],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for split_name, dataframe in splits.items():
        parquet_path = output_dir / f"{dataset_version}.{split_name}.parquet"
        dataframe.to_parquet(parquet_path, index=False)
        if split_name != "all":
            _write_npz(
                output_dir / f"{dataset_version}.{split_name}.npz",
                dataframe,
                feature_columns,
                TARGET_COLUMN,
            )

    (output_dir / f"{dataset_version}.feature_manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    (output_dir / f"{dataset_version}.preparation_summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )


def prepare_modeling_data(
    raw_path: str | Path = DEFAULT_RAW_PATH,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    config_path: str | Path = "config.yaml",
    embedding_model: str = DEFAULT_EMBEDDING_MODEL,
    token_cap: int = DEFAULT_TOKEN_CAP,
    batch_size: int = DEFAULT_BATCH_SIZE,
    dataset_version: str = DEFAULT_DATASET_VERSION,
) -> dict[str, Any]:
    raw_path = Path(raw_path)
    output_dir = Path(output_dir)
    config_path = Path(config_path)
    config = load_config(config_path)

    print(f"loading embedding model: {embedding_model}")
    model, tokenizer = load(embedding_model)
    mx.eval(model.parameters())

    rows, texts, summary = _load_rows_and_texts(
        raw_path=raw_path,
        config_path=config_path,
        token_cap=token_cap,
        tokenizer=tokenizer,
    )
    embeddings = _embed_texts(
        texts=texts,
        model=model,
        tokenizer=tokenizer,
        token_cap=token_cap,
        batch_size=batch_size,
    )

    dataframe = pd.DataFrame(rows)
    embedding_columns = [f"diff_emb_{index:03d}" for index in range(embeddings.shape[1])]
    embedding_frame = pd.DataFrame(embeddings, columns=embedding_columns)
    dataframe = pd.concat([dataframe.reset_index(drop=True), embedding_frame], axis=1)
    dataframe, one_hot_columns, categories = _add_one_hot_columns(dataframe)

    numeric_columns = [
        "changed_files",
        "additions",
        "deletions",
        "diff_lines",
        "commits",
        "pr_title_length",
        "pr_body_length",
        "has_pr_body",
        "source_file_count",
        "source_patch_count",
        "source_file_ratio",
        "source_patch_char_count",
        "source_patch_token_count_raw",
        "source_patch_token_count_capped",
    ]
    feature_columns = numeric_columns + one_hot_columns + embedding_columns
    dataframe[feature_columns] = dataframe[feature_columns].fillna(0)

    splits = _split_by_repo(
        dataframe=dataframe,
        train_ratio=config.split.train_ratio,
        val_ratio=config.split.val_ratio,
        seed=config.split.random_seed,
    )

    split_summary = {}
    for split_name, split_df in splits.items():
        labels = Counter(split_df[TARGET_COLUMN].dropna().astype(int).tolist())
        split_summary[split_name] = {
            "rows": int(len(split_df)),
            "repos": int(split_df["repo"].nunique()),
            "review_concern_0": int(labels.get(0, 0)),
            "review_concern_1": int(labels.get(1, 0)),
            "accepted_quality_rows": int(split_df["accepted_quality"].sum()),
        }

    manifest = {
        "dataset_version": dataset_version,
        "target_column": TARGET_COLUMN,
        "feature_columns": feature_columns,
        "metadata_columns": [
            "example_id",
            "repo",
            "pr_number",
            "split",
            "accepted_quality",
            "top_language",
            "author_association",
        ],
        "embedding_columns": embedding_columns,
        "numeric_columns": numeric_columns,
        "one_hot_columns": one_hot_columns,
        "categories": categories,
        "embedding_model": embedding_model,
        "embedding_token_cap": token_cap,
        "split": {
            "method": "repository_level_random",
            "train_ratio": config.split.train_ratio,
            "val_ratio": config.split.val_ratio,
            "test_ratio": config.split.test_ratio,
            "seed": config.split.random_seed,
        },
        "fit_example": (
            "data=np.load(train_npz); model.fit(data['X'], data['y']); "
            "pred=model.predict(np.load(val_npz)['X'])"
        ),
    }
    summary.update(
        {
            "output_dir": str(output_dir),
            "embedding_model": embedding_model,
            "embedding_token_cap": token_cap,
            "embedding_batch_size": batch_size,
            "embedding_dimensions": int(embeddings.shape[1]),
            "dataset_version": dataset_version,
            "feature_count": len(feature_columns),
            "split_summary": split_summary,
        }
    )

    _write_outputs(
        splits=splits,
        output_dir=output_dir,
        dataset_version=dataset_version,
        feature_columns=feature_columns,
        summary=summary,
        manifest=manifest,
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare modeling-ready train/val/test files with capped ModernBERT diff embeddings.",
    )
    parser.add_argument("--raw", default=DEFAULT_RAW_PATH)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--embedding-model", default=DEFAULT_EMBEDDING_MODEL)
    parser.add_argument("--token-cap", type=int, default=DEFAULT_TOKEN_CAP)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--dataset-version", default=DEFAULT_DATASET_VERSION)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = prepare_modeling_data(
        raw_path=args.raw,
        output_dir=args.output_dir,
        config_path=args.config,
        embedding_model=args.embedding_model,
        token_cap=args.token_cap,
        batch_size=args.batch_size,
        dataset_version=args.dataset_version,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
