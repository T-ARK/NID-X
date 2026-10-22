"""
Script to inspect a dataset CSV and print its schema, label distribution,
and basic quality summary. Run BEFORE training.

Usage:
    python scripts/inspect_dataset.py [path/to/dataset.csv]
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.core.config import settings
from backend.app.services.dataset_service import (
    build_quality_report, load_raw, prepare_dataframe, save_quality_report,
)


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else settings.dataset_path

    print(f"\n{'='*60}")
    print(f"  NID-X Dataset Inspector")
    print(f"{'='*60}")
    print(f"  Dataset: {path}")

    if not path.exists():
        print(f"\n  ERROR: File not found: {path}")
        print(f"\n  Place your dataset CSV at: {path}")
        print(f"  See docs/dataset.md for download instructions.")
        sys.exit(1)

    print("\n  Loading (may take a moment for large files)...")
    df = load_raw(path, max_rows=50_000)

    print(f"\n  Rows loaded : {len(df):,}")
    print(f"  Columns     : {len(df.columns)}")
    print(f"\n  Column names (first 30):")
    for col in df.columns[:30]:
        print(f"    - {col!r}  [{df[col].dtype}]")
    if len(df.columns) > 30:
        print(f"    ... and {len(df.columns) - 30} more")

    label_col = settings.LABEL_COLUMN
    if label_col in df.columns:
        print(f"\n  Label column: '{label_col}'")
        dist = df[label_col].astype(str).str.strip().value_counts()
        print(f"  Label distribution ({len(dist)} classes):")
        for lbl, cnt in dist.head(20).items():
            print(f"    {lbl}: {cnt:,}")
    else:
        cols_lower = [c.strip().lower() for c in df.columns]
        print(f"\n  WARNING: Label column '{label_col}' not found.")
        print(f"  Available columns: {df.columns.tolist()[:10]}")
        print(f"\n  Set LABEL_COLUMN in .env to match your dataset.")

    report = build_quality_report(df, label_col, path)
    out = save_quality_report(report)
    print(f"\n  Data quality report saved: {out}")
    print(f"\n  Missing values  : {report['missing_total']:,}")
    print(f"  Duplicate rows  : {report['duplicate_rows']:,}")
    print(f"  Constant features: {len(report['constant_features'])}")
    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    main()
