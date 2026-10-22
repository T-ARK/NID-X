"""FastAPI route definitions for NID-X."""
from __future__ import annotations

import io
import logging
import uuid
from typing import Optional

import pandas as pd
from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse

from backend.app.core.config import settings
from backend.app.db.database import (
    acknowledge_alert, resolve_alert, get_alerts, get_history,
    insert_alert, insert_alerts_batch, insert_prediction_batch,
    get_alerts_count, get_overview_stats, get_alerts_summary,
    clear_alerts_and_history,
)
from backend.app.schemas.schemas import (
    AlertRecord, AlertsResponse, CSVPredictResponse, ErrorResponse,
    HealthResponse, HistoryRecord, HistoryResponse, MetricsResponse,
    ModelInfoResponse, PerClassMetrics, PredictRequest, PredictResponse,
    PredictionResult, ReportEntry, ReportsListResponse, SettingsResponse,
    SettingsUpdateRequest,
)
from backend.app.services.evaluation_service import load_evaluation_report
from backend.app.services.prediction_service import (
    get_model_version, is_model_available, predict_dataframe, predict_records,
)
from backend.app.services.report_service import (
    generate_summary_report, get_report_path, list_reports,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Health ────────────────────────────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(
        status="ok",
        model_loaded=is_model_available(),
        model_version=get_model_version(),
        app_version=settings.APP_VERSION,
        env=settings.ENV,
    )


# ── Model info ────────────────────────────────────────────────────────────────

@router.get("/model/info", response_model=ModelInfoResponse)
def model_info():
    from backend.app.services.preprocessing_service import load_feature_schema
    import json

    if not settings.metadata_path.exists():
        return ModelInfoResponse(available=False)

    with open(settings.metadata_path) as f:
        md = json.load(f)

    schema = load_feature_schema()

    return ModelInfoResponse(
        model_name=md.get("model_name"),
        model_version=md.get("model_version"),
        training_timestamp=md.get("training_timestamp"),
        dataset_id=md.get("dataset_source"),
        classification_mode=md.get("classification_mode"),
        feature_count=md.get("feature_count"),
        feature_names=schema["feature_names"][:30] if schema else None,
        target_mapping=md.get("target_mapping"),
        evaluation_split=md.get("evaluation_split"),
        available=True,
    )


# ── Metrics ───────────────────────────────────────────────────────────────────

_SAMPLE_FILENAMES = {"sample_flows.csv"}


def _report_is_sample(report: dict) -> bool:
    """Return True if the evaluation report was produced from the bundled sample data."""
    src = (report.get("metadata") or {}).get("dataset_source", "")
    return any(s in src for s in _SAMPLE_FILENAMES)


@router.get("/metrics", response_model=MetricsResponse)
def metrics():
    report = load_evaluation_report()
    if report is None:
        return MetricsResponse(available=False)

    is_sample = _report_is_sample(report)

    pc_raw = report.get("per_class") or {}
    per_class = {
        k: PerClassMetrics(**v) for k, v in pc_raw.items()
    }

    comparison_data = None
    if settings.comparison_path.exists():
        try:
            comp_df = pd.read_csv(settings.comparison_path)
            comparison_data = comp_df.to_dict(orient="records")
        except Exception:
            pass

    md = report.get("metadata", {})
    return MetricsResponse(
        available=True,
        is_sample_data=is_sample,
        accuracy=report.get("accuracy"),
        precision=report.get("precision"),
        recall=report.get("recall"),
        f1_score=report.get("f1_score"),
        false_positive_rate=report.get("false_positive_rate"),
        false_negative_rate=report.get("false_negative_rate"),
        roc_auc=report.get("roc_auc"),
        pr_auc=report.get("pr_auc"),
        confusion_matrix=report.get("confusion_matrix"),
        per_class=per_class if per_class else None,
        training_duration_s=report.get("training_duration_s"),
        inference_duration_ms=report.get("inference_duration_ms"),
        n_train=report.get("n_train"),
        n_test=report.get("n_test"),
        model_name=md.get("model_name"),
        evaluated_at=md.get("training_timestamp"),
        model_comparison=comparison_data,
    )


# ── Predict ───────────────────────────────────────────────────────────────────

@router.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    if not is_model_available():
        raise HTTPException(status_code=503, detail="Model not trained. Run train_model.py first.")
    try:
        result = predict_records(req.records)
    except Exception as e:
        logger.exception("Prediction error")
        raise HTTPException(status_code=500, detail=str(e))

    # Persist history and alerts
    try:
        insert_prediction_batch(
            source_type="api",
            batch_id=result["batch_id"],
            model_ver=result.get("model_version", ""),
            record_count=result["total"],
            attack_count=result["attack_count"],
            benign_count=result["benign_count"],
        )
        for pred in result["predictions"]:
            if pred["predicted_class"] == 1:
                insert_alert(
                    predicted_class=pred["predicted_label"],
                    score=pred.get("probability"),
                    model_ver=pred.get("model_version", ""),
                    source_type="api",
                    batch_id=result["batch_id"],
                )
    except Exception as e:
        logger.warning("DB write error: %s", e)

    preds = [PredictionResult(**p) for p in result["predictions"]]
    return PredictResponse(
        predictions=preds,
        attack_count=result["attack_count"],
        benign_count=result["benign_count"],
        total=result["total"],
        model_version=result.get("model_version"),
        batch_id=result["batch_id"],
    )


# ── CSV Upload & Traffic Analysis ─────────────────────────────────────────────

@router.post("/predict/csv", response_model=CSVPredictResponse)
async def predict_csv(file: UploadFile = File(...)):
    if not is_model_available():
        raise HTTPException(status_code=503, detail="Model not trained. Please train the model on a user-uploaded dataset first.")

    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    content = await file.read()
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail=f"File exceeds {settings.MAX_UPLOAD_MB} MB limit.")

    try:
        df = pd.read_csv(io.BytesIO(content), low_memory=False)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Cannot parse CSV: {e}")

    if df.empty:
        raise HTTPException(status_code=422, detail="CSV file is empty.")

    if len(df) > settings.MAX_UPLOAD_ROWS:
        raise HTTPException(
            status_code=413,
            detail=f"CSV has {len(df)} rows, maximum is {settings.MAX_UPLOAD_ROWS}.",
        )

    try:
        from backend.app.services.traffic_analysis_service import analyze_uploaded_traffic
        result = analyze_uploaded_traffic(
            df=df,
            filename=file.filename or "uploaded_traffic.csv",
            threshold=settings.PREDICTION_THRESHOLD,
        )
    except Exception as e:
        logger.exception("Traffic analysis error")
        raise HTTPException(status_code=500, detail=str(e))

    total = result["total_records"]
    atk = result["attack_count"]
    ben = result["benign_count"]
    rate = result["attack_rate"]

    # Persist in SQLite
    try:
        insert_prediction_batch(
            source_type="csv_upload",
            batch_id=result["batch_id"],
            model_ver=result.get("model_version", ""),
            record_count=total,
            attack_count=atk,
            benign_count=ben,
            summary={"filename": file.filename, "threat_level": result.get("overall_threat_level")},
        )
        alerts_to_insert = [
            {
                "predicted_class": pred["predicted_label"],
                "score": pred.get("probability"),
                "model_ver": pred.get("model_version", ""),
                "source_type": "csv_upload",
                "batch_id": result["batch_id"],
                "severity": "CRITICAL" if (pred.get("probability") or 0) >= 0.85 else "HIGH",
            }
            for pred in result["predictions"]
            if pred["predicted_class"] == 1
        ]
        if alerts_to_insert:
            insert_alerts_batch(alerts_to_insert)
    except Exception as e:
        logger.warning("DB write error: %s", e)

    # Save prediction CSV export
    try:
        generate_summary_report(result["predictions"], result["batch_id"])
    except Exception as e:
        logger.warning("Could not save prediction export: %s", e)

    return CSVPredictResponse(
        batch_id=result["batch_id"],
        total_records=total,
        attack_count=atk,
        benign_count=ben,
        attack_rate=rate,
        predictions=result["predictions"],
        warnings=result.get("warnings", []),
        model_version=result.get("model_version"),
        overall_threat_level=result.get("overall_threat_level"),
        inference_ms=result.get("inference_ms"),
        evaluation=result.get("evaluation"),
        charts=result.get("charts"),
        chart_data=result.get("chart_data"),
        analytical_report=result.get("analytical_report"),
        report_id=result.get("report_id"),
    )


