# Muhomory GitHub Workflow Dataset — Project Master Document

> **Single source of truth** for the Muhomory GitHub Workflow Dataset project.
> This document follows the **CRISP-DM** methodology in its first part, and contains additional operational sections at the end.
> When this document and the code disagree, **the code wins**. Current CRISP-DM report fragments are `business_understanding.tex` and `data_understanding.tex`.

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

### 1.1 Determine Business Objectives

#### 1.1.1 Background

Over the last several years the market for AI-assisted software engineering has matured considerably. Coding assistants, autonomous developer agents, and automated code review systems have moved from research prototypes to commercial products that are actively used inside engineering organizations. These systems are trained and evaluated on datasets of source code and code-related artifacts, and the quality of those datasets is increasingly recognized as a bottleneck on model quality.

The existing public resources in this space — The Stack, CommitPack, CodeSearchNet, and similar collections — focus on isolated artifacts: raw source code, individual commits, or aligned code–text pairs. They rarely capture the engineering workflow in which those artifacts are produced. The issue that motivated a change, the discussion that shaped its direction, the pull request that implemented it, and the review activity that either accepted or contested it are typically not linked together in a form that an ML team can consume directly.

Companies building code-related AI systems are therefore forced to choose between three unattractive options:

- parse raw GitHub event dumps themselves, which requires substantial engineering effort and still leaves them with significant noise, bot pollution, and missing cross-event links;
- contract manual labeling, which is expensive and rarely tailored to software engineering;
- limit themselves to existing open datasets and accept that the workflow layer is missing.

The Muhomory GitHub Workflow Dataset project addresses this gap. It delivers a curated collection of software engineering workflow traces assembled from public GitHub activity, together with a baseline machine learning model that demonstrates the dataset carries real predictive signal on a realistic downstream task. Both deliverables are produced by a reusable pipeline that can be rerun on new time slices of GitHub activity.

#### 1.1.2 Business Objectives

The business objective is to deliver a reusable dataset of public GitHub workflow traces. Each trace should connect the motivating issue, pull request metadata, discussion, review activity, code diff, quality metadata, and provenance into one structured record suitable for machine learning teams building code review or developer-assistance systems.

#### 1.1.3 Business Success Criteria

The business goal is achieved if the final release:

- contains a curated multi-repository dataset of linked GitHub workflows, filtered to remove bots, trivial changes, generated files, documentation-only changes, and incomplete issue-to-pull-request-to-review chains;
- supports at least one realistic downstream task with a model that beats simple baselines;
- is valuable enough to be positioned as a niche dataset product for AI teams working on code review automation.

### 1.2 Assess Situation

#### 1.2.1 Inventory of Resources

Two categories of data support the project. The first is the **GH Archive** public dataset, accessed primarily through BigQuery and, as a fallback, through direct download of the hourly `.json.gz` dumps. GH Archive provides hourly snapshots of GitHub public events going back to 2011 and serves as the source for candidate pull request discovery. The second is the **GitHub REST API**, which is used to enrich each candidate with full pull request metadata, files, reviews, comments, linked issues, and the full unified diff. API access is authenticated with a personal access token stored in the `GITHUB_TOKEN` environment variable.

The software resources consist of the project codebase, a standard Python 3.10 environment with the dependencies listed in `requirements.txt`, and a YAML configuration file that centralizes every pipeline parameter. Hardware resources are limited to the team's local development machines; the project explicitly avoids paid compute and paid data services.

#### 1.2.2 Requirements, Assumptions, and Constraints

Key assumptions underpinning the project are the following:

- public GitHub activity is sufficiently representative of real engineering workflows to train models whose behavior transfers to private codebases;
- rule-based filtering is sufficient to reach usable quality without full manual labeling (verified during evaluation through an audit sample);
- the `review_concern` label, defined in section 1.3, captures a real and useful signal about the quality of a pull request at the moment it is opened;
- splitting data by repository is sufficient to prevent train/test leakage for the scope of this project; time-based splitting is deferred to a future version.

Constraints apply primarily to data access and compute. The GitHub REST API imposes a rate limit of approximately five thousand requests per hour per token, which sets an upper bound on enrichment throughput. The project operates on public repositories only. Local disk and memory are sufficient for dataset sizes in the low tens of thousands of traces but would require revisiting for significantly larger runs.

#### 1.2.3 Risks and Contingencies

