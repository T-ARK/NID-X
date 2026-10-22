"""Central configuration for NID-X backend."""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


BASE_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    # ── App ──────────────────────────────────────────────────────────────────
    APP_NAME: str = "NID-X"
    APP_VERSION: str = "0.1.0"
    ENV: str = "development"

    # ── Paths ────────────────────────────────────────────────────────────────
    DATA_DIR: Path = BASE_DIR / "data"
    RAW_DIR: Path = BASE_DIR / "data" / "raw"
    PROCESSED_DIR: Path = BASE_DIR / "data" / "processed"
    SAMPLE_DIR: Path = BASE_DIR / "data" / "sample"
    MODELS_DIR: Path = BASE_DIR / "models"
    REPORTS_DIR: Path = BASE_DIR / "reports"
    FIGURES_DIR: Path = BASE_DIR / "reports" / "figures"

    # ── Dataset ──────────────────────────────────────────────────────────────
    DATASET_FILENAME: str = "network_flows.csv"
    LABEL_COLUMN: str = "Label"
    CLASSIFICATION_MODE: str = "binary"          # "binary" | "multiclass"
    BENIGN_LABEL: str = "BENIGN"
    MAX_TRAINING_ROWS: int = 500_000
    CHUNK_SIZE: int = 50_000

    # ── Training ─────────────────────────────────────────────────────────────
    RANDOM_SEED: int = 42
    TEST_SPLIT: float = 0.20
    VAL_SPLIT: float = 0.10
    N_ESTIMATORS: int = 100
    MAX_DEPTH: int = 20
    N_JOBS: int = -1
    CV_FOLDS: int = 3
    HYPERPARAM_BUDGET: int = 10

    # ── Inference ────────────────────────────────────────────────────────────
    PREDICTION_THRESHOLD: float = 0.50
    MAX_UPLOAD_MB: int = 50
    MAX_UPLOAD_ROWS: int = 100_000
    BATCH_SIZE: int = 1_000

    # ── CORS ─────────────────────────────────────────────────────────────────
    FRONTEND_ORIGIN: str = "http://localhost:5173"

    # ── Database ─────────────────────────────────────────────────────────────
    DB_PATH: Path = BASE_DIR / "backend" / "nidx.db"

    # ── Model artifact paths ─────────────────────────────────────────────────
    @property
    def model_path(self) -> Path:
        return self.MODELS_DIR / "intrusion_model.joblib"

    @property
    def metadata_path(self) -> Path:
        return self.MODELS_DIR / "model_metadata.json"

    @property
    def feature_schema_path(self) -> Path:
        return self.MODELS_DIR / "feature_schema.json"

    @property
    def evaluation_report_path(self) -> Path:
        return self.REPORTS_DIR / "evaluation_report.json"

    @property
    def comparison_path(self) -> Path:
        return self.REPORTS_DIR / "model_comparison.csv"

    @property
    def data_quality_path(self) -> Path:
        return self.REPORTS_DIR / "data_quality_report.json"

    @property
    def dataset_path(self) -> Path:
        return self.RAW_DIR / self.DATASET_FILENAME

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

# Ensure critical directories exist on import
for _d in [
    settings.MODELS_DIR, settings.REPORTS_DIR, settings.FIGURES_DIR,
    settings.PROCESSED_DIR, settings.SAMPLE_DIR, settings.RAW_DIR,
]:
    _d.mkdir(parents=True, exist_ok=True)
