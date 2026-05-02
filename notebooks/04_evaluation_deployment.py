# %% [markdown]
# # Evaluation and Deployment
#
# CRISP-DM Evaluation and Deployment summary for the review-concern project.

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

from pipeline.evaluation import evaluate_project

REPORT_DIR = PROJECT_ROOT / "reports/evaluation_v0.2"
FIGURE_DIR = PROJECT_ROOT / "figures/evaluation"
RUN_EVALUATION = False

if RUN_EVALUATION:
    evaluate_project(
        prep_summary_path=PROJECT_ROOT / "data/processed/modeling_v0.2/dataset_modeling_v0.2.preparation_summary.json",
        modeling_summary_path=PROJECT_ROOT / "reports/modeling_v0.2/modeling_summary.json",
        output_dir=REPORT_DIR,
        figure_dir=FIGURE_DIR,
    )

# %% [markdown]
# ## Evaluate Results
#
# The scorecard checks whether the data mining results satisfy the original
# business and data mining success criteria.

# %%
scorecard = pd.read_csv(REPORT_DIR / "evaluation_scorecard.csv")
scorecard

# %% [markdown]
# ## Review Process
#
# The process review focuses on whether the CRISP-DM steps were sufficient and
# whether any weak assumptions remain.

# %%
summary = json.loads((REPORT_DIR / "evaluation_summary.json").read_text())
summary["business_result"], summary["data_mining_result"], summary["deployment_result"]

# %% [markdown]
# ## Determine Next Steps
#
# The current result is demonstrable, and another iteration should focus on
# improving model quality.

# %%
summary["recommendation"]

# %% [markdown]
# ## Deployment
#
# The deployment artifacts are a public dataset page and a local Streamlit demo.

# %%
summary["huggingface_dataset_url"], summary["streamlit_demo_url"]

# %%
display(Image(filename=str(FIGURE_DIR / "evaluation_scorecard.png")))
