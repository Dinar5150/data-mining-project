from __future__ import annotations

import csv
import random
from pathlib import Path
from typing import Any

from pipeline.config import AppConfig, ensure_parent_dir
from pipeline.export_jsonl import iter_jsonl

AUDIT_LABELS = [
    "accept_good",
    "reject_trivial",
    "reject_bad_issue_link",
    "reject_weak_review",
    "reject_docs_only",
    "reject_deps_only",
    "reject_bad_diff",
    "reject_no_real_problem",
    "reject_other",
]


def load_examples(path: str | Path) -> list[dict[str, Any]]:
    return list(iter_jsonl(path))


def _dedupe_examples(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for row in rows:
        example_id = row.get("example_id")
        if not example_id or example_id in seen:
            continue
        seen.add(example_id)
        deduped.append(row)
    return deduped


def _sample_rows(
    rng: random.Random,
    rows: list[dict[str, Any]],
    size: int,
) -> list[dict[str, Any]]:
    if size <= 0 or not rows:
        return []
    if len(rows) <= size:
        return list(rows)
    return rng.sample(rows, size)


def make_audit_sample(config: AppConfig) -> dict[str, int]:
    accepted = load_examples(config.output.accepted_path)
    rejected = load_examples(config.output.rejected_path)
    rng = random.Random(config.audit.random_seed)

    borderline = [
        row
        for row in accepted + rejected
        if 60 <= (row.get("quality") or {}).get("score", 0) <= 80
    ]

    sample = []
    sample.extend(_sample_rows(rng, accepted, config.audit.accepted_sample_size))
    sample.extend(_sample_rows(rng, rejected, config.audit.rejected_sample_size))
    sample.extend(_sample_rows(rng, borderline, config.audit.borderline_sample_size))
    sample = _dedupe_examples(sample)

    ensure_parent_dir(config.output.audit_path)
    with Path(config.output.audit_path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "example_id",
                "repo",
                "pr_url",
                "linked_issue_url",
                "issue_title",
                "pr_title",
                "score",
                "accepted",
                "reject_reasons",
                "discussion_count",
                "meaningful_review_comment_count",
                "source_patch_count",
                "files_preview",
                "review_preview",
                "valid_labels",
                "human_label",
                "human_notes",
            ],
        )
        writer.writeheader()

        for example in sample:
            issue = example.get("issue") or {}
            pr = example.get("pr") or {}
            review_comments = (example.get("review") or {}).get("review_comments", [])
            files = (example.get("code_diff") or {}).get("files", [])
            quality = example.get("quality") or {}

            review_preview = "\n\n".join(
                (comment.get("body") or "") for comment in review_comments[:3]
            )
            files_preview = "\n".join(
                f"{item.get('filename')} +{item.get('additions')} -{item.get('deletions')}"
                for item in files[:5]
            )

            writer.writerow(
                {
                    "example_id": example.get("example_id"),
                    "repo": example.get("repo"),
                    "pr_url": example.get("pr_url"),
                    "linked_issue_url": example.get("linked_issue_url"),
                    "issue_title": issue.get("title"),
                    "pr_title": pr.get("title"),
                    "score": quality.get("score"),
                    "accepted": quality.get("accepted"),
                    "reject_reasons": ",".join(quality.get("reject_reasons", [])),
                    "discussion_count": quality.get("discussion_count"),
                    "meaningful_review_comment_count": quality.get(
                        "meaningful_review_comment_count"
                    ),
                    "source_patch_count": quality.get("source_patch_count"),
                    "files_preview": files_preview,
                    "review_preview": review_preview[:1500],
                    "valid_labels": ",".join(AUDIT_LABELS),
                    "human_label": "",
                    "human_notes": "",
                }
            )

    return {
        "accepted_loaded": len(accepted),
        "rejected_loaded": len(rejected),
        "borderline_pool": len(borderline),
        "sample_size": len(sample),
    }
