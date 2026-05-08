# Muhomory GitHub Workflow Dataset

End-to-end CRISP-DM project that builds a curated dataset of GitHub
pull-request review traces and trains a baseline `review_concern` classifier
on top of it.

```text
Issue → Discussion → PR → Review → Code Diff → Merge
```

- **Public dataset:** <https://huggingface.co/datasets/bulatSharif/gh-pr-issue-traces-10k>
- **Report:** [`docs/report/report.pdf`](docs/report/report.pdf)
- **Full project document:** [`docs/MASTER_CONTEXT.md`](docs/MASTER_CONTEXT.md)

## Repository Layout

| Folder | Purpose |
| --- | --- |
| [`pipeline/`](pipeline/README.md) | Python package and `python -m pipeline` CLI for every dataset stage. |
| [`notebooks/`](notebooks/README.md) | CRISP-DM notebooks: data understanding → preparation → modeling → evaluation. |
| [`sql/`](sql/README.md) | BigQuery templates for the candidate-discovery step. |
| [`data/`](data/README.md) | Candidate CSVs, raw enriched JSONL, and processed modeling matrices. |
| [`figures/`](figures/README.md) | Plots used by the report. |
| [`reports/`](reports/README.md) | Trained model, metrics, and evaluation summaries. |
| [`app/`](app/README.md) | Streamlit demo of the trained classifier. |
| [`docs/`](docs/README.md) | Full write-up, deployment guide, dataset card, LaTeX report sources. |

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export GITHUB_TOKEN=...               # required for enrichment
```

End-to-end: download → enrich → process → train → evaluate.

```bash
# 1. Build candidate PRs (BigQuery — see sql/ — or local GH Archive)
python -m pipeline download-gharchive --start-date 2025-01-01 --end-date 2025-01-31 \
    --output-dir data/gharchive/2025-01
python -m pipeline candidates-from-gharchive \
    --input-glob "data/gharchive/2025-01/*.json.gz" \
    --output data/candidates/candidate_prs_2025_01.csv

# 2. Enrich candidates via the GitHub API
python -m pipeline enrich --candidates-dir data/candidates \
    --pattern "candidate_prs_2025_*.csv" --limit-total 10000 --sample-seed 42

# 3. Build accepted/rejected datasets, splits, features, audit, report, dataset card
python -m pipeline finalize

# 4. Train and evaluate the baseline classifier (see notebooks/)
jupyter lab notebooks/03_modeling.ipynb
jupyter lab notebooks/04_evaluation_deployment.ipynb

# 5. Run the demo
python -m streamlit run app/streamlit_app.py
```

See [`pipeline/README.md`](pipeline/README.md) for the full CLI reference and
[`docs/MASTER_CONTEXT.md`](docs/MASTER_CONTEXT.md) for the long-form write-up.

## Configuration

All pipeline parameters live in [`config.yaml`](config.yaml). Key knobs:

- `github.max_workers` — enrichment parallelism (rate-limit aware).
- `dataset.min_*` / `dataset.max_*` — quality thresholds.
- `output.*` — every artifact path the CLI reads or writes.

## Requirements

- Python 3.10+
- A GitHub personal access token in `GITHUB_TOKEN`
- BigQuery access *or* enough disk space for local GH Archive dumps

## License & Contact

Authors: Bulat Sharipov, Dinar Yakupov, Danil Fathutdinov, Marsel Berheev, Makar Egorov (DS-01, Innopolis University).