Several risks affect delivery.

- **Data quality.** GH Archive events are noisy; bots produce a large fraction of surface-level activity; trivial or generated changes are common; and not every repository exposes a clean issue-to-pull-request-to-review-to-merge chain. The pipeline mitigates this risk through multi-stage filtering, including bot heuristics, size thresholds, linked-issue requirements, and file-level filters on generated and vendored content. A residual-noise check is performed on an audit sample during evaluation.
- **Label imbalance.** The `review_concern` positive class may be rare in a workflow-filtered dataset; if the class balance proves too skewed, the label definition will be revised before modeling.
- **Insufficient candidate volume.** The chosen time windows may yield too few candidates; the pipeline is designed to extend easily to additional time windows if needed.
- **API quota exhaustion.** GitHub rate limits may be hit during large enrichment runs; the client handles this through retry with backoff and explicit rate-limit-aware sleeps.

#### 1.2.4 Terminology

A full glossary of project-specific terms, phrased in plain language, is provided in section 7. Readers unfamiliar with GitHub workflow terminology, with the internal vocabulary of the pipeline, or with the modeling task should consult that section before continuing.

#### 1.2.5 Costs and Benefits

The direct cost is mainly team time; data access and compute are free or local. As a conservative benchmark, raw GitHub datasets are sold at about $250 per 100,000 records. This project targets a smaller but richer dataset: about 10,000 enriched workflow traces with issue, review, discussion, and diff context. A realistic non-exclusive license price is about $1,000-$3,000 per customer, or $5,000-$10,000 with refreshes and support. With five basic customers, expected revenue is about $5,000-$15,000; with three enterprise customers, about $15,000-$30,000. The business value is saved engineering effort: customers avoid building a GitHub collection, enrichment, filtering, and schema pipeline themselves.

### 1.3 Determine Data Mining Goals

#### 1.3.1 Data Mining Goals

Translated into data mining terms, the business objective corresponds to the following goals.

**Goal 1 — corpus construction.** Construct at least five thousand accepted workflow traces, with a target of about ten thousand traces. One trace is one pull request-centered workflow record. Accepted means that the trace passed the project filters: merged pull request, explicit linked issue, source-code changes, non-empty diff, review and discussion activity, and no bot, generated-only, documentation-only, or trivial-change pattern. Each accepted trace should follow the fixed schema consisting of linked issue, discussion, pull request metadata, review activity, code diff, quality metadata, and provenance.

**Goal 2 — supervised classifier.** Construct a supervised binary classifier for a task named `review_concern`. Given a pull request at the moment it is opened, the classifier predicts whether reviewers will raise substantive concerns during review.

The label is defined as follows:

- **positive (1):** the pull request received at least one formal review with state `CHANGES_REQUESTED`, or at least two meaningful review comments;
- **negative (0):** the pull request received review activity but no concerns meeting the positive threshold;
- **excluded:** pull requests with no review activity at all.

A strict separation is maintained between features available at prediction time, which are intrinsic to the pull request, and features derived from review activity, which are available only after the fact and are excluded from the training feature set.

Three modeling variants are planned in order of increasing complexity:

1. **Logistic regression** on a small hand-crafted feature subset, as a sanity baseline;
2. **XGBoost** on the full tabular feature set, as the main baseline;
3. **XGBoost with ModernBERT embeddings** of the source-code diff, to test whether code-change signal contributes predictive power beyond the tabular features.

Data is split at the repository level, so that all pull requests from a given repository fall into the same split.

**Supporting goals.** Build a reproducible collection pipeline, export the dataset in reusable formats, and provide minimal documentation for external users.

#### 1.3.2 Data Mining Success Criteria

On the **data** side, success is defined by four quantitative targets:

- the final dataset contains at least five thousand accepted traces and targets approximately ten thousand;
- it spans at least five hundred unique repositories and at least three source-code languages;
- trace completeness — the proportion of accepted traces that contain a linked issue, a merged pull request, at least one review, and a non-empty diff — is at least ninety-five percent;
- a manual audit of one hundred accepted traces finds trivial, documentation-only, or otherwise unsuitable traces at a rate below ten percent.

On the **modeling** side, success is defined by two quantitative targets on the held-out test set:

- ROC-AUC strictly greater than a random baseline;
- F1 score strictly greater than a majority-class baseline.

