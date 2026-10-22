# NID-X: Dataset Documentation & Ingestion Guide

## 1. Supported Public Datasets
NID-X is engineered to ingest standard network flow capture datasets:

### A. CIC-IDS2017 (Canadian Institute for Cybersecurity)
- **Official Source**: [https://www.unb.ca/cic/datasets/ids-2017.html](https://www.unb.ca/cic/datasets/ids-2017.html)
- **Kaggle Mirror**: [https://www.kaggle.com/datasets/cicdataset/cicids2017](https://www.kaggle.com/datasets/cicdataset/cicids2017)
- **Format**: Comma-Separated Values (`.csv`)
- **Label Column**: `Label`
- **Classes**:
  - `BENIGN` (Normal traffic)
  - `DDoS`, `PortScan`, `Bot`, `Infiltration`, `Web Attack – Brute Force`, `Web Attack – XSS`, `Web Attack – Sql Injection`, `FTP-Patator`, `SSH-Patator`
- **Recommended File**: `Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv` (225,745 flows)

### B. UNSW-NB15 (Australian Centre for Cyber Security)
- **Official Source**: [https://research.unsw.edu.au/projects/unsw-nb15-dataset](https://research.unsw.edu.au/projects/unsw-nb15-dataset)
- **Kaggle Mirror**: [https://www.kaggle.com/datasets/mrwellsdavid/unsw-nb15](https://www.kaggle.com/datasets/mrwellsdavid/unsw-nb15)
- **Format**: Comma-Separated Values (`.csv`)
- **Label Column**: `label` (0 = Normal, 1 = Attack) or `attack_cat` (Multiclass)
- **Classes**:
  - `Normal`
  - `Fuzzers`, `Analysis`, `Backdoors`, `DoS`, `Exploits`, `Generic`, `Reconnaissance`, `Shellcode`, `Worms`

---

## 2. Ingestion & Preprocessing Rules
To ensure zero target leakage and maintain model validity:
1. **Identifier Exclusions**:
   - `Flow ID`, `Source IP`, `Destination IP`, `Source Port`, `Destination Port`, `Timestamp`, `External IP` are automatically identified and excluded.
2. **Numeric Cleaning**:
   - String numbers with whitespace are normalized and converted to `float64`.
   - Infinite values (`np.inf`, `-np.inf`) are converted to `np.nan`.
   - Constant or single-value features are removed.
3. **Pipeline Transformers**:
   - Median Imputation (`SimpleImputer(strategy='median')`)
   - Standard Scaling (`StandardScaler()`)
   - Categorical Encoding (`OrdinalEncoder(handle_unknown='use_encoded_value', unknown_value=-1)`)
   - Fitted exclusively on training rows.

---

## 3. Large File Handling & Memory Safety
Full intrusion datasets often exceed 5 to 10 GB uncompressed. NID-X handles this through:
- **Chunked CSV Reading**: `pd.read_csv(chunksize=50_000, low_memory=False)`
- **Configurable Row Caps**: `--rows N` flag in `train_model.py` (default: 500,000 rows).
- **Stratified Subsampling**: Preserves class frequency ratios across splits.

---

## 4. Step-by-Step Setup Instructions

### Step 1: Download the Public Dataset
Download one of the CSV files from CIC-IDS2017 or UNSW-NB15.

### Step 2: Place in Raw Data Directory
```bash
cp /path/to/downloaded.csv /home/ark123/Documents/cyber/data/raw/network_flows.csv
```

### Step 3: Inspect Schema and Quality
Run the inspection tool to verify column types, missing values, and class distributions:
```bash
python scripts/inspect_dataset.py data/raw/network_flows.csv
```

### Step 4: Execute Model Training
```bash
# Train on up to 100,000 flows using binary classification mode
python scripts/train_model.py --dataset data/raw/network_flows.csv --rows 100000

# Or train in multiclass mode
python scripts/train_model.py --dataset data/raw/network_flows.csv --multiclass
```

### Step 5: Evaluate Model and Render Visualizations
```bash
python scripts/evaluate_model.py --dataset data/raw/network_flows.csv
```

---

## 5. Demonstration Test Fixture
For CI and local interface testing without requiring immediate gigabyte-scale downloads, a small labeled synthetic dataset is provided at:
```
data/sample/sample_flows.csv
```
This file is generated via `python scripts/generate_sample.py` and is explicitly identified in the interface as `SYNTHETIC DEMO DATA`. It must never be presented as genuine benchmark evidence.
