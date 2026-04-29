from __future__ import annotations

from typing import Any


def compact_user(user: dict[str, Any] | None) -> dict[str, Any] | None:
    if not user:
        return None
    return {
        "login": user.get("login"),
        "type": user.get("type"),
        "html_url": user.get("html_url"),
    }


def compact_comment(comment: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": comment.get("id"),
        "author": compact_user(comment.get("user")),
        "body": comment.get("body"),
        "created_at": comment.get("created_at"),
        "updated_at": comment.get("updated_at"),
        "html_url": comment.get("html_url"),
    }


def compact_review(review: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": review.get("id"),
        "author": compact_user(review.get("user")),
        "state": review.get("state"),
        "body": review.get("body"),
        "submitted_at": review.get("submitted_at"),
        "commit_id": review.get("commit_id"),
        "html_url": review.get("html_url"),
    }


def compact_review_comment(comment: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": comment.get("id"),
        "author": compact_user(comment.get("user")),
        "path": comment.get("path"),
        "diff_hunk": comment.get("diff_hunk"),
        "body": comment.get("body"),
        "created_at": comment.get("created_at"),
        "updated_at": comment.get("updated_at"),
        "commit_id": comment.get("commit_id"),
        "original_commit_id": comment.get("original_commit_id"),
        "line": comment.get("line"),
        "original_line": comment.get("original_line"),
        "html_url": comment.get("html_url"),
    }


def compact_file(file_item: dict[str, Any]) -> dict[str, Any]:
    return {
        "filename": file_item.get("filename"),
        "status": file_item.get("status"),
        "additions": file_item.get("additions"),
        "deletions": file_item.get("deletions"),
        "changes": file_item.get("changes"),
        "patch": file_item.get("patch"),
        "raw_url": file_item.get("raw_url"),
        "blob_url": file_item.get("blob_url"),
        "previous_filename": file_item.get("previous_filename"),
    }


def build_dataset_example(
    enriched: dict[str, Any],
    quality: dict[str, Any],
) -> dict[str, Any]:
    pr = enriched["pr"]
    linked_issue = enriched["linked_issue"]
    example_id = (
        f"{enriched['repo_name'].replace('/', '__')}__pull_{enriched['pr_number']}"
    )

    return {
        "example_id": example_id,
        "repo": enriched["repo_name"],
        "pr_number": enriched["pr_number"],
        "pr_url": pr.get("html_url"),
        "linked_issue_number": enriched.get("linked_issue_number"),
        "linked_issue_url": linked_issue.get("html_url") if linked_issue else None,
        "issue": {
            "title": linked_issue.get("title") if linked_issue else None,
            "body": linked_issue.get("body") if linked_issue else None,
            "author": compact_user(linked_issue.get("user")) if linked_issue else None,
            "created_at": linked_issue.get("created_at") if linked_issue else None,
            "updated_at": linked_issue.get("updated_at") if linked_issue else None,
            "comments": [
                compact_comment(comment)
                for comment in enriched["linked_issue_comments"]
            ],
        },
        "discussion": {
            "pr_comments": [compact_comment(comment) for comment in enriched["pr_comments"]],
        },
        "pr": {
            "title": pr.get("title"),
            "body": pr.get("body"),
            "author": compact_user(pr.get("user")),
            "created_at": pr.get("created_at"),
            "updated_at": pr.get("updated_at"),
            "closed_at": pr.get("closed_at"),
            "merged_at": pr.get("merged_at"),
            "base_sha": (pr.get("base") or {}).get("sha"),
            "head_sha": (pr.get("head") or {}).get("sha"),
            "merge_commit_sha": pr.get("merge_commit_sha"),
            "changed_files": pr.get("changed_files"),
            "additions": pr.get("additions"),
            "deletions": pr.get("deletions"),
            "commits": pr.get("commits"),
        },
        "review": {
            "reviews": [compact_review(review) for review in enriched["reviews"]],
            "review_comments": [
                compact_review_comment(comment)
                for comment in enriched["review_comments"]
            ],
        },
        "code_diff": {
            "files": [compact_file(file_item) for file_item in enriched["files"]],
            "full_diff": enriched.get("full_diff"),
        },
        "quality": quality,
        "provenance": {
            "source": "gharchive_bigquery_plus_github_rest_api",
            "retrieved_at": enriched.get("retrieved_at"),
            "candidate_source": "githubarchive.year.2025",
            "api_errors": enriched.get("api_errors", []),
        },
    }
