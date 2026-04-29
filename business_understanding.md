# Business Understanding

## Background

**Muhomory** is a data science company specializing in data pipelines, large-scale preprocessing, and curated datasets for machine learning. Our core business is turning raw, noisy, publicly available data into structured data products that other companies can use directly for training and evaluation.

The current market is driven by the rapid adoption of AI coding assistants, autonomous developer agents, and code review automation tools. Companies such as GitHub, Cursor, Anthropic, and OpenAI need large volumes of high-quality software engineering data to train and evaluate their models. Existing open datasets such as The Stack, CodeSearchNet, and CommitPack mostly contain raw code or commits without the surrounding engineering context of how a change was discussed, reviewed, and merged. This creates a commercial opportunity for curated workflow-level datasets.

Customers that want this kind of data currently have three imperfect options. They can parse GH Archive themselves, which requires substantial engineering effort and large-scale filtering. They can buy generic labeling services, which are expensive and not tailored to software engineering. Or they can use open datasets that miss the workflow layer entirely. This project addresses that gap.

The project is executed by the Muhomory internal team consisting of a Project Manager, a Business Unit representative, a Data Scientist, a Model Developer, and a Business Analyst. The main stakeholders are Muhomory management, potential B2B customers building AI coding products, and the internal execution team.

## Business Objectives

The primary business objective is to design and deliver a curated dataset of software engineering workflows extracted from public GitHub activity, suitable to be positioned as a commercial data product for AI companies building code assistants and developer agents.

The secondary objectives are:

1. Validate that the dataset supports a realistic downstream ML task that customers care about.
2. Build a reusable extraction and filtering pipeline that can be rerun on new GH Archive slices.
3. Establish Muhomory's positioning in the niche of workflow-level software engineering datasets.

The key business question is: can we turn public GitHub activity into a structured, quality-controlled dataset product that is useful enough for commercial AI use within the project's time and resource limits?

## Business Success Criteria

The project is considered a business success if all of the following criteria are met.

1. **Product completeness.** The final dataset contains workflow sequences from at least three commercially relevant mainstream programming languages, with Python and at least two other languages observed in the accepted dataset, and is based on at least 1000 unique public repositories.
2. **Downstream applicability.** The dataset supports at least one realistic downstream task, namely PR trace quality classification, and a baseline ML model performs strictly better than a random baseline on that task.
3. **Usability of the product.** The final dataset is published in standard machine learning formats, with JSONL as the working format and Parquet as the release format, accompanied by a schema description, a data card, and usage examples. It must load in a standard Python environment without extra cleaning scripts.
4. **Commercial readiness.** The team produces a short product description that summarizes the value proposition, customer segments, pricing reference, and example use cases.
5. **Delivery within resource limits.** The entire project is executed on existing local hardware, with zero external paid services, and is finished by the hard deadline of 30.04.2026.

## Assess Situation

### Inventory of Resources

**Personnel.** The project is executed by five roles: Project Manager, Business Unit, Data Scientist, Model Developer, and Business Analyst.

**Data sources.** The main source is GH Archive, used through BigQuery as a candidate search index. The secondary source is the GitHub REST API, used to enrich selected pull requests with reviews, comments, files, and diffs. Both are public and free.

**Compute and storage.** We use local machines with up to 16 GB GPU memory and 1–10 TB of local storage. All enrichment, filtering, feature export, and packaging are performed locally.

**Software.** The implemented pipeline is a Python CLI codebase using `requests`, `pandas`, `PyYAML`, and `PyArrow`. Candidate discovery is done in BigQuery and exported to CSV. For modeling we use scikit-learn and XGBoost. For visualization and reporting we use matplotlib, seaborn, and Power BI where needed. The codebase is stored in a private GitHub repository with Python modules and selected notebooks for modeling and analysis.

### Requirements, Assumptions, Constraints

**Requirements.**

1. The final dataset must represent software engineering workflows as sequences of linked events: issue, discussion, pull request, review, code diff, merge.
2. The pipeline must keep JSONL as the resumable processing format and provide Parquet export for release.
3. The dataset must include a documented schema and a data card.
4. The dataset must contain only data from public repositories. License filtering remains a business requirement and a known implementation gap if not completed by release.

**Assumptions.**

1. Public GitHub data is representative enough to capture engineering workflows useful for downstream ML.
2. Rule-based filtering is sufficient to produce a usable high-precision accepted tier without manual labeling of every example.
3. A simple supervised baseline is enough to demonstrate dataset usefulness at this stage.

**Constraints.**

