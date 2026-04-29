from __future__ import annotations

from typing import Any

from pipeline.config import AppConfig
from pipeline.export_jsonl import append_jsonl, iter_jsonl, truncate_jsonl


def to_review_sft(example: dict[str, Any]) -> dict[str, Any]:
    pr = example.get("pr") or {}
    files = (example.get("code_diff") or {}).get("files", [])
    review_comments = (example.get("review") or {}).get("review_comments", [])

    diff_text = "\n\n".join(
        f"File: {file_item['filename']}\n{file_item.get('patch') or ''}"
        for file_item in files
        if file_item.get("patch")
    )
    target = "\n\n".join(
        f"File: {comment.get('path')}\nComment: {comment.get('body')}"
        for comment in review_comments
        if comment.get("body")
    )

    return {
        "example_id": example.get("example_id"),
        "task_type": "code_review_generation",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a senior software engineer performing a code review. "
                    "Provide concrete, actionable review comments."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"PR title:\n{pr.get('title')}\n\n"
                    f"PR description:\n{pr.get('body')}\n\n"
                    f"Diff:\n{diff_text}"
                ),
            },
            {
                "role": "assistant",
                "content": target,
            },
        ],
        "metadata": {
            "repo": example.get("repo"),
            "pr_number": example.get("pr_number"),
            "pr_url": example.get("pr_url"),
            "score": (example.get("quality") or {}).get("score"),
        },
    }


def to_issue_to_patch_sft(example: dict[str, Any]) -> dict[str, Any]:
    issue = example.get("issue") or {}
    pr = example.get("pr") or {}
    discussion = example.get("discussion") or {}
    full_diff = (example.get("code_diff") or {}).get("full_diff") or ""

    issue_comments = "\n\n".join(
        comment.get("body") or "" for comment in issue.get("comments", []) if comment.get("body")
    )
    pr_comments = "\n\n".join(
        comment.get("body") or ""
        for comment in discussion.get("pr_comments", [])
        if comment.get("body")
    )

    return {
        "example_id": example.get("example_id"),
        "task_type": "issue_to_patch",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a software engineer implementing a change request. "
                    "Produce a patch that addresses the described issue."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Issue title:\n{issue.get('title')}\n\n"
                    f"Issue body:\n{issue.get('body')}\n\n"
                    f"Issue discussion:\n{issue_comments}\n\n"
                    f"PR description:\n{pr.get('body')}\n\n"
                    f"PR discussion:\n{pr_comments}"
                ),
            },
            {
                "role": "assistant",
                "content": full_diff,
            },
        ],
        "metadata": {
            "repo": example.get("repo"),
            "pr_number": example.get("pr_number"),
            "pr_url": example.get("pr_url"),
            "linked_issue_url": example.get("linked_issue_url"),
            "score": (example.get("quality") or {}).get("score"),
            "context_level": "patch_only",
        },
    }


def export_sft_datasets(config: AppConfig) -> dict[str, int]:
    truncate_jsonl(config.output.review_sft_path)
    truncate_jsonl(config.output.issue_to_patch_sft_path)

    review_count = 0
    issue_to_patch_count = 0
    accepted_count = 0

    for example in iter_jsonl(config.output.accepted_path):
        accepted_count += 1

        review_sft = to_review_sft(example)
        if review_sft["messages"][-1]["content"].strip():
            append_jsonl(config.output.review_sft_path, review_sft)
            review_count += 1

        issue_to_patch_sft = to_issue_to_patch_sft(example)
        if issue_to_patch_sft["messages"][-1]["content"].strip():
            append_jsonl(config.output.issue_to_patch_sft_path, issue_to_patch_sft)
            issue_to_patch_count += 1

    return {
        "accepted_loaded": accepted_count,
        "review_sft_rows": review_count,
        "issue_to_patch_sft_rows": issue_to_patch_count,
    }
