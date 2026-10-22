"""Model training engine: train, compare, and select best model."""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
import sys
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import (
    StratifiedKFold, cross_val_score, train_test_split
)
from sklearn.pipeline import Pipeline
from sklearn.tree import DecisionTreeClassifier

from backend.app.core.config import settings
from backend.app.services.dataset_service import (
    build_quality_report, load_raw, prepare_dataframe, save_quality_report,
)
from backend.app.services.preprocessing_service import (
    build_pipeline, get_feature_names_out, save_feature_schema,
)
from backend.app.services.evaluation_service import (
    evaluate_model, save_evaluation_report, generate_figures,
)

logger = logging.getLogger(__name__)


def _build_candidate_models(fast: bool = False) -> Dict[str, Any]:
    """Return candidate model dict, optionally tuned for faster execution."""
    n_jobs = 1 if fast else settings.N_JOBS
    lr_max_iter = 200 if fast else 500
    return {
        "LogisticRegression": LogisticRegression(
            max_iter=lr_max_iter, class_weight="balanced",
            random_state=settings.RANDOM_SEED,
        ),
        "DecisionTree": DecisionTreeClassifier(
            max_depth=settings.MAX_DEPTH, class_weight="balanced",
            random_state=settings.RANDOM_SEED
        ),
        "RandomForest": RandomForestClassifier(
            n_estimators=settings.N_ESTIMATORS, max_depth=settings.MAX_DEPTH,
            class_weight="balanced", n_jobs=n_jobs,
            random_state=settings.RANDOM_SEED
        ),
        "HistGradientBoosting": HistGradientBoostingClassifier(
            max_iter=100, random_state=settings.RANDOM_SEED
        ),
    }


SELECTION_CRITERION = "f1"   # documented selection criterion


