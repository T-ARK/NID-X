"""
User-controlled dataset download and setup helper for NID-X.

Supported Public Datasets:
1. CIC-IDS2017 (Canadian Institute for Cybersecurity)
   - Official: https://www.unb.ca/cic/datasets/ids-2017.html
   - File format: CSV (e.g. Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv)
   - Target column: 'Label' (BENIGN, DDoS, PortScan, etc.)
2. UNSW-NB15 (Cyber Range Lab of the Australian Centre for Cyber Security)
   - Official: https://research.unsw.edu.au/projects/unsw-nb15-dataset
   - File format: CSV (UNSW_NB15_training-set.csv / UNSW_NB15_testing-set.csv)
   - Target column: 'label' (0 = Normal, 1 = Attack) or 'attack_cat' (multiclass)

Usage:
    python scripts/download_dataset.py --dataset cicids2017
    python scripts/download_dataset.py --dataset unsw_nb15
    python scripts/download_dataset.py --demo
"""
import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.core.config import settings


def print_instructions(dataset: str):
    print(f"\n{'='*70}")
    print(f"  NID-X DATASET SETUP INSTRUCTIONS: {dataset.upper()}")
    print(f"{'='*70}")

    if dataset.lower() == "cicids2017":
        print("""
1. DATASET: CIC-IDS2017 (Canadian Institute for Cybersecurity)
   Official URL: https://www.unb.ca/cic/datasets/ids-2017.html
   Direct Kaggle Mirror: https://www.kaggle.com/datasets/cicdataset/cicids2017

2. RECOMMENDED SUBSET FILE:
   Download: 'Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv' or
             'Thursday-WorkingHours-Morning-WebAttacks.pcap_ISCX.csv'

3. PLACEMENT:
   Place the downloaded CSV in:
     data/raw/network_flows.csv

4. VERIFY SCHEMA:
   Run:
     python scripts/inspect_dataset.py data/raw/network_flows.csv

5. TRAIN MODEL:
   Run:
     python scripts/train_model.py --dataset data/raw/network_flows.csv --rows 100000
""")
    elif dataset.lower() in ("unsw", "unsw_nb15", "unsw-nb15"):
        print("""
1. DATASET: UNSW-NB15
   Official URL: https://research.unsw.edu.au/projects/unsw-nb15-dataset
   Kaggle Mirror: https://www.kaggle.com/datasets/mrwellsdavid/unsw-nb15

2. RECOMMENDED SUBSET FILE:
   Download: 'UNSW_NB15_training-set.csv'

3. PLACEMENT & CONFIGURATION:
   Place the file in:
     data/raw/network_flows.csv
   Note: If your file uses 'label' (lowercase) or 'attack_cat', update your .env:
     LABEL_COLUMN=label
     BENIGN_LABEL=0

4. VERIFY SCHEMA:
   Run:
     python scripts/inspect_dataset.py data/raw/network_flows.csv

5. TRAIN MODEL:
   Run:
     python scripts/train_model.py --dataset data/raw/network_flows.csv
""")
    else:
        print(f"Unknown dataset '{dataset}'. Choose 'cicids2017' or 'unsw_nb15'.")
    print(f"{'='*70}\n")


def generate_demo():
    from scripts.generate_sample import generate_sample
    print("\nGenerating demonstration synthetic dataset for testing interface...")
    out = generate_sample(n_benign=500, n_attack=250, seed=42)
    print(f"Demo dataset created at: {out}")
    print("NOTE: This is synthetic test fixture data for testing the UI and pipeline.")
    print("Never mix synthetic data with official benchmark results.")


def main():
    parser = argparse.ArgumentParser(description="NID-X Dataset Setup Helper")
    parser.add_argument("--dataset", type=str, choices=["cicids2017", "unsw_nb15"], help="Dataset to get setup instructions for")
    parser.add_argument("--demo", action="store_true", help="Generate local demonstration synthetic dataset for UI testing")
    args = parser.parse_args()

    if args.demo:
        generate_demo()
    elif args.dataset:
        print_instructions(args.dataset)
    else:
        print_instructions("cicids2017")
        print_instructions("unsw_nb15")


if __name__ == "__main__":
    main()
