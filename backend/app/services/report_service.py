"""Report listing and generation service."""
from __future__ import annotations

import csv
import io
import json
import logging
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


def list_reports() -> List[dict]:
    reports = []
    for report_id, name, rtype, path in REPORT_REGISTRY:
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
        reports.append({
            "report_id": report_file.stem if suffix == "md" else report_file.name.replace(".", "_"),
            "name": f"Traffic Analysis Report ({suffix.upper()}): {report_file.stem.replace('analytical_report_', '')}",
            "type": suffix,
            "size_bytes": report_file.stat().st_size,
            "created_at": datetime.fromtimestamp(report_file.stat().st_mtime, tz=timezone.utc).isoformat(),
            "available": True,
        })

    for pred_file in sorted(settings.REPORTS_DIR.glob("predictions_*.csv"), reverse=True):
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
    # Static registry
    for rid, _, _, path in REPORT_REGISTRY:
        if rid == report_id:
            if not path.exists():
                raise FileNotFoundError(f"Report '{report_id}' has not been generated yet.")
            return path

    # Dynamic analytical reports & predictions
    if report_id.startswith("analytical_report_") or report_id.startswith("predictions_"):
        # Check direct matches with .md, .json, .csv
        for ext in [".md", ".json", ".csv"]:
            p = settings.REPORTS_DIR / f"{report_id}{ext}"
            if p.exists() and p.parent.resolve() == settings.REPORTS_DIR.resolve():
                return p
        # Check underscore replacement (e.g. analytical_report_12345678_json)
        for ext in ["json", "md", "csv"]:
            if report_id.endswith(f"_{ext}"):
                base = report_id[:-len(f"_{ext}")]
                p = settings.REPORTS_DIR / f"{base}.{ext}"
                if p.exists() and p.parent.resolve() == settings.REPORTS_DIR.resolve():
                    return p

    # Figures
    if report_id.startswith("figure_"):
        stem = report_id[len("figure_"):]
        path = settings.FIGURES_DIR / f"{stem}.png"
        if path.exists() and path.parent.resolve() == settings.FIGURES_DIR.resolve():
            return path
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
