from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any

from pipeline.audit import make_audit_sample
from pipeline.config import AppConfig, load_config
from pipeline.datacard import write_dataset_card
from pipeline.enrich import run_enrichment
from pipeline.export_jsonl import iter_jsonl, truncate_jsonl, write_jsonl
from pipeline.features import export_feature_tables
from pipeline.filters import evaluate_example
from pipeline.gharchive import build_candidates_from_gharchive, download_gharchive_slice
from pipeline.parquet_export import export_trace_parquet
from pipeline.report import write_quality_report
from pipeline.schema import build_dataset_example
from pipeline.sft import export_sft_datasets
from pipeline.split import split_examples_by_repo


def process_enriched(config: AppConfig) -> dict[str, int]:
    truncate_jsonl(config.output.accepted_path)
    truncate_jsonl(config.output.rejected_path)

    accepted_examples: list[dict[str, Any]] = []
    rejected_examples: list[dict[str, Any]] = []
    stats = {"processed": 0, "accepted": 0, "rejected": 0}
    for enriched in iter_jsonl(config.output.raw_path):
        quality = evaluate_example(enriched, config.dataset, config.filters)
        example = build_dataset_example(enriched, quality)
        stats["processed"] += 1
        if quality["accepted"]:
            accepted_examples.append(example)
            stats["accepted"] += 1
        else:
            rejected_examples.append(example)
            stats["rejected"] += 1

    accepted_examples.sort(key=lambda row: row.get("example_id", ""))
    rejected_examples.sort(key=lambda row: row.get("example_id", ""))
    write_jsonl(config.output.accepted_path, accepted_examples)
    write_jsonl(config.output.rejected_path, rejected_examples)
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
    enrich_input_group = enrich_parser.add_mutually_exclusive_group(required=True)
    enrich_input_group.add_argument(
        "--candidates",
        help="Path to the exported candidate CSV from BigQuery.",
    )
    enrich_input_group.add_argument(
        "--candidates-dir",
        help="Directory containing monthly candidate CSV files.",
    )
    enrich_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit on the number of candidate rows to process in single-file mode.",
    )
    enrich_parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Optional row offset when reading the candidate CSV in single-file mode.",
    )
    enrich_parser.add_argument(
        "--pattern",
        default="candidate_prs_*.csv",
        help="Glob pattern used inside --candidates-dir. Default: candidate_prs_*.csv",
    )
    enrich_parser.add_argument(
        "--limit-total",
        type=int,
        default=None,
        help="Total number of candidates to submit across all matched files in directory mode.",
    )
    enrich_parser.add_argument(
        "--sample-seed",
        type=int,
        default=42,
        help="Random seed for reproducible balanced sampling in directory mode.",
    )
    enrich_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show file discovery and selection stats without calling the GitHub API.",
    )

    download_parser = subparsers.add_parser(
        "download-gharchive",
        help="Download GH Archive hourly .json.gz files for a date range.",
    )
    download_parser.add_argument(
        "--start-date",
        required=True,
        help="Start date in YYYY-MM-DD format.",
    )
    download_parser.add_argument(
        "--end-date",
        required=True,
        help="End date in YYYY-MM-DD format.",
    )
    download_parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory where downloaded .json.gz files will be stored.",
    )
    download_parser.add_argument(
        "--no-skip-existing",
        action="store_true",
        help="Redownload files even if they already exist locally.",
    )

    candidates_parser = subparsers.add_parser(
        "candidates-from-gharchive",
        help="Build candidate CSV from locally downloaded GH Archive hourly files.",
    )
    candidates_parser.add_argument(
        "--input-glob",
        required=True,
        help="Glob pattern for local GH Archive .json.gz files, e.g. data/gharchive/2015-01-*.json.gz",
    )
    candidates_parser.add_argument(
        "--output",
        required=True,
        help="Destination CSV path for candidate PR rows.",
    )
    candidates_parser.add_argument(
        "--limit-files",
        type=int,
        default=None,
        help="Optional limit on the number of hourly files to scan.",
    )

    subparsers.add_parser("process", help="Build accepted and rejected datasets from raw JSONL.")
    subparsers.add_parser("split", help="Split processed examples by repository into train/val/test JSONL.")
    subparsers.add_parser("features", help="Export flat feature tables for train/val/test splits.")
    subparsers.add_parser("export-parquet", help="Export accepted and rejected traces to Parquet.")
    subparsers.add_parser("sft", help="Export SFT datasets from accepted traces.")
    subparsers.add_parser("audit", help="Generate a human audit CSV sample.")
    subparsers.add_parser("report", help="Generate a markdown quality report.")
    subparsers.add_parser("data-card", help="Generate a dataset card from processed outputs.")
    subparsers.add_parser(
        "finalize",
        help="Run process, split, features, Parquet export, SFT export, audit, report, and data card.",
    )

    return parser


def _print_stats(command: str, stats: dict[str, Any]) -> None:
    print(f"[{command}]")
    for key, value in stats.items():
        print(f"{key}: {value}")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    parser = build_parser()
    args = parser.parse_args()
    config = load_config(args.config)

    if args.command == "enrich":
        if args.candidates_dir:
            if args.offset:
                parser.error("--offset is only supported with --candidates.")
            if args.limit is not None:
                parser.error("--limit is only supported with --candidates.")
        elif args.limit_total is not None:
            parser.error("--limit-total is only supported with --candidates-dir.")

        stats = run_enrichment(
            config=config,
            candidates_path=Path(args.candidates) if args.candidates else None,
            candidates_dir=Path(args.candidates_dir) if args.candidates_dir else None,
            pattern=args.pattern,
            limit=args.limit,
            limit_total=args.limit_total,
            offset=args.offset,
            sample_seed=args.sample_seed,
            dry_run=args.dry_run,
        )
        _print_stats("enrich", stats)
        return

    if args.command == "download-gharchive":
        stats = download_gharchive_slice(
            output_dir=Path(args.output_dir),
            start_date=args.start_date,
            end_date=args.end_date,
            skip_existing=not args.no_skip_existing,
        )
        _print_stats("download-gharchive", stats)
        return

    if args.command == "candidates-from-gharchive":
        stats = build_candidates_from_gharchive(
            input_glob=args.input_glob,
            output_csv=Path(args.output),
            limit_files=args.limit_files,
        )
        _print_stats("candidates-from-gharchive", stats)
        return

    if args.command == "process":
        _print_stats("process", process_enriched(config))
        return

    if args.command == "split":
        _print_stats("split", split_examples_by_repo(config))
        return

    if args.command == "features":
        _print_stats("features", export_feature_tables(config))
        return

    if args.command == "export-parquet":
        _print_stats("export-parquet", export_trace_parquet(config))
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

    if args.command == "data-card":
        _print_stats("data-card", write_dataset_card(config))
        return

    if args.command == "finalize":
        process_stats = process_enriched(config)
        split_stats = split_examples_by_repo(config)
        feature_stats = export_feature_tables(config)
        parquet_stats = export_trace_parquet(config)
        sft_stats = export_sft_datasets(config)
        audit_stats = make_audit_sample(config)
        report_stats = write_quality_report(config)
        data_card_stats = write_dataset_card(config)
        _print_stats("process", process_stats)
        _print_stats("split", split_stats)
        _print_stats("features", feature_stats)
        _print_stats("export-parquet", parquet_stats)
        _print_stats("sft", sft_stats)
        _print_stats("audit", audit_stats)
        _print_stats("report", report_stats)
        _print_stats("data-card", data_card_stats)
        return

    parser.error(f"Unsupported command: {args.command}")
