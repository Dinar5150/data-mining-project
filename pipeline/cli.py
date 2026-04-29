from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from pipeline.audit import make_audit_sample
from pipeline.config import AppConfig, load_config
from pipeline.enrich import run_enrichment
from pipeline.export_jsonl import append_jsonl, iter_jsonl, truncate_jsonl
from pipeline.filters import evaluate_example
from pipeline.report import write_quality_report
from pipeline.schema import build_dataset_example
from pipeline.sft import export_sft_datasets


def process_enriched(config: AppConfig) -> dict[str, int]:
    truncate_jsonl(config.output.accepted_path)
    truncate_jsonl(config.output.rejected_path)

    stats = {"processed": 0, "accepted": 0, "rejected": 0}
    for enriched in iter_jsonl(config.output.raw_path):
        quality = evaluate_example(enriched, config.dataset, config.filters)
        example = build_dataset_example(enriched, quality)
        output_path = (
            config.output.accepted_path if quality["accepted"] else config.output.rejected_path
        )
        append_jsonl(output_path, example)
        stats["processed"] += 1
        if quality["accepted"]:
            stats["accepted"] += 1
        else:
            stats["rejected"] += 1
    return stats


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GH trace dataset MVP pipeline")
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to the YAML config file.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    enrich_parser = subparsers.add_parser("enrich", help="Enrich candidate PRs via GitHub API.")
    enrich_parser.add_argument(
        "--candidates",
        required=True,
        help="Path to the exported candidate CSV from BigQuery.",
    )
    enrich_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit on the number of candidate rows to process.",
    )
    enrich_parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Optional row offset when reading the candidate CSV.",
    )

    subparsers.add_parser("process", help="Build accepted and rejected datasets from raw JSONL.")
    subparsers.add_parser("sft", help="Export SFT datasets from accepted traces.")
    subparsers.add_parser("audit", help="Generate a human audit CSV sample.")
    subparsers.add_parser("report", help="Generate a markdown quality report.")
    subparsers.add_parser("finalize", help="Run process, sft export, audit, and report.")

    return parser


def _print_stats(command: str, stats: dict[str, Any]) -> None:
    print(f"[{command}]")
    for key, value in stats.items():
        print(f"{key}: {value}")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    config = load_config(args.config)

    if args.command == "enrich":
        stats = run_enrichment(
            config=config,
            candidates_path=Path(args.candidates),
            limit=args.limit,
            offset=args.offset,
        )
        _print_stats("enrich", stats)
        return

    if args.command == "process":
        _print_stats("process", process_enriched(config))
        return

    if args.command == "audit":
        _print_stats("audit", make_audit_sample(config))
        return

    if args.command == "sft":
        _print_stats("sft", export_sft_datasets(config))
        return

    if args.command == "report":
        _print_stats("report", write_quality_report(config))
        return

    if args.command == "finalize":
        process_stats = process_enriched(config)
        sft_stats = export_sft_datasets(config)
        audit_stats = make_audit_sample(config)
        report_stats = write_quality_report(config)
        _print_stats("process", process_stats)
        _print_stats("sft", sft_stats)
        _print_stats("audit", audit_stats)
        _print_stats("report", report_stats)
        return

    parser.error(f"Unsupported command: {args.command}")
