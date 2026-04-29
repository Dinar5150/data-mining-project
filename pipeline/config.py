from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(slots=True)
class GitHubConfig:
    token_env: str = "GITHUB_TOKEN"
    api_base: str = "https://api.github.com"
    api_version: str = "2022-11-28"
    per_page: int = 100
    max_workers: int = 4
    retry_count: int = 5
    request_timeout_seconds: int = 60
    sleep_on_rate_limit: bool = True


@dataclass(slots=True)
class DatasetConfig:
    min_discussion_comments: int = 2
    min_review_comments: int = 2
    min_meaningful_review_comments: int = 2
    min_changed_files: int = 2
    max_changed_files: int = 30
    min_diff_lines: int = 50
    max_diff_lines: int = 2000
    require_linked_issue: bool = True
    require_source_patch: bool = True
    store_full_diff: bool = True


@dataclass(slots=True)
class FilterConfig:
    exclude_bots: bool = True
    exclude_docs_only: bool = True
    exclude_lockfile_only: bool = True
    exclude_generated_vendor_only: bool = True
    exclude_trivial_review_comments: bool = True


@dataclass(slots=True)
class AuditConfig:
    accepted_sample_size: int = 150
    rejected_sample_size: int = 50
    borderline_sample_size: int = 50
    random_seed: int = 42


@dataclass(slots=True)
class OutputConfig:
    raw_path: str = "data/raw/enriched_prs_raw.jsonl"
    failed_path: str = "data/raw/enriched_prs_failed.jsonl"
    accepted_path: str = "data/processed/dataset_mvp_v0.1.accepted.jsonl"
    rejected_path: str = "data/processed/dataset_mvp_v0.1.rejected.jsonl"
    review_sft_path: str = "data/processed/dataset_mvp_v0.1.review_sft.jsonl"
    issue_to_patch_sft_path: str = "data/processed/dataset_mvp_v0.1.issue_to_patch_sft.jsonl"
    audit_path: str = "data/audit/audit_sample.csv"
    report_path: str = "reports/quality_report_v0.1.md"


@dataclass(slots=True)
class AppConfig:
    github: GitHubConfig
    dataset: DatasetConfig
    filters: FilterConfig
    audit: AuditConfig
    output: OutputConfig


def _load_section(data: dict[str, Any], key: str, cls: type[Any]) -> Any:
    return cls(**data.get(key, {}))


def load_config(path: str | Path = "config.yaml") -> AppConfig:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    return AppConfig(
        github=_load_section(raw, "github", GitHubConfig),
        dataset=_load_section(raw, "dataset", DatasetConfig),
        filters=_load_section(raw, "filters", FilterConfig),
        audit=_load_section(raw, "audit", AuditConfig),
        output=_load_section(raw, "output", OutputConfig),
    )


def ensure_parent_dir(path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
