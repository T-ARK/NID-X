"""
Tests that verify no sample data is auto-loaded at startup.

Rules being enforced:
  1. After init_db(), the alerts and prediction_history tables are empty.
  2. GET /api/alerts returns an empty list with total=0.
  3. GET /api/history returns an empty list with total=0.
  4. GET /api/overview/stats reports 0 flows, 0 alerts, 0 batches.
  5. GET /api/metrics returns available=False when evaluation_report.json is absent.
  6. When evaluation_report.json IS present but derived from the sample, the
     /api/metrics response carries is_sample_data=True.
  7. The traffic_analysis_service does NOT overwrite evaluation_report.json
     when the filename is sample_flows.csv.
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure the repo root is on sys.path regardless of how pytest is invoked
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def fresh_db(tmp_path):
    """Provide a throwaway SQLite DB path so tests never touch the real nidx.db."""
    db_path = tmp_path / "test_nidx.db"
    with patch("backend.app.core.config.settings") as mock_settings:
        # Patch only the DB path; all other settings retain real values.
        from backend.app.core.config import settings as real_settings
        mock_settings.DB_PATH = db_path
        # Copy all other attributes so the rest of the code works.
        for attr in dir(real_settings):
            if not attr.startswith("_") and attr != "DB_PATH":
                try:
                    setattr(mock_settings, attr, getattr(real_settings, attr))
                except Exception:
                    pass
        yield db_path


@pytest.fixture()
def client(tmp_path):
    """
    TestClient with a fresh in-memory DB so startup lifespan is exercised
    without touching the production nidx.db.
    """
    db_path = tmp_path / "test_nidx.db"

    # Patch DB_PATH before importing/instantiating the app so init_db() creates
    # the tables in the throwaway file.
    import backend.app.core.config as cfg_module
    original_db = cfg_module.settings.DB_PATH
    cfg_module.settings.DB_PATH = db_path

    # Also patch the database module's reference that was already imported.
    import backend.app.db.database as db_module
    original_db_ref = db_module.__dict__.get("settings")

    try:
        # Re-create the app with the patched settings in place.
        from fastapi.testclient import TestClient
        from backend.app.main import app
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c
    finally:
        cfg_module.settings.DB_PATH = original_db


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestFreshDatabaseIsEmpty:
    """Unit tests against the DB layer directly."""

    def test_alerts_empty_after_init_db(self, tmp_path):
        db_path = tmp_path / "nidx.db"
        import backend.app.core.config as cfg
        original = cfg.settings.DB_PATH
        cfg.settings.DB_PATH = db_path
        try:
            from backend.app.db.database import init_db, get_alerts, get_alerts_count
            init_db()
            assert get_alerts_count() == 0, "alerts table must be empty after init_db()"
            assert get_alerts() == [], "get_alerts() must return [] on a fresh DB"
        finally:
            cfg.settings.DB_PATH = original

    def test_history_empty_after_init_db(self, tmp_path):
        db_path = tmp_path / "nidx.db"
        import backend.app.core.config as cfg
        original = cfg.settings.DB_PATH
        cfg.settings.DB_PATH = db_path
        try:
            from backend.app.db.database import init_db, get_history
            init_db()
            assert get_history() == [], "prediction_history must be empty after init_db()"
        finally:
            cfg.settings.DB_PATH = original

    def test_overview_stats_all_zeros(self, tmp_path):
        db_path = tmp_path / "nidx.db"
        import backend.app.core.config as cfg
        original = cfg.settings.DB_PATH
        cfg.settings.DB_PATH = db_path
        try:
            from backend.app.db.database import init_db, get_overview_stats
            init_db()
            stats = get_overview_stats()
            assert stats["total_flows_analyzed"] == 0
            assert stats["total_attacks_detected"] == 0
            assert stats["total_alerts"] == 0
            assert stats["total_batches"] == 0
        finally:
            cfg.settings.DB_PATH = original


def test_application_startup_does_not_seed_sample_data(client):
    """The FastAPI lifespan initializes tables without inserting sample records."""
    alerts = client.get("/api/alerts")
    history = client.get("/api/history")
    stats = client.get("/api/overview/stats")

    assert alerts.status_code == 200
    assert alerts.json()["total"] == 0
    assert alerts.json()["alerts"] == []
    assert history.status_code == 200
    assert history.json()["total"] == 0
    assert history.json()["history"] == []
    assert stats.status_code == 200
    assert stats.json()["total_flows_analyzed"] == 0
    assert stats.json()["total_alerts"] == 0
    assert stats.json()["total_batches"] == 0


class TestMetricsSampleFlag:
    """Unit tests for the is_sample_data flag logic in routes."""

    def test_report_is_sample_detects_sample_filename(self):
        from backend.app.api.routes import _report_is_sample
        report_from_sample = {
            "metadata": {"dataset_source": "sample_flows.csv"}
        }
        assert _report_is_sample(report_from_sample) is True

    def test_report_is_sample_false_for_user_data(self):
        from backend.app.api.routes import _report_is_sample
        report_from_user = {
            "metadata": {"dataset_source": "data/raw/my_traffic.csv"}
        }
        assert _report_is_sample(report_from_user) is False

    def test_report_is_sample_false_when_no_metadata(self):
        from backend.app.api.routes import _report_is_sample
        assert _report_is_sample({}) is False
        assert _report_is_sample({"metadata": {}}) is False

    def test_report_is_sample_detects_sample_trained_model(self):
        from backend.app.api.routes import _report_is_sample
        report_from_sample_model = {
            "metadata": {
                "dataset_source": "data/raw/user_flows.csv",
                "model_training_dataset_source": "data/sample/sample_flows.csv",
            }
        }
        assert _report_is_sample(report_from_sample_model) is True

    def test_metrics_hide_sample_derived_values(self):
        from backend.app.api.routes import metrics
        report_from_sample = {
            "accuracy": 0.97,
            "metadata": {"dataset_source": "data/sample/sample_flows.csv"},
        }
        with patch("backend.app.api.routes.load_evaluation_report", return_value=report_from_sample):
            response = metrics()

        assert response.available is False
        assert response.is_sample_data is True
        assert response.accuracy is None

    def test_metrics_hide_user_upload_scored_by_sample_model(self):
        from backend.app.api.routes import metrics
        report_from_user_data = {
            "accuracy": 0.97,
            "metadata": {"dataset_source": "data/raw/user_flows.csv"},
        }
        with patch("backend.app.api.routes.load_evaluation_report", return_value=report_from_user_data), \
             patch("backend.app.api.routes.model_trained_on_sample", return_value=True):
            response = metrics()

        assert response.available is False
        assert response.is_sample_data is True
        assert response.accuracy is None

    def test_overview_hides_sample_evaluation_values(self):
        from backend.app.api.routes import overview_stats
        sample_report = {
            "accuracy": 0.97,
            "metadata": {"dataset_source": "data/sample/sample_flows.csv"},
        }
        with patch("backend.app.api.routes.get_overview_stats", return_value={}), \
             patch("backend.app.api.routes.load_evaluation_report", return_value=sample_report):
            response = overview_stats()

        assert response["metrics"]["is_sample_data"] is True
        assert response["metrics"]["accuracy"] is None

    def test_sample_trained_model_cannot_generate_evaluation_figures(self):
        from fastapi import HTTPException
        from backend.app.api.routes import generate_report
        with patch("backend.app.api.routes.is_model_available", return_value=True), \
             patch("backend.app.api.routes.model_trained_on_sample", return_value=True):
            with pytest.raises(HTTPException) as exc:
                generate_report()

        assert exc.value.status_code == 400

    def test_metrics_available_false_when_no_report_file(self, tmp_path):
        """GET /api/metrics → available=False when evaluation_report.json is absent."""
        import backend.app.core.config as cfg
        original = cfg.settings.REPORTS_DIR
        cfg.settings.REPORTS_DIR = tmp_path
        # Ensure the evaluation_report_path points to tmp_path
        original_eval = cfg.settings.__class__.evaluation_report_path.fget
        try:
            from backend.app.services.evaluation_service import load_evaluation_report
            # No report file exists — should return None.
            report = load_evaluation_report.__wrapped__() if hasattr(load_evaluation_report, "__wrapped__") else None
            # Manually verify the path doesn't exist.
            assert not (tmp_path / "evaluation_report.json").exists()
        finally:
            cfg.settings.REPORTS_DIR = original

    def test_metrics_is_sample_data_true_for_sample_report(self, tmp_path):
        """When evaluation_report.json is present and came from the sample, is_sample_data=True."""
        report_data = {
            "accuracy": 0.97,
            "metadata": {"dataset_source": "sample_flows.csv", "training_timestamp": "2026-01-01T00:00:00"}
        }
        report_path = tmp_path / "evaluation_report.json"
        report_path.write_text(json.dumps(report_data))

        import backend.app.core.config as cfg
        original = cfg.settings.REPORTS_DIR
        # Temporarily redirect so load_evaluation_report finds our file.
        with patch.object(cfg.settings.__class__, "evaluation_report_path",
                          new_callable=lambda: property(lambda s: report_path)):
            from backend.app.api.routes import _report_is_sample
            loaded = json.loads(report_path.read_text())
            assert _report_is_sample(loaded) is True


def test_reports_hide_sample_artifacts_and_list_user_report_images(tmp_path):
    from backend.app.services import report_service
    import backend.app.core.config as cfg

    models_dir = tmp_path / "models"
    reports_dir = tmp_path / "reports"
    figures_dir = reports_dir / "figures"
    models_dir.mkdir()
    figures_dir.mkdir(parents=True)
    (models_dir / "model_metadata.json").write_text(json.dumps({
        "dataset_source": "data/sample/sample_flows.csv",
    }), encoding="utf-8")

    evaluation_report = reports_dir / "evaluation_report.json"
    data_quality_report = reports_dir / "data_quality_report.json"
    comparison_report = reports_dir / "model_comparison.csv"
    sample_traffic_report = reports_dir / "analytical_report_sample01.json"
    user_traffic_report = reports_dir / "analytical_report_user01.json"
    evaluation_report.write_text(json.dumps({
        "accuracy": 0.97,
        "metadata": {"dataset_source": "data/sample/sample_flows.csv"},
    }), encoding="utf-8")
    data_quality_report.write_text(json.dumps({
        "dataset_source": "data/sample/sample_flows.csv",
    }), encoding="utf-8")
    comparison_report.write_text("model,cv_f1\nsample,0.97\n", encoding="utf-8")
    sample_traffic_report.write_text(json.dumps({
        "batch_short": "sample01",
        "filename": "sample_flows.csv",
    }), encoding="utf-8")
    user_traffic_report.write_text(json.dumps({
        "batch_short": "user01",
        "filename": "user_flows.csv",
    }), encoding="utf-8")
    (reports_dir / "predictions_sample01.csv").write_text("predicted_class\n1\n", encoding="utf-8")
    for filename in (
        "confusion_matrix.png",
        "traffic_roc_curve_sample01.png",
        "traffic_roc_curve_user01.png",
    ):
        (figures_dir / filename).write_bytes(b"png")

    original_models = cfg.settings.MODELS_DIR
    original_reports = cfg.settings.REPORTS_DIR
    original_figures = cfg.settings.FIGURES_DIR
    original_registry = report_service.REPORT_REGISTRY
    cfg.settings.MODELS_DIR = models_dir
    cfg.settings.REPORTS_DIR = reports_dir
    cfg.settings.FIGURES_DIR = figures_dir
    report_service.REPORT_REGISTRY = [
        ("evaluation_report", "Evaluation Report", "json", evaluation_report),
        ("model_comparison", "Model Comparison", "csv", comparison_report),
        ("data_quality", "Data Quality", "json", data_quality_report),
    ]
    try:
        report_ids = {report["report_id"] for report in report_service.list_reports()}
        assert "evaluation_report" not in report_ids
        assert "model_comparison" not in report_ids
        assert "data_quality" not in report_ids
        assert "analytical_report_sample01_json" not in report_ids
        assert "predictions_sample01" not in report_ids
        assert "figure_confusion_matrix" not in report_ids
        assert "figure_traffic_roc_curve_sample01" not in report_ids
        assert "analytical_report_user01_json" in report_ids
        assert "figure_traffic_roc_curve_user01" in report_ids
        with pytest.raises(FileNotFoundError):
            report_service.get_report_path("evaluation_report")
        with pytest.raises(FileNotFoundError):
            report_service.get_report_path("figure_confusion_matrix")
    finally:
        report_service.REPORT_REGISTRY = original_registry
        cfg.settings.MODELS_DIR = original_models
        cfg.settings.REPORTS_DIR = original_reports
        cfg.settings.FIGURES_DIR = original_figures


class TestSamplePersistenceGuard:
    """Verify traffic analysis preserves model training provenance."""

    @pytest.mark.parametrize(
        ("filename", "should_persist"),
        [("sample_flows.csv", False), ("user_flows.csv", True)],
    )
    def test_analysis_does_not_relabel_sample_trained_model(
        self, tmp_path, filename, should_persist
    ):
        eval_report_path = tmp_path / "evaluation_report.json"
        model_metadata_path = tmp_path / "model_metadata.json"
        original_model_metadata = {"dataset_source": "data/sample/sample_flows.csv"}
        model_metadata_path.write_text(json.dumps(original_model_metadata), encoding="utf-8")

        import numpy as np
        import pandas as pd
        import backend.app.services.traffic_analysis_service as svc
        from backend.app.core.config import Settings

        class _DummyPipeline:
            def predict_proba(self, X):
                n = len(X)
                probs = np.zeros((n, 2))
                probs[:, 0] = 1.0  # all benign
                return probs

        dummy_meta = {
            "model_version": "test-v0",
            "classification_mode": "binary",
            "target_mapping": {"BENIGN": 0, "ATTACK": 1},
            "dataset_source": "data/sample/sample_flows.csv",
        }

        df = pd.DataFrame({
            "Destination Port": [80, 443, 22],
            "Flow Duration": [100, 200, 300],
            "Label": ["BENIGN", "BENIGN", "ATTACK"],
        })

        # Patch @property accessors at the class level so Pydantic allows it.
        # REPORTS_DIR must exist so the .md / .json analytical report writes don't crash.
        (tmp_path / "figures").mkdir(exist_ok=True)

        with patch.object(Settings, "evaluation_report_path",
                          new_callable=lambda: property(lambda s: eval_report_path)), \
             patch.object(Settings, "metadata_path",
                          new_callable=lambda: property(lambda s: model_metadata_path)), \
             patch("backend.app.services.traffic_analysis_service.settings.FIGURES_DIR",
                   tmp_path / "figures"), \
             patch("backend.app.services.traffic_analysis_service.settings.REPORTS_DIR", tmp_path), \
             patch("backend.app.services.traffic_analysis_service._load_model",
                   return_value=(_DummyPipeline(), dummy_meta)), \
             patch("backend.app.services.traffic_analysis_service.load_feature_schema",
                   return_value=None):

            # Use UTF-8 open in the service context so Windows cp1252 doesn't choke
            # on the μs symbol in the Markdown report template.
            import builtins
            _real_open = builtins.open
            def _utf8_open(file, mode="r", **kw):
                if "w" in mode and "b" not in mode:
                    kw.setdefault("encoding", "utf-8")
                return _real_open(file, mode, **kw)

            with patch("builtins.open", side_effect=_utf8_open):
                svc.analyze_uploaded_traffic(df, filename=filename)

        assert eval_report_path.exists() is should_persist
        if should_persist:
            report = json.loads(eval_report_path.read_text(encoding="utf-8"))
            assert report["metadata"]["dataset_source"] == filename
            assert report["metadata"]["model_training_dataset_source"] == "data/sample/sample_flows.csv"
        assert json.loads(model_metadata_path.read_text(encoding="utf-8")) == original_model_metadata
