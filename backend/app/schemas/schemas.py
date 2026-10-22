"""Pydantic schemas for NID-X API."""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


# ── Health ────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    model_version: Optional[str] = None
    app_version: str
    env: str


# ── Model Info ────────────────────────────────────────────────────────────────

class ModelInfoResponse(BaseModel):
    model_name: Optional[str] = None
    model_version: Optional[str] = None
    training_timestamp: Optional[str] = None
    dataset_id: Optional[str] = None
    classification_mode: Optional[str] = None
    feature_count: Optional[int] = None
    feature_names: Optional[List[str]] = None
    target_mapping: Optional[Dict[str, int]] = None
    evaluation_split: Optional[str] = None
    available: bool = False


# ── Metrics ───────────────────────────────────────────────────────────────────

class PerClassMetrics(BaseModel):
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1_score: Optional[float] = None
    support: Optional[int] = None


class MetricsResponse(BaseModel):
    available: bool = False
    # When True the metrics came from the bundled demo model trained on sample data,
    # not from a user-uploaded dataset.
    is_sample_data: bool = False
    accuracy: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1_score: Optional[float] = None
    false_positive_rate: Optional[float] = None
    false_negative_rate: Optional[float] = None
    roc_auc: Optional[float] = None
    pr_auc: Optional[float] = None
    confusion_matrix: Optional[List[List[int]]] = None
    per_class: Optional[Dict[str, PerClassMetrics]] = None
    training_duration_s: Optional[float] = None
    inference_duration_ms: Optional[float] = None
    n_train: Optional[int] = None
    n_test: Optional[int] = None
    model_name: Optional[str] = None
    evaluated_at: Optional[str] = None
    model_comparison: Optional[List[Dict[str, Any]]] = None



# ── Prediction ────────────────────────────────────────────────────────────────

class PredictRequest(BaseModel):
    records: List[Dict[str, Any]] = Field(..., min_length=1, max_length=1000)


class PredictionResult(BaseModel):
    row_index: int
    predicted_label: str
    predicted_class: int
    probability: Optional[float] = None
    model_version: Optional[str] = None
    timestamp: str
    warning: Optional[str] = None


class PredictResponse(BaseModel):
    predictions: List[PredictionResult]
    attack_count: int
    benign_count: int
    total: int
    model_version: Optional[str] = None
    batch_id: str


# ── CSV Upload ────────────────────────────────────────────────────────────────

class CSVPredictResponse(BaseModel):
    batch_id: str
    total_records: int
    attack_count: int
    benign_count: int
    attack_rate: float
    predictions: List[Dict[str, Any]]
    warnings: List[str]
    model_version: Optional[str] = None
    overall_threat_level: Optional[str] = None
    inference_ms: Optional[float] = None
    evaluation: Optional[Dict[str, Any]] = None
    charts: Optional[List[Dict[str, Any]]] = None
    chart_data: Optional[Dict[str, Any]] = None
    analytical_report: Optional[Dict[str, Any]] = None
    report_id: Optional[str] = None


# ── Alerts ────────────────────────────────────────────────────────────────────

class AlertRecord(BaseModel):
    id: str
    timestamp: str
    predicted_class: str
    score: Optional[float] = None
    model_ver: Optional[str] = None
    source_type: Optional[str] = None
    batch_id: Optional[str] = None
    flow_meta: Optional[str] = None
    severity: str = "HIGH"
    acknowledged: int = 0
    resolved: int = 0


class AlertsResponse(BaseModel):
    alerts: List[AlertRecord]
    total: int
    page: int
    page_size: int
    summary: Optional[Dict[str, int]] = None


# ── History ───────────────────────────────────────────────────────────────────

class HistoryRecord(BaseModel):
    id: str
    timestamp: str
    source_type: str
    batch_id: Optional[str] = None
    model_ver: Optional[str] = None
    record_count: int = 0
    attack_count: int = 0
    benign_count: int = 0
    summary: Optional[str] = None


class HistoryResponse(BaseModel):
    history: List[HistoryRecord]
    total: int


# ── Reports ───────────────────────────────────────────────────────────────────

class ReportEntry(BaseModel):
    report_id: str
    name: str
    type: str
    size_bytes: int
    created_at: Optional[str] = None
    available: bool


class ReportsListResponse(BaseModel):
    reports: List[ReportEntry]


# ── Error ─────────────────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    detail: str
    code: Optional[str] = None


# ── Settings ──────────────────────────────────────────────────────────────────

class SettingsResponse(BaseModel):
    classification_mode: str
    prediction_threshold: float
    max_upload_mb: int
    max_upload_rows: int
    batch_size: int
    random_seed: int
    label_column: str
    dataset_filename: str
    model_available: bool


class SettingsUpdateRequest(BaseModel):
    classification_mode: Optional[str] = None
    prediction_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    max_upload_mb: Optional[int] = Field(None, ge=1, le=500)
    batch_size: Optional[int] = Field(None, ge=10, le=10000)
