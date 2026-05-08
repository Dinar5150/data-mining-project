# Deployment Guide

This project has two deployment artifacts.

## Public Dataset

Dataset page: <https://huggingface.co/datasets/bulatSharif/gh-pr-issue-traces-10k>

The Hugging Face release is the public data artifact. It is intended for external inspection, reuse, and future CRISP-DM iterations.

## Streamlit Demo

The Streamlit application demonstrates the trained review-concern model on prepared pull request rows.

Run locally from the project root:

```bash
~/.venvs/general/bin/python -m streamlit run streamlit_app.py --server.port 8501
```

Then open:

```text
http://localhost:8501
```

The demo is intended to show how the trained baseline behaves, expose probabilities and thresholds, and make the model limitations inspectable.

## Maintenance Notes

Refresh the app whenever the prepared feature manifest, selected model, or threshold changes. Refresh the dataset card and public files whenever a new collection window is released.