1. GitHub API is limited to roughly 5000 requests per hour per token, which constrains enrichment throughput.
2. Local storage and time budget prevent full GH Archive processing, so the project must work on targeted candidate slices.
3. The project has a hard deadline of 30.04.2026 and must remain realistic for a small team.

### Risks and Contingencies

**Data quality risk.** GH Archive events are noisy and include bots, trivial changes, and generated files. Mitigation: multi-stage filtering with bot heuristics, diff-size thresholds, linked-issue checks, and file-level source filters.

**Event linking risk.** Not every repository exposes a clean `issue -> PR -> review -> merge` chain. Mitigation: prioritize high-quality traces with explicit linked issues and documented discussion/review signals.

**API and compute risk.** GitHub API limits and local compute may cap dataset scale. Mitigation: conservative concurrency, resumable JSONL checkpoints, and a realistic target for the accepted tier.

**Schedule risk.** The team is small and the deadline is tight. Mitigation: prioritize the core pipeline, accepted/rejected labeling, repo-level split, feature export, and baseline modeling over optional enhancements.

### Terminology

**Business terms**

- **Curated dataset** — a dataset that has been cleaned, filtered, and structured for a specific use case.
- **Workflow sequence** — an ordered chain of engineering events describing how a change was introduced.
- **Trace** — the internal name used in the pipeline for a workflow sequence.
- **Example** — one dataset record corresponding to one workflow sequence / trace.
- **Data product** — a dataset packaged together with schema, documentation, and usage examples, ready to be licensed or sold.
- **Downstream task** — a machine learning task that a customer would solve using our dataset, in this project PR trace quality classification.
- **Bot event** — an event generated automatically by an account such as `dependabot`, `github-actions`, or `renovate`.

**Technical terms**

- **GH Archive** — a public archive of GitHub events.
- **GitHub event** — a single GitHub activity record such as `PullRequestEvent` or `IssueCommentEvent`.
- **Merged PR** — a pull request whose changes were accepted into the base branch.
- **Diff** — the code difference between the PR branch and the base branch.
- **Parquet** — a columnar storage format used for release packaging and ML consumption.
- **Data card** — a concise document describing dataset source, schema, filtering rules, limitations, and intended use.

### Costs and Benefits

Data acquisition is free because both GH Archive and the GitHub API are public. Infrastructure cost is effectively zero because processing uses existing local hardware. The primary cost is the team's time.

Potential benefits:

1. **Conservative scenario.** The dataset remains an internal portfolio asset and reusable pipeline.
2. **Realistic scenario.** The dataset is licensed to a few AI startups as a niche workflow-level data product.
3. **Optimistic scenario.** The dataset supports an enterprise-style engagement or custom curation offering.

Given the near-zero direct monetary cost, the project is economically justified if it yields a credible reusable pipeline and a demonstrably useful dataset.

## Data Mining Goals

The data mining goal of this project is to build an end-to-end pipeline that transforms GH Archive candidates plus GitHub REST API enrichment into a structured dataset of software engineering workflow sequences, and to validate the usefulness of this dataset with a baseline machine learning model.

Concretely, the pipeline must:

1. Identify promising merged PR candidates from GH Archive using BigQuery.
2. Enrich those candidates through the GitHub REST API with pull request metadata, files, reviews, review comments, issue comments, linked issue data, and diffs.
3. Apply rule-based filters to remove bot-generated events, trivial documentation-only changes, lockfile-only changes, generated code changes, and oversized PRs.
4. Score the resulting traces and split them into accepted and rejected examples.
5. Export accepted/rejected traces to JSONL and Parquet.
6. Produce repo-level train/validation/test splits and flat feature tables for modeling.

On top of this dataset, the Model Developer trains a baseline supervised model for **PR trace quality classification**. Given features of a curated PR trace, the model predicts whether the trace belongs to the accepted tier or the rejected tier. This validates that the dataset contains real predictive signal and provides a customer-facing proof-of-usefulness artifact.

## Data Mining Success Criteria

The data mining part of the project is considered successful if all of the following criteria are met.

1. **Dataset scale.** The final dataset contains at least 5000 accepted workflow sequences and an additional rejected pool for error analysis, drawn from at least 1000 unique repositories and covering multiple mainstream languages including Python and at least two others observed in the data.
2. **Sequence quality.** At least 90% of accepted sequences contain a merged PR together with at least one review or review comment.
3. **Noise level.** Bot-generated or clearly trivial traces are materially reduced in the accepted tier, as shown by reject-reason analysis and audit sampling.
4. **Schema completeness.** At least 80% of accepted sequences contain the core fields required for downstream ML: repository metadata, timestamps, author, PR size, review information, merge flag, and quality label.
5. **Baseline model performance.** The baseline classifier on the PR quality classification task performs strictly better than a random baseline on a held-out test set, measured by F1-score and ROC-AUC.
6. **Usability.** The final Parquet export loads into a standard Python environment without additional cleaning scripts in under five minutes on project hardware.