# ── Dataset Upload (User-Provided Training/Benchmark Data) ─────────────────────

@router.post("/dataset/upload")
async def upload_dataset(file: UploadFile = File(...)):
    """Upload user network traffic dataset to data/raw/ for model training and analysis."""
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV datasets are accepted.")

    max_bytes = 200 * 1024 * 1024  # 200 MB limit
    content = await file.read()
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail="Dataset exceeds 200 MB limit.")

    try:
        df = pd.read_csv(io.BytesIO(content), nrows=50)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Cannot parse CSV: {e}")

    settings.RAW_DIR.mkdir(parents=True, exist_ok=True)
    target_path = settings.RAW_DIR / settings.DATASET_FILENAME
    with open(target_path, "wb") as f:
        f.write(content)

    logger.info("Saved user-uploaded dataset to %s (%d bytes)", target_path, len(content))
    return {
        "status": "ok",
        "message": f"Successfully uploaded dataset '{file.filename}' to {target_path.name}.",
        "path": str(target_path),
        "columns_sample": df.columns.tolist()[:15],
        "size_bytes": len(content),
    }


# ── Alerts ────────────────────────────────────────────────────────────────────

@router.get("/alerts", response_model=AlertsResponse)
def alerts(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    unack_only: bool = Query(False),
    batch_id: Optional[str] = Query(None),
):
    offset = (page - 1) * page_size
    rows = get_alerts(limit=page_size, offset=offset, unack_only=unack_only, batch_id=batch_id)
    alert_records = []
    for r in rows:
        alert_records.append(AlertRecord(
            id=r["id"],
            timestamp=r["timestamp"],
            predicted_class=r["predicted_class"],
            score=r["score"],
            model_ver=r.get("model_ver"),
            source_type=r.get("source_type"),
            batch_id=r.get("batch_id"),
            flow_meta=r.get("flow_meta"),
            severity=r.get("severity", "HIGH"),
            acknowledged=r.get("acknowledged", 0),
            resolved=r.get("resolved", 0),
        ))
    total_count = get_alerts_count(unack_only=unack_only, batch_id=batch_id)
    summary_data = get_alerts_summary()
    return AlertsResponse(
        alerts=alert_records,
        total=total_count,
        page=page,
        page_size=page_size,
        summary=summary_data,
    )


