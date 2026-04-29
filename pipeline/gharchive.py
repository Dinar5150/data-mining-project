from __future__ import annotations

import csv
import gzip
import json
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import requests

from pipeline.config import ensure_parent_dir

LOGGER = logging.getLogger(__name__)
GHARCHIVE_BASE_URL = "https://data.gharchive.org"
CANDIDATE_FIELDNAMES = [
    "repo_name",
    "pr_number",
    "pr_url",
    "pr_title",
    "pr_body",
    "merge_commit_sha",
    "additions",
    "deletions",
    "changed_files",
    "issue_comment_events",
    "review_events",
    "review_comment_events",
    "first_seen_at",
    "last_seen_at",
]


@dataclass(slots=True)
class PullRequestAggregate:
    repo_name: str
    pr_number: int
    pr_url: str | None = None
    pr_title: str | None = None
    pr_body: str | None = None
    merge_commit_sha: str | None = None
    additions: int | None = None
    deletions: int | None = None
    changed_files: int | None = None
    merged_close_events: int = 0
    pr_closed_at: str | None = None
    issue_comment_events: int = 0
    review_events: int = 0
    review_comment_events: int = 0
    first_seen_at: str | None = None
    last_seen_at: str | None = None

    def register_activity(self, created_at: str, event_type: str) -> None:
        if self.first_seen_at is None or created_at < self.first_seen_at:
            self.first_seen_at = created_at
        if self.last_seen_at is None or created_at > self.last_seen_at:
            self.last_seen_at = created_at

        if event_type == "IssueCommentEvent":
            self.issue_comment_events += 1
        elif event_type == "PullRequestReviewEvent":
            self.review_events += 1
        elif event_type == "PullRequestReviewCommentEvent":
            self.review_comment_events += 1

    def register_merged_close(self, created_at: str, pull_request: dict[str, Any]) -> None:
        self.merged_close_events += 1
        if self.pr_closed_at is None or created_at < self.pr_closed_at:
            self.pr_closed_at = created_at

        self.pr_url = pull_request.get("html_url") or self.pr_url
        self.pr_title = pull_request.get("title") or self.pr_title
        self.pr_body = pull_request.get("body") or self.pr_body
        self.merge_commit_sha = pull_request.get("merge_commit_sha") or self.merge_commit_sha
        self.additions = _as_int(pull_request.get("additions"), self.additions)
        self.deletions = _as_int(pull_request.get("deletions"), self.deletions)
        self.changed_files = _as_int(pull_request.get("changed_files"), self.changed_files)


def _as_int(value: Any, default: int | None = None) -> int | None:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def iter_hourly_urls(start_date: str, end_date: str) -> list[str]:
    start = _parse_date(start_date)
    end = _parse_date(end_date)
    if end < start:
        raise ValueError("end_date must be greater than or equal to start_date")

    urls: list[str] = []
    current = start
    while current <= end:
        for hour in range(24):
            urls.append(
                f"{GHARCHIVE_BASE_URL}/{current:%Y-%m-%d}-{hour}.json.gz"
            )
        current += timedelta(days=1)
    return urls


def download_gharchive_slice(
    output_dir: str | Path,
    start_date: str,
    end_date: str,
    skip_existing: bool = True,
) -> dict[str, int]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    urls = iter_hourly_urls(start_date, end_date)

    stats = {
        "requested_files": 0,
        "downloaded_files": 0,
        "skipped_existing": 0,
        "failed_files": 0,
    }
    session = requests.Session()

    for index, url in enumerate(urls, start=1):
        stats["requested_files"] += 1
        filename = url.rsplit("/", 1)[-1]
        destination = output_path / filename

        if skip_existing and destination.exists():
            stats["skipped_existing"] += 1
        else:
            try:
                with session.get(url, stream=True, timeout=120) as response:
                    response.raise_for_status()
                    with destination.open("wb") as handle:
                        for chunk in response.iter_content(chunk_size=1024 * 1024):
                            if chunk:
                                handle.write(chunk)
                stats["downloaded_files"] += 1
            except requests.RequestException:
                if destination.exists():
                    destination.unlink(missing_ok=True)
                stats["failed_files"] += 1
                LOGGER.exception("Failed to download %s", url)

        if index % 24 == 0 or index == len(urls):
            LOGGER.info(
                "GH Archive download progress: processed=%s downloaded=%s skipped=%s failed=%s",
                index,
                stats["downloaded_files"],
                stats["skipped_existing"],
                stats["failed_files"],
            )

    return stats