## Project Plan

The project follows the six phases of CRISP-DM plus a final packaging phase.

| Phase | Soft Deadline | Hard Deadline | Main Tasks |
| :---- | :---- | :---- | :---- |
| Business Understanding | 24.03.2026 | 26.03.2026 | Background, objectives, success criteria, resources, risks, costs, goals, tools |
| Data Understanding | 30.03.2026 | 01.04.2026 | Candidate exploration, schema exploration, quality assessment, feasibility statement |
| Data Preparation | 05.04.2026 | 07.04.2026 | Enrichment pipeline, filtering, event linking, accepted/rejected export, split, feature export, Parquet export |
| Modeling | 11.04.2026 | 13.04.2026 | Baseline model for PR quality classification, feature selection, tuning, overfitting check |
| Evaluation | 17.04.2026 | 19.04.2026 | Business and technical evaluation, success-criteria scorecard, error analysis |
| Deployment | 23.04.2026 | 25.04.2026 | Dataset packaging, data card, documentation, one-pager, publication |
| Finalisation | 27.04.2026 | 30.04.2026 | Final report, slides, video, optional Power BI, polishing |

### Roles and Responsibilities

| Role | Primary responsibilities across phases |
| :---- | :---- |
| Project Manager | Timeline, coordination, risk tracking, report consistency, submission |
| Business Unit | Business framing, market analysis, cost/benefit, final business assessment |
| Data Scientist | Data audit, cleaning rules, quality metrics, dataset preparation |
| Model Developer | Baseline model, feature set, metrics, interpretation |
| Business Analyst | Visualizations, slides, video, final report polishing |

### Initial Assessment of Tools and Techniques

For candidate discovery we use BigQuery over GH Archive and export candidate tables to CSV. For enrichment we use a Python CLI pipeline with synchronous GitHub REST API calls, conservative concurrency, and resumable JSONL checkpoints. For filtering and linking we use Python rule-based logic over enriched traces. For modeling we use logistic regression as a sanity baseline and XGBoost as the main baseline. For packaging we use JSONL as the working format and PyArrow-based Parquet export as the release format.

## Overview of the Next CRISP-DM Phases

### Data Understanding

The goal of this phase is to prove that the data sources are sufficient to build the planned dataset and to document the initial picture of the data.

The Data Scientist explores a representative candidate slice from GH Archive, measures event-type counts, review/discussion coverage, bot share, and PR-size distributions, and confirms that the candidate pool is rich enough for downstream enrichment.

The Model Developer checks which features will be available for the baseline model, what the target variable is (`accepted / rejected`), and whether there are leakage risks.

The Business Analyst prepares the visualizations for this phase, and the Project Manager closes the phase with an explicit feasibility statement.

### Data Preparation

The goal of this phase is to turn raw candidate events into the final structured dataset and make it ready for modeling and release packaging.

The Data Scientist owns the pipeline: query GH Archive in BigQuery, export candidate PRs to CSV, enrich selected PRs through the GitHub API, filter noisy traces, build accepted/rejected JSONL outputs, and export Parquet. The Model Developer defines the flat feature schema and repo-level split strategy. The Business Analyst prepares before/after filtering visuals.

### Modeling

The goal of this phase is to train the baseline model that proves the dataset carries real signal.

The Model Developer trains a random baseline, logistic regression sanity baseline, and XGBoost main baseline on the accepted-vs-rejected PR trace quality classification task. Metrics are F1-score and ROC-AUC, with confusion matrix and feature importance for interpretation.

### Evaluation

The goal of this phase is to check every success criterion explicitly and reproducibly.

The Business Unit prepares a success-criteria scorecard. The Data Scientist verifies scale, language coverage, noise reduction, and schema completeness. The Model Developer verifies that the baseline outperforms the random baseline and performs a short error analysis.

### Deployment

The goal of this phase is to package the dataset and model artifacts into a form that can be handed to another team or to a customer.

The Data Scientist prepares final JSONL and Parquet outputs, the schema description, and the data card. The Model Developer packages the baseline model and inference example. The Business Unit produces the product one-pager. The Business Analyst prepares slides and video.

### Finalisation

The Project Manager owns the final consistency pass over the report, artifacts, and submission package. The team checks that every success criterion is traceable, every notebook or script runs in a clean environment, and all deliverables required by the assignment are present.
