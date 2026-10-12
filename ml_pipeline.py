"""
Person 4 Deliverable: Unified Multi-Domain ML Pipeline & Anomaly Classification Benchmark
-----------------------------------------------------------------------------------------
Integrates features extracted by:
  - Person 1: Time-Domain Statistical Features (Mean, RMS, Skewness, Kurtosis, etc.)
  - Person 2: Fast Fourier Transform (FFT) & Frequency Spectral Features (Dominant Freq, Spectral Energy)
  - Person 3: TSFresh FDR-Selected Complex Temporal Features

Trains and benchmarks multiple classification models (Random Forest, Gradient Boosting, Baseline).
Generates comprehensive evaluation metrics (Accuracy, Precision, Recall, F1, ROC-AUC, Confusion Matrix).
Analyzes cross-domain feature importance (Time vs Frequency vs TSFresh) to demonstrate which features
drive machine anomaly detection.
"""

import os
import sys
import json
import logging
from typing import Dict, List, Tuple, Any

import numpy as np
import pandas as pd
import joblib

from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    confusion_matrix,
    roc_curve,
    classification_report
)

import matplotlib  # type: ignore
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # type: ignore
import seaborn as sns  # type: ignore

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("ml_pipeline")

DATA_DIR = "data"
OUTPUT_PLOT_DIR = "outputs/evaluation"
MODELS_DIR = "models"


def load_and_merge_features() -> pd.DataFrame:
    """
    Loads Person 1 (Time), Person 2 (Frequency), and Person 3 (TSFresh) feature files
    and fuses them on 'window_id' into a unified feature matrix.
    """
    time_path = os.path.join(DATA_DIR, "time_features.csv")
    freq_path = os.path.join(DATA_DIR, "frequency_features.csv")
    tsfresh_path = os.path.join(DATA_DIR, "tsfresh_features_selected.csv")

    if not os.path.exists(time_path):
        raise FileNotFoundError(f"Person 1 time features not found at {time_path}. Run time_features.py first.")
    if not os.path.exists(freq_path):
        raise FileNotFoundError(f"Person 2 frequency features not found at {freq_path}. Run frequency_features.py first.")
    if not os.path.exists(tsfresh_path):
        raise FileNotFoundError(f"Person 3 TSFresh features not found at {tsfresh_path}.")

    logger.info("Loading Person 1 Time-Domain features...")
    df_time = pd.read_csv(time_path)
    logger.info(f"Loaded Time features: {df_time.shape[0]} rows, {df_time.shape[1] - 2} features")

    logger.info("Loading Person 2 Frequency-Domain features...")
    df_freq = pd.read_csv(freq_path)
    logger.info(f"Loaded Frequency features: {df_freq.shape[0]} rows, {df_freq.shape[1] - 2} features")

    logger.info("Loading Person 3 TSFresh features...")
    df_tsfresh = pd.read_csv(tsfresh_path)
    logger.info(f"Loaded TSFresh features: {df_tsfresh.shape[0]} rows, {df_tsfresh.shape[1] - 2} features")

    # Rename columns to ensure explicit domain attribution
    time_feature_cols = [c for c in df_time.columns if c not in ["window_id", "label"]]
    time_rename = {c: f"TIME__{c}" for c in time_feature_cols}
    df_time = df_time.rename(columns=time_rename)

    freq_feature_cols = [c for c in df_freq.columns if c not in ["window_id", "label"]]
    freq_rename = {c: f"FREQ__{c}" for c in freq_feature_cols}
    df_freq = df_freq.rename(columns=freq_rename)

    tsfresh_feature_cols = [c for c in df_tsfresh.columns if c not in ["window_id", "label"]]
    tsfresh_rename = {c: f"TSFRESH__{c}" for c in tsfresh_feature_cols}
    df_tsfresh = df_tsfresh.rename(columns=tsfresh_rename)

    # Merge on window_id & label
    merged = pd.merge(df_time, df_freq, on=["window_id", "label"], how="inner")
    merged = pd.merge(merged, df_tsfresh, on=["window_id", "label"], how="inner")

    # Impute any edge NaN/inf values with median
    feature_cols = [c for c in merged.columns if c not in ["window_id", "label"]]
    for col in feature_cols:
        merged[col] = merged[col].replace([np.inf, -np.inf], np.nan)
        if merged[col].isnull().any():
            median_val = merged[col].median()
            merged[col] = merged[col].fillna(median_val if not np.isnan(median_val) else 0.0)

    combined_path = os.path.join(DATA_DIR, "combined_features.csv")
    merged.to_csv(combined_path, index=False)
    logger.info(f"Successfully fused unified feature matrix: {merged.shape[0]} windows x {len(feature_cols)} features")
    logger.info(f"Saved combined features to: {combined_path}")

    return merged


