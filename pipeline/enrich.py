from __future__ import annotations

import csv
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from requests import HTTPError, RequestException

from pipeline.config import AppConfig
from pipeline.export_jsonl import append_jsonl, iter_jsonl
from pipeline.github_client import GitHubClient

LOGGER = logging.getLogger(__name__)
CLOSING_RE = re.compile(
    r"(?i)\b(fix|fixes|fixed|close|closes|closed|resolve|resolves|resolved)\s+#(\d+)"
)


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def split_repo(repo_name: str) -> tuple[str, str]:
    owner, repo = repo_name.split("/", 1)
    return owner, repo


def candidate_key(repo_name: str, pr_number: int | str) -> str:
    return f"{repo_name}#{int(pr_number)}"


def extract_linked_issue_number(title: str | None, body: str | None) -> int | None:
    text = f"{title or ''}\n{body or ''}"
    match = CLOSING_RE.search(text)
    if not match:
        return None
    return int(match.group(2))


def read_candidates(
    csv_path: str | Path,
    limit: int | None = None,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    duplicates_removed = 0
    with Path(csv_path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for index, row in enumerate(reader):
            if index < offset:
                continue
            key = candidate_key(row["repo_name"], row["pr_number"])
            if key in seen_keys:
                duplicates_removed += 1
                continue
            seen_keys.add(key)
            rows.append(row)
            if limit is not None and len(rows) >= limit:
                break
    return rows, duplicates_removed


def load_seen_keys(paths: Iterable[str | Path]) -> set[str]:
    seen: set[str] = set()
    for path in paths:
        for row in iter_jsonl(path):
            repo_name = row.get("repo_name") or row.get("repo")
            pr_number = row.get("pr_number")
            if repo_name and pr_number is not None:
                seen.add(candidate_key(repo_name, pr_number))
    return seen


def _safe_get(client: GitHubClient, url: str, api_errors: list[dict[str, Any]], stage: str) -> Any:
    try:
        return client.get(url)
    except RequestException as exc:
        api_errors.append(_error_payload(stage, exc))
        return None


def _safe_get_paginated(
    client: GitHubClient,
    url: str,
    api_errors: list[dict[str, Any]],
    stage: str,
) -> list[Any]:
    try:
        return client.get_paginated(url)
    except RequestException as exc:
        api_errors.append(_error_payload(stage, exc))
        return []


def _safe_get_text(
    client: GitHubClient,
    url: str,
    accept: str,
    api_errors: list[dict[str, Any]],
    stage: str,
) -> str | None:
    try:
        return client.get_text(url, accept=accept)
    except RequestException as exc:
        api_errors.append(_error_payload(stage, exc))
        return None


def _error_payload(stage: str, exc: Exception) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "stage": stage,
        "error_type": exc.__class__.__name__,
        "message": str(exc),
    }
    if isinstance(exc, HTTPError) and exc.response is not None:
        payload["status_code"] = exc.response.status_code
    return payload


def enrich_pr(client: GitHubClient, candidate: dict[str, Any], config: AppConfig) -> dict[str, Any]:
    repo_name = candidate["repo_name"]
    pr_number = int(candidate["pr_number"])
    owner, repo = split_repo(repo_name)
    base = f"{config.github.api_base}/repos/{owner}/{repo}"
    api_errors: list[dict[str, Any]] = []

    pr = client.get(f"{base}/pulls/{pr_number}")
    files = client.get_paginated(f"{base}/pulls/{pr_number}/files")
    reviews = client.get_paginated(f"{base}/pulls/{pr_number}/reviews")
    review_comments = client.get_paginated(f"{base}/pulls/{pr_number}/comments")
    pr_comments = client.get_paginated(f"{base}/issues/{pr_number}/comments")

    full_diff = None
    if config.dataset.store_full_diff:
        full_diff = _safe_get_text(
            client,
            f"{base}/pulls/{pr_number}",
            accept="application/vnd.github.v3.diff",
            api_errors=api_errors,
            stage="full_diff",
        )

    linked_issue_number = extract_linked_issue_number(pr.get("title"), pr.get("body"))
    linked_issue = None
    linked_issue_comments: list[Any] = []

    if linked_issue_number:
        issue = _safe_get(
            client,
            f"{base}/issues/{linked_issue_number}",
            api_errors,
            "linked_issue",
        )
        if issue and "pull_request" not in issue:
            linked_issue = issue
            linked_issue_comments = _safe_get_paginated(
                client,
                f"{base}/issues/{linked_issue_number}/comments",
                api_errors,
                "linked_issue_comments",
            )
        else:
            linked_issue_number = None

    return {
        "repo_name": repo_name,
        "pr_number": pr_number,
        "candidate": candidate,
        "pr": pr,
        "files": files,
        "reviews": reviews,
        "review_comments": review_comments,
        "pr_comments": pr_comments,
        "full_diff": full_diff,
        "linked_issue_number": linked_issue_number,
        "linked_issue": linked_issue,
        "linked_issue_comments": linked_issue_comments,
        "api_errors": api_errors,
        "retrieved_at": now_utc_iso(),
    }


def _failure_row(candidate: dict[str, Any], exc: Exception) -> dict[str, Any]:
    return {
        "repo_name": candidate.get("repo_name"),
        "pr_number": int(candidate.get("pr_number")),
        "candidate": candidate,
        "error_type": exc.__class__.__name__,
        "error_message": str(exc),
        "retrieved_at": now_utc_iso(),
    }


def _run_enrich_candidate(
    candidate: dict[str, Any],
    config: AppConfig,
) -> dict[str, Any]:
    client = GitHubClient(config.github)
    return enrich_pr(client, candidate, config)


def run_enrichment(
    config: AppConfig,
    candidates_path: str | Path,
    limit: int | None = None,
    offset: int = 0,
) -> dict[str, int]:
    candidates, duplicates_removed = read_candidates(
        candidates_path,
        limit=limit,
        offset=offset,
    )
    seen = load_seen_keys((config.output.raw_path, config.output.failed_path))
    pending = [
        row
        for row in candidates
        if candidate_key(row["repo_name"], row["pr_number"]) not in seen
    ]

    stats = {
        "candidate_rows": len(candidates),
        "duplicates_removed": duplicates_removed,
        "already_seen": len(candidates) - len(pending),
        "submitted": len(pending),
        "succeeded": 0,
        "failed": 0,
    }

    LOGGER.info(
        "Loaded %s unique candidates from %s (%s duplicates removed, %s already seen).",
        len(candidates),
        candidates_path,
        duplicates_removed,
        stats["already_seen"],
    )

    if not pending:
        LOGGER.info("No pending candidates left to enrich.")
        return stats

    processed = 0
    progress_interval = max(config.github.progress_interval, 1)
    with ThreadPoolExecutor(max_workers=config.github.max_workers) as executor:
        futures = {
            executor.submit(_run_enrich_candidate, candidate, config): candidate
            for candidate in pending
        }
        for future in as_completed(futures):
            candidate = futures[future]
            try:
                enriched = future.result()
            except Exception as exc:
                append_jsonl(config.output.failed_path, _failure_row(candidate, exc))
                stats["failed"] += 1
                processed += 1
                if processed % progress_interval == 0 or processed == len(pending):
                    LOGGER.info(
                        "Enrichment progress: processed=%s/%s succeeded=%s failed=%s skipped=%s",
                        processed,
                        len(pending),
                        stats["succeeded"],
                        stats["failed"],
                        stats["already_seen"],
                    )
                continue

            append_jsonl(config.output.raw_path, enriched)
            stats["succeeded"] += 1
            processed += 1
            if processed % progress_interval == 0 or processed == len(pending):
                LOGGER.info(
                    "Enrichment progress: processed=%s/%s succeeded=%s failed=%s skipped=%s",
                    processed,
                    len(pending),
                    stats["succeeded"],
                    stats["failed"],
                    stats["already_seen"],
                )

    LOGGER.info("Enrichment finished: %s", stats)
    return stats
