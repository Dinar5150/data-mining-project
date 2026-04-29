from __future__ import annotations

from pathlib import Path

from pipeline.config import AppConfig, ensure_parent_dir
from pipeline.features import accepted_language_distribution
from pipeline.report import load_examples, load_failure_count, make_quality_report


def write_dataset_card(config: AppConfig) -> dict[str, int | float]:
    accepted = load_examples(config.output.accepted_path)
    rejected = load_examples(config.output.rejected_path)
    failed_count = load_failure_count(config.output.failed_path)
    metrics = make_quality_report(accepted, rejected, failed_count)

    unique_repos = sorted(
        {
            example.get("repo")
            for example in accepted + rejected
            if example.get("repo")
        }
    )
    language_counts = accepted_language_distribution(config.output.accepted_path)
    language_lines = [
        f"- {language}: {count}"
        for language, count in language_counts.most_common(10)
    ] or ["- none observed yet"]

    lines = [
        "# Dataset Card",
        "",
        "## Summary",
        "",
        "- Name: GH Trace Dataset MVP",
        "- Sources: GH Archive candidate search plus GitHub REST API enrichment",
        "- Unit of data: one workflow trace, internally also called a trace or example",
        "- Primary downstream label: `quality.accepted` (accepted vs rejected)",
        "- Release formats: JSONL working files plus Parquet exports",
        "",
        "## Current Snapshot",
        "",
        f"- Accepted examples: {metrics['accepted']}",
        f"- Rejected examples: {metrics['rejected']}",
        f"- Failed API fetches: {metrics['failed_api_fetch']}",
        f"- Acceptance rate: {metrics['acceptance_rate']:.2%}",
        f"- Unique repositories: {len(unique_repos)}",
        "",
        "## Observed Languages in Accepted Examples",
        "",
        *language_lines,
        "",
        "## Label Definition",
        "",
        "- Positive label (`accepted=1`): merged PR trace that passes all hard filters and reaches score >= 70.",
        "- Negative label (`accepted=0`): merged PR trace rejected by at least one hard filter or by score threshold.",
        "",
        "## Intended Uses",
        "",
        "- Accepted-vs-rejected PR trace quality classification.",
        "- Curated training data selection for downstream LLM workflows.",
        "- Error analysis over rejected traces.",
        "",
        "## Known Limitations",
        "",
        "- Candidate retrieval currently starts from merged PRs only.",
        "- Linked issues are detected via explicit `fixes/closes/resolves #issue` mentions.",
        "- Language coverage is inferred from changed source-file extensions, not repository metadata.",
        "- License filtering is documented in BU but not yet implemented in the current pipeline.",
        "- Full diffs depend on GitHub API availability and may be missing for some PRs.",
        "",
    ]

    ensure_parent_dir(config.output.data_card_path)
    Path(config.output.data_card_path).write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )
    return {
        "accepted": metrics["accepted"],
        "rejected": metrics["rejected"],
        "unique_repos": len(unique_repos),
    }
