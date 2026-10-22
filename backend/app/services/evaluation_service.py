"""Model evaluation: metrics, charts, reports."""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score, average_precision_score, classification_report,
    confusion_matrix, f1_score, precision_recall_curve, precision_score,
    recall_score, roc_auc_score, roc_curve,
)

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


def evaluate_model(
    pipeline,
    X: pd.DataFrame,
    y: pd.Series,
    binary: bool = True,
    split: str = "test",
    label_names: Optional[List[str]] = None,
    threshold: float = 0.5,
) -> dict:
    """Compute metrics from ground-truth labels and pipeline predictions."""
    t0 = time.perf_counter()
    y_prob = None

    if hasattr(pipeline, "predict_proba"):
        y_prob = pipeline.predict_proba(X)
        if binary:
            y_score = y_prob[:, 1]
            y_pred = (y_score >= threshold).astype(int)
        else:
            y_pred = np.argmax(y_prob, axis=1)
            y_score = None
    else:
        y_pred = pipeline.predict(X)
        y_score = None

    infer_ms = (time.perf_counter() - t0) * 1000

    acc = float(accuracy_score(y, y_pred))
    prec = float(precision_score(y, y_pred, average="weighted", zero_division=0))
    rec = float(recall_score(y, y_pred, average="weighted", zero_division=0))
    f1 = float(f1_score(y, y_pred, average="weighted", zero_division=0))

    cm = confusion_matrix(y, y_pred).tolist()

    # FPR / FNR (binary)
    fpr, fnr = None, None
    if binary and len(cm) == 2:
        tn, fp, fn, tp = confusion_matrix(y, y_pred).ravel()
        fpr = float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0
        fnr = float(fn / (fn + tp)) if (fn + tp) > 0 else 0.0

    # ROC-AUC
    roc_auc = None
    if binary and y_score is not None:
        try:
            roc_auc = float(roc_auc_score(y, y_score))
        except Exception:
            pass

    # PR-AUC
    pr_auc = None
    if binary and y_score is not None:
        try:
            pr_auc = float(average_precision_score(y, y_score))
        except Exception:
            pass

    # Per-class
    report = classification_report(y, y_pred, output_dict=True, zero_division=0)
    per_class = {
        str(k): {
            "precision": round(v["precision"], 4),
            "recall": round(v["recall"], 4),
            "f1_score": round(v["f1-score"], 4),
            "support": int(v["support"]),
        }
        for k, v in report.items()
        if k not in ("accuracy", "macro avg", "weighted avg")
    }

    return {
        "split": split,
        "accuracy": round(acc, 4),
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1_score": round(f1, 4),
        "false_positive_rate": round(fpr, 4) if fpr is not None else None,
        "false_negative_rate": round(fnr, 4) if fnr is not None else None,
        "roc_auc": round(roc_auc, 4) if roc_auc is not None else None,
        "pr_auc": round(pr_auc, 4) if pr_auc is not None else None,
        "confusion_matrix": cm,
        "per_class": per_class,
        "inference_duration_ms": round(infer_ms, 2),
    }


