#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# NID-X: Machine Learning Network Intrusion Detector
# Orchestration script for Linux / Ubuntu
# ═══════════════════════════════════════════════════════════════

set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="$ROOT_DIR/venv/bin/python3"
if [ ! -f "$PYTHON_BIN" ]; then
    PYTHON_BIN="python3"
fi

COMMAND="${1:-all}"

case "$COMMAND" in
    backend)
        echo "Starting NID-X FastAPI backend on http://127.0.0.1:8000..."
        "$PYTHON_BIN" -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
        ;;
    frontend)
        echo "Starting NID-X Vite frontend on http://localhost:5173..."
        cd "$ROOT_DIR/frontend"
        npm run dev
        ;;
    build)
        echo "Building NID-X frontend..."
        cd "$ROOT_DIR/frontend"
        npm run build
        ;;
    test)
        echo "Running backend test suite..."
        "$PYTHON_BIN" -m pytest backend/tests/test_nidx.py -v
        echo "Running frontend test suite..."
        cd "$ROOT_DIR/frontend"
        npm test
        ;;
    sample)
        echo "Notice: Synthetic dataset generation is disabled. Please provide or upload a user dataset."
        exit 1
        ;;
    train)
        echo "Training candidate models on user dataset..."
        DATASET="${2:-data/raw/network_flows.csv}"
        "$PYTHON_BIN" scripts/train_model.py --dataset "$DATASET"
        ;;
    evaluate)
        echo "Evaluating model and rendering figures on user dataset..."
        "$PYTHON_BIN" scripts/evaluate_model.py
        ;;
    inspect)
        DATASET="${2:-data/raw/network_flows.csv}"
        "$PYTHON_BIN" scripts/inspect_dataset.py "$DATASET"
        ;;
    all)
        echo "============================================================"
        echo "  NID-X: ML NETWORK INTRUSION DETECTOR"
        echo "  NETWORKS UNDER WATCH."
        echo "============================================================"
        echo "Starting Backend (port 8000) & Frontend (port 5173)..."

        # Trap SIGINT and SIGTERM to kill background children
        trap 'kill 0' SIGINT SIGTERM EXIT

        "$PYTHON_BIN" -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 &
        BACKEND_PID=$!

        cd "$ROOT_DIR/frontend"
        npm run dev &
        FRONTEND_PID=$!

        echo "Backend PID: $BACKEND_PID | Frontend PID: $FRONTEND_PID"
        echo "Press CTRL+C to terminate both servers."
        wait
        ;;
    *)
        echo "Usage: ./run.sh [backend|frontend|build|test|sample|train|evaluate|inspect|all]"
        exit 1
        ;;
esac
