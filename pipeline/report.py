from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from pipeline.config import AppConfig, ensure_parent_dir
from pipeline.export_jsonl import iter_jsonl


def load_examples(path: str | Path) -> list[dict[str, Any]]:
    return list(iter_jsonl(path))


def load_failure_count(path: str | Path) -> int:
    return sum(1 for _ in iter_jsonl(path))


def _average(values: list[int | float]) -> float:
    return sum(values) / len(values) if values else 0.0


def make_quality_report(
    accepted: list[dict[str, Any]],
    rejected: list[dict[str, Any]],
    failed_count: int,
) -> dict[str, Any]:
    all_examples = accepted + rejected
    reject_counter: Counter[str] = Counter()
    top_extensions: Counter[str] = Counter()
    top_repos: Counter[str] = Counter()

    for example in rejected:
        reject_counter.update((example.get("quality") or {}).get("reject_reasons", []))

    for example in accepted:
        repo_name = example.get("repo")
        if repo_name:
            top_repos[repo_name] += 1

        for file_item in (example.get("code_diff") or {}).get("files", []):
            filename = file_item.get("filename") or ""
            extension = f".{filename.rsplit('.', 1)[-1]}" if "." in filename else ""
            top_extensions[extension] += 1

    accepted_scores = [
        (example.get("quality") or {}).get("score", 0) for example in accepted
    ]
    accepted_diff_lines = [
        (example.get("quality") or {}).get("diff_lines", 0) for example in accepted
    ]
    accepted_review_comments = [
        (example.get("quality") or {}).get("meaningful_review_comment_count", 0)
        for example in accepted
    ]
    accepted_discussions = [
        (example.get("quality") or {}).get("discussion_count", 0)
        for example in accepted
    ]
    accepted_changed_files = [
        (example.get("pr") or {}).get("changed_files", 0) or 0 for example in accepted
    ]

    total_examples = len(all_examples)
    accepted_count = len(accepted)
    rejected_count = len(rejected)

    return {
        "total_examples": total_examples,
        "accepted": accepted_count,
        "rejected": rejected_count,
        "failed_api_fetch": failed_count,
        "acceptance_rate": accepted_count / total_examples if total_examples else 0.0,
        "avg_score_accepted": _average(accepted_scores),
        "avg_changed_files_accepted": _average(accepted_changed_files),
        "avg_diff_lines_accepted": _average(accepted_diff_lines),
        "avg_meaningful_review_comments": _average(accepted_review_comments),
        "avg_discussion_count": _average(accepted_discussions),
        "reject_reasons": reject_counter.most_common(),
        "top_extensions": top_extensions.most_common(20),
        "top_repos": top_repos.most_common(20),
    }


def write_quality_report(config: AppConfig) -> dict[str, Any]:
    accepted = load_examples(config.output.accepted_path)
    rejected = load_examples(config.output.rejected_path)
    failed_count = load_failure_count(config.output.failed_path)
    metrics = make_quality_report(accepted, rejected, failed_count)

    lines = [
        "# Quality Report v0.1",
        "",
        "## Summary",
        "",
        f"- Total processed examples: {metrics['total_examples']}",
        f"- Accepted: {metrics['accepted']}",
        f"- Rejected: {metrics['rejected']}",
        f"- Failed API fetches: {metrics['failed_api_fetch']}",
        f"- Acceptance rate: {metrics['acceptance_rate']:.2%}",
        "",
        "## Accepted Stats",
        "",
        f"- Avg score: {metrics['avg_score_accepted']:.2f}",
        f"- Avg changed files: {metrics['avg_changed_files_accepted']:.2f}",
        f"- Avg diff lines: {metrics['avg_diff_lines_accepted']:.2f}",
        f"- Avg meaningful review comments: {metrics['avg_meaningful_review_comments']:.2f}",
        f"- Avg discussion count: {metrics['avg_discussion_count']:.2f}",
        "",
        "## Reject Reasons",
        "",
    ]

    if metrics["reject_reasons"]:
        for reason, count in metrics["reject_reasons"]:
            lines.append(f"- {reason}: {count}")
    else:
        lines.append("- none")

    lines.extend(["", "## Top Extensions", ""])
    if metrics["top_extensions"]:
        for extension, count in metrics["top_extensions"]:
            label = extension or "[no extension]"
            lines.append(f"- {label}: {count}")
    else:
        lines.append("- none")

    lines.extend(["", "## Top Repos", ""])
    if metrics["top_repos"]:
        for repo_name, count in metrics["top_repos"]:
            lines.append(f"- {repo_name}: {count}")
    else:
        lines.append("- none")

    ensure_parent_dir(config.output.report_path)
    Path(config.output.report_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return metrics