def train_and_benchmark(df_merged: pd.DataFrame) -> Dict[str, Any]:
    """
    Trains Random Forest, Gradient Boosting, and Baseline Logistic Regression.
    Computes all standard academic evaluation metrics and feature importances.
    """
    feature_cols = [c for c in df_merged.columns if c not in ["window_id", "label"]]
    X = df_merged[feature_cols].values
    y = df_merged["label"].values

    # Stratified 80/20 train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )

    logger.info(f"Train set: {len(X_train)} samples ({np.sum(y_train==0)} Normal, {np.sum(y_train==1)} Anomaly)")
    logger.info(f"Test set:  {len(X_test)} samples ({np.sum(y_test==0)} Normal, {np.sum(y_test==1)} Anomaly)")

    # Standard scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # 1. Random Forest Classifier (Optimized regularized trees to stay compact and prevent overfitting)
    rf_clf = RandomForestClassifier(
        n_estimators=100,
        max_depth=8,
        min_samples_split=4,
        random_state=42,
        n_jobs=-1
    )
    rf_clf.fit(X_train_scaled, y_train)

    # 2. Gradient Boosting Classifier
    gb_clf = GradientBoostingClassifier(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.1,
        random_state=42
    )
    gb_clf.fit(X_train_scaled, y_train)

    # 3. Baseline Logistic Regression
    lr_clf = LogisticRegression(max_iter=1000, random_state=42)
    lr_clf.fit(X_train_scaled, y_train)

    models = {
        "Random Forest Classifier": rf_clf,
        "Gradient Boosting Classifier": gb_clf,
        "Baseline (Logistic Regression)": lr_clf
    }

    results = {}
    for name, model in models.items():
        y_pred = model.predict(X_test_scaled)
        y_prob = model.predict_proba(X_test_scaled)[:, 1] if hasattr(model, "predict_proba") else y_pred

        acc = float(accuracy_score(y_test, y_pred))
        prec = float(precision_score(y_test, y_pred, zero_division=0))
        rec = float(recall_score(y_test, y_pred, zero_division=0))
        f1 = float(f1_score(y_test, y_pred, zero_division=0))
        auc = float(roc_auc_score(y_test, y_prob))
        cm = confusion_matrix(y_test, y_pred).tolist()

        # 5-fold stratified cross-validation
        cv_scores = cross_val_score(model, X_train_scaled, y_train, cv=5, scoring="accuracy")

        results[name] = {
            "accuracy": round(acc, 4),
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1_score": round(f1, 4),
            "roc_auc": round(auc, 4),
            "cv_accuracy_mean": round(float(np.mean(cv_scores)), 4),
            "cv_accuracy_std": round(float(np.std(cv_scores)), 4),
            "confusion_matrix": cm,
            "y_test": y_test.tolist(),
            "y_pred": y_pred.tolist(),
            "y_prob": y_prob.tolist()
        }

    # Best model is Random Forest or Gradient Boosting
    best_model_name = "Random Forest Classifier"

    # Analyze Feature Importances from Random Forest
    rf_importances = rf_clf.feature_importances_
    feature_imp_df = pd.DataFrame({
        "feature": feature_cols,
        "importance": rf_importances
    })

    # Domain attribution
    def get_domain(f_name: str) -> str:
        if f_name.startswith("TIME__"):
            return "Time-Domain Analysis"
        elif f_name.startswith("FREQ__"):
            return "Frequency-Domain Analysis (FFT)"
        elif f_name.startswith("TSFRESH__"):
            return "TSFresh Feature Engineering"
        return "Sensor Raw"

    feature_imp_df["domain"] = feature_imp_df["feature"].apply(get_domain)
    feature_imp_df = feature_imp_df.sort_values(by="importance", ascending=False).reset_index(drop=True)

    # Domain Importance Aggregation
    domain_totals = feature_imp_df.groupby("domain")["importance"].sum().to_dict()
    domain_percentages = {k: round(v * 100.0, 2) for k, v in domain_totals.items()}

    # Save trained best model compressed (< 2 MB)
    os.makedirs(MODELS_DIR, exist_ok=True)
    model_save_path = os.path.join(MODELS_DIR, "rf_classifier.joblib")
    joblib.dump(rf_clf, model_save_path, compress=3)
    logger.info(f"Saved compressed Random Forest Classifier to: {model_save_path}")

    scaler_save_path = os.path.join(MODELS_DIR, "classifier_scaler.pkl")
    joblib.dump(scaler, scaler_save_path, compress=3)

    # Save Ranked Features CSV
    ranked_csv_path = os.path.join(DATA_DIR, "top_features_ranked.csv")
    feature_imp_df.to_csv(ranked_csv_path, index=False)
    logger.info(f"Saved ranked feature importances to: {ranked_csv_path}")

    # Generate Evaluation Visualizations
    generate_evaluation_plots(results, feature_imp_df, domain_percentages, y_test)

    # Save JSON metrics
    metrics_payload = {
        "best_model": best_model_name,
        "models_benchmarked": results,
        "domain_importance_share_percent": domain_percentages,
        "top_10_features": feature_imp_df.head(10).to_dict(orient="records")
    }

    metrics_json_path = os.path.join(MODELS_DIR, "classification_metrics.json")
    with open(metrics_json_path, "w") as f:
        # Strip large raw test arrays from JSON file for minimal size
        compact_payload = {
            "best_model": best_model_name,
            "models_benchmarked": {
                m: {k: v for k, v in data.items() if k not in ["y_test", "y_pred", "y_prob"]}
                for m, data in results.items()
            },
            "domain_importance_share_percent": domain_percentages,
            "top_10_features": feature_imp_df.head(10).to_dict(orient="records")
        }
        json.dump(compact_payload, f, indent=2)
    logger.info(f"Saved evaluation metrics JSON to: {metrics_json_path}")

    # Print Terminal Benchmark Table
    print("\n" + "="*80)
    print(" MULTI-MODEL ANOMALY CLASSIFICATION BENCHMARK")
    print("="*80)
    table_rows = []
    for m_name, res in results.items():
        table_rows.append({
            "Model": m_name,
            "Accuracy": f"{res['accuracy']*100:.2f}%",
            "Precision": f"{res['precision']*100:.2f}%",
            "Recall": f"{res['recall']*100:.2f}%",
            "F1-Score": f"{res['f1_score']*100:.2f}%",
            "ROC-AUC": f"{res['roc_auc']:.4f}",
            "5-Fold CV Acc": f"{res['cv_accuracy_mean']*100:.2f}% ± {res['cv_accuracy_std']*100:.2f}%"
        })
    print(pd.DataFrame(table_rows).to_string(index=False))
    print("="*80)

    print("\n" + "="*80)
    print(" FEATURE DOMAIN IMPORTANCE SHARE (TIME vs FREQUENCY vs TSFRESH)")
    print("="*80)
    for dom, pct in sorted(domain_percentages.items(), key=lambda x: x[1], reverse=True):
        print(f"  • {dom:30}: {pct:6.2f}%")
    print("="*80)

    print("\n" + "="*80)
    print(" TOP 10 DISCRIMINATIVE FEATURES OVERALL")
    print("="*80)
    top_display = feature_imp_df.head(10)[["feature", "domain", "importance"]].copy()
    top_display["importance"] = top_display["importance"].apply(lambda v: f"{v:.4f}")
    print(top_display.to_string(index=False))
    print("="*80 + "\n")

    return metrics_payload