def save_evaluation_report(metrics: dict, metadata: dict) -> Path:
    report = {**metrics, "metadata": metadata}
    path = settings.evaluation_report_path
    with open(path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    return path


def load_evaluation_report() -> Optional[dict]:
    path = settings.evaluation_report_path
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def generate_figures(
    pipeline,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    binary: bool = True,
    full_df: Optional[pd.DataFrame] = None,
) -> List[Path]:
    """Generate and save all required EDA and evaluation figures in dark brutalist theme."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import seaborn as sns
    from sklearn.inspection import permutation_importance

    figures_dir = settings.FIGURES_DIR
    figures_dir.mkdir(parents=True, exist_ok=True)
    saved: List[Path] = []

    plt.rcParams["text.color"] = "#F5F5F5"
    plt.rcParams["axes.labelcolor"] = "#A0A0A0"
    plt.rcParams["xtick.color"] = "#A0A0A0"
    plt.rcParams["ytick.color"] = "#A0A0A0"

    try:
        y_pred = pipeline.predict(X_test)

        # ── 1. Confusion Matrix ───────────────────────────────────────────
        cm = confusion_matrix(y_test, y_pred)
        fig, ax = plt.subplots(figsize=(6, 5), facecolor="#050505")
        ax.set_facecolor("#101010")
        sns.heatmap(
            cm, annot=True, fmt="d", cmap="Reds", ax=ax,
            annot_kws={"color": "white", "weight": "bold"},
            linewidths=1, linecolor="#292929", cbar=False,
        )
        ax.set_title("CONFUSION MATRIX [HELD-OUT TEST SET]", color="#F5F5F5", pad=12, fontfamily="monospace", fontsize=11)
        ax.set_xlabel("PREDICTED CLASS", color="#A0A0A0", fontfamily="monospace", fontsize=9)
        ax.set_ylabel("ACTUAL CLASS", color="#A0A0A0", fontfamily="monospace", fontsize=9)
        ax.tick_params(colors="#A0A0A0")
        for spine in ax.spines.values():
            spine.set_edgecolor("#292929")
        plt.tight_layout()
        p = figures_dir / "confusion_matrix.png"
        fig.savefig(p, dpi=120, bbox_inches="tight", facecolor=fig.get_facecolor())
        plt.close(fig)
        saved.append(p)

        # ── 2. ROC & PR Curves (Binary) ──────────────────────────────────
        if binary and hasattr(pipeline, "predict_proba"):
            y_prob = pipeline.predict_proba(X_test)[:, 1]

            # ROC
            fpr_arr, tpr_arr, _ = roc_curve(y_test, y_prob)
            auc = roc_auc_score(y_test, y_prob)
            fig, ax = plt.subplots(figsize=(6, 5), facecolor="#050505")
            ax.set_facecolor("#101010")
            ax.plot(fpr_arr, tpr_arr, color="#FF3038", lw=2.5, label=f"ROC-AUC: {auc:.4f}")
            ax.plot([0, 1], [0, 1], color="#444", lw=1, linestyle="--", label="Random Baseline")
            ax.set_xlabel("FALSE POSITIVE RATE (FPR)", color="#A0A0A0", fontfamily="monospace", fontsize=9)
            ax.set_ylabel("TRUE POSITIVE RATE (TPR)", color="#A0A0A0", fontfamily="monospace", fontsize=9)
            ax.set_title("ROC CURVE", color="#F5F5F5", pad=12, fontfamily="monospace", fontsize=11)
            ax.tick_params(colors="#A0A0A0")
            ax.legend(facecolor="#101010", edgecolor="#292929", labelcolor="white")
            for spine in ax.spines.values():
                spine.set_edgecolor("#292929")
            ax.grid(True, color="#1e1e1e", linestyle="--", alpha=0.5)
            plt.tight_layout()
            p = figures_dir / "roc_curve.png"
            fig.savefig(p, dpi=120, bbox_inches="tight", facecolor=fig.get_facecolor())
            plt.close(fig)
            saved.append(p)

            # PR Curve
            prec_arr, rec_arr, _ = precision_recall_curve(y_test, y_prob)
            pr_auc = average_precision_score(y_test, y_prob)
            fig, ax = plt.subplots(figsize=(6, 5), facecolor="#050505")
            ax.set_facecolor("#101010")
            ax.plot(rec_arr, prec_arr, color="#FF3038", lw=2.5, label=f"PR-AUC (AP): {pr_auc:.4f}")
            ax.set_xlabel("RECALL", color="#A0A0A0", fontfamily="monospace", fontsize=9)
            ax.set_ylabel("PRECISION", color="#A0A0A0", fontfamily="monospace", fontsize=9)
            ax.set_title("PRECISION-RECALL CURVE", color="#F5F5F5", pad=12, fontfamily="monospace", fontsize=11)
            ax.tick_params(colors="#A0A0A0")
            ax.legend(facecolor="#101010", edgecolor="#292929", labelcolor="white")
            for spine in ax.spines.values():
                spine.set_edgecolor("#292929")
            ax.grid(True, color="#1e1e1e", linestyle="--", alpha=0.5)
            plt.tight_layout()
            p = figures_dir / "pr_curve.png"
            fig.savefig(p, dpi=120, bbox_inches="tight", facecolor=fig.get_facecolor())
            plt.close(fig)
            saved.append(p)

        # ── 3. Feature Importance ─────────────────────────────────────────
        clf = pipeline.named_steps.get("clf")
        importances = None
        names = None
        if hasattr(clf, "feature_importances_"):
            importances = clf.feature_importances_
            names = X_test.columns.tolist()
        elif hasattr(clf, "coef_"):
            importances = np.abs(clf.coef_[0])
            names = X_test.columns.tolist()
        else:
            try:
                # Permutation importance (sample for speed)
                sample_idx = np.random.choice(len(X_test), min(len(X_test), 200), replace=False)
                perm = permutation_importance(
                    pipeline, X_test.iloc[sample_idx], y_test.iloc[sample_idx],
                    n_repeats=3, random_state=42, n_jobs=1
                )
                importances = perm.importances_mean
                names = X_test.columns.tolist()
            except Exception as pe:
                logger.debug("Permutation importance fallback skipped: %s", pe)

        if importances is not None and names is not None and len(importances) == len(names):
            top_n = min(15, len(importances))
            idx = np.argsort(importances)[-top_n:]
            fig, ax = plt.subplots(figsize=(8, 5.5), facecolor="#050505")
            ax.set_facecolor("#101010")
            ax.barh(range(top_n), importances[idx], color="#FF3038", alpha=0.85, edgecolor="#FF3038")
            ax.set_yticks(range(top_n))
            clean_names = [str(names[i])[:28] for i in idx]
            ax.set_yticklabels(clean_names, color="#F5F5F5", fontfamily="monospace", fontsize=8)
            ax.set_title(f"TOP {top_n} FEATURE IMPORTANCES", color="#F5F5F5", pad=12, fontfamily="monospace", fontsize=11)
            ax.set_xlabel("IMPORTANCE SCORE", color="#A0A0A0", fontfamily="monospace", fontsize=9)
            ax.tick_params(colors="#A0A0A0")
            for spine in ax.spines.values():
                spine.set_edgecolor("#292929")
            ax.grid(True, axis="x", color="#1e1e1e", linestyle="--", alpha=0.5)
            plt.tight_layout()
            p = figures_dir / "feature_importance.png"
            fig.savefig(p, dpi=120, bbox_inches="tight", facecolor=fig.get_facecolor())
            plt.close(fig)
            saved.append(p)

        # ── 4. Class Distribution ─────────────────────────────────────────
        fig, ax = plt.subplots(figsize=(6, 4.5), facecolor="#050505")
        ax.set_facecolor("#101010")
        counts = y_test.value_counts().sort_index()
        class_labels = ["BENIGN (0)", "ATTACK (1)"] if binary and len(counts) == 2 else [f"Class {k}" for k in counts.index]
        colors = ["#444444", "#FF3038"] if binary and len(counts) == 2 else ["#FF3038"] * len(counts)
        bars = ax.bar(class_labels, counts.values, color=colors, edgecolor="#292929", width=0.45)
        for b in bars:
            h = b.get_height()
            ax.annotate(
                f"{int(h):,} ({h/len(y_test):.1%})",
                xy=(b.get_x() + b.get_width() / 2, h),
                xytext=(0, 4), textcoords="offset points",
                ha="center", va="bottom", color="#F5F5F5", fontfamily="monospace", fontsize=8,
            )
        ax.set_title("CLASS DISTRIBUTION [HELD-OUT TEST SET]", color="#F5F5F5", pad=12, fontfamily="monospace", fontsize=11)
        ax.set_ylabel("FLOW COUNT", color="#A0A0A0", fontfamily="monospace", fontsize=9)
        ax.tick_params(colors="#A0A0A0")
        for spine in ax.spines.values():
            spine.set_edgecolor("#292929")
        ax.grid(True, axis="y", color="#1e1e1e", linestyle="--", alpha=0.5)
        plt.tight_layout()
        p = figures_dir / "class_distribution.png"
        fig.savefig(p, dpi=120, bbox_inches="tight", facecolor=fig.get_facecolor())
        plt.close(fig)
        saved.append(p)

        # ── 5. Numeric Feature Distributions ──────────────────────────────
        num_cols = X_test.select_dtypes(include=[np.number]).columns.tolist()[:4]
        if num_cols:
            fig, axes = plt.subplots(2, 2, figsize=(9, 6), facecolor="#050505")
            axes = axes.flatten()
            for i, col in enumerate(num_cols):
                ax = axes[i]
                ax.set_facecolor("#101010")
                vals = X_test[col].dropna()
                # Clip extreme outliers for visualization
                p99 = np.percentile(vals, 99) if len(vals) > 0 else 1
                filtered = vals[vals <= p99]
                ax.hist(filtered, bins=25, color="#FF3038", alpha=0.75, edgecolor="#101010")
                ax.set_title(str(col)[:22], color="#F5F5F5", fontfamily="monospace", fontsize=9)
                ax.tick_params(colors="#686868", labelsize=7)
                for spine in ax.spines.values():
                    spine.set_edgecolor("#292929")
                ax.grid(True, color="#1a1a1a", linestyle=":", alpha=0.5)
            fig.suptitle("NUMERIC FEATURE DISTRIBUTIONS [TRUNCATED AT 99TH PCT]", color="#F5F5F5", fontfamily="monospace", fontsize=10)
            plt.tight_layout()
            p = figures_dir / "numeric_distributions.png"
            fig.savefig(p, dpi=120, bbox_inches="tight", facecolor=fig.get_facecolor())
            plt.close(fig)
            saved.append(p)

        # ── 6. Correlation Heatmap ────────────────────────────────────────
        corr_cols = X_test.select_dtypes(include=[np.number]).columns.tolist()[:8]
        if len(corr_cols) >= 3:
            fig, ax = plt.subplots(figsize=(7, 5.5), facecolor="#050505")
            ax.set_facecolor("#101010")
            corr = X_test[corr_cols].corr()
            sns.heatmap(
                corr, annot=True, fmt=".2f", cmap="vlag", center=0, ax=ax,
                annot_kws={"color": "white", "fontsize": 7},
                linewidths=0.5, linecolor="#292929", cbar=False,
            )
            ax.set_title("FEATURE CORRELATION MATRIX", color="#F5F5F5", pad=12, fontfamily="monospace", fontsize=11)
            ax.tick_params(colors="#A0A0A0", labelsize=8)
            for spine in ax.spines.values():
                spine.set_edgecolor("#292929")
            plt.tight_layout()
            p = figures_dir / "correlation_heatmap.png"
            fig.savefig(p, dpi=120, bbox_inches="tight", facecolor=fig.get_facecolor())
            plt.close(fig)
            saved.append(p)

        # ── 7. Model Comparison Chart ─────────────────────────────────────
        if settings.comparison_path.exists():
            try:
                comp_df = pd.read_csv(settings.comparison_path)
                if not comp_df.empty and "model" in comp_df.columns:
                    fig, ax = plt.subplots(figsize=(8, 4.5), facecolor="#050505")
                    ax.set_facecolor("#101010")
                    x = np.arange(len(comp_df))
                    width = 0.28
                    ax.bar(x - width/2, comp_df["cv_f1"], width, label="CV F1", color="#686868", edgecolor="#292929")
                    ax.bar(x + width/2, comp_df["val_f1"], width, label="Validation F1", color="#FF3038", edgecolor="#292929")
                    ax.set_xticks(x)
                    ax.set_xticklabels(comp_df["model"], color="#F5F5F5", fontfamily="monospace", fontsize=8)
                    ax.set_ylabel("F1 SCORE", color="#A0A0A0", fontfamily="monospace", fontsize=9)
                    ax.set_title("CANDIDATE MODEL COMPARISON [CV F1 vs VAL F1]", color="#F5F5F5", pad=12, fontfamily="monospace", fontsize=11)
                    ax.tick_params(colors="#A0A0A0")
                    ax.legend(facecolor="#101010", edgecolor="#292929", labelcolor="white")
                    ax.set_ylim(0, 1.05)
                    for spine in ax.spines.values():
                        spine.set_edgecolor("#292929")
                    ax.grid(True, axis="y", color="#1e1e1e", linestyle="--", alpha=0.5)
                    plt.tight_layout()
                    p = figures_dir / "model_comparison.png"
                    fig.savefig(p, dpi=120, bbox_inches="tight", facecolor=fig.get_facecolor())
                    plt.close(fig)
                    saved.append(p)
            except Exception as ce:
                logger.debug("Model comparison chart error: %s", ce)

        # ── 8. Error Analysis ─────────────────────────────────────────────
        if binary and len(cm) == 2:
            tn, fp, fn, tp = cm.ravel()
            total_cases = tn + fp + fn + tp
            fig, ax = plt.subplots(figsize=(6, 4.5), facecolor="#050505")
            ax.set_facecolor("#101010")
            categories = ["TN\n(Benign OK)", "FP\n(False Alarm)", "FN\n(Missed Attack)", "TP\n(Detected Attack)"]
            vals = [tn, fp, fn, tp]
            colors = ["#2a2a2a", "#883030", "#FF3038", "#444444"]
            bars = ax.bar(categories, vals, color=colors, edgecolor="#292929", width=0.5)
            for b, v in zip(bars, vals):
                ax.annotate(
                    f"{v}\n({v/total_cases:.1%})",
                    xy=(b.get_x() + b.get_width() / 2, b.get_height()),
                    xytext=(0, 4), textcoords="offset points",
                    ha="center", va="bottom", color="#F5F5F5", fontfamily="monospace", fontsize=8,
                )
            ax.set_title("SECURITY ERROR ANALYSIS [DETECTION OUTCOMES]", color="#F5F5F5", pad=12, fontfamily="monospace", fontsize=11)
            ax.tick_params(colors="#A0A0A0")
            for spine in ax.spines.values():
                spine.set_edgecolor("#292929")
            ax.grid(True, axis="y", color="#1e1e1e", linestyle="--", alpha=0.5)
            plt.tight_layout()
            p = figures_dir / "error_analysis.png"
            fig.savefig(p, dpi=120, bbox_inches="tight", facecolor=fig.get_facecolor())
            plt.close(fig)
            saved.append(p)

    except Exception as e:
        logger.warning("Figure generation error: %s", e)

    return saved

