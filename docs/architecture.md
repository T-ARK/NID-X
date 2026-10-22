# NID-X: System Architecture Documentation

## 1. Overview
**NID-X (ML Network Intrusion Detector)** is an industrial-grade, defensive cybersecurity analytics platform that classifies network flows and flags suspicious activity using supervised machine learning algorithms.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        NID-X OPERATIONAL CONSOLE                       │
│             React 18 + TypeScript + Vite (Port 5173)                   │
│   • Industrial Dark Brutalist Theme (#050505, #101010, #FF3038)        │
│   • Overview Hero & Topology Visualizer                                │
│   • CSV Traffic Analysis & Live Batch Classifier                       │
│   • Model Performance & Figure Viewer (ROC/PR/Confusion Matrix)        │
│   • Alerts Management & SQLite Audit Log                               │
│   • Reports & Artifact Download Engine                                 │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTP / REST (/api/*)
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        FASTAPI BACKEND ENGINE                          │
│               Uvicorn ASGI Server (Port 8000)                          │
│   • Pydantic V2 Request & Response Validation                          │
│   • Streaming CSV Ingestion & Size Enforcers                           │
│   • Model Telemetry & Status API                                       │
│   • Background Training Workers & Report Generators                    │
└───────┬───────────────────────────┬────────────────────────────┬───────┘
        │                           │                            │
        ▼                           ▼                            ▼
┌──────────────────┐    ┌───────────────────────────┐    ┌─────────────────┐
│   ML PIPELINE    │    │       PERSISTENCE         │    │   SQLITE DB     │
│ • ColumnCleaner  │    │ • models/intrusion_model  │    │ • alerts        │
│ • MedianImputer  │    │   .joblib                 │    │ • prediction_   │
│ • StandardScaler │    │ • models/feature_schema   │    │   history       │
│ • OrdinalEncoder │    │ • reports/evaluation_     │    │   (WAL Mode)    │
│ • Candidate Clfs │    │   report.json             │    └─────────────────┘
│   - LogReg       │    │ • reports/model_          │
│   - DecisionTree │    │   comparison.csv          │
│   - RandomForest │    │ • reports/figures/*.png   │
│   - HistGBDT     │    └───────────────────────────┘
└──────────────────┘
```

---

## 2. Machine Learning Architecture

### 2.1 Candidate Models
The training engine trains four supervised classification models:
1. **Logistic Regression**: Linear baseline with balanced class weights.
2. **Decision Tree Classifier**: Single tree model with bounded maximum depth (`MAX_DEPTH=20`).
3. **Random Forest Classifier**: Ensemble of 100 decision trees with balanced subsampling.
4. **Histogram-based Gradient Boosting Classifier**: Fast gradient-boosted decision trees capable of handling large tabular flow datasets.

### 2.2 Model Selection Criterion
Candidates are evaluated using **3-Fold Stratified Cross-Validation** on the training split. The final production candidate is selected using **weighted F1-Score** (`SELECTION_CRITERION = "f1"`), preventing accuracy paradoxes on imbalanced intrusion datasets.

### 2.3 Preprocessing & Leakage Prevention
- **Train/Test Isolation**: Preprocessors (scalers, imputers, encoders) are fit strictly on training data (`X_train`) and transformed onto validation and held-out test splits.
- **Leakage Col Exclusions**: Flow IDs, raw IP addresses, TCP/UDP ports, timestamps, and target-derived columns are stripped prior to model ingestion.
- **Input Alignment**: New inference records are re-indexed against `feature_schema.json`. Missing features are filled with `NaN` and imputed with training median values.

---

## 3. Dark Brutalist Design System
The frontend follows an industrial control console aesthetic:
- **Primary Background**: `#050505` (Pitch Black)
- **Secondary Background**: `#0A0A0A`
- **Panel Background**: `#101010` (Charcoal)
- **Primary Text**: `#F5F5F5` (High Contrast White)
- **Muted Technical Text**: `#686868`
- **Signal Red**: `#FF3038` (Used exclusively for attack indicators, active navigation, and alerts)
- **Typography**: Space Grotesk / IBM Plex Mono / Inter
- **Form Factor**: Zero rounded corners (`border-radius: 0`), sharp registration marks, monospace metadata tags.

---

## 4. API Endpoints
| Route | Method | Description |
|---|---|---|
| `/api/health` | GET | Real-time backend status, model loading state, version |
| `/api/model/info` | GET | Active model metadata, schema, and split configuration |
| `/api/metrics` | GET | Held-out test evaluation metrics and candidate comparison |
| `/api/predict` | POST | JSON single/batch flow classification |
| `/api/predict/csv` | POST | Multipart CSV upload and batch prediction |
| `/api/alerts` | GET | Paginated SQLite alert log with severity levels |
| `/api/alerts/{id}/acknowledge` | POST | Acknowledge alert event |
| `/api/alerts/{id}/resolve` | POST | Resolve alert event |
| `/api/history` | GET | Audit log of past batch predictions |
| `/api/reports` | GET | Registry of generated reports and figure PNGs |
| `/api/reports/{id}/download` | GET | Download JSON report, CSV export, or PNG figure |
| `/api/reports/generate` | POST | Regenerate all 9 evaluation and EDA figures |
| `/api/settings` | GET/PATCH | Dynamic configuration of thresholds, upload limits |
| `/api/train` | POST | Asynchronous background model retraining |
| `/api/train/status` | GET | Current background training state |