@router.post("/alerts/clear")
def clear_alerts_route():
    """Clear all alerts and prediction history for a clean audit run."""
    return clear_alerts_and_history()


# ── Overview Live Stats ───────────────────────────────────────────────────────

@router.get("/overview/stats")
def overview_stats():
    stats = get_overview_stats()
    eval_rep = load_evaluation_report()
    if eval_rep is not None:
        eval_rep["is_sample_data"] = _report_is_sample(eval_rep)
    stats["metrics"] = eval_rep
    return stats


# ── Sample Dataset On Demand ──────────────────────────────────────────────────

@router.get("/dataset/sample")
def get_sample_dataset():
    """Load sample demonstration data ONLY when explicitly requested by user."""
    sample_path = settings.SAMPLE_DIR / "sample_flows.csv"
    if not sample_path.exists():
        raise HTTPException(status_code=404, detail="Sample demonstration dataset file not found.")
    return FileResponse(str(sample_path), media_type="text/csv", filename="sample_flows.csv")


@router.post("/alerts/{alert_id}/acknowledge", status_code=204)
def ack_alert(alert_id: str):
    ok = acknowledge_alert(alert_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Alert not found.")


@router.post("/alerts/{alert_id}/resolve", status_code=204)
def resolve_alert_route(alert_id: str):
    ok = resolve_alert(alert_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Alert not found.")


# ── History ───────────────────────────────────────────────────────────────────

@router.get("/history", response_model=HistoryResponse)
def history(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    rows = get_history(limit=limit, offset=offset)
    records = [HistoryRecord(**r) for r in rows]
    return HistoryResponse(history=records, total=len(rows))


# ── Reports ───────────────────────────────────────────────────────────────────

@router.get("/reports", response_model=ReportsListResponse)
def list_report_files():
    return ReportsListResponse(
        reports=[ReportEntry(**r) for r in list_reports()]
    )


@router.get("/reports/{report_id}/download")
def download_report(report_id: str):
    try:
        path = get_report_path(report_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    media_map = {"json": "application/json", "csv": "text/csv", "png": "image/png"}
    suffix = path.suffix.lstrip(".")
    media_type = media_map.get(suffix, "application/octet-stream")
    return FileResponse(str(path), media_type=media_type, filename=path.name)


@router.post("/reports/generate")
def generate_report():
    """Regenerate figures from the last evaluation if a trained model is available."""
    if not is_model_available():
        raise HTTPException(status_code=503, detail="No trained model. Run train_model.py first.")

    import json
    import joblib
    from pathlib import Path
    from backend.app.services.dataset_service import load_raw, prepare_dataframe
    from backend.app.services.evaluation_service import generate_figures

    dataset_to_use = None
    if settings.dataset_path.exists():
        dataset_to_use = settings.dataset_path
    elif settings.metadata_path.exists():
        with open(settings.metadata_path) as f:
            md = json.load(f)
        src = md.get("dataset_source")
        if src and Path(src).exists() and "sample_flows.csv" not in str(src):
            dataset_to_use = Path(src)

    if not dataset_to_use:
        raise HTTPException(
            status_code=400,
            detail="No user-uploaded dataset found. Please upload your network traffic dataset first. Synthetic data generation is disabled.",
        )

    try:
        pipeline = joblib.load(settings.model_path)
        df = load_raw(dataset_to_use, max_rows=20_000)
        binary = (settings.CLASSIFICATION_MODE == "binary")
        X, y, _ = prepare_dataframe(
            df,
            label_col=settings.LABEL_COLUMN,
            binary=binary,
            benign_label=settings.BENIGN_LABEL,
        )
        saved = generate_figures(pipeline, X, y, binary=binary, full_df=df)
        return {
            "message": f"Successfully generated {len(saved)} figures from user-uploaded dataset.",
            "figures": [p.name for p in saved],
            "status": "ok",
        }
    except Exception as e:
        logger.exception("Failed to regenerate figures: %s", e)
        raise HTTPException(status_code=500, detail=f"Figure generation failed: {e}")


# ── Settings ──────────────────────────────────────────────────────────────────

@router.get("/settings", response_model=SettingsResponse)
def get_settings():
    return SettingsResponse(
        classification_mode=settings.CLASSIFICATION_MODE,
        prediction_threshold=settings.PREDICTION_THRESHOLD,
        max_upload_mb=settings.MAX_UPLOAD_MB,
        max_upload_rows=settings.MAX_UPLOAD_ROWS,
        batch_size=settings.BATCH_SIZE,
        random_seed=settings.RANDOM_SEED,
        label_column=settings.LABEL_COLUMN,
        dataset_filename=settings.DATASET_FILENAME,
        model_available=is_model_available(),
    )


@router.patch("/settings", response_model=SettingsResponse)
def update_settings(req: SettingsUpdateRequest):
    if req.classification_mode is not None:
        settings.CLASSIFICATION_MODE = req.classification_mode
    if req.prediction_threshold is not None:
        settings.PREDICTION_THRESHOLD = req.prediction_threshold
    if req.max_upload_mb is not None:
        settings.MAX_UPLOAD_MB = req.max_upload_mb
    if req.batch_size is not None:
        settings.BATCH_SIZE = req.batch_size
    return get_settings()


# ── Training Service Trigger (Non-blocking background) ────────────────────────

_training_state = {"running": False, "last_result": None, "error": None}


@router.get("/train/status")
def train_status():
    return _training_state


def _bg_train_worker(dataset_path_str: Optional[str] = None):
    global _training_state
    _training_state["running"] = True
    _training_state["error"] = None
    try:
        from pathlib import Path
        from backend.app.services.training_service import train
        from backend.app.services.prediction_service import reload_model

        target_path = Path(dataset_path_str) if dataset_path_str else settings.dataset_path
        if not target_path or not target_path.exists():
            raise FileNotFoundError(
                "No user-uploaded dataset found. Please upload a dataset to data/raw/ before training. Synthetic data generation is disabled."
            )

        meta = train(dataset_path=target_path)
        reload_model()
        _training_state["last_result"] = meta.get("model_version")
    except Exception as e:
        logger.exception("Background training error: %s", e)
        _training_state["error"] = str(e)
    finally:
        _training_state["running"] = False


@router.post("/train", status_code=202)
def trigger_training(bg: BackgroundTasks, dataset: Optional[str] = None):
    if _training_state["running"]:
        raise HTTPException(status_code=409, detail="A training job is already in progress.")
    target = Path(dataset) if dataset else settings.dataset_path
    if not target.exists():
        raise HTTPException(
            status_code=400,
            detail="No user-uploaded dataset found. Please upload your network flow dataset before training. Synthetic data generation is disabled.",
        )
    bg.add_task(_bg_train_worker, str(target))
    return {"message": "Model training started in background using user-uploaded dataset.", "status": "started"}

