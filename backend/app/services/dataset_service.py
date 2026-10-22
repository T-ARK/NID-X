"""Dataset loading and data quality reporting."""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from backend.app.core.config import settings

logger = logging.getLogger(__name__)

# Columns that are pure identifiers or timestamps – evaluated at load time
EXCLUDE_PATTERNS = [
    "flow id", "source ip", "src ip", "destination ip", "dst ip",
    "source port", "src port", "destination port", "dst port",
    "timestamp", "external ip", "sid", "unnamed",
]

# Columns that directly encode the label
LABEL_LEAKAGE_PATTERNS: list[str] = []


def _normalise_col(col: str) -> str:
    return col.strip().lower().replace(" ", "_").replace("/", "_")


def load_raw(path: Path, max_rows: Optional[int] = None) -> pd.DataFrame:
    """Load CSV in chunks; optionally cap rows."""
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    chunks = []
    rows_read = 0
    for chunk in pd.read_csv(
        path,
        chunksize=settings.CHUNK_SIZE,
        low_memory=False,
        on_bad_lines="warn",
    ):
        chunks.append(chunk)
        rows_read += len(chunk)
        if max_rows and rows_read >= max_rows:
            break

    df = pd.concat(chunks, ignore_index=True)
    if max_rows:
        df = df.iloc[:max_rows]
    logger.info("Loaded %d rows, %d cols from %s", len(df), len(df.columns), path)
    return df


def fingerprint(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def build_quality_report(df: pd.DataFrame, label_col: str, path: Optional[Path] = None) -> dict:
    """Generate a data quality report from the raw dataframe."""
    report: dict = {}
    report["total_records"] = len(df)
    report["total_features"] = len(df.columns) - (1 if label_col in df.columns else 0)

    # Missing values
    missing = df.isnull().sum()
    missing = missing[missing > 0]
    report["missing_values"] = {c: int(v) for c, v in missing.items()}
    report["missing_total"] = int(missing.sum())

    # Duplicates
    dup_count = int(df.duplicated().sum())
    report["duplicate_rows"] = dup_count

    # Class distribution
    if label_col in df.columns:
        dist = df[label_col].value_counts().to_dict()
        report["class_distribution"] = {str(k): int(v) for k, v in dist.items()}
    else:
        report["class_distribution"] = {}

    # Infinite values
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    inf_counts = {c: int(np.isinf(df[c]).sum()) for c in numeric_cols if np.isinf(df[c]).any()}
    report["infinite_values"] = inf_counts

    # Constant / near-constant features
    constant_features = [c for c in df.columns if df[c].nunique() <= 1]
    report["constant_features"] = constant_features

    if path:
        report["dataset_source"] = str(path)
        report["dataset_fingerprint"] = fingerprint(path)

    return report


def prepare_dataframe(
    df: pd.DataFrame,
    label_col: str,
    binary: bool = True,
    benign_label: str = "BENIGN",
) -> tuple[pd.DataFrame, pd.Series, dict]:
    """
    Clean columns, remove leakage cols, encode binary/multiclass target.
    Returns (X, y, info_dict).
    """
    orig_cols = df.columns.tolist()
    df = df.copy()

    # Strip whitespace from column names
    df.columns = [c.strip() for c in df.columns]

    # Find label column (case-insensitive)
    matched_label = next(
        (c for c in df.columns if c.strip().lower() == label_col.strip().lower()),
        None,
    )
    if matched_label is None:
        raise ValueError(
            f"Label column '{label_col}' not found. Available: {df.columns.tolist()[:20]}"
        )
    label_col = matched_label

    # Strip whitespace in label values
    df[label_col] = df[label_col].astype(str).str.strip()

    # Exclude identifier/timestamp columns
    excluded: list[str] = []
    keep_cols: list[str] = []
    for col in df.columns:
        if col == label_col:
            continue
        col_lower = col.lower().replace(" ", "_")
        if any(pat in col_lower for pat in EXCLUDE_PATTERNS):
            excluded.append(col)
        else:
            keep_cols.append(col)

    # Drop fully constant features
    constant = [c for c in keep_cols if df[c].nunique() <= 1]
    excluded.extend(constant)
    keep_cols = [c for c in keep_cols if c not in constant]

    # Extract target
    y_raw = df[label_col]

    X = df[keep_cols].copy()

    # Convert numeric-looking string columns
    for col in X.columns:
        if X[col].dtype == object:
            converted = pd.to_numeric(X[col], errors="coerce")
            if converted.notna().mean() > 0.8:
                X[col] = converted

    # Replace inf with NaN
    X = X.replace([np.inf, -np.inf], np.nan)

    # Encode target
    if binary:
        y = (y_raw != benign_label).astype(int)
        target_mapping = {benign_label: 0, "ATTACK": 1}
    else:
        classes = sorted(y_raw.unique())
        mapping = {lbl: i for i, lbl in enumerate(classes)}
        y = y_raw.map(mapping).fillna(-1).astype(int)
        target_mapping = mapping

    info = {
        "excluded_features": excluded,
        "kept_features": keep_cols,
        "label_column": label_col,
        "binary_mode": binary,
        "target_mapping": target_mapping,
        "n_samples": len(X),
    }
    return X, y, info


def save_quality_report(report: dict) -> Path:
    path = settings.data_quality_path
    with open(path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    return path
