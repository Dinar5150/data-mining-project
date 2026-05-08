# `app/` — Streamlit Demo

Interactive demo of the trained `review_concern` classifier. The app loads the
selected model and the prepared `test` / `val` / `train` parquet splits and
lets you inspect predictions, feature contributions, and a numeric what-if
panel.

## Files

- [`streamlit_app.py`](streamlit_app.py) — single-file Streamlit application.

## Inputs

The app reads these artifacts from elsewhere in the repo (paths are resolved
relative to the project root):

- [`reports/modeling_v0.2/selected_model.joblib`](../reports/README.md)
- [`reports/modeling_v0.2/modeling_summary.json`](../reports/README.md)
- [`data/processed/modeling_v0.2/`](../data/README.md) parquet splits + feature manifest

## Run

```bash
python -m streamlit run app/streamlit_app.py --server.port 8501
```

Then open http://localhost:8501.

See [`docs/deployment_guide.md`](../docs/deployment_guide.md) for the full
deployment overview.
