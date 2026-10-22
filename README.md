# NID-X: ML Network Intrusion Detector

> **NETWORKS UNDER WATCH.**  
> Precision machine learning. Measurable evidence. Monochromatic industrial cybersecurity operations console.

```
███╗   ██╗██╗██████╗       ██╗  ██╗
████╗  ██║██║██╔══██╗      ╚██╗██╔╝
██╔██╗ ██║██║██║  ██║█████╗ ╚███╔╝ 
██║╚██╗██║██║██║  ██║╚════╝ ██╔██╗ 
██║ ╚████║██║██████╔╝      ██╔╝ ██╗
╚═╝  ╚═══╝╚═╝╚═════╝       ╚═╝  ╚═╝
```

---

## 1. Project Overview & Objectives
**NID-X** is a modular, production-grade machine learning network intrusion detection system with a high-contrast dark brutalist web console. It empowers cybersecurity researchers, security analysts, and engineers to train supervised classifiers on real network-flow traffic datasets (CIC-IDS2017, UNSW-NB15), benchmark candidates, audit predictions, inspect data quality, and triage anomaly alerts.

### Primary Objectives:
- **Supervised ML Classification**: Train and evaluate Logistic Regression, Decision Tree, Random Forest, and HistGradientBoosting classifiers.
- **Model Comparison & Selection**: Compare candidates using 3-fold stratified cross-validation and held-out test splits, selecting the champion model via F1-Score to protect against imbalanced traffic bias.
- **Explainable Evidence**: Compute feature importance, confusion matrices, ROC curves, PR curves, and error analysis.
- **Batch CSV Ingestion**: Upload, validate, and analyze external network-flow captures.
- **Alert Persistence**: Track machine-flagged anomalies in an ACID-compliant SQLite audit store.
- **Zero Fabrication**: All dashboard metrics, curves, and confusion cells originate from actual evaluated datasets and model weights.

---

## 2. Architecture & Technology Stack

| Layer | Technologies | Role |
|---|---|---|
| **Frontend** | React 18, TypeScript, Vite, React Router 6 | Dark brutalist industrial console (`#050505`, `#FF3038`), responsive layouts, SVG network visualizer. |
| **Backend API** | FastAPI, Uvicorn, Pydantic V2 | REST API, streaming CSV validation, asynchronous background training tasks. |
| **Machine Learning**| Scikit-learn, Pandas, NumPy, Joblib | Preprocessing pipelines, standard scaling, median imputation, model persistence. |
| **Visualizations** | Matplotlib, Seaborn | 9 real generated evaluation and exploratory data analysis charts. |
| **Persistence** | SQLite (WAL mode), JSON, CSV | Local audit database for alerts and prediction history; auditable report artifacts. |
| **Testing** | Pytest, Vitest, Testing Library | Backend and ML tests; frontend unit and router tests. |

---

## 3. Supported Datasets & Schema Requirements

