"""Report listing and generation service."""
from __future__ import annotations

import csv
import io
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from backend.app.core.config import settings

logger = logging.getLogger(__name__)

REPORT_REGISTRY = [
    ("evaluation_report", "Evaluation Report (JSON)", "json", settings.evaluation_report_path),
    ("model_comparison", "Model Comparison (CSV)", "csv", settings.comparison_path),
    ("data_quality", "Data Quality Report (JSON)", "json", settings.data_quality_path),
]

EVALUATION_FIGURES = {
    "class_distribution",
    "error_analysis",
    "confusion_matrix",
    "roc_curve",
    "pr_curve",
    "feature_importance",
    "model_comparison",
    "numeric_distributions",
    "correlation_heatmap",
}


def is_sample_dataset(source: object) -> bool:
    normalized = str(source or "").replace("\\", "/").rstrip("/").lower()
    return normalized == "sample_flows.csv" or normalized.endswith("/sample_flows.csv")


def model_trained_on_sample() -> bool:
    """Treat sample-trained or legacy-ingestion metadata as untrusted provenance."""
    if not settings.metadata_path.exists():
        return False
    with open(settings.metadata_path, encoding="utf-8") as metadata_file:
        metadata = json.load(metadata_file)
    if metadata.get("last_ingested_at"):
        return True
    source = metadata.get("training_dataset_source") or metadata.get("dataset_source")
    return is_sample_dataset(source)


def _report_source(path: Path) -> str | None:
    if path.suffix.lower() == ".json":
        with open(path, encoding="utf-8") as report_file:
            report = json.load(report_file)
        metadata = report.get("metadata") or {}
        return (
            metadata.get("dataset_source")
            or report.get("dataset_source")
            or report.get("filename")
            or ""
        )
    if path.suffix.lower() == ".md":
        content = path.read_text(encoding="utf-8")
        match = re.search(r"^\*\*Analyzed File:\*\*\s*`?([^`\r\n]+)", content, re.MULTILINE)
        return match.group(1).strip() if match else None
    return None


def _sample_analytical_report(path: Path) -> bool:
    return path.exists() and is_sample_dataset(_report_source(path))


def _sample_evaluation_report(path: Path) -> bool:
    if not path.exists():
        return False
    with open(path, encoding="utf-8") as report_file:
        report = json.load(report_file)
    metadata = report.get("metadata") or {}
    return any(
        is_sample_dataset(source)
        for source in (
            metadata.get("dataset_source"),
            metadata.get("model_training_dataset_source"),
            metadata.get("training_dataset_source"),
        )
    )


def _sample_report_batches() -> set[str]:
    batches = set()
    for report_file in settings.REPORTS_DIR.glob("analytical_report_*.json"):
        if _sample_analytical_report(report_file):
            report = json.loads(report_file.read_text(encoding="utf-8"))
            batch = report.get("batch_short") or str(report.get("batch_id", ""))[:8]
            if batch:
                batches.add(batch)
    return batches


def _hidden_sample_report(report_id: str, path: Path) -> bool:
    if path.exists() and path.stat().st_size == 0:
        return True

    if report_id == "evaluation_report":
        return model_trained_on_sample() or _sample_evaluation_report(path)
    if report_id == "data_quality":
        return is_sample_dataset(_report_source(path))
    if report_id == "model_comparison":
        return model_trained_on_sample() or _sample_evaluation_report(settings.evaluation_report_path)
    if report_id.startswith("analytical_report_"):
        return is_sample_dataset(_report_source(path))
    if report_id.startswith("predictions_"):
        return report_id.removeprefix("predictions_") in _sample_report_batches()
    if report_id.startswith("figure_"):
        stem = report_id.removeprefix("figure_")
        if stem in EVALUATION_FIGURES:
            return model_trained_on_sample() or _sample_evaluation_report(settings.evaluation_report_path)
        if stem.startswith("traffic_"):
            batch = stem.rsplit("_", 1)[-1]
            report_path = settings.REPORTS_DIR / f"analytical_report_{batch}.json"
            return not report_path.exists() or _sample_analytical_report(report_path)
        return any(stem.endswith(f"_{batch}") for batch in _sample_report_batches())
    return False