These thresholds are deliberately modest, because the purpose of the modeling exercise in this project is to demonstrate that the dataset carries learnable signal, not to produce a state-of-the-art model.

### 1.4 Produce Project Plan

#### 1.4.1 Project Plan

The project is organized into the six CRISP-DM phases and is expected to iterate between them as typical for the methodology.

- **Business understanding** is stabilized in the current document.
- **Data understanding** is performed through exploratory analysis of the candidate pool and of the enriched traces, with the output consolidated in a dedicated notebook.
- **Data preparation** is encapsulated in the pipeline under the `pipeline/` package and is already implemented end to end; remaining preparation work concerns the implementation of the `review_concern` label and the partitioning of the feature table into PR-intrinsic and review-derived groups.
- **Modeling** proceeds through the three planned variants in sequence.
- **Evaluation** is consolidated in an evaluation scorecard that checks each data and modeling success criterion against its target.
- **Deployment** delivers the final dataset, the reference model, and the accompanying documentation.

The project consumes a single data pipeline run on a larger time window than the MVP, producing the `dataset_v1.0` release, followed by modeling and evaluation work on that release. Iteration between phases is expected: in particular, the data preparation phase will be revisited once the `review_concern` label distribution is measured, and the feature table will be revisited once the first modeling results are available.

#### 1.4.2 Initial Assessment of Tools and Techniques

The pipeline is implemented in Python with a small, conventional stack: `requests` for HTTP, `pandas` and `pyarrow` for tabular handling and Parquet, and standard library tooling elsewhere. Modeling uses `scikit-learn` for logistic regression, `xgboost` for gradient-boosted trees, and MLX-backed ModernBERT embeddings on local Apple Silicon. Evaluation uses `scikit-learn` metrics. This toolset is deliberately mainstream, because one of the business success criteria is that the dataset be consumable in a standard Python environment.

### 1.5 Users and Use Cases

Two user groups are targeted explicitly.

- **ML researchers and engineers at AI companies** building coding assistants, code review automation, or autonomous developer agents. They use the dataset to fine-tune or evaluate language models on workflow-context tasks such as generating review comments, predicting review concerns, or producing patches from issues.
- **Engineering teams inside software companies** who train internal models to assist their own code review process. Their primary use case is predicting, at pull request opening time, whether the pull request is likely to attract substantive review concerns, so that reviewer attention can be prioritized accordingly.

### 1.6 Scope and Non-Goals

**In scope:** the extraction and curation of workflow traces for merged pull requests from public GitHub repositories; multi-language coverage across a fixed list of fourteen source-code extensions; the `review_concern` downstream task with its three modeling variants; and the standard set of commercial data product documentation artifacts.

**Out of scope:**

- **unmerged pull requests** are not included, and as a consequence merge outcome prediction is not a task this dataset supports;
- **private repositories** are not accessed;
- **large-scale supervised fine-tuning** of a language model on the SFT files produced by the pipeline is not part of the project; the SFT files are delivered as a secondary artifact, and the project's own ML evaluation uses the tabular `review_concern` task;
- **language detection** is not attempted beyond file-extension matching;
- **production-grade deployment** in the form of an inference service with monitoring is not part of the project; the deployment artifact is a documented, reproducible dataset together with a reference model.

---

## 2. Data Understanding

### 2.1 Collect Initial Data

Data collection has two stages.

**Stage 1 — candidate discovery.** Candidate pull requests were selected from GH Archive by finding merged pull request events and joining them with issue comment, review, and review comment activity for the same repository and pull request number. The candidate filter kept pull requests with 2-30 changed files, 50-2000 changed lines, at least two issue comment events, at least one review event, and at least two review comment events. The SQL path is `sql/01_candidate_prs.sql`; the local fallback is implemented in `pipeline/gharchive.py`.

**Stage 2 — GitHub REST enrichment.** Each candidate was enriched with the full pull request object, changed-file list, formal reviews, inline review comments, pull request comments, the full unified diff, and linked issue data when available. Linked issues are detected from closing-keyword references such as `fixes #123` in the pull request title or body. Cross-repository issue references are not followed.

The current raw collected file is `enriched_prs_raw.jsonl` in the repository root. It contains the March 2025 MVP slice and is the source used by the Data Understanding notebook and report.

### 2.2 Describe Data

