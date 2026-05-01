# GH Trace Dataset MVP

Minimal pipeline for collecting engineering traces of the form:

```text
Issue -> Discussion -> PR -> Review -> Code Diff -> Merge
```

The pipeline follows a strict MVP shape:

1. Use GH Archive in BigQuery or local GH Archive hourly dumps to find candidate merged pull requests.
2. Enrich those candidates via the GitHub REST API.
3. Apply hard filters and a simple quality score.
4. Export accepted and rejected examples for PR quality classification.
5. Generate train/val/test splits, flat feature tables, Parquet exports, an audit CSV, a dataset card, and a quality report.

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
.\.venv\Scripts\Activate.ps1
.\.venv\Scripts\pip.exe install -r requirements.txt
```

## Config

Default settings live in [config.yaml](/C:/Users/Dinar/Desktop/GitHub%20projects/data-mining-project/config.yaml).

Key values to review before running:

- `github.max_workers`
- `dataset.require_linked_issue`
- `dataset.store_full_diff`
- output paths under `output`

## Candidate Discovery

You can build candidate PR CSV files in two ways.

### Option A: BigQuery

Run the SQL templates in `sql/` against GH Archive in BigQuery.

- [sql/01_candidate_prs.sql](/C:/Users/Dinar/Desktop/GitHub%20projects/data-mining-project/sql/01_candidate_prs.sql) builds the candidate table.
- [sql/02_candidate_stats.sql](/C:/Users/Dinar/Desktop/GitHub%20projects/data-mining-project/sql/02_candidate_stats.sql) inspects distribution and samples.

Export the resulting table to CSV and place it at `data/candidates/candidate_prs_2025.csv` or pass a different path to the CLI.

### Option B: Local GH Archive hourly dumps

Download hourly `.json.gz` files and build the candidate CSV locally with the same event-level candidate filters as the SQL path.

If you already have `wget` in a Unix-like shell, the January 2015 download looks like:

```bash
wget https://data.gharchive.org/2015-01-{01..31}-{0..23}.json.gz
```

Note: this brace expansion works in Bash-like shells, not in standard PowerShell. On Windows PowerShell, prefer the built-in downloader below.

If you want a shell-independent method, use the built-in downloader:

```bash
.\.venv\Scripts\python.exe -m pipeline download-gharchive --start-date 2015-01-01 --end-date 2015-01-31 --output-dir data/gharchive/2015-01
```

Then build the candidate CSV:

```bash
.\.venv\Scripts\python.exe -m pipeline candidates-from-gharchive --input-glob "data/gharchive/2015-01/*.json.gz" --output data/candidates/candidate_prs_2015_01.csv
```

For a smoke test you can limit the number of hourly files:

```bash
.\.venv\Scripts\python.exe -m pipeline candidates-from-gharchive --input-glob "data/gharchive/2015-01/*.json.gz" --output data/candidates/candidate_prs_2015_01_smoke.csv --limit-files 24
```

## CLI Workflow

Enrich raw candidates:

```bash
.\.venv\Scripts\python.exe -m pipeline enrich --candidates data/candidates/candidate_prs_2025.csv --limit 1000
```

Enrich a balanced random sample across all monthly candidate CSVs in a directory:

```bash
.\.venv\Scripts\python.exe -m pipeline enrich --candidates-dir data/candidates --pattern "candidate_prs_2025_*.csv" --limit-total 10000 --sample-seed 42
```

Preview the overnight selection without making GitHub API calls:

```bash
.\.venv\Scripts\python.exe -m pipeline enrich --candidates-dir data/candidates --pattern "candidate_prs_2025_*.csv" --limit-total 10000 --sample-seed 42 --dry-run
```

Process enriched rows into accepted and rejected datasets:

```bash
.\.venv\Scripts\python.exe -m pipeline process
```

Split examples by repository into train/val/test:

```bash
.\.venv\Scripts\python.exe -m pipeline split
```

Export flat feature tables for modeling:

```bash
.\.venv\Scripts\python.exe -m pipeline features
```

Export accepted and rejected traces to Parquet:

```bash
.\.venv\Scripts\python.exe -m pipeline export-parquet
```

Generate an audit sample:

```bash
.\.venv\Scripts\python.exe -m pipeline audit
```

Generate a markdown quality report:

```bash
.\.venv\Scripts\python.exe -m pipeline report
```

Export SFT views from the accepted trace dataset:

```bash
.\.venv\Scripts\python.exe -m pipeline sft
```

Generate a dataset card:

```bash
.\.venv\Scripts\python.exe -m pipeline data-card
```

Run post-processing in one step:

```bash
.\.venv\Scripts\python.exe -m pipeline finalize
```

## Notes

- Enrichment is resumable. The CLI skips PRs already present in the raw or failed JSONL outputs.
- Directory-mode enrichment samples from pending rows after deduplication and seen-row filtering, so `--limit-total 10000` means up to 10,000 actual API submissions.
- Multi-file directory mode uses balanced random sampling across matched CSV files and shuffles the final selection globally before submission.
- Linked issues are detected only via `fixes/closes/resolves #123` style references in the PR title/body.
- The pipeline intentionally favors precision over recall in the accepted dataset.
- The baseline downstream task is PR trace quality classification: `accepted` vs `rejected`.
- `finalize` regenerates accepted/rejected datasets, repo-level splits, feature tables, Parquet exports, SFT views, the audit CSV, the quality report, and the dataset card.
