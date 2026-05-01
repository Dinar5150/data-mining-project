from __future__ import annotations

import csv
import logging
import random
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


def read_candidate_file(
    csv_path: str | Path,
    seen: set[str],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    local_keys: set[str] = set()
    raw_rows = 0
    local_duplicates_removed = 0
    already_seen = 0

    with Path(csv_path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            raw_rows += 1
            key = candidate_key(row["repo_name"], row["pr_number"])
            if key in local_keys:
                local_duplicates_removed += 1
                continue
            local_keys.add(key)
            if key in seen:
                already_seen += 1
                continue
            rows.append(row)

    return {
        "path": Path(csv_path),
        "raw_rows": raw_rows,
        "local_duplicates_removed": local_duplicates_removed,
        "already_seen": already_seen,
        "pending_rows": rows,
    }


def load_seen_keys(paths: Iterable[str | Path]) -> set[str]:
    seen: set[str] = set()
    for path in paths:
        for row in iter_jsonl(path):
            repo_name = row.get("repo_name") or row.get("repo")
            pr_number = row.get("pr_number")
            if repo_name and pr_number is not None:
                seen.add(candidate_key(repo_name, pr_number))
    return seen


def discover_candidate_files(
    candidates_dir: str | Path,
    pattern: str,
) -> list[Path]:
    base_dir = Path(candidates_dir)
    if not base_dir.exists():
        raise FileNotFoundError(f"Candidates directory does not exist: {base_dir}")
    if not base_dir.is_dir():
        raise NotADirectoryError(f"Candidates path is not a directory: {base_dir}")

    files = sorted(path for path in base_dir.glob(pattern) if path.is_file())
    if not files:
        raise FileNotFoundError(
            f"No candidate CSV files matched pattern {pattern!r} in {base_dir}."
        )
    return files


def _rebalance_quotas(
    available_by_file: dict[str, int],
    limit_total: int,
) -> dict[str, int]:
    quotas = {name: 0 for name in available_by_file}
    remaining_capacity = max(limit_total, 0)
    active = [name for name, count in available_by_file.items() if count > 0]

    while remaining_capacity > 0 and active:
        base_quota = remaining_capacity // len(active)
        remainder = remaining_capacity % len(active)
        assigned_this_round = 0
        next_active: list[str] = []

        for index, name in enumerate(active):
            desired = base_quota + (1 if index < remainder else 0)
            available = available_by_file[name] - quotas[name]
            take = min(desired, available)
            quotas[name] += take
            remaining_capacity -= take
            assigned_this_round += take
            if quotas[name] < available_by_file[name]:
                next_active.append(name)

        if assigned_this_round == 0:
            break
        active = next_active

    return quotas


def balanced_sample_by_file(
    file_infos: list[dict[str, Any]],
    limit_total: int | None,
    sample_seed: int,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    rng = random.Random(sample_seed)
    available_by_file = {
        info["path"].name: len(info["pending_rows"])
        for info in file_infos
    }
    total_pending = sum(available_by_file.values())

    if limit_total is None or limit_total >= total_pending:
        selected_rows = [
            row
            for info in file_infos
            for row in info["pending_rows"]
        ]
        selected_counts = {
            info["path"].name: len(info["pending_rows"])
            for info in file_infos
        }
        rng.shuffle(selected_rows)
        return selected_rows, selected_counts

    quotas = _rebalance_quotas(available_by_file, limit_total)
    selected_rows: list[dict[str, Any]] = []
    selected_counts: dict[str, int] = {}

    for info in file_infos:
        filename = info["path"].name
        rows = info["pending_rows"]
        quota = quotas.get(filename, 0)
        if quota >= len(rows):
            chosen = list(rows)
        else:
            chosen = rng.sample(rows, quota)
        selected_counts[filename] = len(chosen)
        selected_rows.extend(chosen)

    rng.shuffle(selected_rows)
    return selected_rows, selected_counts


def prepare_candidates_from_directory(
    candidates_dir: str | Path,
    pattern: str,
    seen: set[str],
    limit_total: int | None,
    sample_seed: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    files = discover_candidate_files(candidates_dir, pattern)
    file_infos: list[dict[str, Any]] = []
    global_pending_keys: set[str] = set()
    global_duplicates_removed = 0

    for path in files:
        info = read_candidate_file(path, seen)
        unique_pending_rows: list[dict[str, Any]] = []
        for row in info["pending_rows"]:
            key = candidate_key(row["repo_name"], row["pr_number"])
            if key in global_pending_keys:
                global_duplicates_removed += 1
                continue
            global_pending_keys.add(key)
            unique_pending_rows.append(row)
        info["pending_rows"] = unique_pending_rows
        file_infos.append(info)

    selected_rows, selected_counts = balanced_sample_by_file(
        file_infos=file_infos,
        limit_total=limit_total,
        sample_seed=sample_seed,
    )

    total_raw_rows = sum(info["raw_rows"] for info in file_infos)
    total_local_duplicates_removed = sum(
        info["local_duplicates_removed"] for info in file_infos
    )
    total_already_seen = sum(info["already_seen"] for info in file_infos)
    total_pending = sum(len(info["pending_rows"]) for info in file_infos)

    file_stats: list[dict[str, Any]] = []
    for info in file_infos:
        filename = info["path"].name
        file_stats.append(
            {
                "file": filename,
                "raw_rows": info["raw_rows"],
                "deduped_rows": info["raw_rows"] - info["local_duplicates_removed"],
                "already_seen": info["already_seen"],
                "pending_rows": len(info["pending_rows"]),
                "selected_rows": selected_counts.get(filename, 0),
            }
        )

    stats = {
        "matched_files": len(files),
        "total_raw_rows": total_raw_rows,
        "duplicates_removed": total_local_duplicates_removed + global_duplicates_removed,
        "local_duplicates_removed": total_local_duplicates_removed,
        "global_duplicates_removed": global_duplicates_removed,
        "already_seen": total_already_seen,
        "total_pending_rows": total_pending,
        "selected_rows": len(selected_rows),
        "limit_total": limit_total,
        "sample_seed": sample_seed,
        "shortfall": max((limit_total or total_pending) - len(selected_rows), 0)
        if limit_total is not None
        else 0,
        "file_stats": file_stats,
    }
    return selected_rows, stats


def _log_directory_selection(stats: dict[str, Any]) -> None:
    LOGGER.info(
        "Matched %s candidate files. total_raw_rows=%s total_pending_rows=%s total_selected_rows=%s",
        stats["matched_files"],
        stats["total_raw_rows"],
        stats["total_pending_rows"],
        stats["selected_rows"],
    )
    for file_stat in stats["file_stats"]:
        LOGGER.info(
            "Candidate file %s: raw=%s deduped=%s already_seen=%s pending=%s selected=%s",
            file_stat["file"],
            file_stat["raw_rows"],
            file_stat["deduped_rows"],
            file_stat["already_seen"],
            file_stat["pending_rows"],
            file_stat["selected_rows"],
        )
    if stats["global_duplicates_removed"]:
        LOGGER.info(
            "Removed %s duplicate candidates across files after local deduplication.",
            stats["global_duplicates_removed"],
        )
    if stats["shortfall"]:
        LOGGER.info(
            "Selection shortfall: requested=%s selected=%s shortfall=%s",
            stats["limit_total"],
            stats["selected_rows"],
            stats["shortfall"],
        )


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
    candidates_path: str | Path | None = None,
    candidates_dir: str | Path | None = None,
    pattern: str = "candidate_prs_*.csv",
    limit: int | None = None,
    limit_total: int | None = None,
    offset: int = 0,
    sample_seed: int = 42,
    dry_run: bool = False,
) -> dict[str, Any]:
    seen = load_seen_keys((config.output.raw_path, config.output.failed_path))
    if candidates_dir is not None:
        pending, selection_stats = prepare_candidates_from_directory(
            candidates_dir=candidates_dir,
            pattern=pattern,
            seen=seen,
            limit_total=limit_total,
            sample_seed=sample_seed,
        )
        stats = {
            "mode": "directory",
            "matched_files": selection_stats["matched_files"],
            "candidate_rows": selection_stats["total_raw_rows"],
            "duplicates_removed": selection_stats["duplicates_removed"],
            "already_seen": selection_stats["already_seen"],
            "submitted": len(pending),
            "succeeded": 0,
            "failed": 0,
            "sample_seed": sample_seed,
        }
        _log_directory_selection(selection_stats)
    else:
        if candidates_path is None:
            raise ValueError("Either candidates_path or candidates_dir must be provided.")
        candidates, duplicates_removed = read_candidates(
            candidates_path,
            limit=limit,
            offset=offset,
        )
        pending = [
            row
            for row in candidates
            if candidate_key(row["repo_name"], row["pr_number"]) not in seen
        ]

        stats = {
            "mode": "single_file",
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
    if dry_run:
        LOGGER.info("Dry-run enabled. Skipping GitHub API enrichment.")
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