The raw file contains 7,563 enriched pull request records and occupies about 1.2 GB. It covers 4,758 repositories and 6,529 authors. Most pull requests were created and merged in March 2025; enrichment was retrieved on April 30, 2026 and May 1, 2026.

Each raw record contains `candidate`, `pr`, `files`, `reviews`, `review_comments`, `pr_comments`, `full_diff`, `linked_issue`, `linked_issue_comments`, `api_errors`, and `retrieved_at`. This is the enriched raw layer, not yet the final accepted dataset. The processed trace schema is still defined by section 9.

### 2.3 Explore Data

Data exploration is implemented in `notebooks/01_data_understanding.ipynb`. The notebook is code-only, contains no markdown cells, and was executed successfully with the `~/.venvs/general/` environment.

The notebook computes compact per-record statistics without storing full diff text in memory. It produces summary tables for completeness, repositories, languages, extensions, review states, rejection reasons, and numeric distributions. It also generates the following figures under `figures/data_understanding/`:

- `collection_timeline.png`
- `schema_completeness.png`
- `size_distributions.png`
- `review_activity.png`
- `language_distribution.png`
- `quality_filters.png`
- `repo_concentration.png`

Observed exploration results:

- top repositories by raw record count include `llvm/llvm-project` (77), `kubernetes/kubernetes` (45), and `openshift/release` (42);
- most common source languages by changed files are TypeScript, Python, Go, Java, Rust, and JavaScript;
- median pull request size is 5 changed files and 186 changed lines;
- median review activity is 6 formal reviews and 6 inline review comments;
- the current raw `review_concern` definition is positive for 94.5% of records, mostly because candidate discovery already required review comment activity.

### 2.4 Verify Data Quality

Raw enrichment quality is sufficient for analysis, but the file is not yet the final curated dataset.

Completeness results on `enriched_prs_raw.jsonl`:

- pull request object, file list, and full diff: 100.0%;
- formal reviews: 99.9%;
- review comments and pull request comments: 99.7%;
- source files: 80.9%;
- explicit linked issue: 12.2%;
- API error rows: 12 records, all from linked-issue lookup.

Under the current strict filters, 721 records pass as accepted traces, equal to 9.5% of the raw enriched file. The dominant rejection reason is `no_explicit_linked_issue` (6,639 records), followed by `no_source_patches` and `no_source_files`. The next data preparation step must either preserve the strict linked-issue requirement and expand collection volume, or revise linked-issue extraction if higher recall is required.

---

## 3. Data Preparation

### 3.1 Select Data

Data selection now uses all 7,563 enriched rows from `enriched_prs_raw.jsonl` for preparation. The modeling target is `review_concern`: positive if the pull request received a `CHANGES_REQUESTED` review or at least two meaningful review comments, negative if review activity exists without those signals, and excluded if review activity is absent. This leaves 7,556 labeled rows and excludes 7 rows.

Columns are restricted to pull-request-intrinsic fields and source-code patch embeddings. Review-derived counts, review states, and quality scores are retained as metadata only and are not used as model features.

### 3.2 Clean Data

Cleaning is implemented by `pipeline.data_preparation`. The existing hard-filter logic is reused to attach reject reasons and the accepted/rejected quality flag, but the modeling table keeps both accepted and rejected rows. Missing source patches are represented by an empty patch embedding plus explicit source-patch count and token-count features.

The leakage check is part of cleaning: review counts, review states, meaningful-review counts, discussion counts, and quality score are excluded from the feature columns because they are observed after pull request opening.

### 3.3 Construct Data

Data construction produces the `review_concern` label, PR-intrinsic numeric features, one-hot language and author-association features, and a 768-dimensional ModernBERT embedding of source-code `files[].patch` text. The patch text is capped at 1,000 ModernBERT tokens per row before embedding. The embedding model is `mlx-community/nomicai-modernbert-embed-base-4bit`.

The generated modeling table contains 805 numeric features per row: 17 tabular numeric features, 20 categorical one-hot features, and 768 embedding features.

### 3.4 Integrate Data

Integration combines pull request metadata, linked issue metadata, changed-file metadata, source patches, constructed labels, and quality metadata into one flat modeling row per pull request. Rows are split by repository with seed 42, so no repository appears in more than one split.

### 3.5 Format Data

Prepared modeling artifacts are under `data/processed/modeling_v0.1/`.

