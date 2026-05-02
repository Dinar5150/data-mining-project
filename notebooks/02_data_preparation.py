# %% [markdown]
# # Data Preparation
#
# This notebook mirrors `pipeline.data_preparation`. It follows the CRISP-DM
# data-preparation tasks: select data, clean data, construct data, integrate
# data, and format data.

# %%
from pathlib import Path
import json
import sys
import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier

PROJECT_ROOT = next(
    path for path in (Path.cwd(), *Path.cwd().parents) if (path / "pipeline").exists()
)
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.data_preparation import prepare_modeling_data

DATASET_VERSION = "dataset_modeling_v0.2"
OUTPUT_DIR = PROJECT_ROOT / "data/processed/modeling_v0.2"
RUN_PREPARATION = False

if RUN_PREPARATION:
    prepare_modeling_data(
        raw_path=PROJECT_ROOT / "enriched_prs_raw_new.jsonl",
        output_dir=OUTPUT_DIR,
        config_path=PROJECT_ROOT / "config.yaml",
        token_cap=1000,
        batch_size=32,
        dataset_version=DATASET_VERSION,
    )

# %% [markdown]
# ## Select Data
#
# The raw enriched pull request records are split by repository. The modeling
# target is `review_concern`; rows without review activity are excluded from
# train/validation/test matrices.

# %%
summary = json.loads(
    (OUTPUT_DIR / f"{DATASET_VERSION}.preparation_summary.json").read_text()
)
manifest = json.loads(
    (OUTPUT_DIR / f"{DATASET_VERSION}.feature_manifest.json").read_text()
)
summary["split_summary"]

# %% [markdown]
# ## Clean Data
#
# Bot authors, documentation-only changes, generated/vendor-only changes, and
# missing source patches are retained as quality metadata. These fields are kept
# for audit and are not used as model features.

# %%
pd.DataFrame(summary["top_reject_reasons"], columns=["reason", "rows"])

# %% [markdown]
# ## Construct Data
#
# The table contains pull-request-intrinsic tabular features plus a 768-dim
# ModernBERT embedding of source-code `files[].patch`, capped to 1,000 tokens
# per row.

# %%
print("target:", manifest["target_column"])
print("feature_count:", len(manifest["feature_columns"]))
print("embedding_columns:", len(manifest["embedding_columns"]))
print("token_cap:", manifest["embedding_token_cap"])

# %% [markdown]
# ## Integrate Data
#
# Pull request metadata, changed-file summaries, source patches, labels, and
# quality metadata are integrated into one row per pull request.

# %%
all_df = pd.read_parquet(
    OUTPUT_DIR / f"{DATASET_VERSION}.all.parquet",
    columns=[
        "example_id",
        "repo",
        "pr_number",
        "split",
        "review_concern",
        "accepted_quality",
        "top_language",
        "source_patch_token_count_capped",
    ],
)
all_df.head()

# %% [markdown]
# ## Format Data
#
# The `.npz` files contain numeric `X` and `y` arrays and can be passed directly
# to scikit-learn style `.fit()` and `.predict()` calls.

# %%
train = np.load(OUTPUT_DIR / f"{DATASET_VERSION}.train.npz")
val = np.load(OUTPUT_DIR / f"{DATASET_VERSION}.val.npz")
print("train:", train["X"].shape, train["y"].shape, np.bincount(train["y"]))
print("val:", val["X"].shape, val["y"].shape, np.bincount(val["y"]))

model = DummyClassifier(strategy="most_frequent")
model.fit(train["X"], train["y"])
pred = model.predict(val["X"])
print("fit_predict_ok:", pred.shape)
