# NID-X: Model Evaluation & Security Metrics

## 1. Security Metrics Rationale
In network intrusion detection, classification accuracy is often misleading: if 99% of network traffic is benign, a naive classifier that predicts everything as benign achieves 99% accuracy while missing 100% of attacks.

NID-X measures performance across comprehensive detection criteria:

| Metric | Formula | Security Operational Significance |
|---|---|---|
| **Accuracy** | $(TP + TN) / \text{Total}$ | Overall baseline correctness. |
| **Precision** | $TP / (TP + FP)$ | Percentage of flagged flows that are actual attacks. High precision minimizes false alarm fatigue in SOCs. |
| **Recall / Detection Rate** | $TP / (TP + FN)$ | Percentage of actual attacks captured. High recall prevents adversary dwell time and undetected breaches. |
| **F1-Score** | $2 \cdot \frac{\text{Prec} \cdot \text{Rec}}{\text{Prec} + \text{Rec}}$ | Primary model selection criterion. Balances false alarms against missed attacks. |
| **False Positive Rate (FPR)** | $FP / (FP + TN)$ | Rate at which benign traffic is incorrectly blocked or flagged. Critical for operational availability. |
| **False Negative Rate (FNR)** | $FN / (FN + TP)$ | Rate of undetected attacks slipping past detection boundaries. |
| **ROC-AUC** | Area under ROC Curve | Evaluates discrimination capacity across all potential decision thresholds. |
| **PR-AUC (Average Precision)**| Area under Precision-Recall Curve | Essential metric for highly imbalanced class distributions. |

---

## 2. Generated Evaluation Figures
All figures are saved to `reports/figures/` and viewable via the dashboard:

1. **`confusion_matrix.png`**:
   Heatmap comparing actual vs predicted labels with exact flow counts and cell percentages.
2. **`roc_curve.png`**:
   True Positive Rate vs False Positive Rate curve across probability thresholds, annotated with ROC-AUC.
3. **`pr_curve.png`**:
   Precision vs Recall curve across thresholds, annotated with Average Precision (AP).
4. **`feature_importance.png`**:
   Top 15 most influential traffic flow features (e.g. packet lengths, duration, flag counts).
5. **`class_distribution.png`**:
   Held-out test set class frequency distribution with sample counts and percentages.
6. **`numeric_distributions.png`**:
   Subplots showing distributions of key numerical features truncated at the 99th percentile to remove extreme flow outliers.
7. **`correlation_heatmap.png`**:
   Correlation matrix among top traffic metrics to evaluate collinearity.
8. **`model_comparison.png`**:
   Grouped bar chart comparing the 4 candidates on Cross-Validation F1 vs Validation F1.
9. **`error_analysis.png`**:
   Breakdown of detection outcomes: True Negatives (Benign OK), False Positives (False Alarm), False Negatives (Missed Attack), and True Positives (Detected Attack).

---

## 3. Decision Threshold Configuration
Predicted probabilities output by tree-based models or standard classifiers may not be strictly calibrated. Users can tune the decision threshold via the Settings dashboard or API (`POST /api/settings`):
- **Lower threshold (e.g., 0.30)**: Favors Recall (maximizes detection of subtle attacks at the expense of higher false alarm rates).
- **Higher threshold (e.g., 0.70)**: Favors Precision (suppresses false alarms for automated alerting pipelines).