### 3.1 Supported Public Datasets
1. **CIC-IDS2017 (Canadian Institute for Cybersecurity)**
   - **Source**: [https://www.unb.ca/cic/datasets/ids-2017.html](https://www.unb.ca/cic/datasets/ids-2017.html)
   - **Kaggle**: [https://www.kaggle.com/datasets/cicdataset/cicids2017](https://www.kaggle.com/datasets/cicdataset/cicids2017)
   - **Target Column**: `Label` (Values: `BENIGN`, `DDoS`, `PortScan`, `Bot`, etc.)
   - **Expected Schema**: Flow Duration, Total Fwd/Bwd Packets, Packet Length Mean/Std, Flow Bytes/s, Flag counts (`SYN`, `ACK`, `PSH`, `URG`).
2. **UNSW-NB15 (Australian Centre for Cyber Security)**
   - **Source**: [https://research.unsw.edu.au/projects/unsw-nb15-dataset](https://research.unsw.edu.au/projects/unsw-nb15-dataset)
   - **Target Column**: `label` (0 = Normal, 1 = Attack) or `attack_cat` (Multiclass).

### 3.2 Automated Preprocessing & Leakage Prevention
- **Target Leakage Protection**: Source IP, Destination IP, Source Port, Destination Port, Flow ID, and timestamps are stripped automatically to prevent memorization of host identities.
- **Data Hygiene**: Constant features are eliminated; infinite numbers are coerced to `NaN` and imputed with median training values.
- **Fit Boundaries**: Scalers and encoders fit strictly on the training partition.

---

## 4. Installation & Setup

### Prerequisites
- Python 3.10+ (tested on Python 3.11 – 3.14)
- Node.js 18+ and npm 9+

### Windows (PowerShell)
Run these commands from the project root:
```powershell
py -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
```

Install the frontend dependencies:
```powershell
cd frontend
npm install
cd ..
```

The backend uses its built-in defaults; creating a `.env` file is optional.

### Linux / macOS
Run these commands from the project root:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
cd frontend && npm install && cd ..
```

---

## 5. Dataset Placement & Model Training

### ⚡ Quick Start — Demo Dataset (Fastest Path, ~8 seconds)

Use the bundled synthetic demo dataset with the `--fast` flag. This uses a single-fold
evaluation pass instead of 3-fold cross-validation, cutting training time by ~4×.

**Windows (PowerShell):**
```powershell
# Train all 4 candidates and save the best model (~8 s)
.\backend\venv\Scripts\python.exe scripts/train_model.py `
    --dataset data/sample/sample_flows.csv --fast

# Generate all 9 evaluation and EDA figures
.\backend\venv\Scripts\python.exe scripts/evaluate_model.py `
    --dataset data/sample/sample_flows.csv
```

**Linux / macOS:**
```bash
python scripts/train_model.py --dataset data/sample/sample_flows.csv --fast
python scripts/evaluate_model.py --dataset data/sample/sample_flows.csv
```

> **`--fast` flag explained:** reduces CV folds from 3 → 1 (ShuffleSplit), caps
> LogisticRegression `max_iter` at 200, and pins `n_jobs=1` for RandomForest to
> avoid joblib process-spawn overhead on small datasets. Model selection logic and
> artifact output are identical to the standard run.

---

### Option A: Full Standard Training — Demo Dataset

Run the full 3-fold cross-validation pipeline (standard, ~30 s on the 300-row demo):

**Windows (PowerShell):**
```powershell
# Inspect dataset schema and label distribution
.\backend\venv\Scripts\python.exe scripts/inspect_dataset.py data/sample/sample_flows.csv

# Train all 4 candidate models with 3-fold CV
.\backend\venv\Scripts\python.exe scripts/train_model.py `
    --dataset data/sample/sample_flows.csv

# Generate evaluation metrics and all 9 EDA charts
.\backend\venv\Scripts\python.exe scripts/evaluate_model.py `
    --dataset data/sample/sample_flows.csv
```

**Linux / macOS:**
```bash
python scripts/inspect_dataset.py data/sample/sample_flows.csv
python scripts/train_model.py --dataset data/sample/sample_flows.csv
python scripts/evaluate_model.py --dataset data/sample/sample_flows.csv
```

---

### Option B: Full Public Dataset (CIC-IDS2017 / UNSW-NB15)

**Windows (PowerShell):**
```powershell
# 1. Place your downloaded CSV in data/raw/
Copy-Item "C:\path\to\Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv" `
    data\raw\network_flows.csv

# 2. Verify schema and label distribution
.\backend\venv\Scripts\python.exe scripts/inspect_dataset.py data\raw\network_flows.csv

# 3. Train models on up to 100,000 flows
.\backend\venv\Scripts\python.exe scripts/train_model.py `
    --dataset data\raw\network_flows.csv --rows 100000

# 4. Evaluate and generate figures
.\backend\venv\Scripts\python.exe scripts/evaluate_model.py `
    --dataset data\raw\network_flows.csv
```

**Linux / macOS:**
```bash
cp /path/to/Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv data/raw/network_flows.csv
python scripts/inspect_dataset.py data/raw/network_flows.csv
python scripts/train_model.py --dataset data/raw/network_flows.csv --rows 100000
python scripts/evaluate_model.py --dataset data/raw/network_flows.csv
```

---

## 6. Launching the Application

### Windows (PowerShell) — Two Terminals

**Terminal 1 — Backend:**
```powershell
.\backend\venv\Scripts\python.exe -m uvicorn backend.app.main:app `
    --host 127.0.0.1 --port 8000 --reload
```

**Terminal 2 — Frontend:**
```powershell
cd frontend
npm run dev -- --host 127.0.0.1
```

Open the dashboard at **`http://127.0.0.1:5173`**. The backend API is at **`http://127.0.0.1:8000`**.

### Linux / macOS — One-Command Orchestration
```bash
./run.sh all
```
*Starts FastAPI backend on `http://127.0.0.1:8000` and Vite frontend on `http://localhost:5173` in parallel.*

### Linux / macOS — Running Services Individually
```bash
# Terminal 1 - Backend
source venv/bin/activate
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 - Frontend
cd frontend
npm run dev
```

Visit the dashboard at: **`http://localhost:5173`**

---

## 7. Interactive Dashboard Walkthrough

### 1. Main Overview (`/`)
- Asymmetric editorial hero with the headline: **`NETWORKS UNDER WATCH.`**
- Real-time status indicators for backend connectivity, model availability, and dataset configuration.
- Monochromatic network topology visualizer with SVG corner registration marks.
- Live metric panels displaying held-out accuracy, recall, precision, F1-score, and false positive rate.

### 2. Traffic Analysis (`/traffic`)
- Drag-and-drop CSV upload panel with 50 MB safety boundaries.
- Instant model batch inference reporting total flows, attack predictions, benign counts, and attack percentage.
- Real-time tabular search, label filtering, and confidence score breakdown.
- **Export Results**: Download the annotated batch as a timestamped CSV.

### 3. Model Performance (`/performance`)
- Telemetry panel displaying selected algorithm, training latency, inference speed, and evaluation split.
- Interactive confusion matrix with percentage breakdowns.
- Per-class precision, recall, and support tables.
- Candidate model comparison table (Cross-validation F1 vs Validation F1).
- Interactive figure gallery displaying all 9 generated Matplotlib/Seaborn charts.

### 4. Alert Management (`/alerts`)
- Persistent SQLite audit log tracking every anomalous detection.
- Severity scoring and confidence values.
- Actionable **ACK** (Acknowledge) and **RESOLVE** controls for incident tracking.
- Clear operational disclaimer: *Model predictions do not constitute confirmed incidents.*

### 5. Reports & Artifacts (`/reports`)
- Auditable registry of generated evaluation reports, data quality summaries, and candidate comparisons.
- Direct downloads for `evaluation_report.json`, `model_comparison.csv`, and all chart PNGs.
- **"GENERATE ALL REPORTS"** button to re-run figure rendering from active model weights.

### 6. System Configuration (`/settings`)
- Configurable prediction threshold slider (0.10 – 0.90).
- Upload file size limits and batch processing parameters.
- Background model retraining controller.
- Read-only environment telemetry and CLI cheatsheet.

---

## 8. Automated Testing

### Backend & ML Tests (Pytest)

**Windows (PowerShell):**
```powershell
.\backend\venv\Scripts\python.exe -m pytest backend/tests/ -v
```

**Linux / macOS:**
```bash
./venv/bin/pytest backend/tests/ -v
```

*Covers database isolation, sample-flag detection, persistence guards, and API integration tests.*

### Frontend Tests (Vitest)
```bash
cd frontend
npm test
```
*Covers component rendering, error and empty states, confusion matrix math, model comparison highlights, and router rendering.*

### Frontend Production Build
```bash
cd frontend
npm run build
```

---

## 9. API Reference

| Endpoint | Method | Input | Response |
|---|---|---|---|
| `/api/health` | GET | None | Backend status, model loaded flag, versions |
| `/api/model/info` | GET | None | Model name, version, dataset source, feature schema |
| `/api/metrics` | GET | None | Held-out test metrics, confusion matrix, model comparison |
| `/api/predict` | POST | JSON `{"records": [...]}` | Classification labels, probabilities, batch ID |
| `/api/predict/csv` | POST | Multipart CSV file | Batch prediction summary, prediction array, warnings |
| `/api/alerts` | GET | Query: `page`, `page_size`, `unack_only` | Paginated SQLite alert events |
| `/api/alerts/{id}/acknowledge` | POST | Alert UUID | 204 No Content |
| `/api/alerts/{id}/resolve` | POST | Alert UUID | 204 No Content |
| `/api/history` | GET | Query: `limit`, `offset` | Prediction history log |
| `/api/reports` | GET | None | List of available reports and figure PNGs |
| `/api/reports/{id}/download` | GET | Report ID | File download (JSON, CSV, or PNG) |
| `/api/reports/generate` | POST | None | Re-renders and saves all 9 figures |
| `/api/settings` | GET/PATCH | Settings JSON | Runtime settings response |
| `/api/train` | POST | Query: `dataset` | 202 Accepted (Background worker) |
| `/api/train/status` | GET | None | Background training execution state |

---

## 10. Security & Ethical Boundaries
- **Defensive Instrument**: NID-X is exclusively designed for passive flow analysis, defensive monitoring, and machine learning research.
- **No Destructive Automation**: Does not execute unauthorized network scans, endpoint isolation, or automated firewall drops without explicit human authorization.
- **Resource Safeguards**: Enforces strict file size limits (50 MB default) and chunked processing to prevent denial-of-service against the API.
- **No Hardcoded Secrets**: Uses environment configuration (`.env`) and parameterized database queries with SQLite WAL mode.

---

## 11. Operational States
- **Newly Installed State**: Backend returns `model_loaded: false`. Overview and Performance pages show setup instructions and training commands.
- **Demo State**: Model trained on `data/sample/sample_flows.csv`. Clearly labeled as synthetic demo fixture for interface verification.
- **Benchmark / Production State**: Model trained on public dataset `data/raw/network_flows.csv`. Displays genuine metrics and discrimination curves from held-out splits.

---

## 12. `--fast` vs Standard Training — Reference

| Setting | Standard | `--fast` |
|---|---|---|
| CV strategy | 3-fold `StratifiedKFold` | 1-fold `ShuffleSplit` (80/20) |
| LogisticRegression `max_iter` | 500 | 200 |
| `n_jobs` (RandomForest / CV) | `-1` (all cores) | `1` (no subprocess spawn) |
| Typical time (300-row demo) | ~30 s | ~8 s |
| Typical time (100 k-row dataset) | ~5–15 min | ~2–5 min |
| Model selection logic | unchanged | unchanged |
| Saved artifacts | identical | identical |

Use `--fast` for demos, CI pipelines, or whenever you need a trained model quickly.
Use the standard run when you want the most reliable cross-validated model comparison.
# sss
