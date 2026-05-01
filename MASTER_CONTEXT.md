# Muhomory GitHub Workflow Dataset — Project Master Document

> **Single source of truth** for the Muhomory GitHub Workflow Dataset project.
> This document follows the **CRISP-DM** methodology in its first part, and contains additional operational sections at the end.
> When this document and the code disagree, **the code wins**. When this document and `business_understanding.md` disagree, **this document wins**.

---

## Table of Contents

**Part A — CRISP-DM Phases**
1. [Business Understanding](#1-business-understanding)
2. [Data Understanding](#2-data-understanding)
3. [Data Preparation](#3-data-preparation)
4. [Modeling](#4-modeling)
5. [Evaluation](#5-evaluation)
6. [Deployment](#6-deployment)

**Part B — Operational Sections**
7. [Glossary & Terminology](#7-glossary--terminology)
8. [Repository Layout](#8-repository-layout)
9. [Data Schema Reference](#9-data-schema-reference)
10. [Reject Reasons Reference](#10-reject-reasons-reference)
11. [CLI Reference](#11-cli-reference)
12. [Local Setup Guide](#12-local-setup-guide)
13. [Project Status Dashboard](#13-project-status-dashboard)
14. [Task Checklist](#14-task-checklist)
15. [Presentation & Video Materials](#15-presentation--video-materials)
16. [Configuration Reference](#16-configuration-reference)

---

# Part A — CRISP-DM Phases

---

## 1. Business Understanding

### 1.1 Problem Statement

Public datasets for training code-related ML systems mostly contain **isolated artifacts**:
- Raw source code (The Stack)
- Individual commits (CommitPack)
- Code–text pairs (CodeSearchNet)

They **do not capture the engineering workflow** — the issue that motivated a change, the discussion around it, the diff that implemented it, and the review activity that accepted or contested it.

Companies building AI coding assistants, autonomous developer agents, and automated code review tools need this workflow-level data. Current alternatives are:

| Option | Problem |
|---|---|
| Parse GH Archive directly | Substantial engineering effort, noise, bot pollution, missing cross-event links |
| Contract manual labeling | Expensive, not tailored to software engineering |
| Use existing open datasets | Miss the workflow layer entirely |

**This project fills that gap** by producing a curated dataset of software engineering workflow traces plus a baseline ML model that demonstrates the dataset carries real predictive signal.

### 1.2 Project Objectives

**Primary objective.** Deliver a curated dataset of software engineering workflow traces. Each trace contains a linked issue, pre-merge discussion, pull request metadata, review activity, and the full code diff.

**Secondary objectives.**
- Build a reusable pipeline that can be rerun on new GH Archive slices.
- Train a baseline ML model on a realistic downstream task to validate the dataset.
- Produce documentation artifacts for external use (dataset card, schema, examples, deployment guide).

**Key question.** Can public GitHub activity, filtered and restructured, produce a dataset whose structure and quality are sufficient for commercial use by AI companies building code-related ML systems?

### 1.3 Business Success Criteria

| # | Criterion | Verifiable via |
|---|---|---|
| 1 | **Product completeness** — dataset covers 3+ mainstream programming languages including Python | Dataset card language distribution |
| 2 | **Downstream applicability** — dataset supports at least one realistic downstream task; baseline model beats random | Evaluation scorecard |
| 3 | **Usability** — dataset loads in standard Python environment without extra cleaning scripts | Deployment guide |
| 4 | **Commercial readiness** — short product description with value proposition, customer segments, example use cases | Product one-pager |
| 5 | **Delivery within budget** — executed on existing local hardware, zero external paid services | Repository state |

### 1.4 Users and Use Cases

**Target user group 1.** ML researchers and engineers at AI companies building coding assistants, code review automation, or developer agents. They use the dataset to fine-tune or evaluate LLMs on workflow-context tasks (e.g., generating review comments, predicting review concerns, producing patches from issues).

**Target user group 2.** Engineering teams inside software companies, who use the dataset to train models assisting their own code review process. Primary use case: predicting, at PR opening time, whether the PR is likely to receive substantive concerns — so reviewer attention can be prioritized.

### 1.5 ML Objectives

The ML task is a binary classification task called **`review_concern`**.

> Given a pull request at the moment of opening, predict whether reviewers will raise substantive concerns.

**Label definition.**
- **Label = 1** if the PR received at least one formal review with state `CHANGES_REQUESTED`, **or** at least two meaningful review comments.
- **Label = 0** if the PR received review activity (at least one review or review comment) but no concerns meeting the above threshold.
- **Excluded** from the modeling set: PRs with no review activity at all.

**Feature constraint.** Only **PR-intrinsic features** are used for training (no leakage from review activity). Full partitioning is in [Section 4.2](#42-feature-partitioning).

**Split strategy.** Train/val/test split is done by **repository**, not by PR. All PRs from the same repo fall into the same split.

**Model progression.**
1. Logistic regression on hand-crafted features (sanity baseline)
2. XGBoost on the full no-leak feature set (main tabular baseline)
3. Model using ModernBERT embeddings of PR title, body, and linked issue text

**Evaluation metrics.**
- **Primary:** ROC-AUC and F1 on held-out test set
- **Secondary:** precision-recall curve, confusion matrix, feature importance, calibration
- **Minimum bar:** strictly better than a random baseline on both primary metrics

### 1.6 Data Mining Success Criteria

| # | Criterion | Target Value |
|---|---|---|
| 1 | Dataset scale | ≥ 5000 accepted traces (target ~10000) |
| 2 | Unique repositories | ≥ 500 |
| 3 | Language coverage | ≥ 3 from the 14 source extensions |
| 4 | Trace completeness | ≥ 95% with issue + merged PR + review + non-empty diff |
| 5 | Bot pollution | 0% bot-authored in accepted |
| 6 | Residual noise in audit | < 10% trivial/docs-only in 100-trace audit sample |
| 7 | Schema completeness | 100% populate all 7 top-level blocks |
| 8 | Baseline ROC-AUC | > 0.5 + epsilon on test set |
| 9 | Baseline F1 | > majority-class F1 on test set |
| 10 | Load time | Parquet → pandas in < 2 minutes |

### 1.7 Scope and Non-Goals

**In scope.**
- Extraction and curation of workflow traces for **merged** pull requests from public GitHub repositories
- Multi-language coverage across 14 source-code extensions
- Baseline ML model for `review_concern` with three progressive variants
- Standard data product documentation

**Out of scope.**
- **Unmerged pull requests** — not included. Merge outcome prediction is therefore NOT a task this dataset supports (this differs from the earlier BU document, which listed it as an example).
- **Private repositories** — not accessed.
- **LLM fine-tuning on SFT files** — SFT files are produced as a secondary deliverable, but the project's own ML evaluation uses the tabular `review_concern` task.
- **Language detection** beyond file extension matching.
- **Production-grade deployment** (inference API, monitoring) — out of scope. The deployment artifact is a documented, reproducible dataset and reference model.

### 1.8 Assumptions

1. Public GitHub activity is representative enough of real engineering workflows.
2. Rule-based filtering is sufficient to reach usable quality without full manual labeling.
3. The `review_concern` label captures a real and useful signal about PR quality.
4. Repository-level splitting is sufficient to prevent train/test leakage (time-based splitting deferred to a future version).

### 1.9 Risks and Contingencies

| Risk | Mitigation |
|---|---|
| **Data quality** — GH Archive events are noisy (bots, trivial changes, generated files) | Multi-stage filtering with bot heuristics, size thresholds, linked-issue checks, file-level filters |
| **Event linking** — not every repo exposes a clean issue→PR→review→merge chain | Prioritize traces with explicit linked issues and documented review signals |
| **API & compute limits** — GitHub API ≈ 5000 req/hour/token | Conservative concurrency, resumable JSONL checkpoints |
| **Label imbalance** — `review_concern` positives may be too rare | Measure after first pipeline run; revise label if needed |
| **Insufficient candidates** in chosen time window | Widen window; measurable after next run |

---

## 2. Data Understanding

### 2.1 Data Sources

Two sources used in sequence:

**Source 1 — GH Archive (candidate discovery).**
Public dataset `githubarchive.day.YYYYMMDD`. Contains hourly dumps of GitHub public events since 2011. Two access paths:
- **BigQuery** via `sql/01_candidate_prs.sql` (primary path)
- **Local hourly `.json.gz` dumps** via `pipeline/gharchive.py` (fallback)

**Source 2 — GitHub REST API (enrichment).**
`https://api.github.com`. Called per candidate to fetch full PR details, files, reviews, comments, linked issue, and the unified diff. Requires personal access token (env var `GITHUB_TOKEN`).

### 2.2 Pipeline Data Flow

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   GH Archive     │────▶│   Candidates     │────▶│    GitHub API    │
│   (BigQuery)     │     │   CSV            │     │   Enrichment     │
└──────────────────┘     └──────────────────┘     └──────────────────┘
                                                            │
                                                            ▼
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   Parquet        │◀────│   Accepted /     │◀────│   Raw JSONL      │
│   + Features     │     │   Rejected JSONL │     │   (enriched)     │
│   + SFT          │     │                  │     │                  │
└──────────────────┘     └──────────────────┘     └──────────────────┘
                                │
                                ▼
                         ┌──────────────────┐
                         │  Train/Val/Test  │
                         │  (repo-level)    │
                         └──────────────────┘
```

### 2.3 Candidate Stage

Runs on GH Archive events over a fixed window. Aggregates events per PR. One candidate row = one merged PR with basic counts.

**SQL-level filters already applied:**
- PR is merged (`PullRequestEvent`, `action=closed`, `merged=true`)
- `changed_files` within [min, max]
- `additions + deletions` within [min, max]
- At least one review event or one review comment event
- Author login does not match bot patterns

**Candidate row fields:**
`repo_name`, `pr_number`, `pr_url`, `pr_title`, `pr_body`, `merge_commit_sha`, `additions`, `deletions`, `changed_files`, `issue_comment_events`, `review_events`, `review_comment_events`, timestamps.

> **Note:** Local GH Archive path produces a slightly different column set than the BigQuery SQL. Current dataset uses BigQuery only; both paths converge at the enrichment step.

### 2.4 Enrichment Stage

For each candidate, 8 GitHub API calls:

| # | Endpoint | Purpose |
|---|---|---|
| 1 | `GET /repos/{o}/{r}/pulls/{n}` | Full PR object |
| 2 | `GET /repos/{o}/{r}/pulls/{n}/files` | File list with patches |
| 3 | `GET /repos/{o}/{r}/pulls/{n}/reviews` | Formal reviews |
| 4 | `GET /repos/{o}/{r}/pulls/{n}/comments` | Inline review comments |
| 5 | `GET /repos/{o}/{r}/issues/{n}/comments` | PR thread comments |
| 6 | `GET /repos/{o}/{r}/issues/{issue_n}` | Linked issue (if detected) |
| 7 | `GET /repos/{o}/{r}/issues/{issue_n}/comments` | Issue comments |
| 8 | `GET /repos/{o}/{r}/pulls/{n}` (diff media type) | Full unified diff |

Linked issue detected by regex over PR body: `(fix|fixes|close|closes|resolve|resolves) #<N>`.

**Measured throughput:** ~2.4 seconds per PR end-to-end (single token, includes retries and rate-limit waits). 7500 PRs took ~18000 seconds.

**Failure modes:** deleted repo, private repo, cross-repo issue reference (not followed), API 5xx after retries. Failures → `data/raw/enriched_prs_failed.jsonl`.

### 2.5 Data Exploration

> **Status:** Initial MVP run on March 2025 data produced ~7500 enriched PRs. Full distribution report pending next pipeline run.

**Fields to populate after next run:**
- Candidate count (BigQuery output)
- Enriched count, failure count, failure breakdown
- Accepted count, rejected count
- Reject reasons breakdown
- Language distribution in accepted set
- Repository count; top-20 repos by trace count
- Diff-size distribution
- Review-activity distribution
- Linked-issue presence rate
- `review_concern` label distribution (once implemented)

### 2.6 Data Quality Observations

Known observations:
- `finalize` CLI command has minor edge-case inconsistencies (tracked in [Section 14](#14-task-checklist)).
- Linked-issue regex does not follow cross-repo references; such PRs are treated as having no linked issue and rejected.
- `author_association` is occasionally null for deleted users.
- Full-diff endpoint may truncate very large diffs; such PRs are rejected anyway by size filter.

### 2.7 Feasibility Statement

**Verdict: feasible at target scope (~10000 traces).**

- Pipeline throughput: ~2.4s per PR
- Target run: ~10000 traces = ~7 hours (single overnight run)
- Failure rate: observed low
- Assumes GitHub token rate limits hold

---

## 3. Data Preparation

### 3.1 Overview

Data preparation turns raw candidate events into the final structured dataset. Owned by the pipeline under `pipeline/`. Covers: enrichment, filtering, scoring, schema assembly, split, feature export, Parquet export, SFT export.

### 3.2 Filtering Rules

All filtering implemented in `pipeline/filters.py`, function `evaluate_example`. Each rule violation produces a **reject reason**. See full reference in [Section 10](#10-reject-reasons-reference).

**Hard filters applied per trace:**

| Category | Rule |
|---|---|
| **Merge status** | PR must be merged |
| **Linked issue** | PR body must contain explicit closing keyword + issue number |
| **Author** | Not a known bot login |
| **Size** | `changed_files ∈ [2, 30]`, `diff_lines ∈ [50, 2000]` |
| **File types** | Not docs-only, not lockfile-only, not generated-only |
| **Source files** | Must contain at least one source file and one source patch |
| **Review activity** | ≥ 2 review comments, ≥ 2 meaningful review comments |
| **Discussion** | ≥ 2 total comments (PR + issue) |
| **Full diff** | Must be available if `store_full_diff` is true |

### 3.3 Quality Scoring

An integer score computed from positive signals minus penalties. **Acceptance threshold = 70.**

**Positive signals (additive):**

| Signal | Points |
|---|---|
| PR merged | +20 |
| Has linked issue | +20 |
| Meets meaningful review comment threshold | +20 |
| Meets discussion threshold | +10 |
| Has source files | +10 |
| Has source patches | +10 |
| Diff size within range | +10 |
| Any review has `CHANGES_REQUESTED` | +10 |
| Else any review has `COMMENTED` | +5 |

**Penalties (subtractive, −20 each):**
- `bot_author`, `docs_only`, `lockfile_only`, `generated_or_vendor_only`

**Acceptance rule:** `accepted = (len(reject_reasons) == 0) AND (score >= 70)`.

### 3.4 Schema Assembly

Schema building lives in `pipeline/schema.py`. Produces one nested JSON object per enriched PR. Full field reference in [Section 9](#9-data-schema-reference).

**Seven top-level blocks:**
1. `issue` — linked issue data
2. `discussion` — PR-thread comments
3. `pr` — PR metadata
4. `review` — formal reviews + inline comments
5. `code_diff` — files with patches + full unified diff
6. `quality` — pipeline decision (accepted, score, reject reasons)
7. `provenance` — source, timestamps, API errors

### 3.5 Train/Validation/Test Split

Implemented in `pipeline/split.py`. **Repository-level stratification:** all PRs from the same repo fall into the same split.

| Split | Ratio |
|---|---|
| Train | 0.8 |
| Val | 0.1 |
| Test | 0.1 |

Seed: 42 (reproducible).

### 3.6 Feature Export

Implemented in `pipeline/features.py`. Produces flat CSV and Parquet feature tables for each split.

> **Known gap:** The current feature table mixes PR-intrinsic features with review-derived features. For `review_concern` modeling this must be partitioned into two groups (see [Section 4.2](#42-feature-partitioning)). **Partitioning is not yet implemented.**

**Current feature columns** (see `FEATURE_COLUMNS` in `pipeline/features.py`):
`example_id`, `repo`, `pr_number`, `accepted`, `score`, `changed_files`, `additions`, `deletions`, `diff_lines`, `num_reviews`, `num_review_comments`, `num_meaningful_review_comments`, `discussion_count`, `has_linked_issue`, `pr_body_length`, `issue_body_length`, `source_file_count`, `source_patch_count`, `source_file_ratio`, `has_changes_requested`, `review_states_count_approved`, `review_states_count_commented`, `review_states_count_changes_requested`, `top_language`, `author_association`.

### 3.7 Output Artifacts

| Artifact | Path | Format |
|---|---|---|
| Enriched raw | `data/raw/enriched_prs_raw.jsonl` | JSONL |
| Failed enrichments | `data/raw/enriched_prs_failed.jsonl` | JSONL |
| Accepted traces | `data/processed/dataset_mvp_v0.1.accepted.jsonl` | JSONL |
| Rejected traces | `data/processed/dataset_mvp_v0.1.rejected.jsonl` | JSONL |
| Accepted traces (release) | `data/processed/dataset_mvp_v0.1.accepted.parquet` | Parquet |
| Rejected traces | `data/processed/dataset_mvp_v0.1.rejected.parquet` | Parquet |
| Train split | `data/processed/dataset_mvp_v0.1.train.jsonl` | JSONL |
| Val split | `data/processed/dataset_mvp_v0.1.val.jsonl` | JSONL |
| Test split | `data/processed/dataset_mvp_v0.1.test.jsonl` | JSONL |
| Feature tables | `data/processed/dataset_mvp_v0.1.{split}.features.{csv,parquet}` | CSV + Parquet |
| Review SFT | `data/processed/dataset_mvp_v0.1.review_sft.jsonl` | JSONL |
| Issue→Patch SFT | `data/processed/dataset_mvp_v0.1.issue_to_patch_sft.jsonl` | JSONL |
| Audit sample | `data/audit/audit_sample.csv` | CSV |
| Quality report | `reports/quality_report_v0.1.md` | Markdown |
| Dataset card | `data/processed/DATASET_CARD.md` | Markdown |

---

## 4. Modeling

### 4.1 Modeling Task

**Task:** Binary classification — `review_concern`
**Target:** Does a PR, at opening time, attract substantive review concerns?

**Label formula (to be implemented):**

```
review_concern = 1 if (
    any(review.state == "CHANGES_REQUESTED") OR
    count(meaningful_review_comments) >= 2
)
review_concern = 0 if (
    (count(reviews) >= 1 OR count(review_comments) >= 1) AND
    review_concern != 1
)
EXCLUDED if no review activity at all
```

This label is **distinct from `quality.accepted`**, which is a curation label and cannot be used as the modeling target (it would leak the same features used to predict it).

### 4.2 Feature Partitioning

**Critical rule:** No review-derived features in training features for `review_concern`.

| Group | Available at prediction time? | Used in training? |
|---|---|---|
| **PR-intrinsic** (no-leak) | Yes — at PR opening | **Yes** |
| **Review-derived** (leak) | No — only after review | **No** (analysis only) |

**PR-intrinsic features (use for training):**
- `changed_files`, `additions`, `deletions`, `diff_lines`
- `has_linked_issue`, `issue_body_length`
- `pr_body_length`
- `source_file_count`, `source_patch_count`, `source_file_ratio`
- `top_language`, `author_association`
- Text features from PR title, PR body, linked issue body (for ModernBERT variant)

**Review-derived features (exclude from training):**
- `num_reviews`, `num_review_comments`, `num_meaningful_review_comments`
- `discussion_count`
- `has_changes_requested`
- `review_states_count_*`
- `score`, `accepted` (these depend on review signals)

### 4.3 Model Progression

Three models trained in order of increasing complexity:

| Stage | Model | Features | Purpose |
|---|---|---|---|
| 1 | Logistic Regression | Small hand-crafted subset | Sanity baseline |
| 2 | XGBoost | Full no-leak tabular set | Main tabular baseline |
| 3 | XGBoost + ModernBERT | Tabular + text embeddings | Test if NL signal helps |

### 4.4 Evaluation Metrics

**Primary:**
- ROC-AUC (on held-out test set)
- F1-score (on held-out test set)

**Secondary:**
- Precision-recall curve
- Confusion matrix
- Feature importance (tree models)
- Calibration plot

**Minimum bar:** strictly better than random baseline on both primary metrics.

### 4.5 Modeling Artifacts (Planned)

Notebooks to be created under `notebooks/`:
- `03_modeling_baselines.ipynb` — logistic regression
- `04_modeling_xgboost.ipynb` — XGBoost main baseline
- `05_modeling_modernbert.ipynb` — ModernBERT-enhanced variant

---

## 5. Evaluation

### 5.1 Evaluation Approach

Each success criterion from [Section 1.6](#16-data-mining-success-criteria) is checked explicitly and verifiably using pipeline outputs and modeling notebook results. Evaluation is consolidated in an **evaluation scorecard** — a table with one row per criterion, measured value, target, and verdict.

### 5.2 Evaluation Scorecard Template

| # | Criterion | Target | Measured | Verdict |
|---|---|---|---|---|
| 1 | Dataset scale | ≥ 5000 accepted | _TBD_ | _TBD_ |
| 2 | Unique repositories | ≥ 500 | _TBD_ | _TBD_ |
| 3 | Language coverage | ≥ 3 | _TBD_ | _TBD_ |
| 4 | Trace completeness | ≥ 95% | _TBD_ | _TBD_ |
| 5 | Bot pollution | 0% | _TBD_ | _TBD_ |
| 6 | Residual audit noise | < 10% | _TBD_ | _TBD_ |
| 7 | Schema completeness | 100% | _TBD_ | _TBD_ |
| 8 | Baseline ROC-AUC | > random | _TBD_ | _TBD_ |
| 9 | Baseline F1 | > majority | _TBD_ | _TBD_ |
| 10 | Parquet load time | < 2 min | _TBD_ | _TBD_ |

### 5.3 Error Analysis

Planned analyses:
- **Reject reason breakdown** — frequency of each reason in rejected pool
- **Audit sample review** — human-judged trivial/docs/weak-review rate in 100 accepted traces
- **Label imbalance check** — `review_concern` class balance in the modeling set
- **Feature importance** — top features for XGBoost baseline
- **Failure mode analysis** — confusion matrix error cases, especially false positives on `review_concern`

### 5.4 Business Evaluation

The Business Unit prepares:
- Success-criteria scorecard
- Short product description (one-pager) covering value proposition, customer segments, example use cases
- Commercial readiness assessment

---

## 6. Deployment

### 6.1 Deployment Goal

Package the dataset and reference model into a form that can be handed to an external team or customer. **The deployment artifact is data + documentation + reference code, not a running service.**

### 6.2 Deliverables

| Artifact | Path / Location | Status |
|---|---|---|
| Final accepted dataset (JSONL) | `data/processed/dataset_v1.0.accepted.jsonl` | Planned |
| Final accepted dataset (Parquet) | `data/processed/dataset_v1.0.accepted.parquet` | Planned |
| Rejected pool (for error analysis) | `data/processed/dataset_v1.0.rejected.{jsonl,parquet}` | Planned |
| Train/Val/Test splits | `data/processed/dataset_v1.0.{train,val,test}.{jsonl,features.{csv,parquet}}` | Planned |
| SFT files | `data/processed/dataset_v1.0.{review_sft,issue_to_patch_sft}.jsonl` | Planned |
| Schema documentation | This document, [Section 9](#9-data-schema-reference) | Present |
| Dataset card | `data/processed/DATASET_CARD.md` | Auto-generated |
| Quality report | `reports/quality_report_v1.0.md` | Auto-generated |
| Reference model + inference example | `notebooks/` + saved model artifact | Planned |
| Deployment guide | To be written | Planned |
| Product one-pager | To be written | Planned |
| Final report + slides + video | Presentation materials | Planned |

### 6.3 Reproducibility Requirements

- Pipeline must run end-to-end on project hardware with zero paid services
- All config lives in `config.yaml`
- Data splits reproducible from seed (42)
- Dataset card + quality report auto-generated by the pipeline

---

# Part B — Operational Sections

---

## 7. Glossary & Terminology

Plain-language definitions of every term used in this project. Grouped by topic.

### 7.1 Core Concepts

**Pull request (PR)** — A proposed change to a GitHub repository. Identified by `owner/repo` + integer PR number. One PR = one row in our dataset.

**Candidate** — A PR that looks plausible for inclusion, before any enrichment. Produced by the BigQuery SQL or by `pipeline/gharchive.py`. A candidate has only the basic fields visible in GH Archive events.

**Enrichment** — The process of calling the GitHub REST API to fetch full PR details (PR object, files, reviews, comments, linked issue, full diff).

**Trace (also called example)** — One fully-assembled enriched PR as a nested JSON object. Seven top-level blocks. "Trace" = documentation term; "example" = code term; they mean the same thing.

**Accepted example** — A trace that passed all hard filters AND reached score ≥ 70. Written to `dataset_*.accepted.jsonl`.

**Rejected example** — A trace that failed at least one hard filter OR did not reach the score threshold. Written to `dataset_*.rejected.jsonl` (kept for error analysis).

**Reject reason** — A short string identifying why a trace failed acceptance. See [Section 10](#10-reject-reasons-reference).

**Quality score** — Integer from weighted sum of positive signals minus penalties. Threshold for acceptance: 70.

### 7.2 Review-Related Terms

**Review** — A formal submission on a PR with a state: `APPROVED`, `CHANGES_REQUESTED`, `COMMENTED`, `DISMISSED`, or `PENDING`. We never see `PENDING` (not visible externally).

**Review comment** — An inline comment on a specific line or diff hunk. Looks like a sticky note on the code.

**Issue comment / PR comment** — A thread-level comment on the conversation tab. Not tied to code.

**Meaningful review comment** — A review comment that passes the trivial-comment filter. Must be ≥ 30 characters after trim/lower AND not match trivial phrases (`lgtm`, `looks good`, `thanks`, `+1`, `approved`, etc.).

> Example of meaningful: *"This branch swallows the original exception and makes debugging harder."*
> Example of NOT meaningful: *"lgtm"*

**Changes requested** — The `CHANGES_REQUESTED` review state. Indicates reviewer blocked the PR pending changes. Primary positive signal for `review_concern`.

**Author association** — GitHub field indicating PR author's relationship to the repo: `OWNER`, `MEMBER`, `COLLABORATOR`, `CONTRIBUTOR`, `FIRST_TIME_CONTRIBUTOR`, `FIRST_TIMER`, `NONE`.

### 7.3 Code-Related Terms

**Patch (file-level)** — The unified-diff text for a **single changed file**, as returned by GitHub in the `patch` field.

**Full diff** — The unified-diff text of the **whole PR**. Fetched with `Accept: application/vnd.github.v3.diff`.

**Source file** — A changed file whose extension is in `SOURCE_EXTS` (14 languages: Python, JS, TS, Go, Java, Rust, C, C++, C#, Ruby, PHP, Swift, Kotlin, Scala).

**Generated / vendor file** — File whose path contains `vendor/`, `dist/`, `build/`, `generated/`, `node_modules/`, `third_party/`, `.pb.`, `.generated.`, etc.

**Lockfile** — `package-lock.json`, `yarn.lock`, `poetry.lock`, `Cargo.lock`, etc.

**Docs-only change** — PR where every changed file is documentation (`.md`, `.rst`, `.txt`, `.adoc`, or path contains `docs/`).

### 7.4 ML Task Terms

**Review concern label** — The binary modeling target. 1 = reviewers raised substantive concerns. 0 = review happened but no concerns. Excluded = no review at all. See [Section 4.1](#41-modeling-task).

**Label leakage** — Using a feature the model would not have at prediction time. For us, prediction time = PR opening. Any review-derived feature is leakage.

**PR-intrinsic feature** — Computable at PR opening: title, body, files, size, author, linked issue. Safe for training.

**Review-derived feature** — Only available after review activity. Excluded from training.

**Repo-level stratified split** — Train/val/test split by repository. Prevents learning repo-specific conventions.

### 7.5 Data Format Terms

**JSONL** — Newline-delimited JSON (one JSON object per line). Working format.

**Parquet** — Columnar storage format. Release format.

**SFT format** — Supervised fine-tuning format for LLM training. Contains `messages` list in chat format (system, user, assistant) + `metadata`.

### 7.6 Filter Terms

**Bot author** — Login ending in `[bot]` or containing known bot fragments (`dependabot`, `renovate`, `github-actions`, `pre-commit-ci`, `snyk-bot`, `deepsource`, `imgbot`).

**Trivial diff** — Smaller than min line count (default 50) or fewer than min files (default 2).

**Oversized diff** — More than max lines (default 2000) or more than max files (default 30).

---

## 8. Repository Layout

```
.
├── config.yaml                      # All pipeline parameters
├── requirements.txt                 # Python dependencies
├── business_understanding.md        # CRISP-DM BU document (external deliverable)
├── pipeline/                        # Python pipeline
│   ├── __init__.py
│   ├── __main__.py                  # Entry point
│   ├── cli.py                       # Command-line interface
│   ├── config.py                    # Config loading (YAML → dataclasses)
│   ├── gharchive.py                 # Local GH Archive candidate building
│   ├── github_client.py             # GitHub REST API client with retries
│   ├── enrich.py                    # PR enrichment orchestrator
│   ├── filters.py                   # Quality evaluation + reject reasons
│   ├── schema.py                    # Trace assembly (nested JSON)
│   ├── split.py                     # Repo-level train/val/test split
│   ├── features.py                  # Feature table export (CSV + Parquet)
│   ├── parquet_export.py            # Trace Parquet export
│   ├── sft.py                       # SFT format export
│   ├── audit.py                     # Audit sample CSV
│   ├── report.py                    # Quality report generation
│   ├── datacard.py                  # Dataset card generation
│   └── export_jsonl.py              # JSONL I/O utilities
├── sql/                             # BigQuery queries
│   ├── 01_candidate_prs.sql         # Produces candidate table
│   └── 02_candidate_stats.sql       # Exploratory statistics
├── data/                            # Data artifacts (gitignored)
│   ├── candidates/                  # Candidate CSVs
│   ├── raw/                         # Enriched JSONL + failures
│   ├── processed/                   # Accepted/rejected, splits, SFT, etc.
│   └── audit/                       # Audit CSVs
├── reports/                         # Generated quality reports (gitignored)
└── notebooks/                       # (to be added) analysis notebooks
    ├── 01_data_understanding.ipynb
    ├── 02_data_preparation.ipynb
    ├── 03_modeling_baselines.ipynb
    ├── 04_modeling_xgboost.ipynb
    ├── 05_modeling_modernbert.ipynb
    └── 06_evaluation.ipynb
```

**Naming conventions:**
- Python files, config keys: `lower_snake_case`
- Markdown docs: `lower_snake_case.md`
- Notebooks: `NN_lower_snake_case.ipynb` (NN = two-digit phase number)
- Dataset artifacts: `dataset_{version}.{purpose}.{extension}`

**Gitignored:** `data/candidates/*`, `data/raw/*`, `data/processed/*`, `data/audit/*`, `reports/*` (only `.gitkeep` tracked).

---

## 9. Data Schema Reference

Each trace (one row of the dataset) is a nested JSON object with **top-level identifiers** plus **seven blocks**.

### 9.1 Top-Level Identifiers

| Field | Type | Description |
|---|---|---|
| `example_id` | string | `{repo_slashes_to_underscores}__pull_{pr_number}` |
| `repo` | string | `owner/name` |
| `pr_number` | int | GitHub PR number |
| `pr_url` | string | HTML URL of PR |
| `linked_issue_number` | int or null | Detected via closing keyword regex |
| `linked_issue_url` | string or null | HTML URL of linked issue |

### 9.2 Block: `issue` (linked issue data)

All fields are null if no linked issue detected.

| Field | Type | Description |
|---|---|---|
| `title` | string | Issue title |
| `body` | string | Issue body |
| `author` | object | `{login, type, html_url}` |
| `created_at` | ISO timestamp | |
| `updated_at` | ISO timestamp | |
| `comments` | array of comment objects | Each comment: `{id, author, body, created_at, updated_at, html_url}` |

### 9.3 Block: `discussion`

| Field | Type | Description |
|---|---|---|
| `pr_comments` | array of comment objects | Thread-level PR comments (not inline) |

### 9.4 Block: `pr`

| Field | Type | Description |
|---|---|---|
| `title` | string | PR title |
| `body` | string | PR description |
| `author` | object | `{login, type, html_url}` |
| `author_association` | string | `OWNER` / `MEMBER` / ... |
| `created_at`, `updated_at`, `closed_at`, `merged_at` | ISO timestamp | |
| `base_sha`, `head_sha`, `merge_commit_sha` | string | Git SHAs |
| `changed_files`, `additions`, `deletions`, `commits` | int | Counts |

### 9.5 Block: `review`

| Field | Type | Description |
|---|---|---|
| `reviews` | array | Formal reviews: `{id, author, state, body, submitted_at, commit_id, html_url}` |
| `review_comments` | array | Inline comments: `{id, author, path, diff_hunk, body, created_at, updated_at, commit_id, original_commit_id, line, original_line, html_url}` |

Review `state` values: `APPROVED`, `CHANGES_REQUESTED`, `COMMENTED`, `DISMISSED`.

### 9.6 Block: `code_diff`

| Field | Type | Description |
|---|---|---|
| `files` | array | Each: `{filename, status, additions, deletions, changes, patch, raw_url, blob_url, previous_filename}` |
| `full_diff` | string or null | Complete unified diff text |

File `status` values: `added`, `modified`, `removed`, `renamed`.

### 9.7 Block: `quality`

| Field | Type | Description |
|---|---|---|
| `accepted` | bool | Final pipeline decision |
| `score` | int | Quality score |
| `tier` | string | `mvp_silver` (accepted) or `rejected` |
| `reject_reasons` | array of strings | See [Section 10](#10-reject-reasons-reference) |
| `discussion_count` | int | PR comments + linked issue comments |
| `review_comment_count` | int | Total inline review comments |
| `meaningful_review_comment_count` | int | After trivial filter |
| `source_file_count` | int | Changed files with source extension |
| `source_patch_count` | int | Source files that have a patch |
| `diff_lines` | int | `additions + deletions` |

### 9.8 Block: `provenance`

| Field | Type | Description |
|---|---|---|
| `source` | string | `gharchive_bigquery_plus_github_rest_api` |
| `retrieved_at` | ISO timestamp | |
| `candidate_source` | string | |
| `api_errors` | array | Each: `{stage, error_type, message, status_code?}` |

---

## 10. Reject Reasons Reference

Each rejection reason attached to `quality.reject_reasons`. A trace can have multiple.

| Reason | What it means | Why it's applied |
|---|---|---|
| `not_merged` | PR was closed without merge | We only want traces of accepted changes — the diff reflects the final state |
| `no_explicit_linked_issue` | No `fixes #N` / `closes #N` / `resolves #N` keyword in PR body | Without a linked issue, we lose the "why" of the change |
| `bot_author` | Author login matches bot pattern | Bots don't represent human engineering work |
| `bad_changed_files_count` | `changed_files < 2` or `> 30` | Single-file = trivial; huge = not reviewable as unit |
| `bad_diff_size` | `additions + deletions < 50` or `> 2000` | Too-small diffs = trivial; too-large = mechanical refactors or merges |
| `no_files` | PR has no file changes recorded | Empty PR, likely an API anomaly |
| `docs_only` | All changed files are documentation | Docs changes don't exercise engineering workflow patterns we want |
| `lockfile_only` | All changed files are dependency lockfiles | Auto-generated; no engineering reasoning |
| `generated_or_vendor_only` | All changed files are in `vendor/`, `dist/`, `generated/`, etc. | Not hand-written code |
| `no_source_files` | Not a single file has a source-code extension | Without source, there's nothing to review in code |
| `no_source_patches` | Source files exist but none have a `patch` field | API didn't return patches — can't reconstruct the change |
| `not_enough_review_comments` | Total inline review comments < 2 | Too little review signal |
| `not_enough_meaningful_review_comments` | After filtering trivial comments, < 2 meaningful remain | "lgtm"-only reviews don't teach the model anything |
| `not_enough_discussion` | `pr_comments + issue_comments < 2` | Too little workflow context |
| `missing_full_diff` | Full diff was requested but not retrieved | Required field for `code_diff.full_diff` |

**Note on penalties:** `bot_author`, `docs_only`, `lockfile_only`, `generated_or_vendor_only` each subtract 20 points from the quality score in addition to being reject reasons.

---

## 11. CLI Reference

All commands run as `python -m pipeline <command> [options]`. Config is read from `config.yaml` by default (override with `--config PATH`).

### 11.1 Stage 1 — Candidate Discovery

**Option A: BigQuery path (primary).**

Run `sql/01_candidate_prs.sql` in BigQuery, export result as CSV to `data/candidates/candidates_YYYY_MM.csv`.

**Option B: Local GH Archive path (fallback).**

```bash
# Step 1: Download GH Archive hourly dumps
python -m pipeline download-gharchive \
    --start-date 2026-01-01 \
    --end-date 2026-01-07 \
    --output-dir data/gharchive/2026-01

# Step 2: Build candidate CSV from downloaded files
python -m pipeline candidates-from-gharchive \
    --input-glob "data/gharchive/2026-01/*.json.gz" \
    --output data/candidates/candidates_2026_01.csv
```

### 11.2 Stage 2 — Enrichment

```bash
# Requires env var GITHUB_TOKEN
python -m pipeline enrich \
    --candidates data/candidates/candidates_2026_01.csv

# With limits for testing
python -m pipeline enrich \
    --candidates data/candidates/candidates_2026_01.csv \
    --limit 100 \
    --offset 0
```

Output: `data/raw/enriched_prs_raw.jsonl` (appended) and `data/raw/enriched_prs_failed.jsonl` (appended on failure).

### 11.3 Stage 3 — Processing

```bash
# Apply filters, compute scores, write accepted/rejected JSONL
python -m pipeline process
```

### 11.4 Stage 4 — Split

```bash
# Repo-level train/val/test split
python -m pipeline split
```

### 11.5 Stage 5 — Export

```bash
# Flat feature tables for modeling
python -m pipeline features

# Trace Parquet export
python -m pipeline export-parquet

# SFT datasets for LLM training
python -m pipeline sft
```

### 11.6 Stage 6 — Quality Assurance

```bash
# Human audit sample (accepted + rejected + borderline)
python -m pipeline audit

# Markdown quality report
python -m pipeline report

# Dataset card
python -m pipeline data-card
```

### 11.7 Full Post-Enrichment Run

```bash
# Runs: process → split → features → export-parquet → sft → audit → report → data-card
python -m pipeline finalize
```

> **Known issue:** `finalize` has minor edge-case inconsistencies. Running stages individually is more reliable.

### 11.8 Command Summary Table

| Command | Input | Output | Runtime (approx) |
|---|---|---|---|
| `download-gharchive` | GH Archive URLs | `data/gharchive/*.json.gz` | Minutes–hours |
| `candidates-from-gharchive` | Local `.json.gz` | Candidates CSV | Minutes |
| `enrich` | Candidates CSV | `enriched_prs_raw.jsonl` | ~2.4s per PR |
| `process` | Raw JSONL | `accepted.jsonl`, `rejected.jsonl` | Seconds |
| `split` | Processed JSONL | `train/val/test.jsonl` | Seconds |
| `features` | Split JSONL | Feature CSV + Parquet | Seconds |
| `export-parquet` | Processed JSONL | Traces Parquet | Seconds |
| `sft` | Accepted JSONL | SFT JSONL | Seconds |
| `audit` | Processed JSONL | Audit CSV | Seconds |
| `report` | Processed JSONL | Quality report MD | Seconds |
| `data-card` | Processed JSONL | Dataset card MD | Seconds |
| `finalize` | Raw JSONL | All of the above | ~1 minute |

---

## 12. Local Setup Guide

### 12.1 Prerequisites

- Python 3.10+
- Git
- GitHub personal access token (public repo read permission)
- (Optional) Google Cloud project with BigQuery access
- ~10 GB free disk for MVP-sized runs

### 12.2 Setup Steps

```bash
# 1. Clone
git clone <repository-url>
cd <repository-dir>

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux / macOS
# .venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure GitHub token
export GITHUB_TOKEN=ghp_your_token_here        # Linux / macOS
# $env:GITHUB_TOKEN = "ghp_your_token_here"    # Windows PowerShell

# 5. Verify config
cat config.yaml                                # Review parameters

# 6. Smoke test with a small slice
python -m pipeline enrich \
    --candidates data/candidates/sample.csv \
    --limit 5
```

### 12.3 Data Directory Bootstrap

The `.gitkeep` files should already be in place. If missing:

```bash
mkdir -p data/candidates data/raw data/processed data/audit reports
touch data/candidates/.gitkeep data/raw/.gitkeep data/processed/.gitkeep data/audit/.gitkeep reports/.gitkeep
```

### 12.4 Typical End-to-End Run

```bash
# Assume candidates CSV is already in place
export GITHUB_TOKEN=ghp_...

# 1. Enrich
python -m pipeline enrich --candidates data/candidates/candidates_2026_01.csv

# 2. Everything else in one go
python -m pipeline finalize
```

### 12.5 Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `RuntimeError: Missing GitHub token` | `GITHUB_TOKEN` not exported | `export GITHUB_TOKEN=...` |
| Long sleeps during enrichment | GitHub rate limit hit | Expected; pipeline handles automatically |
| 404 errors on specific PRs | Repo deleted or made private | Written to failures JSONL, skipped |
| `finalize` edge-case inconsistency | Known issue | Run stages individually |
| Parquet write fails | `pyarrow` version mismatch | `pip install --upgrade pyarrow` |

---

## 13. Project Status Dashboard

### 13.1 Dataset Versions

| Version | Time Window | Status | Size |
|---|---|---|---|
| `dataset_mvp_v0.1` | March 2025 | **Complete (MVP)** | ~7500 enriched PRs |
| `dataset_v1.0` | First weeks of several months in 2026 | **In collection** (final submission) | Target ~10000 traces |

### 13.2 CRISP-DM Phase Progress

```
Business Understanding  ████████████████████░  95%
Data Understanding      ████████████░░░░░░░░  60%
Data Preparation        ████████████████░░░░  80%
Modeling                ░░░░░░░░░░░░░░░░░░░░   0%
Evaluation              ░░░░░░░░░░░░░░░░░░░░   0%
Deployment              ███░░░░░░░░░░░░░░░░░  15%
```

### 13.3 Artifact Status

**Complete:**
- Full `pipeline/` module tree (15 modules)
- `config.yaml` populated
- BigQuery SQL (`sql/01_candidate_prs.sql`, `sql/02_candidate_stats.sql`)
- `business_understanding.md` (draft)
- MVP run: ~7500 enriched PRs
- Dataset card auto-generator
- Quality report auto-generator
- Audit sample generator
- 2026 data collection has started

**In progress:**
- `dataset_v1.0` data collection
- This master document

**Not started:**
- Analysis notebooks (data understanding, preparation, modeling, evaluation)
- `review_concern` label implementation in pipeline
- Feature partitioning (no-leak vs review-derived)
- Baseline model (logistic regression)
- XGBoost model
- ModernBERT-enhanced model
- Evaluation scorecard
- Slide deck
- Video
- Product one-pager
- Final report
- Deployment guide
- User-facing dataset README

### 13.4 Known Issues

| ID | Issue | Impact | Workaround |
|---|---|---|---|
| I-1 | `finalize` command has minor edge-case inconsistencies | Low | Run stages individually |
| I-2 | Candidate CSV columns differ between BigQuery and local GH Archive | None (MVP uses BigQuery) | Stick to BigQuery path |
| I-3 | `quality.accepted` is a curation label, not a modeling target | Blocks modeling | Implement `review_concern` label |
| I-4 | Feature table mixes PR-intrinsic and review-derived columns | Blocks modeling | Partition features per [Section 4.2](#42-feature-partitioning) |
| I-5 | Linked-issue regex does not follow cross-repo references | Minor coverage loss | Accepted trade-off |

---

## 14. Task Checklist

Tasks ordered by priority. Priority legend:

- **P0** — Blocks final submission
- **P1** — Important for quality
- **P2** — Nice to have

Status legend: `[ ]` not started, `[~]` in progress, `[x]` done.

### 14.1 Data Preparation Tasks

| ID | Task | Priority | Est. Effort | Status | Depends on |
|---|---|---|---|---|---|
| DP-1 | Complete `dataset_v1.0` data collection (2026 data) | P0 | 1–2 days | `[~]` | — |
| DP-2 | Implement `review_concern` label in `pipeline/filters.py` or new module | P0 | 0.5 day | `[ ]` | — |
| DP-3 | Partition features into PR-intrinsic vs review-derived groups in `pipeline/features.py` | P0 | 0.5 day | `[ ]` | DP-2 |
| DP-4 | Fix `finalize` edge-case inconsistencies | P2 | 0.5 day | `[ ]` | — |
| DP-5 | Audit sample review (100 accepted traces, manual labeling) | P1 | 0.5 day | `[ ]` | DP-1 |

### 14.2 Notebook Tasks

| ID | Task | Priority | Est. Effort | Status | Depends on |
|---|---|---|---|---|---|
| NB-1 | `01_data_understanding.ipynb` — EDA, distributions, reject reasons breakdown | P0 | 0.5 day | `[ ]` | DP-1 |
| NB-2 | `02_data_preparation.ipynb` — feature analysis, label balance, split visualization | P0 | 0.5 day | `[ ]` | DP-2, DP-3 |
| NB-3 | `03_modeling_baselines.ipynb` — logistic regression baseline | P0 | 0.5 day | `[ ]` | NB-2 |
| NB-4 | `04_modeling_xgboost.ipynb` — XGBoost main baseline | P0 | 1 day | `[ ]` | NB-3 |
| NB-5 | `05_modeling_modernbert.ipynb` — ModernBERT-enhanced variant | P1 | 1–2 days | `[ ]` | NB-4 |
| NB-6 | `06_evaluation.ipynb` — scorecard, error analysis, feature importance | P0 | 0.5 day | `[ ]` | NB-4 |

### 14.3 Documentation Tasks

| ID | Task | Priority | Est. Effort | Status | Depends on |
|---|---|---|---|---|---|
| DOC-1 | Update `business_understanding.md` to match this doc (task = review_concern, criteria values) | P0 | 0.5 day | `[ ]` | — |
| DOC-2 | Evaluation scorecard (filled with measured values) | P0 | 0.25 day | `[ ]` | NB-6 |
| DOC-3 | Product one-pager | P0 | 0.5 day | `[ ]` | NB-6 |
| DOC-4 | Deployment guide / user-facing README for the dataset | P0 | 0.5 day | `[ ]` | DP-1 |
| DOC-5 | Final report consolidating all phases | P0 | 1 day | `[ ]` | DOC-2, DOC-3 |

### 14.4 Presentation Tasks

| ID | Task | Priority | Est. Effort | Status | Depends on |
|---|---|---|---|---|---|
| PR-1 | Slide deck (walk through CRISP-DM phases + results) | P0 | 0.5 day | `[ ]` | NB-6 |
| PR-2 | Video recording (6 scenes per script) | P0 | 0.25 day | `[ ]` | PR-1 |

### 14.5 Dependency Graph

```
DP-1 ──┬─────────────────► NB-1 ──┐
       │                          │
       └► DP-2 ──► DP-3 ──► NB-2 ─┴► NB-3 ──► NB-4 ──┬► NB-5
                                                     │
                                                     └► NB-6 ──┬► DOC-2 ──┐
                                                               │          │
                                                               └► DOC-3 ──┤
                                                                          │
                                                                          ├► DOC-5 ──► PR-1 ──► PR-2
                                                               DP-1 ──► DOC-4 ──┘

DOC-1 (independent, can be done any time)
DP-4  (independent, low priority)
DP-5  (after DP-1, before NB-6)
```

---

## 15. Presentation & Video Materials

### 15.1 Presentation Outline

Walk through each CRISP-DM stage, what was done, show modeling results.

1. **Business Understanding** — problem, market, objectives, success criteria
2. **Data Understanding** — sources, schema, exploration highlights
3. **Data Preparation** — pipeline overview, filtering, scoring
4. **Modeling** — task, feature partitioning, model progression, metrics
5. **Evaluation** — scorecard, error analysis, business assessment
6. **Deployment** — dataset packaging, documentation, reference model

### 15.2 Video Script (6 Scenes)

**Scene 1 — The market problem**
> "AI coding assistants are becoming more powerful, but they need high-quality software engineering data. Existing datasets often contain code, commits, or isolated examples, but they miss the full workflow: why a change was made, how it was discussed, reviewed, and merged."

**Scene 2 — The raw-data problem**
> "GH Archive contains public GitHub activity, but it is noisy and difficult to use directly. It includes bots, trivial PRs, generated files, lockfile-only changes, oversized diffs, and incomplete event chains."

**Scene 3 — The Muhomory solution**
> "Our pipeline discovers merged PR candidates, enriches them with reviews, comments, files, diffs, linked issues, and repository metadata, then filters and scores the traces."

**Scene 4 — The resulting product**
> "The output is a curated workflow-level dataset: each example represents a software engineering trace, packaged in JSONL and Parquet, with schema documentation, labels, and usage examples."

**Scene 5 — ML validation**
> "To show that the dataset is useful, we train a baseline model for PR trace quality classification. The model performs better than random, which shows that the accepted and rejected traces contain learnable signal."

**Scene 6 — Why it matters**
> "For AI companies, this saves engineering time and provides higher-quality training and evaluation data. For Muhomory, it demonstrates a reusable pipeline for commercial dataset creation."

---

## 16. Configuration Reference

All pipeline parameters live in `config.yaml`. **Edit here when you need to tune the pipeline.**

### 16.1 GitHub Client Settings

```yaml
github:
  token_env: GITHUB_TOKEN          # Env var holding the PAT
  api_base: "https://api.github.com"
  api_version: "2022-11-28"        # GitHub REST API version
  per_page: 100                    # Pagination size
  max_workers: 2                   # Concurrency (keep low to avoid rate limits)
  retry_count: 5                   # Retry attempts per request
  request_timeout_seconds: 60
  sleep_on_rate_limit: true        # Auto-wait on 403 rate-limit
  progress_interval: 10            # Log progress every N PRs
```

### 16.2 Dataset Filters

```yaml
dataset:
  min_discussion_comments: 2       # PR comments + issue comments total
  min_review_comments: 2           # Raw inline review comment count
  min_meaningful_review_comments: 2  # After trivial-comment filter
  min_changed_files: 2
  max_changed_files: 30
  min_diff_lines: 50               # additions + deletions
  max_diff_lines: 2000
  require_linked_issue: true       # Reject if no `fixes #N` etc.
  require_source_patch: true       # Reject if no source file has a patch
  store_full_diff: true            # Fetch full unified diff from GitHub
```

### 16.3 Filter Toggles

```yaml
filters:
  exclude_bots: true
  exclude_docs_only: true
  exclude_lockfile_only: true
  exclude_generated_vendor_only: true
  exclude_trivial_review_comments: true
```

### 16.4 Audit Sampling

```yaml
audit:
  accepted_sample_size: 150
  rejected_sample_size: 50
  borderline_sample_size: 50       # Score in [60, 80]
  random_seed: 42
```

### 16.5 Train/Val/Test Split

```yaml
split:
  train_ratio: 0.8
  val_ratio: 0.1
  test_ratio: 0.1
  random_seed: 42
```

### 16.6 Output Paths

All output paths are configurable. Default names include version string `dataset_mvp_v0.1`. **For `dataset_v1.0`, update the `output.*` paths accordingly.**

```yaml
output:
  raw_path: "data/raw/enriched_prs_raw.jsonl"
  failed_path: "data/raw/enriched_prs_failed.jsonl"
  accepted_path: "data/processed/dataset_mvp_v0.1.accepted.jsonl"
  rejected_path: "data/processed/dataset_mvp_v0.1.rejected.jsonl"
  # ... (see config.yaml for full list)
```

### 16.7 Common Tuning Scenarios

| Goal | Parameter to change |
|---|---|
| Stricter review signal | Raise `min_meaningful_review_comments` |
| Allow smaller PRs | Lower `min_diff_lines` |
| Allow larger PRs | Raise `max_diff_lines` |
| Permit docs-only | Set `filters.exclude_docs_only: false` |
| Drop linked-issue requirement | Set `dataset.require_linked_issue: false` |
| Increase throughput (risky) | Raise `github.max_workers` (watch for secondary rate limits) |
| Switch dataset version | Update all `output.*` paths |
| Change split ratios | Edit `split.train_ratio` / `val_ratio` / `test_ratio` (must sum to 1.0) |

---
