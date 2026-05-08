# `pipeline/` — Python Package & CLI

Reusable modules and the `python -m pipeline ...` command-line interface that
drives every stage of the dataset build.

## Modules

| File | Purpose |
| --- | --- |
| [`cli.py`](cli.py) | Argument parsing and dispatch for `python -m pipeline ...`. |
| [`config.py`](config.py) | Typed configuration loader for [`config.yaml`](../config.yaml). |
| [`gharchive.py`](gharchive.py) | Local GH Archive download + candidate extraction. |
| [`github_client.py`](github_client.py) | Authenticated GitHub REST client with retry/backoff. |
| [`enrich.py`](enrich.py) | Enriches candidate PRs into raw JSONL records. |
| [`schema.py`](schema.py) | Trace record schema & validation. |
| [`filters.py`](filters.py) | Hard filters and quality scoring. |
| [`features.py`](features.py) | Flat feature table export. |
| [`split.py`](split.py) | Repository-stratified train / val / test split. |
| [`parquet_export.py`](parquet_export.py) | Parquet exporters for accepted / rejected traces. |
| [`export_jsonl.py`](export_jsonl.py) | JSONL helpers. |
| [`sft.py`](sft.py) | SFT view generation from accepted traces. |
| [`audit.py`](audit.py) | Human-audit CSV sampler. |
| [`report.py`](report.py) | Markdown quality report. |
| [`datacard.py`](datacard.py) | Dataset card generator. |
| [`data_preparation.py`](data_preparation.py) | Build modeling matrices (`.parquet` + `.npz`) from raw JSONL. |
| [`modeling.py`](modeling.py) | Train, tune, and persist the baseline classifier. |
| [`evaluation.py`](evaluation.py) | Scorecard, confusion matrices, and evaluation summary. |

## CLI Commands

Run from the project root inside the project virtualenv.

| Command | Description |
| --- | --- |
| `download-gharchive` | Download GH Archive hourly dumps. |
| `candidates-from-gharchive` | Build candidate CSV from local GH Archive dumps. |
| `enrich` | Enrich candidate PRs via the GitHub API. |
| `process` | Build accepted / rejected datasets from raw JSONL. |
| `split` | Repository-level train / val / test JSONL split. |
| `features` | Flat feature tables for each split. |
| `export-parquet` | Export accepted / rejected traces to Parquet. |
| `sft` | Export SFT views from accepted traces. |
| `audit` | Human-audit sample CSV. |
| `report` | Markdown quality report. |
| `data-card` | Dataset card for the public release. |
| `finalize` | Run `process`, `split`, `features`, `export-parquet`, `sft`, `audit`, `report`, `data-card` end to end. |

Run any command with `--help` to see its arguments.

```bash
python -m pipeline --help
python -m pipeline enrich --help
```