def build_candidates_from_gharchive(
    input_glob: str,
    output_csv: str | Path,
    limit_files: int | None = None,
) -> dict[str, int]:
    input_paths = sorted(Path().glob(input_glob))
    if limit_files is not None:
        input_paths = input_paths[:limit_files]

    aggregates: dict[tuple[str, int], PullRequestAggregate] = {}
    stats = {
        "input_files": len(input_paths),
        "parsed_events": 0,
        "json_errors": 0,
        "candidate_rows": 0,
    }

    for file_index, input_path in enumerate(input_paths, start=1):
        with gzip.open(input_path, "rt", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    stats["json_errors"] += 1
                    continue

                stats["parsed_events"] += 1
                _process_event(event, aggregates)

        if file_index % 24 == 0 or file_index == len(input_paths):
            LOGGER.info(
                "Candidate build progress: files=%s/%s parsed_events=%s current_candidates=%s",
                file_index,
                len(input_paths),
                stats["parsed_events"],
                len(aggregates),
            )

    rows = [
        {
            "repo_name": aggregate.repo_name,
            "pr_number": aggregate.pr_number,
            "pr_url": aggregate.pr_url,
            "pr_title": aggregate.pr_title,
            "pr_body": aggregate.pr_body,
            "merge_commit_sha": aggregate.merge_commit_sha,
            "additions": aggregate.additions,
            "deletions": aggregate.deletions,
            "changed_files": aggregate.changed_files,
            "issue_comment_events": aggregate.issue_comment_events,
            "review_events": aggregate.review_events,
            "review_comment_events": aggregate.review_comment_events,
            "first_seen_at": aggregate.first_seen_at,
            "last_seen_at": aggregate.last_seen_at,
        }
        for aggregate in sorted(
            aggregates.values(),
            key=lambda item: (item.repo_name, item.pr_number),
        )
        if _passes_candidate_filters(aggregate)
    ]

    ensure_parent_dir(output_csv)
    with Path(output_csv).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CANDIDATE_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    stats["candidate_rows"] = len(rows)
    LOGGER.info(
        "Built %s candidate rows from %s GH Archive files into %s",
        len(rows),
        len(input_paths),
        output_csv,
    )
    return stats


def _process_event(
    event: dict[str, Any],
    aggregates: dict[tuple[str, int], PullRequestAggregate],
) -> None:
    event_type = event.get("type")
    repo_name = (event.get("repo") or {}).get("name")
    created_at = event.get("created_at")
    payload = event.get("payload") or {}

    if not repo_name or not created_at or not isinstance(payload, dict):
        return

    if event_type == "PullRequestEvent":
        if payload.get("action") != "closed":
            return
        pull_request = payload.get("pull_request") or {}
        if not _is_merged_pull_request(pull_request):
            return
        pr_number = _as_int(pull_request.get("number"))
        if pr_number is None:
            return
        aggregate = aggregates.setdefault(
            (repo_name, pr_number),
            PullRequestAggregate(repo_name=repo_name, pr_number=pr_number),
        )
        aggregate.register_merged_close(created_at, pull_request)
        return

    if event_type not in (
        "IssueCommentEvent",
        "PullRequestReviewEvent",
        "PullRequestReviewCommentEvent",
    ):
        return

    pr_number = None
    pull_request = payload.get("pull_request")
    if isinstance(pull_request, dict):
        pr_number = _as_int(pull_request.get("number"))
    if pr_number is None:
        issue = payload.get("issue")
        if isinstance(issue, dict):
            pr_number = _as_int(issue.get("number"))
    if pr_number is None:
        return

    aggregate = aggregates.setdefault(
        (repo_name, pr_number),
        PullRequestAggregate(repo_name=repo_name, pr_number=pr_number),
    )
    aggregate.register_activity(created_at, event_type)


def _is_merged_pull_request(pull_request: dict[str, Any]) -> bool:
    merged = pull_request.get("merged")
    if isinstance(merged, bool):
        return merged
    if isinstance(merged, str):
        return merged.lower() == "true"
    return False


def _passes_candidate_filters(aggregate: PullRequestAggregate) -> bool:
    if aggregate.merged_close_events <= 0:
        return False
    if aggregate.changed_files is None or not (2 <= aggregate.changed_files <= 30):
        return False
    additions = aggregate.additions or 0
    deletions = aggregate.deletions or 0
    diff_lines = additions + deletions
    if not (50 <= diff_lines <= 2000):
        return False
    if aggregate.issue_comment_events < 2:
        return False
    if aggregate.review_events < 1:
        return False
    if aggregate.review_comment_events < 2:
        return False
    return True
