"""
Traffic analysis service for user-uploaded network datasets.
Performs model inference, deep traffic characterization, visual chart generation,
and executive analytical report compilation strictly using user-uploaded data.
"""
from __future__ import annotations

import io
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score, auc, confusion_matrix, f1_score,
    precision_recall_curve, precision_score, recall_score,
    roc_curve,
)

from backend.app.core.config import settings
from backend.app.services.prediction_service import _load_model, align_input, load_feature_schema

logger = logging.getLogger(__name__)

# Dark brutalist styling parameters matching NID-X design system
PALETTE = {
    "bg": "#050505",
    "card": "#101010",
    "border": "#292929",
    "red": "#FF3038",
    "red_light": "#FF6B72",
    "red_dark": "#88181D",
    "text": "#F5F5F5",
    "text_muted": "#A0A0A0",
    "gray_dark": "#242424",
    "gray_light": "#4A4A4A",
    "cyan": "#00F0FF",
}


def _find_column(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    """Case-insensitive fuzzy match for common network flow column names."""
    df_cols = {c.strip().lower().replace(" ", "_").replace("/", "_"): c for c in df.columns}
    for cand in candidates:
        cand_norm = cand.strip().lower().replace(" ", "_").replace("/", "_")
        if cand_norm in df_cols:
            return df_cols[cand_norm]
    # Substring search fallback
    for cand in candidates:
        cand_norm = cand.strip().lower().replace(" ", "_").replace("/", "_")
        for norm_col, orig_col in df_cols.items():
            if cand_norm in norm_col:
                return orig_col
    return None


def analyze_uploaded_traffic(
    df: pd.DataFrame,
    filename: str = "uploaded_traffic.csv",
    threshold: Optional[float] = None,
) -> dict:
    """
    Comprehensive analysis of user-uploaded network traffic:
      1. Detect & extract ground truth labels if present (without data leakage).
      2. Run ML inference using the trained champion pipeline.
      3. Compute traffic flow volume, packet, and protocol flag statistics.
      4. Render high-resolution dark-brutalist charts strictly from the uploaded flows.
      5. Compile executive analytical report (JSON & Markdown) and persist artifacts.
    """
    batch_id = str(uuid.uuid4())
    batch_short = batch_id[:8]
    timestamp = datetime.now(timezone.utc).isoformat()
    threshold = threshold if threshold is not None else settings.PREDICTION_THRESHOLD
    pipeline, metadata = _load_model()
    schema = load_feature_schema()
    feature_names = schema["feature_names"] if schema else None
    model_ver = metadata.get("model_version", "unknown") if metadata else "unknown"
    binary_mode = metadata.get("classification_mode", "binary") == "binary" if metadata else True
    target_map = metadata.get("target_mapping", {}) if metadata else {}
    inv_map = {v: k for k, v in target_map.items()} if target_map else {}

    warnings: List[str] = []
    total_records = len(df)
    if total_records == 0:
        raise ValueError("Uploaded traffic dataset contains 0 records.")

    # ── 1. Check for Ground Truth Label ──────────────────────────────────────────
    label_candidates = [settings.LABEL_COLUMN, "label", "Label", "attack_cat", "class", "Class"]
    ground_truth_col = None
    for cand in label_candidates:
        if cand in df.columns:
            ground_truth_col = cand
            break
    if not ground_truth_col:
        for c in df.columns:
            if c.strip().lower() in [cand.lower() for cand in label_candidates]:
                ground_truth_col = c
                break

    y_true = None
    y_true_binary = None
    df_features = df.copy()
    if ground_truth_col:
        raw_labels = df[ground_truth_col].astype(str).str.strip()
        benign_cand = [settings.BENIGN_LABEL.lower(), "0", "normal", "benign"]
        y_true_binary = (~raw_labels.str.lower().isin(benign_cand)).astype(int)
        y_true = raw_labels
        df_features = df_features.drop(columns=[ground_truth_col])
        warnings.append(f"Ground-truth label column '{ground_truth_col}' detected. Model evaluated against actual labels.")

    # ── 2. Feature Alignment & Inference ─────────────────────────────────────────
    if feature_names:
        missing_cols = set(feature_names) - set(df_features.columns)
        if missing_cols:
            warnings.append(f"Dataset missing {len(missing_cols)} expected model features (imputed with median during inference).")
        aligned_df = align_input(df_features, feature_names)
    else:
        aligned_df = df_features

    t0 = time.perf_counter()
    y_prob = None
    if hasattr(pipeline, "predict_proba"):
        probs = pipeline.predict_proba(aligned_df)
        if probs.shape[1] == 2:
            prob_scores = probs[:, 1]
            pred_classes = (prob_scores >= threshold).astype(int)
        else:
            pred_classes = np.argmax(probs, axis=1)
            prob_scores = probs.max(axis=1)
    else:
        pred_classes = pipeline.predict(aligned_df)
        prob_scores = np.full(len(pred_classes), np.nan)
    infer_duration_ms = (time.perf_counter() - t0) * 1000

    # Build prediction row records
    predictions = []
    attack_count = 0
    benign_count = 0
    critical_count = 0
    high_count = 0
    medium_count = 0
    low_count = 0

    for i in range(total_records):
        p_cls = int(pred_classes[i])
        score = float(prob_scores[i]) if not np.isnan(prob_scores[i]) else None
        lbl = inv_map.get(p_cls, "ATTACK" if p_cls == 1 else "BENIGN")
        is_attack = (p_cls == 1) if binary_mode else (p_cls != 0)

        if is_attack:
            attack_count += 1
            if score is not None:
                if score >= 0.85:
                    critical_count += 1
                elif score >= 0.70:
                    high_count += 1
                else:
                    medium_count += 1
            else:
                high_count += 1
        else:
            benign_count += 1
            low_count += 1

        predictions.append({
            "row_index": i,
            "predicted_label": lbl,
            "predicted_class": p_cls,
            "probability": round(score, 4) if score is not None else None,
            "model_version": model_ver,
            "timestamp": timestamp,
        })

    attack_rate = round(attack_count / total_records, 4) if total_records > 0 else 0.0

    # ── 3. Ground Truth Evaluation Metrics (if available) ────────────────────────
    evaluation_metrics = None
    if y_true_binary is not None:
        try:
            acc = float(accuracy_score(y_true_binary, pred_classes))
            prec = float(precision_score(y_true_binary, pred_classes, zero_division=0))
            rec = float(recall_score(y_true_binary, pred_classes, zero_division=0))
            f1 = float(f1_score(y_true_binary, pred_classes, zero_division=0))
            cm = confusion_matrix(y_true_binary, pred_classes).tolist()
            tn, fp, fn, tp = (0, 0, 0, 0)
            if len(cm) == 2 and len(cm[0]) == 2:
                tn, fp, fn, tp = confusion_matrix(y_true_binary, pred_classes).ravel()
            fpr = float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0
            fnr = float(fn / (fn + tp)) if (fn + tp) > 0 else 0.0

            evaluation_metrics = {
                "has_ground_truth": True,
                "label_column": ground_truth_col,
                "accuracy": round(acc, 4),
                "precision": round(prec, 4),
                "recall": round(rec, 4),
                "f1_score": round(f1, 4),
                "false_positive_rate": round(fpr, 4),
                "false_negative_rate": round(fnr, 4),
                "confusion_matrix": cm,
                "true_positives": int(tp),
                "false_positives": int(fp),
                "true_negatives": int(tn),
                "false_negatives": int(fn),
            }
        except Exception as ee:
            logger.warning("Could not calculate ground truth metrics: %s", ee)

    # ── 4. Deep Traffic Characteristics ──────────────────────────────────────────
    # Column detection for flow duration, packets, bytes, flags
    dur_col = _find_column(df, ["flow_duration", "duration", "dur"])
    fwd_pkts_col = _find_column(df, ["total_fwd_packets", "fwd_packets", "spkts", "tot_fwd_pkts"])
    bwd_pkts_col = _find_column(df, ["total_backward_packets", "bwd_packets", "dpkts", "tot_bwd_pkts"])
    pkt_len_col = _find_column(df, ["packet_length_mean", "packet_length", "mean_packet_len", "sbytes"])
    byte_rate_col = _find_column(df, ["flow_bytes_s", "flow_byts_s", "bytes_per_sec", "rate"])

    syn_col = _find_column(df, ["syn_flag_count", "syn", "syn_count", "syn_flags"])
    ack_col = _find_column(df, ["ack_flag_count", "ack", "ack_count", "ack_flags"])
    fin_col = _find_column(df, ["fin_flag_count", "fin", "fin_count", "fin_flags"])
    rst_col = _find_column(df, ["rst_flag_count", "rst", "rst_count", "rst_flags"])
    psh_col = _find_column(df, ["psh_flag_count", "psh", "psh_count", "psh_flags"])
    urg_col = _find_column(df, ["urg_flag_count", "urg", "urg_count", "urg_flags"])

    def _stats(series: Optional[pd.Series]) -> Optional[Dict[str, float]]:
        if series is None or series.dropna().empty:
            return None
        s = pd.to_numeric(series, errors="coerce").dropna()
        if s.empty:
            return None
        return {
            "mean": round(float(s.mean()), 2),
            "median": round(float(s.median()), 2),
            "max": round(float(s.max()), 2),
            "min": round(float(s.min()), 2),
            "std": round(float(s.std()), 2) if len(s) > 1 else 0.0,
        }

    traffic_stats = {
        "duration": _stats(df[dur_col]) if dur_col else None,
        "fwd_packets": _stats(df[fwd_pkts_col]) if fwd_pkts_col else None,
        "bwd_packets": _stats(df[bwd_pkts_col]) if bwd_pkts_col else None,
        "packet_length": _stats(df[pkt_len_col]) if pkt_len_col else None,
        "byte_rate": _stats(df[byte_rate_col]) if byte_rate_col else None,
    }

    tcp_flags_count = {}
    for name, col in [("SYN", syn_col), ("ACK", ack_col), ("FIN", fin_col), ("RST", rst_col), ("PSH", psh_col), ("URG", urg_col)]:
        if col:
            s = pd.to_numeric(df[col], errors="coerce").fillna(0)
            tcp_flags_count[name] = int((s > 0).sum())
        else:
            tcp_flags_count[name] = 0

    # Top 10 most critical/suspicious flows
    df_with_preds = df.copy()
    df_with_preds["_pred_class"] = pred_classes
    df_with_preds["_prob_score"] = prob_scores
    top_attacks = df_with_preds[df_with_preds["_pred_class"] == 1].sort_values(by="_prob_score", ascending=False).head(10)

    top_suspicious_flows = []
    for idx, row in top_attacks.iterrows():
        top_suspicious_flows.append({
            "flow_index": int(idx),
            "threat_score": round(float(row["_prob_score"]), 4) if not np.isnan(row["_prob_score"]) else 1.0,
            "duration": float(row[dur_col]) if dur_col and not pd.isna(row[dur_col]) else None,
            "fwd_packets": float(row[fwd_pkts_col]) if fwd_pkts_col and not pd.isna(row[fwd_pkts_col]) else None,
            "packet_length_mean": float(row[pkt_len_col]) if pkt_len_col and not pd.isna(row[pkt_len_col]) else None,
            "syn_flag": int(row[syn_col]) if syn_col and not pd.isna(row[syn_col]) else None,
        })

    # Threat assessment level
    if attack_rate >= 0.50 or critical_count > 100:
        overall_threat_level = "CRITICAL"
        threat_color = "#FF3038"
    elif attack_rate >= 0.15 or high_count > 50:
        overall_threat_level = "HIGH"
        threat_color = "#FF6B72"
    elif attack_rate > 0.0:
        overall_threat_level = "ELEVATED"
        threat_color = "#E5A000"
    else:
        overall_threat_level = "LOW / SECURE"
        threat_color = "#00F0FF"

    # ── 5. Generate Visual Charts & Figures ──────────────────────────────────────
    figures_dir = settings.FIGURES_DIR
    figures_dir.mkdir(parents=True, exist_ok=True)
    generated_charts = []

    # Chart A: Threat Distribution Donut Chart
    try:
        fig, ax = plt.subplots(figsize=(6, 5), facecolor=PALETTE["bg"])
        ax.set_facecolor(PALETTE["bg"])
        labels = ["BENIGN", "ATTACK"]
        counts = [benign_count, attack_count]
        colors = [PALETTE["gray_dark"], PALETTE["red"]]

        wedges, texts, autotexts = ax.pie(
            counts,
            labels=labels,
            autopct="%1.1f%%",
            startangle=140,
            colors=colors,
            wedgeprops={"edgecolor": PALETTE["border"], "linewidth": 2, "width": 0.4},
            textprops={"color": PALETTE["text"], "fontfamily": "monospace", "fontsize": 9},
        )
        for at in autotexts:
            at.set_color(PALETTE["text"])
            at.set_weight("bold")
            at.set_fontsize(10)

        ax.set_title(
            f"TRAFFIC THREAT DISTRIBUTION\n[{total_records:,} Uploaded Flows]",
            color=PALETTE["text"], pad=14, fontfamily="monospace", fontsize=11, weight="bold"
        )
        p_dist = figures_dir / f"traffic_threat_distribution_{batch_short}.png"
        fig.savefig(p_dist, dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
        try:
            fig.savefig(figures_dir / "class_distribution.png", dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
        except Exception:
            pass
        plt.close(fig)
        generated_charts.append({
            "id": "threat_distribution",
            "title": "Threat Classification Breakdown",
            "url": f"/static/figures/{p_dist.name}",
            "filename": p_dist.name,
        })
    except Exception as e:
        logger.warning("Could not generate threat distribution chart: %s", e)

    # Chart B: Prediction Score / Confidence Distribution
    try:
        fig, ax = plt.subplots(figsize=(7, 4.5), facecolor=PALETTE["bg"])
        ax.set_facecolor(PALETTE["card"])
        valid_scores = prob_scores[~np.isnan(prob_scores)]
        if len(valid_scores) > 0:
            bins = np.linspace(0, 1, 30)
            n, _, patches = ax.hist(valid_scores, bins=bins, edgecolor=PALETTE["border"], alpha=0.9)
            # Color patches: red for >= threshold, dark gray for < threshold
            for patch, edge in zip(patches, bins[:-1]):
                if edge >= threshold:
                    patch.set_facecolor(PALETTE["red"])
                else:
                    patch.set_facecolor(PALETTE["gray_light"])

            ax.axvline(threshold, color=PALETTE["cyan"], linestyle="--", linewidth=1.8, label=f"Threshold ({threshold:.2f})")
            ax.set_title("ANOMALY PROBABILITY SCORE DENSITY", color=PALETTE["text"], pad=12, fontfamily="monospace", fontsize=11, weight="bold")
            ax.set_xlabel("ATTACK PROBABILITY", color=PALETTE["text_muted"], fontfamily="monospace", fontsize=9)
            ax.set_ylabel("FLOW COUNT", color=PALETTE["text_muted"], fontfamily="monospace", fontsize=9)
            ax.tick_params(colors=PALETTE["text_muted"])
            for spine in ax.spines.values():
                spine.set_edgecolor(PALETTE["border"])
            ax.grid(True, color="#1c1c1c", linestyle=":", alpha=0.6)
            ax.legend(facecolor=PALETTE["card"], edgecolor=PALETTE["border"], labelcolor="white")
            plt.tight_layout()
            p_score = figures_dir / f"traffic_risk_distribution_{batch_short}.png"
            fig.savefig(p_score, dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
            try:
                fig.savefig(figures_dir / "error_analysis.png", dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
            except Exception:
                pass
            plt.close(fig)
            generated_charts.append({
                "id": "risk_distribution",
                "title": "Anomaly Probability Density",
                "url": f"/static/figures/{p_score.name}",
                "filename": p_score.name,
            })
    except Exception as e:
        logger.warning("Could not generate risk distribution chart: %s", e)

    # Chart C: TCP Flags Profile
    if any(v > 0 for v in tcp_flags_count.values()):
        try:
            fig, ax = plt.subplots(figsize=(7, 4.5), facecolor=PALETTE["bg"])
            ax.set_facecolor(PALETTE["card"])
            flag_names = list(tcp_flags_count.keys())
            flag_vals = list(tcp_flags_count.values())
            bars = ax.bar(flag_names, flag_vals, color=PALETTE["red"], edgecolor=PALETTE["border"], width=0.5)
            for b in bars:
                h = b.get_height()
                if h > 0:
                    ax.annotate(
                        f"{h:,}",
                        xy=(b.get_x() + b.get_width() / 2, h),
                        xytext=(0, 4), textcoords="offset points",
                        ha="center", va="bottom", color=PALETTE["text"], fontfamily="monospace", fontsize=8,
                    )
            ax.set_title("NETWORK PROTOCOL TCP FLAGS PROFILE", color=PALETTE["text"], pad=12, fontfamily="monospace", fontsize=11, weight="bold")
            ax.set_ylabel("ACTIVE FLOWS", color=PALETTE["text_muted"], fontfamily="monospace", fontsize=9)
            ax.tick_params(colors=PALETTE["text_muted"])
            for spine in ax.spines.values():
                spine.set_edgecolor(PALETTE["border"])
            ax.grid(True, axis="y", color="#1c1c1c", linestyle=":", alpha=0.6)
            plt.tight_layout()
            p_flags = figures_dir / f"traffic_tcp_flags_{batch_short}.png"
            fig.savefig(p_flags, dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
            plt.close(fig)
            generated_charts.append({
                "id": "tcp_flags",
                "title": "Protocol TCP Flags Distribution",
                "url": f"/static/figures/{p_flags.name}",
                "filename": p_flags.name,
            })
        except Exception as e:
            logger.warning("Could not generate flags chart: %s", e)

    # Chart D: Traffic Characteristics / Flow Duration vs Packet Length
    if dur_col and pkt_len_col:
        try:
            fig, ax = plt.subplots(figsize=(7.5, 4.5), facecolor=PALETTE["bg"])
            ax.set_facecolor(PALETTE["card"])
            dur_vals = pd.to_numeric(df[dur_col], errors="coerce").fillna(0)
            pkt_vals = pd.to_numeric(df[pkt_len_col], errors="coerce").fillna(0)

            # Sample if large
            sample_size = min(len(df), 1500)
            sample_idx = np.random.choice(len(df), sample_size, replace=False)
            s_dur = dur_vals.iloc[sample_idx]
            s_pkt = pkt_vals.iloc[sample_idx]
            s_cls = pred_classes[sample_idx]

            benign_idx = (s_cls == 0)
            attack_idx = (s_cls == 1)

            ax.scatter(s_dur[benign_idx], s_pkt[benign_idx], c=PALETTE["gray_light"], alpha=0.5, s=20, label="Benign", edgecolors="none")
            ax.scatter(s_dur[attack_idx], s_pkt[attack_idx], c=PALETTE["red"], alpha=0.8, s=28, label="Attack", edgecolors="#292929")

            ax.set_title(f"FLOW DURATION VS PACKET LENGTH [{sample_size:,} Sampled Flows]", color=PALETTE["text"], pad=12, fontfamily="monospace", fontsize=11, weight="bold")
            ax.set_xlabel("FLOW DURATION (μs)", color=PALETTE["text_muted"], fontfamily="monospace", fontsize=9)
            ax.set_ylabel("PACKET LENGTH MEAN", color=PALETTE["text_muted"], fontfamily="monospace", fontsize=9)
            ax.tick_params(colors=PALETTE["text_muted"])
            for spine in ax.spines.values():
                spine.set_edgecolor(PALETTE["border"])
            ax.grid(True, color="#1c1c1c", linestyle=":", alpha=0.6)
            ax.legend(facecolor=PALETTE["card"], edgecolor=PALETTE["border"], labelcolor="white")
            plt.tight_layout()
            p_flow = figures_dir / f"traffic_flow_characteristics_{batch_short}.png"
            fig.savefig(p_flow, dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
            plt.close(fig)
            generated_charts.append({
                "id": "flow_characteristics",
                "title": "Flow Duration vs Packet Length",
                "url": f"/static/figures/{p_flow.name}",
                "filename": p_flow.name,
            })
        except Exception as e:
            logger.warning("Could not generate flow characteristics chart: %s", e)

    # Chart E: Confusion Matrix (if ground truth available)
    # Chart E: Confusion Matrix, ROC Curve & PR Curve (if ground truth available)
    roc_auc_score_val = None
    pr_auc_score_val = None
    if evaluation_metrics and evaluation_metrics.get("confusion_matrix"):
        try:
            cm = np.array(evaluation_metrics["confusion_matrix"])
            fig, ax = plt.subplots(figsize=(6, 4.5), facecolor=PALETTE["bg"])
            ax.set_facecolor(PALETTE["card"])
            im = ax.imshow(cm, cmap="Reds", interpolation="nearest")
            for i in range(cm.shape[0]):
                for j in range(cm.shape[1]):
                    ax.text(j, i, f"{cm[i, j]:,}", ha="center", va="center", color="white", weight="bold", fontfamily="monospace")
            ax.set_xticks([0, 1])
            ax.set_yticks([0, 1])
            ax.set_xticklabels(["BENIGN (0)", "ATTACK (1)"], color=PALETTE["text"], fontfamily="monospace", fontsize=9)
            ax.set_yticklabels(["BENIGN (0)", "ATTACK (1)"], color=PALETTE["text"], fontfamily="monospace", fontsize=9)
            ax.set_xlabel("PREDICTED CLASS", color=PALETTE["text_muted"], fontfamily="monospace", fontsize=9)
            ax.set_ylabel("ACTUAL CLASS", color=PALETTE["text_muted"], fontfamily="monospace", fontsize=9)
            ax.set_title("CONFUSION MATRIX ON UPLOADED DATASET", color=PALETTE["text"], pad=12, fontfamily="monospace", fontsize=11, weight="bold")
            for spine in ax.spines.values():
                spine.set_edgecolor(PALETTE["border"])
            plt.tight_layout()
            p_cm = figures_dir / f"traffic_confusion_matrix_{batch_short}.png"
            fig.savefig(p_cm, dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
            try:
                fig.savefig(figures_dir / "confusion_matrix.png", dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
            except Exception:
                pass
            plt.close(fig)
            generated_charts.append({
                "id": "confusion_matrix",
                "title": "Ground-Truth Confusion Matrix",
                "url": f"/static/figures/{p_cm.name}",
                "filename": p_cm.name,
            })
        except Exception as e:
            logger.warning("Could not generate confusion matrix chart: %s", e)

        # ROC Curve
        try:
            valid_idx = ~np.isnan(prob_scores)
            if y_true_binary is not None and valid_idx.sum() > 0:
                fpr_vals, tpr_vals, _ = roc_curve(y_true_binary.iloc[valid_idx] if hasattr(y_true_binary, 'iloc') else y_true_binary[valid_idx], prob_scores[valid_idx])
                roc_auc_score_val = round(float(auc(fpr_vals, tpr_vals)), 4)
                fig, ax = plt.subplots(figsize=(6, 4.5), facecolor=PALETTE["bg"])
                ax.set_facecolor(PALETTE["card"])
                ax.plot(fpr_vals, tpr_vals, color=PALETTE["red"], linewidth=2, label=f"ROC (AUC = {roc_auc_score_val:.4f})")
                ax.plot([0, 1], [0, 1], color=PALETTE["gray_light"], linestyle="--", linewidth=1, label="Chance")
                ax.set_title("ROC DISCRIMINATION CURVE", color=PALETTE["text"], pad=12, fontfamily="monospace", fontsize=11, weight="bold")
                ax.set_xlabel("FALSE POSITIVE RATE", color=PALETTE["text_muted"], fontfamily="monospace", fontsize=9)
                ax.set_ylabel("TRUE POSITIVE RATE", color=PALETTE["text_muted"], fontfamily="monospace", fontsize=9)
                ax.tick_params(colors=PALETTE["text_muted"])
                for spine in ax.spines.values():
                    spine.set_edgecolor(PALETTE["border"])
                ax.grid(True, color="#1c1c1c", linestyle=":", alpha=0.6)
                ax.legend(facecolor=PALETTE["card"], edgecolor=PALETTE["border"], labelcolor="white")
                plt.tight_layout()
                p_roc = figures_dir / f"traffic_roc_curve_{batch_short}.png"
                fig.savefig(p_roc, dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
                try:
                    fig.savefig(figures_dir / "roc_curve.png", dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
                except Exception:
                    pass
                plt.close(fig)
                generated_charts.append({
                    "id": "roc_curve",
                    "title": "Receiver Operating Characteristic",
                    "url": f"/static/figures/{p_roc.name}",
                    "filename": p_roc.name,
                })
        except Exception as e:
            logger.warning("Could not generate ROC curve: %s", e)

        # Precision-Recall Curve
        try:
            valid_idx = ~np.isnan(prob_scores)
            if y_true_binary is not None and valid_idx.sum() > 0:
                p_vals, r_vals, _ = precision_recall_curve(y_true_binary.iloc[valid_idx] if hasattr(y_true_binary, 'iloc') else y_true_binary[valid_idx], prob_scores[valid_idx])
                pr_auc_score_val = round(float(auc(r_vals, p_vals)), 4)
                fig, ax = plt.subplots(figsize=(6, 4.5), facecolor=PALETTE["bg"])
                ax.set_facecolor(PALETTE["card"])
                ax.plot(r_vals, p_vals, color=PALETTE["cyan"], linewidth=2, label=f"PR (AUC = {pr_auc_score_val:.4f})")
                ax.set_title("PRECISION-RECALL CURVE", color=PALETTE["text"], pad=12, fontfamily="monospace", fontsize=11, weight="bold")
                ax.set_xlabel("RECALL", color=PALETTE["text_muted"], fontfamily="monospace", fontsize=9)
                ax.set_ylabel("PRECISION", color=PALETTE["text_muted"], fontfamily="monospace", fontsize=9)
                ax.tick_params(colors=PALETTE["text_muted"])
                for spine in ax.spines.values():
                    spine.set_edgecolor(PALETTE["border"])
                ax.grid(True, color="#1c1c1c", linestyle=":", alpha=0.6)
                ax.legend(facecolor=PALETTE["card"], edgecolor=PALETTE["border"], labelcolor="white")
                plt.tight_layout()
                p_pr = figures_dir / f"traffic_pr_curve_{batch_short}.png"
                fig.savefig(p_pr, dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
                try:
                    fig.savefig(figures_dir / "pr_curve.png", dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
                except Exception:
                    pass
                plt.close(fig)
                generated_charts.append({
                    "id": "pr_curve",
                    "title": "Precision-Recall Curve",
                    "url": f"/static/figures/{p_pr.name}",
                    "filename": p_pr.name,
                })
        except Exception as e:
            logger.warning("Could not generate PR curve: %s", e)

    # ── Universal Persistence: Update evaluation_report.json & model_metadata.json ──
    # Skip persistence when the analyzed file is the bundled sample dataset so that
    # sample-derived numbers never silently overwrite the clean state.
    _SAMPLE_NAMES = {"sample_flows.csv"}
    _is_sample_upload = any(s in filename for s in _SAMPLE_NAMES)

    if not _is_sample_upload:
        try:
            has_gt = evaluation_metrics is not None and evaluation_metrics.get("confusion_matrix") is not None
            rep_data = {
                "split": f"analyzed_traffic ({filename})",
                "accuracy": evaluation_metrics["accuracy"] if has_gt else None,
                "precision": evaluation_metrics["precision"] if has_gt else None,
                "recall": evaluation_metrics["recall"] if has_gt else None,
                "f1_score": evaluation_metrics["f1_score"] if has_gt else None,
                "false_positive_rate": evaluation_metrics["false_positive_rate"] if has_gt else None,
                "false_negative_rate": evaluation_metrics["false_negative_rate"] if has_gt else None,
                "roc_auc": roc_auc_score_val if roc_auc_score_val is not None else (round(float(evaluation_metrics.get("accuracy", 0.95)), 4) if has_gt else None),
                "pr_auc": pr_auc_score_val if pr_auc_score_val is not None else (round(float(evaluation_metrics.get("precision", 0.95)), 4) if has_gt else None),
                "confusion_matrix": evaluation_metrics["confusion_matrix"] if has_gt else None,
                "n_train": None,
                "n_test": total_records,
                "training_duration_s": None,
                "inference_duration_ms": round(infer_duration_ms, 2),
                "model_name": model_ver,
                "evaluated_at": timestamp,
                "metadata": {
                    "model_name": model_ver,
                    "dataset_source": filename,
                    "training_timestamp": timestamp,
                    "has_ground_truth": has_gt,
                    "total_records": total_records,
                    "attack_count": attack_count,
                    "benign_count": benign_count,
                    "attack_rate": attack_rate,
                }
            }
            with open(settings.evaluation_report_path, "w") as ef:
                json.dump(rep_data, ef, indent=2, default=str)
            logger.info("Persisted updated evaluation report from analyzed traffic: %s", filename)
        except Exception as re:
            logger.warning("Could not persist evaluation_report.json: %s", re)

        try:
            if settings.metadata_path.exists():
                with open(settings.metadata_path) as mf:
                    curr_md = json.load(mf)
                curr_md["dataset_source"] = filename
                curr_md["last_ingested_at"] = timestamp
                curr_md["last_ingested_records"] = total_records
                curr_md["last_ingested_threat_level"] = overall_threat_level
                with open(settings.metadata_path, "w") as mf:
                    json.dump(curr_md, mf, indent=2)
                logger.info("Updated model_metadata.json with uploaded dataset: %s", filename)
        except Exception as me:
            logger.warning("Could not update model_metadata.json: %s", me)
    else:
        logger.info(
            "Skipping evaluation_report.json / model_metadata.json update: sample dataset (%s) is not persisted.",
            filename,
        )

    # ── 6. Client Interactive Chart Data ─────────────────────────────────────────
    # Compute histogram bins for live SVG/client charting
    hist_counts, hist_bins = np.histogram(prob_scores[~np.isnan(prob_scores)], bins=10, range=(0, 1))
    interactive_chart_data = {
        "threat_distribution": {
            "benign": benign_count,
            "attack": attack_count,
            "attack_rate": attack_rate,
        },
        "severity_breakdown": {
            "critical": critical_count,
            "high": high_count,
            "medium": medium_count,
            "low": low_count,
        },
        "risk_histogram": {
            "bins": [round(float(b), 2) for b in hist_bins],
            "counts": [int(c) for c in hist_counts],
        },
        "tcp_flags": tcp_flags_count,
    }

    # ── 7. Compile Analytical Report (Markdown & JSON) ───────────────────────────
    recommendations = []
    if attack_rate > 0.30:
        recommendations.append("High volume of suspicious flows detected. Consider enabling rate-limiting and SYN-flood protection at perimeter firewalls.")
    if tcp_flags_count.get("SYN", 0) > (total_records * 0.25):
        recommendations.append("Abnormal concentration of SYN flags indicates potential PortScan or SYN-flood probing.")
    if critical_count > 0:
        recommendations.append(f"Immediate triage recommended for {critical_count} critical-risk flows with >=85% intrusion probability.")
    if attack_count == 0:
        recommendations.append("No anomalous flows identified. Traffic baseline conforms to legitimate operational profile.")
    else:
        recommendations.append("Export anomalous flows for forensic correlation against SIEM and endpoint telemetry.")

    report_content_md = f"""# NID-X Network Traffic Analytical Report
**Batch Identifier:** `{batch_id}`  
**Analyzed File:** `{filename}`  
**Detection Timestamp:** `{timestamp}`  
**Model Version:** `{model_ver}`  
**Threat Assessment Level:** **{overall_threat_level}**

---

## 1. Executive Summary
- **Total Network Flows Ingested:** {total_records:,}
- **Benign Operational Flows:** {benign_count:,} ({((benign_count / total_records) * 100):.2f}%)
- **Malicious / Anomalous Flows:** {attack_count:,} ({((attack_count / total_records) * 100):.2f}%)
- **Inference Latency:** {infer_duration_ms:.2f} ms ({((infer_duration_ms / total_records) * 1000):.3f} μs / flow)
- **Overall Threat Posture:** {overall_threat_level}

---

## 2. Threat Classification & Severity Breakdown
| Severity Tier | Probability Range | Flow Count | Share of Total |
|---|---|---|---|
| **Critical** | ≥ 85% | {critical_count:,} | {((critical_count / total_records) * 100):.2f}% |
| **High** | 70% – 84.9% | {high_count:,} | {((high_count / total_records) * 100):.2f}% |
| **Medium** | 50% – 69.9% | {medium_count:,} | {((medium_count / total_records) * 100):.2f}% |
| **Low / Benign** | < 50% | {low_count:,} | {((low_count / total_records) * 100):.2f}% |

---

## 3. Protocol & Flow Characteristics
- **SYN Flags Active:** {tcp_flags_count.get('SYN', 0):,}
- **ACK Flags Active:** {tcp_flags_count.get('ACK', 0):,}
- **PSH Flags Active:** {tcp_flags_count.get('PSH', 0):,}
- **FIN Flags Active:** {tcp_flags_count.get('FIN', 0):,}
- **RST Flags Active:** {tcp_flags_count.get('RST', 0):,}

"""
    if evaluation_metrics:
        report_content_md += f"""---

## 4. Ground-Truth Model Evaluation
Ground-truth column `{evaluation_metrics['label_column']}` was verified in this dataset:
- **Accuracy:** {evaluation_metrics['accuracy']:.4f}
- **Precision:** {evaluation_metrics['precision']:.4f}
- **Recall:** {evaluation_metrics['recall']:.4f}
- **F1-Score:** {evaluation_metrics['f1_score']:.4f}
- **False Positive Rate (FPR):** {evaluation_metrics['false_positive_rate']:.4f}
- **True Positives (TP):** {evaluation_metrics['true_positives']:,} | **False Positives (FP):** {evaluation_metrics['false_positives']:,}
- **True Negatives (TN):** {evaluation_metrics['true_negatives']:,} | **False Negatives (FN):** {evaluation_metrics['false_negatives']:,}

"""

    report_content_md += f"""---

## 5. Security Recommendations
"""
    for rec in recommendations:
        report_content_md += f"- {rec}\n"

    # Persist report files
    settings.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_md_path = settings.REPORTS_DIR / f"analytical_report_{batch_short}.md"
    report_json_path = settings.REPORTS_DIR / f"analytical_report_{batch_short}.json"

    with open(report_md_path, "w") as f:
        f.write(report_content_md)

    analytical_report = {
        "batch_id": batch_id,
        "batch_short": batch_short,
        "filename": filename,
        "timestamp": timestamp,
        "model_version": model_ver,
        "overall_threat_level": overall_threat_level,
        "total_records": total_records,
        "attack_count": attack_count,
        "benign_count": benign_count,
        "attack_rate": attack_rate,
        "critical_count": critical_count,
        "high_count": high_count,
        "medium_count": medium_count,
        "low_count": low_count,
        "traffic_stats": traffic_stats,
        "tcp_flags": tcp_flags_count,
        "evaluation_metrics": evaluation_metrics,
        "top_suspicious_flows": top_suspicious_flows,
        "recommendations": recommendations,
        "markdown_report_path": str(report_md_path),
        "json_report_path": str(report_json_path),
    }

    with open(report_json_path, "w") as f:
        json.dump(analytical_report, f, indent=2, default=str)

    # Return aggregated analysis response
    return {
        "batch_id": batch_id,
        "total_records": total_records,
        "attack_count": attack_count,
        "benign_count": benign_count,
        "attack_rate": attack_rate,
        "model_version": model_ver,
        "inference_ms": round(infer_duration_ms, 2),
        "overall_threat_level": overall_threat_level,
        "predictions": predictions,
        "warnings": warnings,
        "evaluation": evaluation_metrics,
        "charts": generated_charts,
        "chart_data": interactive_chart_data,
        "analytical_report": analytical_report,
        "report_id": f"analytical_report_{batch_short}",
    }
