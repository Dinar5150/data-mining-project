from __future__ import annotations

import os
from typing import Any

from pipeline.config import DatasetConfig, FilterConfig

BOT_PATTERNS = [
    "dependabot",
    "renovate",
    "github-actions",
    "pre-commit-ci",
    "snyk-bot",
    "deepsource",
    "imgbot",
]

DOC_EXTS = {".md", ".rst", ".txt", ".adoc"}
DOC_PATH_PARTS = {"docs/", "doc/", "documentation/", "changelog", "changeset"}
LOCKFILES = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "Pipfile.lock",
    "Cargo.lock",
    "go.sum",
    "composer.lock",
    "Gemfile.lock",
}
GENERATED_OR_VENDOR_PATHS = {
    "vendor/",
    "dist/",
    "build/",
    "generated/",
    "gen/",
    "node_modules/",
    "third_party/",
}
SOURCE_EXTS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".go",
    ".java",
    ".rs",
    ".cpp",
    ".cc",
    ".c",
    ".h",
    ".hpp",
    ".cs",
    ".rb",
    ".php",
    ".swift",
    ".kt",
    ".scala",
}
TRIVIAL_REVIEW_PHRASES = {
    "lgtm",
    "looks good",
    "thanks",
    "thank you",
    "+1",
    "approved",
    "nice",
    "nit",
    "ok",
    "okay",
    "done",
}


def is_bot_login(login: str | None) -> bool:
    if not login:
        return False
    lowered = login.lower()
    return lowered.endswith("[bot]") or any(pattern in lowered for pattern in BOT_PATTERNS)


def file_ext(path: str) -> str:
    return os.path.splitext(path)[1].lower()


def is_doc_file(path: str) -> bool:
    lowered = path.lower()
    return file_ext(path) in DOC_EXTS or any(part in lowered for part in DOC_PATH_PARTS)


def is_lockfile(path: str) -> bool:
    return os.path.basename(path) in LOCKFILES


def is_generated_or_vendor(path: str) -> bool:
    lowered = path.lower()
    return any(part in lowered for part in GENERATED_OR_VENDOR_PATHS)


def is_source_file(path: str) -> bool:
    return file_ext(path) in SOURCE_EXTS


def is_meaningful_review_comment(body: str | None) -> bool:
    if not body:
        return False

    normalized = body.strip().lower()
    if normalized in TRIVIAL_REVIEW_PHRASES:
        return False
    if len(normalized) < 30:
        return False
    return True


def evaluate_example(
    enriched: dict[str, Any],
    dataset_config: DatasetConfig,
    filter_config: FilterConfig,
) -> dict[str, Any]:
    pr = enriched["pr"]
    files = enriched["files"]
    reviews = enriched["reviews"]
    review_comments = enriched["review_comments"]
    pr_comments = enriched["pr_comments"]
    linked_issue = enriched["linked_issue"]
    linked_issue_comments = enriched["linked_issue_comments"]
    full_diff = enriched.get("full_diff")

    reject_reasons: list[str] = []

    if not pr.get("merged"):
        reject_reasons.append("not_merged")

    if dataset_config.require_linked_issue and (
        not enriched.get("linked_issue_number") or not linked_issue
    ):
        reject_reasons.append("no_explicit_linked_issue")

    author_login = (pr.get("user") or {}).get("login")
    if filter_config.exclude_bots and is_bot_login(author_login):
        reject_reasons.append("bot_author")

    changed_files = pr.get("changed_files") or len(files)
    additions = pr.get("additions") or 0
    deletions = pr.get("deletions") or 0
    diff_lines = additions + deletions

    if changed_files < dataset_config.min_changed_files or changed_files > dataset_config.max_changed_files:
        reject_reasons.append("bad_changed_files_count")

    if diff_lines < dataset_config.min_diff_lines or diff_lines > dataset_config.max_diff_lines:
        reject_reasons.append("bad_diff_size")

    filenames = [item.get("filename") for item in files if item.get("filename")]
    if not filenames:
        reject_reasons.append("no_files")

    if filenames and filter_config.exclude_docs_only and all(is_doc_file(path) for path in filenames):
        reject_reasons.append("docs_only")

    if filenames and filter_config.exclude_lockfile_only and all(is_lockfile(path) for path in filenames):
        reject_reasons.append("lockfile_only")

    if filenames and filter_config.exclude_generated_vendor_only and all(
        is_generated_or_vendor(path) for path in filenames
    ):
        reject_reasons.append("generated_or_vendor_only")

    source_files = [path for path in filenames if is_source_file(path)]
    if not source_files:
        reject_reasons.append("no_source_files")

    source_patches = [
        item
        for item in files
        if item.get("filename")
        and is_source_file(item["filename"])
        and item.get("patch")
    ]

    if dataset_config.require_source_patch and not source_patches:
        reject_reasons.append("no_source_patches")

    meaningful_review_comments = review_comments
    if filter_config.exclude_trivial_review_comments:
        meaningful_review_comments = [
            comment
            for comment in review_comments
            if is_meaningful_review_comment(comment.get("body"))
        ]

    if len(review_comments) < dataset_config.min_review_comments:
        reject_reasons.append("not_enough_review_comments")

    if len(meaningful_review_comments) < dataset_config.min_meaningful_review_comments:
        reject_reasons.append("not_enough_meaningful_review_comments")

    discussion_count = len(pr_comments) + len(linked_issue_comments)
    if discussion_count < dataset_config.min_discussion_comments:
        reject_reasons.append("not_enough_discussion")

    if dataset_config.store_full_diff and not full_diff:
        reject_reasons.append("missing_full_diff")

    score = 0
    if pr.get("merged"):
        score += 20
    if enriched.get("linked_issue_number"):
        score += 20
    if len(meaningful_review_comments) >= dataset_config.min_meaningful_review_comments:
        score += 20
    if discussion_count >= dataset_config.min_discussion_comments:
        score += 10
    if source_files:
        score += 10
    if source_patches:
        score += 10
    if dataset_config.min_diff_lines <= diff_lines <= dataset_config.max_diff_lines:
        score += 10

    review_states = {review.get("state") for review in reviews if review.get("state")}
    if "CHANGES_REQUESTED" in review_states:
        score += 10
    elif "COMMENTED" in review_states:
        score += 5

    for penalty_reason in (
        "bot_author",
        "docs_only",
        "lockfile_only",
        "generated_or_vendor_only",
    ):
        if penalty_reason in reject_reasons:
            score -= 20

    accepted = len(reject_reasons) == 0 and score >= 70
    return {
        "accepted": accepted,
        "score": score,
        "tier": "mvp_silver" if accepted else "rejected",
        "reject_reasons": reject_reasons,
        "discussion_count": discussion_count,
        "review_comment_count": len(review_comments),
        "meaningful_review_comment_count": len(meaningful_review_comments),
        "source_file_count": len(source_files),
        "source_patch_count": len(source_patches),
        "diff_lines": diff_lines,
    }