- `dataset_modeling_v0.1.train.npz` and `dataset_modeling_v0.1.val.npz` are ready for `.fit()` and `.predict()` and contain `X`, `y`, feature names, and row identifiers.
- `dataset_modeling_v0.1.train.parquet`, `dataset_modeling_v0.1.val.parquet`, `dataset_modeling_v0.1.test.parquet`, and `dataset_modeling_v0.1.all.parquet` provide inspectable tabular versions.
- `dataset_modeling_v0.1.feature_manifest.json` records the target, feature columns, embedding columns, categories, model name, and split settings.
- `dataset_modeling_v0.1.preparation_summary.json` records row counts, label balance, token counts, and reject-reason summary.

The split contains 6,063 train rows, 717 validation rows, and 777 test rows. The train and validation `.npz` files were smoke-tested with scikit-learn `.fit()` and `.predict()`.

---

## 4. Modeling

### 4.1 Select Modeling Technique

Three modeling techniques are planned in order of increasing complexity.

1. **Logistic regression** on a small hand-crafted subset of the pull-request-intrinsic features, as a sanity baseline. The purpose of this model is to confirm that a simple linear combination of obvious signals already beats a random baseline.
2. **XGBoost** on the full pull-request-intrinsic feature set, as the main tabular baseline. XGBoost is chosen for its strong performance on heterogeneous tabular features, its tolerance of missing values, and the interpretability of its feature importance output.
3. **XGBoost with ModernBERT embeddings** of the source-code patch text, as an advanced variant. The purpose of this variant is to assess whether code-change content contributes predictive power beyond the tabular features.

The modeling assumptions are that the repository-level split prevents train/test leakage at a level sufficient for the scope of this project; that the class balance of `review_concern` on the modeling set will be sufficient to train without specialized imbalance-handling techniques; and that ModernBERT, although pretrained on natural language rather than code, produces code-diff embeddings of sufficient quality to serve as a baseline representation, with the understanding that a dedicated code encoder could be substituted in a future iteration. All three assumptions will be verified empirically before modeling.

### 4.2 Generate Test Design

The test design separates the labeled raw records into training, validation, and test partitions at the repository level, in an **eighty-ten-ten ratio**, with **seed forty-two**, so that all pull requests from a given repository fall into the same partition. Repository-level splitting is chosen over pull-request-level splitting because pull requests from the same repository share authors, conventions, and review culture, and pull-request-level splitting would allow the model to exploit those shared characteristics rather than generalizable signal. The pull requests used for modeling are restricted to those that received review activity at all, in line with the label definition in section 1.3.1.

Model selection is performed on the validation set; the test set is used exactly once per model, at the end, to produce the numbers that appear in the evaluation scorecard.

The metrics are organized as follows:

- **Primary metrics:** ROC-AUC and F1.
- **Secondary outputs:** the precision-recall curve, the confusion matrix, the feature importance for tree models, and a calibration plot.

### 4.3 Build Model

Model building is planned in the notebooks `03_modeling_baselines.ipynb`, `04_modeling_xgboost.ipynb`, and `05_modeling_modernbert.ipynb`. Each notebook will record its parameter settings, the fitted model object, and a model description that covers the feature set used, the training configuration, and any preprocessing applied. The prepared train and validation matrices are available in `data/processed/modeling_v0.1/`; no final models have been trained at the time of writing.

### 4.4 Assess Model

Model assessment compares each trained model against the data mining success criteria in section 1.3.2 and against the other models in the progression. Models are ranked on the validation set by ROC-AUC and F1, with ties broken by the secondary metrics.

The assessment also considers two qualitative dimensions:

- **domain-level plausibility:** whether the features that rank highest in the XGBoost feature importance are consistent with what an experienced reviewer would intuitively expect;
- **error structure:** whether the errors on the test set cluster into interpretable groups.

Revised parameter settings, if any, are recorded alongside the assessment and motivate further iterations.

---

## 5. Evaluation

### 5.1 Evaluate Results

Evaluation assesses both the dataset and the model against the business and data mining success criteria defined in section 1.

- **Dataset evaluation** covers scale, repository and language diversity, trace completeness, the degree to which the accepted pool is free of bots and of generated or documentation-only content, and the residual noise rate measured on the audit sample.
- **Model evaluation** covers ROC-AUC and F1 on the held-out test set, the shape of the precision-recall curve, calibration, and the interpretability of the feature importance.

