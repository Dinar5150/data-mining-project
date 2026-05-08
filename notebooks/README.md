# `notebooks/` — CRISP-DM Notebooks

Each notebook mirrors a CRISP-DM phase and consumes the artifacts produced by
the [`pipeline/`](../pipeline/README.md) package. Notebooks are paired with a
`.py` percent-formatted script of the same name that is the source of truth
when both exist.

| Notebook | Phase | Source script |
| --- | --- | --- |
| [`01_data_understanding.ipynb`](01_data_understanding.ipynb) | Data Understanding | — |
| [`02_data_preparation.ipynb`](02_data_preparation.ipynb) | Data Preparation | [`02_data_preparation.py`](02_data_preparation.py) |
| [`03_modeling.ipynb`](03_modeling.ipynb) | Modeling | [`03_modeling.py`](03_modeling.py) |
| [`04_evaluation_deployment.ipynb`](04_evaluation_deployment.ipynb) | Evaluation & Deployment | [`04_evaluation_deployment.py`](04_evaluation_deployment.py) |

## Running

Notebooks expect to be opened from the project root so that
`PROJECT_ROOT / "pipeline"` resolves correctly. The data-preparation notebook
loads raw enriched PRs from [`data/raw/`](../data/README.md); the modeling and
evaluation notebooks read pre-built matrices from
[`data/processed/modeling_v0.2/`](../data/README.md) and write artifacts to
[`reports/`](../reports/) and [`figures/`](../figures/).