def list_reports() -> List[dict]:
    reports = []
    for report_id, name, rtype, path in REPORT_REGISTRY:
        if _hidden_sample_report(report_id, path):
            continue
        if path.exists():
            stat = path.stat()
            reports.append({
                "report_id": report_id,
                "name": name,
                "type": rtype,
                "size_bytes": stat.st_size,
                "created_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                "available": True,
            })
        else:
            reports.append({
                "report_id": report_id,
                "name": name,
                "type": rtype,
                "size_bytes": 0,
                "created_at": None,
                "available": False,
            })
    # Dynamically discover all analytical reports and prediction CSVs
    for report_file in sorted(settings.REPORTS_DIR.glob("analytical_report_*.*"), reverse=True):
        suffix = report_file.suffix.lstrip(".")
        report_id = report_file.stem if suffix == "md" else report_file.name.replace(".", "_")
        if _hidden_sample_report(f"analytical_report_{report_file.stem.removeprefix('analytical_report_')}", report_file):
            continue
        reports.append({
            "report_id": report_id,
            "name": f"Traffic Analysis Report ({suffix.upper()}): {report_file.stem.replace('analytical_report_', '')}",
            "type": suffix,
            "size_bytes": report_file.stat().st_size,
            "created_at": datetime.fromtimestamp(report_file.stat().st_mtime, tz=timezone.utc).isoformat(),
            "available": True,
        })

    for pred_file in sorted(settings.REPORTS_DIR.glob("predictions_*.csv"), reverse=True):
        if _hidden_sample_report(pred_file.stem, pred_file):
            continue
        reports.append({
            "report_id": pred_file.stem,
            "name": f"Predictions Export (CSV): {pred_file.stem.replace('predictions_', '')}",
            "type": "csv",
            "size_bytes": pred_file.stat().st_size,
            "created_at": datetime.fromtimestamp(pred_file.stat().st_mtime, tz=timezone.utc).isoformat(),
            "available": True,
        })

    # Also list figure files
    for fig in sorted(settings.FIGURES_DIR.glob("*.png"), reverse=True):
        if _hidden_sample_report(f"figure_{fig.stem}", fig):
            continue
        reports.append({
            "report_id": f"figure_{fig.stem}",
            "name": f"Figure: {fig.stem.replace('_', ' ').title()}",
            "type": "png",
            "size_bytes": fig.stat().st_size,
            "created_at": datetime.fromtimestamp(fig.stat().st_mtime, tz=timezone.utc).isoformat(),
            "available": True,
        })
    return reports


def get_report_path(report_id: str) -> Path:
    """Resolve a report_id to a safe filesystem path."""
    def visible(path: Path) -> Path:
        if _hidden_sample_report(report_id, path):
            raise FileNotFoundError(f"Report '{report_id}' is unavailable because it contains sample-data results.")
        return path

    # Static registry
    for rid, _, _, path in REPORT_REGISTRY:
        if rid == report_id:
            if not path.exists():
                raise FileNotFoundError(f"Report '{report_id}' has not been generated yet.")
            return visible(path)

    # Dynamic analytical reports & predictions
    if report_id.startswith("analytical_report_") or report_id.startswith("predictions_"):
        # Check direct matches with .md, .json, .csv
        for ext in [".md", ".json", ".csv"]:
            p = settings.REPORTS_DIR / f"{report_id}{ext}"
            if p.exists() and p.parent.resolve() == settings.REPORTS_DIR.resolve():
                return visible(p)
        # Check underscore replacement (e.g. analytical_report_12345678_json)
        for ext in ["json", "md", "csv"]:
            if report_id.endswith(f"_{ext}"):
                base = report_id[:-len(f"_{ext}")]
                p = settings.REPORTS_DIR / f"{base}.{ext}"
                if p.exists() and p.parent.resolve() == settings.REPORTS_DIR.resolve():
                    return visible(p)

    # Figures
    if report_id.startswith("figure_"):
        stem = report_id[len("figure_"):]
        path = settings.FIGURES_DIR / f"{stem}.png"
        if path.exists() and path.parent.resolve() == settings.FIGURES_DIR.resolve():
            return visible(path)
    raise ValueError(f"Unknown report: {report_id}")


def generate_summary_report(predictions: List[dict], batch_id: str) -> Path:
    """Generate a CSV prediction export and save it."""
    path = settings.REPORTS_DIR / f"predictions_{batch_id[:8]}.csv"
    if not predictions:
        return path
    keys = predictions[0].keys()
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(predictions)
    return path