The consolidated output is the **evaluation scorecard**, a table with one row per criterion containing the target value, the measured value, and a pass-or-fail verdict. A criterion that fails is accompanied by an analysis of why it failed and of whether the failure is blocking for the business objectives. In addition, the evaluation identifies any findings that emerged during the project but were not part of the original success criteria, and assesses whether they suggest additional uses of the dataset or limitations worth documenting.

### 5.2 Review Process

Before deployment, a structured review is performed on the data mining engagement to verify that no important factor or task was overlooked. The review covers the following points:

- the filter rules and their thresholds, checked against the reject reason distribution on the final release;
- the feature partitioning, checked against the label definition, to confirm that no review-derived feature has leaked into the training feature set;
- the repository-level split, to confirm that no repository appears in more than one partition;
- the audit sample, to confirm that the residual noise rate is below the target;
- the pipeline outputs, to confirm that the dataset card and the quality report are consistent with the underlying data;
- the reproducibility of the pipeline, by rerunning the final stages on a small subset from a clean checkout.

The output of this step is a short review-of-process note summarizing what was checked and what, if anything, was corrected as a result.

### 5.3 Determine Next Steps

At the end of evaluation, the project takes one of three paths:

- **proceed to deployment**, if all blocking criteria are met and no defect is uncovered;
- **initiate a further iteration** of data preparation or modeling, if a blocking criterion fails or if the review of process uncovers a defect that cannot be corrected by documentation alone;
- **scope a follow-up project**, if evaluation uncovers substantial new opportunities, such as a second downstream task that the dataset supports well.

The output is a short list of possible actions and an explicit decision on which of them the project adopts.

---

## 6. Deployment

### 6.1 Plan Deployment

The deployment artifact of this project is a **dataset together with its documentation and a reference model**, rather than a running service. Deployment planning therefore focuses on packaging and on making the artifact straightforward to consume.

The deliverables are the following:

- the final accepted dataset, in JSONL and Parquet forms;
- the rejected pool, delivered alongside for error analysis;
- the train, validation, and test splits, both as trace JSONL and as feature tables in CSV and Parquet;
- the SFT files, as JSONL;
- the documentation, consisting of the schema reference in section 9, the auto-generated dataset card, the auto-generated quality report, the evaluation scorecard, the product one-pager, the deployment guide, and this document;
- the reference model, as a saved model artifact accompanied by a short inference example.

The deployment plan specifies that a consumer with a standard Python environment can load the Parquet release with a single call to `pandas.read_parquet` or `pyarrow.parquet.read_table` and can reproduce the reference model by running the modeling notebooks against the released splits.

### 6.2 Plan Monitoring and Maintenance

Because the project delivers a static dataset rather than a running service, monitoring in the operational sense does not apply. Maintenance is planned in terms of reproducibility and extensibility:

- the pipeline is fully parameterized through `config.yaml`;
- the splits are reproducible from a fixed seed;
- the dataset card and the quality report are regenerated by the pipeline rather than edited by hand;
- the two data collection paths — the BigQuery SQL and the local GH Archive fallback — are both kept functional so that the dataset can be extended to new time windows without re-engineering.

Known issues affecting maintenance, including the minor edge cases in the `finalize` command, are documented in section 13 so that future iterations can address them.

### 6.3 Produce Final Report

The **final report** consolidates the outputs of all six phases into a single narrative document intended for external review. It summarizes the business problem, the data, the pipeline, the modeling results, the evaluation against the success criteria, and the deployment artifact, and refers the reader to this document and to the dataset card for technical detail.

The **final presentation** is a short slide deck that walks through the same material in a form suitable for oral delivery, supported by a video whose scene-by-scene script is recorded in section 15.

### 6.4 Review Project

At project close, the team performs a short retrospective in which it records what went well, what went poorly, what would be done differently, and what experience accumulated during the project should be preserved for future work. The output is the **experience documentation**, kept in the repository alongside the final report.

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
├── business_understanding.tex       # CRISP-DM Business Understanding report fragment
├── data_understanding.tex           # CRISP-DM Data Understanding report fragment
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
├── figures/                         # Report figures
│   └── data_understanding/           # Data Understanding EDA plots
├── reports/                         # Generated quality reports (gitignored)
└── notebooks/                       # Analysis notebooks
    └── 01_data_understanding.ipynb
