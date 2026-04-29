from __future__ import annotations

import random
from collections import defaultdict
from pathlib import Path
from typing import Any

from pipeline.config import AppConfig
from pipeline.export_jsonl import iter_jsonl, write_jsonl


def _load_processed_examples(config: AppConfig) -> list[dict[str, Any]]:
    accepted = list(iter_jsonl(config.output.accepted_path))
    rejected = list(iter_jsonl(config.output.rejected_path))
    return accepted + rejected


def split_examples_by_repo(config: AppConfig) -> dict[str, int]:
    examples = _load_processed_examples(config)
    repos_to_examples: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for example in examples:
        repo_name = example.get("repo")
        if repo_name:
            repos_to_examples[repo_name].append(example)

    repo_names = list(repos_to_examples)
    randomizer = random.Random(config.split.random_seed)
    randomizer.shuffle(repo_names)

    total_repos = len(repo_names)
    train_repo_count = int(total_repos * config.split.train_ratio)
    val_repo_count = int(total_repos * config.split.val_ratio)

    split_repo_names = {
        "train": set(repo_names[:train_repo_count]),
        "val": set(repo_names[train_repo_count : train_repo_count + val_repo_count]),
        "test": set(repo_names[train_repo_count + val_repo_count :]),
    }

    split_examples = {"train": [], "val": [], "test": []}
    for split_name, repos in split_repo_names.items():
        rows: list[dict[str, Any]] = []
        for repo_name in repos:
            rows.extend(repos_to_examples[repo_name])
        split_examples[split_name] = sorted(
            rows,
            key=lambda row: row.get("example_id", ""),
        )

    write_jsonl(config.output.train_path, split_examples["train"])
    write_jsonl(config.output.val_path, split_examples["val"])
    write_jsonl(config.output.test_path, split_examples["test"])

    return {
        "total_examples": len(examples),
        "total_repos": total_repos,
        "train_examples": len(split_examples["train"]),
        "val_examples": len(split_examples["val"]),
        "test_examples": len(split_examples["test"]),
        "train_repos": len(split_repo_names["train"]),
        "val_repos": len(split_repo_names["val"]),
        "test_repos": len(split_repo_names["test"]),
    }
