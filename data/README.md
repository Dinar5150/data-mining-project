# `data/` — Datasets

All on-disk data, ordered from upstream raw inputs to downstream modeling
matrices. Contents are gitignored except for `.gitkeep` placeholders.

```
data/
├── candidates/    Candidate PR CSVs from BigQuery or local GH Archive
├── raw/           Enriched PR JSONL (full GitHub payloads + diffs)
└── processed/     Filtered datasets, splits, feature tables, modeling matrices
    ├── modeling_v0.1/
    └── modeling_v0.2/   ← current
```

## `candidates/`

CSV exports from [`sql/01_candidate_prs.sql`](../sql/README.md) or from the
`python -m pipeline candidates-from-gharchive` CLI. One row per candidate
merged pull request — the input to enrichment.

## `raw/`

Output of `python -m pipeline enrich`. JSONL with one full enriched PR record
per line, plus a sibling `*_failed.jsonl` for rows that failed enrichment.
The current run uses `enriched_prs_raw_new.jsonl`.

## `processed/`

Output of `python -m pipeline process` (and downstream steps) and of
`pipeline.data_preparation.prepare_modeling_data`. Contains:

- `dataset_mvp_v0.1.{accepted,rejected,train,val,test}.{jsonl,parquet}` —
  accepted / rejected traces and the repository-level split used by the
  feature-table workflow.
- `dataset_mvp_v0.1.*.features.{csv,parquet}` — flat feature tables.
- `dataset_mvp_v0.1.{review_sft,issue_to_patch_sft}.jsonl` — SFT views.
- `modeling_v0.2/dataset_modeling_v0.2.*` — the modeling matrices consumed by
  `pipeline.modeling` and the [Streamlit demo](../app/streamlit_app.py):
  - `*.all.parquet`, `*.{train,val,test}.parquet` — labeled rows with metadata
  - `*.{train,val,test}.npz` — numeric `X`, `y` arrays
  - `*.feature_manifest.json` — feature column inventory
  - `*.preparation_summary.json` — preparation-stage metadata

See the [Hugging Face dataset card](../docs/huggingface_dataset_card.md) for
the public release schema.
