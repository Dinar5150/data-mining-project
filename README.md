# GH Trace Dataset MVP

Minimal pipeline for collecting engineering traces of the form:

```text
Issue -> Discussion -> PR -> Review -> Code Diff -> Merge
```

The pipeline follows a strict MVP shape:

1. Use GH Archive in BigQuery to find candidate merged pull requests.
2. Enrich those candidates via the GitHub REST API.
3. Apply hard filters and a simple quality score.
4. Export accepted and rejected examples as JSONL.
5. Generate a small audit CSV and a markdown quality report.

## Repository Layout

```text
sql/                    BigQuery SQL templates
pipeline/               Python modules and CLI
data/candidates/        Exported BigQuery candidates CSV
data/raw/               Raw enriched JSONL and failures
data/processed/         Accepted and rejected dataset variants
data/audit/             Human audit samples
reports/                Generated reports
```

## Setup

Requirements:

- Python 3.10+
- A GitHub personal access token in `GITHUB_TOKEN`
- BigQuery access for the candidate search step

Install dependencies:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Config

Default settings live in [config.yaml](/C:/Users/Dinar/Desktop/GitHub%20projects/data-mining-project/config.yaml).

Key values to review before running:

- `github.max_workers`
- `dataset.require_linked_issue`
- `dataset.store_full_diff`
- output paths under `output`

## Candidate Discovery

Run the SQL templates in `sql/` against GH Archive in BigQuery.

- [sql/01_candidate_prs.sql](/C:/Users/Dinar/Desktop/GitHub%20projects/data-mining-project/sql/01_candidate_prs.sql) builds the candidate table.
- [sql/02_candidate_stats.sql](/C:/Users/Dinar/Desktop/GitHub%20projects/data-mining-project/sql/02_candidate_stats.sql) inspects distribution and samples.

Export the resulting table to CSV and place it at `data/candidates/candidate_prs_2025.csv` or pass a different path to the CLI.

## CLI Workflow

Enrich raw candidates:

```bash
python -m pipeline enrich --candidates data/candidates/candidate_prs_2025.csv --limit 1000
```

Process enriched rows into accepted and rejected datasets:

```bash
python -m pipeline process
```

Generate an audit sample:

```bash
python -m pipeline audit
```

Generate a markdown quality report:

```bash
python -m pipeline report
```

Export SFT views from the accepted trace dataset:

```bash
python -m pipeline sft
```

Run post-processing in one step:

```bash
python -m pipeline finalize
```

## Notes

- Enrichment is resumable. The CLI skips PRs already present in the raw or failed JSONL outputs.
- Linked issues are detected only via `fixes/closes/resolves #123` style references in the PR title/body.
- The pipeline intentionally favors precision over recall in the accepted dataset.
- `finalize` regenerates accepted/rejected datasets, SFT views, the audit CSV, and the quality report.
