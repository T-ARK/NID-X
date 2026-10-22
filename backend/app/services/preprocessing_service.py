"""Preprocessing pipeline: imputation, encoding, scaling."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List, Optional

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, OrdinalEncoder, StandardScaler

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


def build_pipeline(X_train: pd.DataFrame) -> Pipeline:
    """
    Build a sklearn Pipeline fitted on X_train column types.
    Returns the unfitted pipeline object (caller must call .fit()).
    """
    numeric_cols = X_train.select_dtypes(include=[np.number]).columns.tolist()
    cat_cols = X_train.select_dtypes(exclude=[np.number]).columns.tolist()

    numeric_transformer = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])

    transformers = [("num", numeric_transformer, numeric_cols)]

    if cat_cols:
        cat_transformer = Pipeline([
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("encoder", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)),
        ])
        transformers.append(("cat", cat_transformer, cat_cols))

    preprocessor = ColumnTransformer(transformers=transformers, remainder="drop")
    return preprocessor


def get_feature_names_out(preprocessor: ColumnTransformer, X: pd.DataFrame) -> List[str]:
    numeric_cols = X.select_dtypes(include=[np.number]).columns.tolist()
    cat_cols = X.select_dtypes(exclude=[np.number]).columns.tolist()
    return numeric_cols + cat_cols


def save_feature_schema(feature_names: List[str], X_sample: pd.DataFrame) -> Path:
    schema = {
        "feature_names": feature_names,
        "feature_count": len(feature_names),
        "dtypes": {c: str(X_sample[c].dtype) for c in X_sample.columns if c in feature_names},
    }
    path = settings.feature_schema_path
    with open(path, "w") as f:
        json.dump(schema, f, indent=2)
    return path


def load_feature_schema() -> Optional[dict]:
    path = settings.feature_schema_path
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def validate_input_schema(df: pd.DataFrame, feature_names: List[str]) -> list[str]:
    """Return list of warnings about mismatched columns."""
    warnings: list[str] = []
    missing = set(feature_names) - set(df.columns)
    extra = set(df.columns) - set(feature_names)
    if missing:
        warnings.append(f"Missing expected columns: {sorted(missing)[:10]}")
    if extra:
        warnings.append(f"Extra columns (will be ignored): {sorted(extra)[:10]}")
    return warnings


def align_input(df: pd.DataFrame, feature_names: List[str]) -> pd.DataFrame:
    """Reindex df to match expected feature names; fill missing with NaN."""
    return df.reindex(columns=feature_names)
