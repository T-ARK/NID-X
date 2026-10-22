"""
Model training entry point.

Usage:
    python scripts/train_model.py [--rows N] [--multiclass] [--fast]

Options:
    --rows N       Maximum rows to load (default: from config)
    --multiclass   Use multiclass mode (default: binary)
    --dataset PATH Path to dataset CSV
    --fast         Speed-optimised mode: 1-fold CV, reduced LR iterations,
                   single-threaded sklearn (avoids joblib spawn overhead on
                   small datasets). Ideal for demo / CI runs.
"""
import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

from backend.app.core.config import settings
from backend.app.services.training_service import train


def main():
    parser = argparse.ArgumentParser(description="Train NID-X intrusion detection model")
    parser.add_argument("--rows", type=int, default=None, help="Max training rows")
    parser.add_argument("--multiclass", action="store_true", help="Multiclass mode")
    parser.add_argument("--dataset", type=str, default=None, help="Path to dataset CSV")
    parser.add_argument(
        "--fast",
        action="store_true",
        help=(
            "Speed-optimised mode: reduces CV folds to 1, caps LogisticRegression "
            "max_iter at 200, and sets n_jobs=1 to skip joblib multiprocess spawn "
            "overhead. Recommended for the demo dataset or CI pipelines."
        ),
    )
    args = parser.parse_args()

    dataset_path = Path(args.dataset) if args.dataset else settings.dataset_path

    if not dataset_path.exists():
        print(f"\nERROR: Dataset not found: {dataset_path}")
        print(f"\nSee docs/dataset.md for instructions on obtaining a dataset.")
        print(f"Expected location: {settings.dataset_path}")
        sys.exit(1)

    binary = not args.multiclass
    print(f"\nStarting training on: {dataset_path}")
    print(f"Mode: {'binary' if binary else 'multiclass'}")
    if args.rows:
        print(f"Max rows: {args.rows:,}")
    if args.fast:
        print("Fast mode: 1-fold CV, reduced LR iterations, n_jobs=1")

    metadata = train(
        dataset_path=dataset_path,
        max_rows=args.rows,
        binary=binary,
        fast=args.fast,
    )

    print(f"\n{'='*60}")
    print(f"  Training Complete")
    print(f"{'='*60}")
    print(f"  Model     : {metadata['model_name']}")
    print(f"  Version   : {metadata['model_version']}")
    print(f"  Saved to  : {settings.model_path}")
    tm = metadata.get("test_metrics", {})
    print(f"\n  Test Metrics:")
    print(f"    Accuracy  : {tm.get('accuracy', 'N/A')}")
    print(f"    Precision : {tm.get('precision', 'N/A')}")
    print(f"    Recall    : {tm.get('recall', 'N/A')}")
    print(f"    F1-Score  : {tm.get('f1_score', 'N/A')}")
    print(f"    ROC-AUC   : {tm.get('roc_auc', 'N/A')}")
    if tm.get('false_positive_rate') is not None:
        print(f"    FPR       : {tm.get('false_positive_rate', 'N/A')}")
    print(f"\n  Reports   : {settings.REPORTS_DIR}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
