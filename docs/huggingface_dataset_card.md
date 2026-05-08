---
license: apache-2.0
pretty_name: GitHub PR Review Traces 10K
language:
- en
task_categories:
- text-classification
- text-generation
tags:
- github
- pull-requests
- code-review
- software-engineering
- data-mining
- program-repair
size_categories:
- 10K<n<100K
configs:
- config_name: default
  data_files:
  - split: train
    path: github_pr_issue_traces_raw_2025_10k.jsonl
---

# GitHub PR Review Traces 10K

## Dataset Summary

This dataset contains 10,000 raw public GitHub pull request traces. Each JSONL row represents one pull request candidate and joins together PR metadata, discussion, code review, changed files, full diff text, optional auxiliary fields, and retrieval provenance.

The data is designed for mining software engineering workflows of the form:

```text
Pull Request -> Discussion -> Review -> Code Diff -> Merge
```

The uploaded file is:

```text
github_pr_issue_traces_raw_2025_10k.jsonl
```

## Collection Method

The dataset was produced with a two-stage pipeline:

1. Candidate discovery from GH Archive event data.
2. Enrichment through the GitHub REST API for pull request details, PR comments, reviews, review comments, changed files, and full diff text.

The file is intentionally raw: it keeps the nested GitHub API-like structure so downstream users can build their own filters, quality labels, retrieval tasks, or modeling views.

## Dataset Statistics

| Statistic | Value |
|---|---:|
| Rows | 10,000 |
| Unique repositories | 6,033 |
| File size | 1,907,104,840 bytes, about 1.91 GB |
| Closed PR records | 10,000 |
| PRs with non-null `merged_at` | 9,997 |
| Rows with full diff text | 9,996 |
| Rows with recorded API errors | 18 |
| Changed files | 94,933 total, 9.49 average per PR |
| Reviews | 92,040 total, 9.20 average per PR |
| Review comments | 113,785 total, 11.38 average per PR |
| PR comments | 54,934 total, 5.49 average per PR |
| Additions | 3,254,131 total, 325.41 average per PR |
| Deletions | 949,515 total, 94.95 average per PR |
| PR `created_at` range | 2019-11-23 to 2026-03-31 |
| PR `merged_at` range | 2025-03-01 to 2026-03-31 |
| Retrieval range | 2026-05-01 to 2026-05-02 |

Top changed-file extensions:

| Extension | Files |
|---|---:|
| `.ts` | 11,949 |
| `.py` | 9,759 |
| `.tsx` | 7,622 |
| `.java` | 6,243 |
| `.go` | 5,663 |
| `.md` | 4,309 |
| `.rs` | 4,032 |
| `.json` | 3,748 |
| `.js` | 2,925 |
| `.yaml` | 2,576 |

## Schema Overview

Each line is a JSON object with these top-level fields:

```text
repo_name
pr_number
candidate
pr
pr_comments
reviews
review_comments
files
full_diff
linked_issue_number
linked_issue
linked_issue_comments
api_errors
retrieved_at
```

Important nested content includes:

- `candidate`: GH Archive-derived candidate metadata, including the source PR URL and event counts.
- `pr`: GitHub REST API pull request metadata, including title, body, author, timestamps, branch SHAs, merge commit SHA, additions, deletions, and changed file count.
- `pr_comments`: issue-thread comments on the pull request.
- `reviews`: pull request review events and review bodies.
- `review_comments`: inline review comments, paths, diff hunks, commit IDs, and line metadata.
- `files`: changed-file records with filenames, statuses, additions, deletions, file patches, and blob/raw URLs.
- `full_diff`: raw unified diff text for the pull request when available.
- `linked_issue`: optional auxiliary metadata when present in the raw record.
- `linked_issue_comments`: optional auxiliary comments when present in the raw record.
- `api_errors`: non-fatal API retrieval issues recorded during enrichment.

## Intended Uses

This dataset can support:

- Pull request trace quality classification.
- Code review comment analysis and review-intent modeling.
- Software engineering process mining across pull requests, reviews, and merges.
- Dataset construction for LLM tasks involving repository maintenance, bug fixing, code review, or PR summarization.
- Evaluation of agents that need to reason across pull request metadata, review discussion, and code diffs.

## Loading

```python
from datasets import load_dataset

dataset = load_dataset("bulatSharif/gh-pr-issue-traces-10k")
train = dataset["train"]
print(train[0].keys())
```

For streaming:

```python
from datasets import load_dataset

dataset = load_dataset(
    "bulatSharif/gh-pr-issue-traces-10k",
    streaming=True,
)
for row in dataset["train"]:
    print(row["repo_name"], row["pr_number"])
    break
```

## Limitations

- The dataset contains public GitHub user-generated content, including usernames, comments, review text, code diffs, and optional auxiliary text fields.
- Optional auxiliary fields are retained in the raw schema but are not required by the preparation or modeling stages.
- Full diff text may be unavailable for a small number of rows due to API or retrieval limits.
- The data is raw and not deduplicated into train, validation, and test splits in this upload.
- Repository-level licenses and contribution policies vary. Users should respect upstream project licenses and GitHub terms when redistributing or training on code and discussion content.

## Provenance

Source data comes from public GitHub activity discovered through GH Archive and enriched through the GitHub REST API. Retrieval was performed between 2026-05-01 and 2026-05-02.