def train(
    dataset_path: Optional[Path] = None,
    max_rows: Optional[int] = None,
    binary: bool = True,
    fast: bool = False,
) -> dict:
    """
    Full training workflow:
      1. Load & validate data
      2. Preprocess
      3. Split (stratified)
      4. Train & CV-evaluate all candidates
      5. Select best by F1
      6. Evaluate on held-out test set
      7. Save artifacts

    Args:
        fast: If True, uses 1-fold CV and reduced hyperparameters to run
              significantly faster. Recommended for the demo dataset or CI.
    Returns metadata dict.
    """
    dataset_path = dataset_path or settings.dataset_path
    max_rows = max_rows or settings.MAX_TRAINING_ROWS
    binary = binary if binary is not None else (settings.CLASSIFICATION_MODE == "binary")

    logger.info("Loading dataset from %s (max_rows=%s)", dataset_path, max_rows)
    df = load_raw(dataset_path, max_rows=max_rows)

    # Data quality
    quality_report = build_quality_report(df, settings.LABEL_COLUMN, dataset_path)
    save_quality_report(quality_report)

    X, y, prep_info = prepare_dataframe(
        df,
        label_col=settings.LABEL_COLUMN,
        binary=binary,
        benign_label=settings.BENIGN_LABEL,
    )

    # Validate class coverage
    if y.nunique() < 2:
        raise ValueError("Dataset must have at least 2 distinct classes after encoding.")

    # Split: stratified
    X_temp, X_test, y_temp, y_test = train_test_split(
        X, y,
        test_size=settings.TEST_SPLIT,
        stratify=y,
        random_state=settings.RANDOM_SEED,
    )
    val_frac = settings.VAL_SPLIT / (1.0 - settings.TEST_SPLIT)
    X_train, X_val, y_train, y_val = train_test_split(
        X_temp, y_temp,
        test_size=val_frac,
        stratify=y_temp,
        random_state=settings.RANDOM_SEED,
    )
    logger.info("Split: train=%d val=%d test=%d", len(X_train), len(X_val), len(X_test))

    # Build preprocessor (fit on train only)
    preprocessor = build_pipeline(X_train)

    feature_names = X_train.columns.tolist()
    save_feature_schema(feature_names, X_train)

    candidate_models = _build_candidate_models(fast=fast)
    cv_folds = 1 if fast else settings.CV_FOLDS
    cv_n_jobs = 1 if fast else settings.N_JOBS

    comparison_rows = []

    # Evaluate all candidates with CV on train
    best_name = None
    best_f1 = -1.0

    for name, clf in candidate_models.items():
        logger.info("Training candidate: %s%s", name, " [fast]" if fast else "")
        pipe = Pipeline([("pre", preprocessor), ("clf", clf)])

        t0 = time.perf_counter()
        if cv_folds == 1:
            # Single-fold: train on 80% / score on 20% — no spawn overhead
            from sklearn.model_selection import ShuffleSplit
            cv = ShuffleSplit(n_splits=1, test_size=0.2, random_state=settings.RANDOM_SEED)
        else:
            cv = StratifiedKFold(n_splits=cv_folds, shuffle=True,
                                 random_state=settings.RANDOM_SEED)
        # For HistGradientBoosting we skip class_weight; it handles imbalance via sample weights
        cv_f1 = cross_val_score(
            pipe, X_train, y_train, cv=cv, scoring="f1_weighted", n_jobs=cv_n_jobs
        ).mean()
        pipe.fit(X_train, y_train)
        duration = time.perf_counter() - t0

        # Val metrics
        val_metrics = evaluate_model(pipe, X_val, y_val, binary=binary, split="validation")

        row = {
            "model": name,
            "cv_f1": round(cv_f1, 4),
            "val_accuracy": round(val_metrics.get("accuracy", 0), 4),
            "val_precision": round(val_metrics.get("precision", 0), 4),
            "val_recall": round(val_metrics.get("recall", 0), 4),
            "val_f1": round(val_metrics.get("f1_score", 0), 4),
            "val_fpr": round(val_metrics.get("false_positive_rate", 0), 4),
            "train_duration_s": round(duration, 2),
        }
        comparison_rows.append(row)

        if cv_f1 > best_f1:
            best_f1 = cv_f1
            best_name = name

        logger.info("%s cv_f1=%.4f val_f1=%.4f", name, cv_f1, val_metrics.get("f1_score", 0))

    # Save comparison
    comparison_df = pd.DataFrame(comparison_rows)
    comparison_df.to_csv(settings.comparison_path, index=False)
    logger.info("Best model by %s: %s (cv_f1=%.4f)", SELECTION_CRITERION, best_name, best_f1)

    # Final model: re-train best on train+val
    best_clf = candidate_models[best_name]
    X_trainval = pd.concat([X_train, X_val])
    y_trainval = pd.concat([y_train, y_val])

    final_pipe = Pipeline([("pre", build_pipeline(X_trainval)), ("clf", best_clf)])
    t0 = time.perf_counter()
    final_pipe.fit(X_trainval, y_trainval)
    train_duration = time.perf_counter() - t0

    # Evaluate on held-out test set
    test_metrics = evaluate_model(
        final_pipe, X_test, y_test,
        binary=binary, split="test",
        label_names=list(prep_info["target_mapping"].keys()),
    )
    test_metrics["n_train"] = len(X_trainval)
    test_metrics["n_test"] = len(X_test)
    test_metrics["training_duration_s"] = round(train_duration, 2)

    # Save model + metadata
    settings.MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(final_pipe, settings.model_path)

    metadata = {
        "model_name": best_name,
        "model_version": f"{best_name}-v1",
        "training_timestamp": datetime.now(timezone.utc).isoformat(),
        "dataset_source": str(dataset_path),
        "classification_mode": "binary" if binary else "multiclass",
        "target_mapping": prep_info["target_mapping"],
        "feature_names": feature_names,
        "feature_count": len(feature_names),
        "evaluation_split": f"stratified train/val/test ({int((1-settings.TEST_SPLIT-settings.VAL_SPLIT)*100)}/{int(settings.VAL_SPLIT*100)}/{int(settings.TEST_SPLIT*100)})",
        "selection_criterion": SELECTION_CRITERION,
        "test_metrics": test_metrics,
        "python_version": sys.version,
        "sklearn_version": __import__("sklearn").__version__,
        "numpy_version": np.__version__,
        "pandas_version": pd.__version__,
        "sampling_used": max_rows is not None and max_rows < len(df),
        "n_original_rows": len(df),
    }
    with open(settings.metadata_path, "w") as f:
        json.dump(metadata, f, indent=2, default=str)

    # Save evaluation report
    save_evaluation_report(test_metrics, metadata)

    # Generate all EDA and evaluation figures
    try:
        generate_figures(final_pipe, X_test, y_test, binary=binary, full_df=df)
        logger.info("Evaluation and EDA figures generated successfully.")
    except Exception as fe:
        logger.warning("Could not generate figures during training: %s", fe)

    logger.info("Training complete. Model saved to %s", settings.model_path)
    return metadata
