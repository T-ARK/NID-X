"""
Post-training evaluation: generate figures and print metrics.

Usage:
    python scripts/evaluate_model.py
"""
import json
import logging
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

from backend.app.core.config import settings
from backend.app.services.evaluation_service import load_evaluation_report, generate_figures
from backend.app.services.prediction_service import is_model_available
from backend.app.services.dataset_service import load_raw, prepare_dataframe
from backend.app.services.preprocessing_service import load_feature_schema


def main():
    if not is_model_available():
        print("No model found. Run train_model.py first.")
        sys.exit(1)

    report = load_evaluation_report()
    if not report:
        print("No evaluation report. Run train_model.py first.")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  NID-X Evaluation Report")
    print(f"{'='*60}")
    md = report.get("metadata", {})
    print(f"  Model     : {md.get('model_name', 'N/A')}")
    print(f"  Version   : {md.get('model_version', 'N/A')}")
    print(f"  Evaluated : {md.get('training_timestamp', 'N/A')}")
    print(f"\n  Test Metrics:")
    for k in ["accuracy", "precision", "recall", "f1_score", "roc_auc", "pr_auc",
              "false_positive_rate", "false_negative_rate"]:
        v = report.get(k)
        print(f"    {k:<25}: {v if v is not None else 'N/A'}")

    print(f"\n  Confusion Matrix:")
    cm = report.get("confusion_matrix")
    if cm:
        for row in cm:
            print(f"    {row}")

    import argparse
    parser = argparse.ArgumentParser(description="Evaluate NID-X model and generate figures")
    parser.add_argument("--dataset", type=str, default=None, help="Path to evaluation dataset CSV")
    args = parser.parse_args()

    # Determine dataset to use for figure generation
    dataset_to_use = None
    if args.dataset and Path(args.dataset).exists():
        dataset_to_use = Path(args.dataset)
    elif settings.dataset_path.exists():
        dataset_to_use = settings.dataset_path
    elif md.get("dataset_source") and Path(md["dataset_source"]).exists() and "sample_flows.csv" not in md["dataset_source"]:
        dataset_to_use = Path(md["dataset_source"])

    # Display candidate comparison if available
    if settings.comparison_path.exists():
        print(f"\n  Candidate Model Comparison:")
        try:
            comp_df = pd.read_csv(settings.comparison_path)
            print(comp_df.to_string(index=False))
        except Exception as e:
            print(f"    (Could not read comparison: {e})")

    # Generate figures if dataset available
    if dataset_to_use and dataset_to_use.exists():
        import joblib
        print(f"\n  Generating evaluation and EDA figures using: {dataset_to_use}")
        pipeline = joblib.load(settings.model_path)
        df = load_raw(dataset_to_use, max_rows=20_000)
        X, y, info = prepare_dataframe(
            df,
            label_col=settings.LABEL_COLUMN,
            binary=(md.get("classification_mode", "binary") == "binary"),
            benign_label=settings.BENIGN_LABEL,
        )
        saved = generate_figures(pipeline, X, y, binary=(md.get("classification_mode", "binary") == "binary"), full_df=df)
        print(f"  Successfully generated {len(saved)} figures:")
        for p in saved:
            print(f"    - {p.name} ({p.stat().st_size / 1024:.1f} KB)")
    else:
        print(f"\n  Skipping figure generation (no dataset available)")

    print(f"\n  Full report: {settings.evaluation_report_path}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