def generate_evaluation_plots(
    results: Dict[str, Any],
    feature_imp_df: pd.DataFrame,
    domain_percentages: Dict[str, float],
    y_test: np.ndarray
):
    """
    Generates 4 academic evaluation figures:
      1. Confusion Matrix Heatmap (Random Forest)
      2. Feature Importance Horizontal Bar Chart (Top 15)
      3. Cross-Domain Importance Share (Pie Chart)
      4. ROC Curves (Random Forest vs Gradient Boosting vs Baseline)
    """
    os.makedirs(OUTPUT_PLOT_DIR, exist_ok=True)

    # 1. Confusion Matrix
    rf_data = results["Random Forest Classifier"]
    cm = np.array(rf_data["confusion_matrix"])
    cm_norm = cm.astype('float') / cm.sum(axis=1)[:, np.newaxis]

    fig, ax = plt.subplots(figsize=(6, 5), dpi=200)
    annot = np.array([[f"{count}\n({pct:.1%})" for count, pct in zip(row_c, row_p)] 
                      for row_c, row_p in zip(cm, cm_norm)])
    sns.heatmap(cm, annot=annot, fmt="", cmap="Blues", cbar=True,
                xticklabels=["Normal (0)", "Anomaly (1)"],
                yticklabels=["Normal (0)", "Anomaly (1)"],
                ax=ax, annot_kws={"fontsize": 11, "fontweight": "bold"})
    ax.set_title("Confusion Matrix — Random Forest Anomaly Detector", fontsize=12, fontweight="bold", pad=12)
    ax.set_xlabel("Predicted Operational State", fontsize=11, fontweight="bold")
    ax.set_ylabel("True Operational State", fontsize=11, fontweight="bold")
    cm_path = os.path.join(OUTPUT_PLOT_DIR, "confusion_matrix.png")
    plt.savefig(cm_path, bbox_inches="tight")
    plt.close()

    # 2. Feature Importance Horizontal Bar Chart
    fig, ax = plt.subplots(figsize=(9, 6), dpi=200)
    top_15 = feature_imp_df.head(15).iloc[::-1]

    palette = {
        "Time-Domain Analysis": "#3B82F6",              # Blue
        "Frequency-Domain Analysis (FFT)": "#10B981",   # Green
        "TSFresh Feature Engineering": "#8B5CF6",       # Purple
        "Sensor Raw": "#6B7280"
    }
    bar_colors = [palette.get(d, "#3B82F6") for d in top_15["domain"]]

    bars = ax.barh(top_15["feature"], top_15["importance"], color=bar_colors, edgecolor="black", alpha=0.85)
    ax.set_title("Top 15 Most Discriminative Features for Anomaly Detection", fontsize=12, fontweight="bold", pad=12)
    ax.set_xlabel("Random Forest Relative Feature Importance (MDI)", fontsize=11, fontweight="bold")
    ax.set_ylabel("Feature Name", fontsize=10)
    ax.grid(axis="x", linestyle=":", alpha=0.6)

    # Custom legend for domains
    import matplotlib.patches as mpatches
    legend_handles = [
        mpatches.Patch(color=c, label=d)
        for d, c in palette.items() if d in top_15["domain"].values
    ]
    ax.legend(handles=legend_handles, loc="lower right", framealpha=0.9, fontsize=9)
    feat_path = os.path.join(OUTPUT_PLOT_DIR, "feature_importance.png")
    plt.savefig(feat_path, bbox_inches="tight")
    plt.close()

    # 3. Domain Importance Share Pie Chart
    fig, ax = plt.subplots(figsize=(6, 5), dpi=200)
    domains = list(domain_percentages.keys())
    shares = list(domain_percentages.values())
    colors = [palette.get(d, "#9CA3AF") for d in domains]

    wedges, texts, autotexts = ax.pie(
        shares, labels=domains, autopct="%1.1f%%",
        startangle=140, colors=colors,
        wedgeprops=dict(width=0.65, edgecolor='w', lw=2)
    )
    for at in autotexts:
        at.set_fontsize(11)
        at.set_fontweight("bold")
    ax.set_title("Cross-Domain Feature Contribution to Anomaly Detection", fontsize=12, fontweight="bold", pad=12)
    pie_path = os.path.join(OUTPUT_PLOT_DIR, "domain_importance_pie.png")
    plt.savefig(pie_path, bbox_inches="tight")
    plt.close()

    # 4. ROC Curves
    fig, ax = plt.subplots(figsize=(7, 6), dpi=200)
    for m_name, res in results.items():
        fpr, tpr, _ = roc_curve(res["y_test"], res["y_prob"])
        auc_score = res["roc_auc"]
        ax.plot(fpr, tpr, lw=2, label=f"{m_name} (AUC = {auc_score:.3f})")

    ax.plot([0, 1], [0, 1], color="gray", lw=1.5, linestyle="--", label="Random Chance (AUC = 0.500)")
    ax.set_xlim([0.0, 1.0])
    ax.set_ylim([0.0, 1.02])
    ax.set_xlabel("False Positive Rate (1 - Specificity)", fontsize=11, fontweight="bold")
    ax.set_ylabel("True Positive Rate (Sensitivity / Recall)", fontsize=11, fontweight="bold")
    ax.set_title("Receiver Operating Characteristic (ROC) Comparison", fontsize=12, fontweight="bold", pad=12)
    ax.legend(loc="lower right", framealpha=0.9, fontsize=10)
    ax.grid(True, linestyle=":", alpha=0.6)
    roc_path = os.path.join(OUTPUT_PLOT_DIR, "roc_curve.png")
    plt.savefig(roc_path, bbox_inches="tight")
    plt.close()

    logger.info(f"Saved 4 academic evaluation figures to: {OUTPUT_PLOT_DIR}")


if __name__ == "__main__":
    df_fused = load_and_merge_features()
    train_and_benchmark(df_fused)
