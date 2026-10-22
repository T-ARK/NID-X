"""Prediction service: load model, run inference."""
from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd

from backend.app.core.config import settings
from backend.app.services.preprocessing_service import align_input, load_feature_schema

logger = logging.getLogger(__name__)

# Module-level cache
_model_pipeline = None
_model_metadata: Optional[dict] = None


def _load_model() -> Tuple[Any, dict]:
    global _model_pipeline, _model_metadata
    if _model_pipeline is not None:
        return _model_pipeline, _model_metadata

    if not settings.model_path.exists():
        raise FileNotFoundError(
            f"Model not found at {settings.model_path}. Run 'python scripts/train_model.py' first."
        )
    _model_pipeline = joblib.load(settings.model_path)

    if settings.metadata_path.exists():
        with open(settings.metadata_path) as f:
            _model_metadata = json.load(f)
    else:
        _model_metadata = {"model_version": "unknown"}

    logger.info("Model loaded: %s", _model_metadata.get("model_version", "unknown"))
    return _model_pipeline, _model_metadata


def is_model_available() -> bool:
    return settings.model_path.exists()


def get_model_version() -> Optional[str]:
    if settings.metadata_path.exists():
        with open(settings.metadata_path) as f:
            md = json.load(f)
        return md.get("model_version")
    return None


def reload_model() -> None:
    """Force reload the cached model."""
    global _model_pipeline, _model_metadata
    _model_pipeline = None
    _model_metadata = None
    _load_model()


def predict_records(
    records: List[Dict[str, Any]],
    threshold: Optional[float] = None,
) -> dict:
    """Run inference on a list of record dicts."""
    pipeline, metadata = _load_model()
    threshold = threshold or settings.PREDICTION_THRESHOLD
    schema = load_feature_schema()
    feature_names = schema["feature_names"] if schema else None

    df = pd.DataFrame(records)
    warnings: List[str] = []

    if feature_names:
        missing_cols = set(feature_names) - set(df.columns)
        if missing_cols:
            warnings.append(f"Input missing {len(missing_cols)} expected features; filled with NaN.")
        df = align_input(df, feature_names)

    t0 = time.perf_counter()
    predictions = _run_inference(pipeline, df, threshold)
    infer_ms = (time.perf_counter() - t0) * 1000

    model_ver = metadata.get("model_version", "unknown") if metadata else "unknown"
    ts = datetime.now(timezone.utc).isoformat()
    binary = metadata.get("classification_mode", "binary") == "binary" if metadata else True
    target_map = metadata.get("target_mapping", {}) if metadata else {}
    inv_map = {v: k for k, v in target_map.items()} if target_map else {}

    results = []
    attack_count = 0
    benign_count = 0
    for i, (pred_cls, prob) in enumerate(predictions):
        label = inv_map.get(pred_cls, "ATTACK" if pred_cls == 1 else "BENIGN")
        is_attack = pred_cls == 1 if binary else pred_cls != 0
        if is_attack:
            attack_count += 1
        else:
            benign_count += 1
        results.append({
            "row_index": i,
            "predicted_label": label,
            "predicted_class": int(pred_cls),
            "probability": round(float(prob), 4) if prob is not None else None,
            "model_version": model_ver,
            "timestamp": ts,
            "warning": warnings[0] if warnings else None,
        })

    batch_id = str(uuid.uuid4())
    return {
        "predictions": results,
        "attack_count": attack_count,
        "benign_count": benign_count,
        "total": len(results),
        "model_version": model_ver,
        "batch_id": batch_id,
        "inference_ms": round(infer_ms, 2),
    }


def predict_dataframe(
    df: pd.DataFrame,
    threshold: Optional[float] = None,
) -> dict:
    """Run inference on a DataFrame (CSV upload path)."""
    records = df.to_dict(orient="records")
    return predict_records(records, threshold=threshold)


def _run_inference(pipeline, df: pd.DataFrame, threshold: float) -> List[Tuple[int, Optional[float]]]:
    results = []
    if hasattr(pipeline, "predict_proba"):
        probs = pipeline.predict_proba(df)
        if probs.shape[1] == 2:
            for p in probs:
                cls = 1 if p[1] >= threshold else 0
                results.append((cls, float(p[1])))
        else:
            preds = np.argmax(probs, axis=1)
            for cls, p in zip(preds, probs):
                results.append((int(cls), float(p.max())))
    else:
        preds = pipeline.predict(df)
        for cls in preds:
            results.append((int(cls), None))
    return results