```

**Naming conventions:**
- Python files, config keys: `lower_snake_case`
- Markdown docs: `lower_snake_case.md`
- LaTeX report fragments: `lower_snake_case.tex`
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
| `dataset_mvp_v0.1` | March 2025 | **Complete (MVP raw enrichment)** | 7563 enriched PRs |
| `dataset_v1.0` | First weeks of several months in 2026 | **In collection** (final submission) | Target ~10000 traces |

### 13.2 CRISP-DM Phase Progress

```
Business Understanding  ████████████████████  100%
Data Understanding      ████████████████████  100%
Data Preparation        ██████████████████░░  90%
Modeling                ░░░░░░░░░░░░░░░░░░░░   0%
Evaluation              ░░░░░░░░░░░░░░░░░░░░   0%
Deployment              ███░░░░░░░░░░░░░░░░░  15%
```

### 13.3 Artifact Status

**Complete:**
- Full `pipeline/` module tree (16 modules)
- `config.yaml` populated
- BigQuery SQL (`sql/01_candidate_prs.sql`, `sql/02_candidate_stats.sql`)
- `business_understanding.tex`
- `data_understanding.tex`
- `data_preparation.tex`
- `notebooks/01_data_understanding.ipynb`
- `notebooks/02_data_preparation.ipynb`
- `notebooks/02_data_preparation.py`
- Data Understanding plots in `figures/data_understanding/`
- MVP raw enrichment: 7563 enriched PRs in `enriched_prs_raw.jsonl`
- Modeling-ready MVP train/validation/test files in `data/processed/modeling_v0.1/`
- `review_concern` label and no-leak feature construction in `pipeline/data_preparation.py`
- Dataset card auto-generator
- Quality report auto-generator
- Audit sample generator
- 2026 data collection has started

**In progress:**
- `dataset_v1.0` data collection
- This master document

**Not started:**
- Modeling and evaluation notebooks
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
| I-3 | `quality.accepted` is a curation label, not a modeling target | Resolved for MVP modeling prep | `review_concern` implemented in `pipeline/data_preparation.py` |
| I-4 | Feature table mixes PR-intrinsic and review-derived columns | Resolved for MVP modeling prep | No-leak feature manifest written under `data/processed/modeling_v0.1/` |
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
| DP-2 | Implement `review_concern` label in `pipeline/filters.py` or new module | P0 | 0.5 day | `[x]` | — |
| DP-3 | Partition features into PR-intrinsic vs review-derived groups in `pipeline/features.py` | P0 | 0.5 day | `[x]` | DP-2 |
| DP-4 | Fix `finalize` edge-case inconsistencies | P2 | 0.5 day | `[ ]` | — |
| DP-5 | Audit sample review (100 accepted traces, manual labeling) | P1 | 0.5 day | `[ ]` | DP-1 |

### 14.2 Notebook Tasks

| ID | Task | Priority | Est. Effort | Status | Depends on |
|---|---|---|---|---|---|
| NB-1 | `01_data_understanding.ipynb` — EDA, distributions, reject reasons breakdown | P0 | 0.5 day | `[x]` | current raw enrichment |
| NB-2 | `02_data_preparation.ipynb` — feature analysis, label balance, split visualization | P0 | 0.5 day | `[x]` | DP-2, DP-3 |
| NB-3 | `03_modeling_baselines.ipynb` — logistic regression baseline | P0 | 0.5 day | `[ ]` | NB-2 |
| NB-4 | `04_modeling_xgboost.ipynb` — XGBoost main baseline | P0 | 1 day | `[ ]` | NB-3 |
| NB-5 | `05_modeling_modernbert.ipynb` — ModernBERT-enhanced variant | P1 | 1–2 days | `[ ]` | NB-4 |
| NB-6 | `06_evaluation.ipynb` — scorecard, error analysis, feature importance | P0 | 0.5 day | `[ ]` | NB-4 |

### 14.3 Documentation Tasks

| ID | Task | Priority | Est. Effort | Status | Depends on |
|---|---|---|---|---|---|
| DOC-1 | Business Understanding report fragment (`business_understanding.tex`) | P0 | 0.5 day | `[x]` | — |
| DOC-1A | Data Understanding report fragment (`data_understanding.tex`) | P0 | 0.5 day | `[x]` | NB-1 |
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
