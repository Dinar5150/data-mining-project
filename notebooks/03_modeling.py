# %% [markdown]
# # Modeling
#
# CRISP-DM modeling stage for `review_concern`.

# %%
from pathlib import Path
import json
import sys

import pandas as pd
from IPython.display import Image, display

PROJECT_ROOT = next(
    path for path in (Path.cwd(), *Path.cwd().parents) if (path / "pipeline").exists()
)
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.modeling import train_and_evaluate

DATASET_VERSION = "dataset_modeling_v0.2"
DATA_DIR = PROJECT_ROOT / "data/processed/modeling_v0.2"
REPORT_DIR = PROJECT_ROOT / "reports/modeling_v0.2"
FIGURE_DIR = PROJECT_ROOT / "figures/modeling"
RUN_MODELING = False

if RUN_MODELING:
    train_and_evaluate(
        data_dir=DATA_DIR,
        dataset_version=DATASET_VERSION,
        report_dir=REPORT_DIR,
        figure_dir=FIGURE_DIR,
    )

# %% [markdown]
# ## Select Modeling Technique
#
# Models are compared against a majority-class baseline. The trained candidates
# are logistic regression and XGBoost, each with tabular-only and full
# tabular-plus-embedding feature sets.

# %%
summary = json.loads((REPORT_DIR / "modeling_summary.json").read_text())
metrics = pd.read_csv(REPORT_DIR / "modeling_metrics.csv")
metrics[
    [
        "model",
        "feature_set",
        "feature_count",
        "val_roc_auc",
        "val_average_precision",
        "val_macro_f1",
        "val_balanced_accuracy",
        "val_threshold",
    ]
]

# %% [markdown]
# ## Generate Test Design
#
# Repository-level train/validation/test splits are inherited from data
# preparation. Model selection uses validation ROC-AUC; the selected threshold
# maximizes validation macro-F1.

# %%
summary["class_balance"], summary["selected_model"], summary["selected_threshold"]

# %% [markdown]
# ## Build Model
#
# The best validation model is assessed on the held-out test split with the
# threshold selected on validation macro-F1.

# %%
print((REPORT_DIR / "selected_test_classification_report.txt").read_text())

# %% [markdown]
# ## Assess Model
#
# Validation plots and selected-model diagnostics are shown below.

# %%
for name in [
    "model_comparison_validation.png",
    "selected_validation_curves.png",
    "selected_validation_confusion.png",
    "selected_test_confusion.png",
    "selected_feature_importance.png",
]:
    display(Image(filename=str(FIGURE_DIR / name)))
