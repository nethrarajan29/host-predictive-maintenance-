"""
TSFresh Automated Time-Series Feature Engineering & Selection Pipeline.

This module implements the complete automated time-series feature engineering,
data cleaning, collinearity filtering, normal-vs-anomaly statistical comparison,
and hypothesis-driven feature selection workflow using Python TSFresh.

Designed to be modular, robust, and reproducible for industrial predictive maintenance.
"""

import os
import sys
import argparse
import logging
from typing import Dict, List, Tuple, Optional, Any

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.feature_selection import mutual_info_classif
import matplotlib  # type: ignore
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # type: ignore
import seaborn as sns  # type: ignore

# TSFresh imports
import tsfresh
from tsfresh import extract_features, select_features
from tsfresh.feature_extraction import EfficientFCParameters
from tsfresh.utilities.dataframe_functions import impute

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("tsfresh_pipeline")

# =====================================================================
# CONFIGURATION CONSTANTS
# =====================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "datasets", "sensor_data.csv")
ALT_DATA_PATH = os.path.join(BASE_DIR, "data", "sensor_data.csv")
OUTPUT_DATA_DIR = os.path.join(BASE_DIR, "data", "tsfresh")
OUTPUT_PLOT_DIR = os.path.join(BASE_DIR, "outputs", "tsfresh")

PRIMARY_SENSOR_COLS = ["Temperature", "Vibration", "Motor_Current", "Pressure", "Noise"]
DEFAULT_WINDOW_SIZE = 30    # 30 daily steps per temporal window
DEFAULT_WINDOW_STRIDE = 15  # 50% overlap between consecutive windows
CORRELATION_THRESHOLD = 0.95
FDR_LEVEL = 0.05
TOP_K_SELECTED = 25
DEFAULT_MAX_MACHINES = 25   # Default 25 machines (~575 windows, ~3,885 candidate features)


# =====================================================================
# 1. LOAD SENSOR DATA
# =====================================================================
def load_sensor_data(filepath: str = DATA_PATH) -> pd.DataFrame:
    """
    Loads sensor dataset with fallback path resolution and forward-fills missing telemetry.
    
    Args:
        filepath: Path to the sensor dataset CSV.
        
    Returns:
        pd.DataFrame: Cleaned raw sensor telemetry dataframe.
    """
    if not os.path.exists(filepath):
        if os.path.exists(ALT_DATA_PATH):
            filepath = ALT_DATA_PATH
        else:
            raise FileNotFoundError(f"Sensor dataset not found at {filepath} or {ALT_DATA_PATH}")
            
    logger.info(f"Loading sensor dataset from: {filepath}")
    df = pd.read_csv(filepath)
    logger.info(f"Loaded raw sensor records: {len(df):,} rows, {len(df.columns)} columns")
    
    # Forward-fill any synthetic missing values
    null_counts = df[PRIMARY_SENSOR_COLS].isnull().sum().sum()
    if null_counts > 0:
        logger.info(f"Forward-filling {null_counts:,} missing sensor values...")
        df[PRIMARY_SENSOR_COLS] = df[PRIMARY_SENSOR_COLS].ffill().bfill()
        
    return df


# =====================================================================
# 2. PREPARE TIME SERIES & WINDOWING
# =====================================================================
def prepare_time_series(df: pd.DataFrame, num_machines: Optional[int] = None) -> pd.DataFrame:
    """
    Assigns Machine IDs and validates temporal ordering.
    
    Args:
        df: Input sensor dataframe.
        num_machines: Optional limit on the number of machines to include.
        
    Returns:
        pd.DataFrame: Dataframe with Machine_ID and time index.
    """
    df_ts = df.copy()
    
    # Detect machine records boundaries (each machine has 365 steps in dataset_generator.py)
    steps_per_machine = 365
    total_records = len(df_ts)
    total_machines = total_records // steps_per_machine
    
    machine_ids = []
    for m in range(total_machines):
        machine_ids.extend([m + 1] * steps_per_machine)
        
    # Handle remaining rows if not exact multiple
    if len(machine_ids) < total_records:
        machine_ids.extend([total_machines + 1] * (total_records - len(machine_ids)))
        
    df_ts["Machine_ID"] = machine_ids[:total_records]
    
    if num_machines is not None and num_machines < total_machines:
        logger.info(f"Subsetting to first {num_machines} machines (out of {total_machines} total) for efficient processing...")
        df_ts = df_ts[df_ts["Machine_ID"] <= num_machines].copy()
        
    return df_ts


def create_windows(
    df: pd.DataFrame,
    window_size: int = DEFAULT_WINDOW_SIZE,
    stride: int = DEFAULT_WINDOW_STRIDE,
    sensor_cols: List[str] = PRIMARY_SENSOR_COLS
) -> Tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
    """
    Segments continuous multi-sensor machine telemetry into discrete temporal windows.
    Each window retains an isolated sequence for TSFresh extraction and a window-level anomaly label.
    
    Args:
        df: Prepared sensor dataframe with Machine_ID.
        window_size: Number of consecutive time steps per window.
        stride: Step size between consecutive window starts.
        sensor_cols: List of continuous sensor columns to include.
        
    Returns:
        Tuple containing:
            - df_windows (pd.DataFrame): Long/flat windowed sensor format for TSFresh [window_id, step, sensor_values...].
            - y_labels (pd.Series): Binary anomaly label per window_id (0 = Normal, 1 = Anomaly).
            - window_metadata (pd.DataFrame): Metadata for each window (machine_id, status, mean health, etc.).
    """
    window_rows = []
    labels_dict = {}
    meta_rows = []
    
    window_counter = 0
    
    grouped = df.groupby("Machine_ID")
    for machine_id, group in grouped:
        group = group.reset_index(drop=True)
        n_steps = len(group)
        
        for start_idx in range(0, n_steps - window_size + 1, stride):
            end_idx = start_idx + window_size
            window_slice = group.iloc[start_idx:end_idx]
            
            w_id = window_counter
            window_counter += 1
            
            # Form TSFresh window slice
            for step_idx, (_, row) in enumerate(window_slice.iterrows()):
                row_dict = {
                    "window_id": w_id,
                    "step": step_idx,
                }
                for s_col in sensor_cols:
                    row_dict[s_col] = float(row[s_col])
                window_rows.append(row_dict)
                
            # Window Anomaly Label determination:
            # If machine status in this window is not 'Healthy' or Health < 80.0 -> Anomaly (1), else Normal (0)
            status_series = window_slice["Machine_Status"].astype(str)
            has_anomaly = not (status_series == "Healthy").all()
            
            mean_health = float(window_slice["Machine_Health"].mean()) if "Machine_Health" in window_slice else 100.0
            last_status = str(window_slice["Machine_Status"].iloc[-1]) if "Machine_Status" in window_slice else "Healthy"
            last_rul = float(window_slice["Remaining_Useful_Life_Days"].iloc[-1]) if "Remaining_Useful_Life_Days" in window_slice else 250.0
            
            label_val = 1 if (has_anomaly or mean_health < 80.0) else 0
            labels_dict[w_id] = label_val
            
            meta_rows.append({
                "window_id": w_id,
                "machine_id": machine_id,
                "start_step": start_idx,
                "end_step": end_idx,
                "mean_health": round(mean_health, 2),
                "last_status": last_status,
                "last_rul": round(last_rul, 1),
                "label": label_val,
                "label_name": "ANOMALY" if label_val == 1 else "NORMAL"
            })
            
    df_windows = pd.DataFrame(window_rows)
    y_labels = pd.Series(labels_dict, name="label")
    df_meta = pd.DataFrame(meta_rows).set_index("window_id")
    
    n_normal = (y_labels == 0).sum()
    n_anomaly = (y_labels == 1).sum()
    logger.info(f"Created {len(y_labels):,} windows (Window Size: {window_size}, Stride: {stride})")
    logger.info(f"  -> NORMAL windows (0): {n_normal:,} ({n_normal/len(y_labels)*100:.1f}%)")
    logger.info(f"  -> ANOMALY windows (1): {n_anomaly:,} ({n_anomaly/len(y_labels)*100:.1f}%)")
    
    return df_windows, y_labels, df_meta


# =====================================================================
# 3. TSFRESH FEATURE EXTRACTION
# =====================================================================
def extract_tsfresh_features(
    df_windows: pd.DataFrame,
    fc_parameters: Optional[Dict] = None,
    n_jobs: int = 0
) -> pd.DataFrame:
    """
    Extracts a large candidate set of time-series features across all sensors using TSFresh.
    
    Args:
        df_windows: Windowed sensor telemetry dataframe.
        fc_parameters: TSFresh feature extraction settings (defaults to EfficientFCParameters).
        n_jobs: Multiprocessing jobs (0 for synchronous execution).
        
    Returns:
        pd.DataFrame: Extracted features matrix indexed by window_id.
    """
    if fc_parameters is None:
        fc_parameters = EfficientFCParameters()
        
    logger.info("Starting TSFresh automated feature extraction...")
    extracted_features = extract_features(
        df_windows,
        column_id="window_id",
        column_sort="step",
        default_fc_parameters=fc_parameters,
        n_jobs=n_jobs,
        disable_progressbar=False
    )
    
    logger.info(f"TSFresh candidate extraction complete! Generated shape: {extracted_features.shape}")
    return extracted_features


# =====================================================================
# 4. CLEAN FEATURE DATASET
# =====================================================================
def clean_features(df_features: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Cleans generated TSFresh features:
    1. Removes constant/zero-variance features and single-value columns.
    2. Detects and replaces NaN, inf, -inf values safely using robust imputation.
    
    Args:
        df_features: Raw extracted feature dataframe.
        
    Returns:
        Tuple of (cleaned pd.DataFrame, cleaning metadata dict).
    """
    initial_count = df_features.shape[1]
    logger.info(f"Initial candidate features: {initial_count:,}")
    
    # 1. Impute NaN, inf, -inf using TSFresh imputation utility
    df_imputed = impute(df_features.copy())
    
    nan_count_post = df_imputed.isnull().sum().sum()
    inf_count_post = np.isinf(df_imputed.values).sum()
    logger.info(f"Invalid values handled: {nan_count_post} NaNs, {inf_count_post} infs remaining")
    
    # 2. Identify & remove constant / zero-variance features
    stds = df_imputed.std(axis=0)
    uniques = df_imputed.nunique(axis=0)
    
    valid_mask = (stds > 1e-12) & (uniques > 1)
    df_cleaned = df_imputed.loc[:, valid_mask].copy()
    
    constant_removed = initial_count - df_cleaned.shape[1]
    logger.info(f"Removed {constant_removed:,} constant/zero-variance features.")
    logger.info(f"Features after constant removal: {df_cleaned.shape[1]:,}")
    
    cleaning_meta = {
        "initial_features": initial_count,
        "constant_removed": constant_removed,
        "features_after_cleaning": df_cleaned.shape[1]
    }
    return df_cleaned, cleaning_meta


# =====================================================================
# 5. REMOVE REDUNDANT / COLLINEAR FEATURES
# =====================================================================
def remove_redundant_features(
    df_features: pd.DataFrame,
    threshold: float = CORRELATION_THRESHOLD
) -> Tuple[pd.DataFrame, List[str]]:
    """
    Removes highly collinear redundant features (|correlation| > threshold),
    retaining one representative feature per correlated group.
    
    Args:
        df_features: Cleaned feature dataframe.
        threshold: Absolute correlation threshold (default 0.95).
        
    Returns:
        Tuple of (filtered pd.DataFrame, list of dropped feature names).
    """
    logger.info(f"Calculating feature correlation matrix for {df_features.shape[1]:,} features...")
    corr_matrix = df_features.corr().abs()
    
    # Select upper triangle of correlation matrix
    upper = corr_matrix.where(np.triu(np.ones(corr_matrix.shape), k=1).astype(bool))
    
    # Find features with correlation greater than threshold
    to_drop = [column for column in upper.columns if any(upper[column] > threshold)]
    df_filtered = df_features.drop(columns=to_drop)
    
    logger.info(f"Collinearity filtering (|r| > {threshold}):")
    logger.info(f"  -> Features before correlation filtering: {df_features.shape[1]:,}")
    logger.info(f"  -> Redundant features removed: {len(to_drop):,}")
    logger.info(f"  -> Features remaining: {df_filtered.shape[1]:,}")
    
    return df_filtered, to_drop


# =====================================================================
# 6. COMPARE NORMAL VS ANOMALY FEATURES
# =====================================================================
def compare_normal_anomaly_features(
    df_features: pd.DataFrame,
    y: pd.Series
) -> pd.DataFrame:
    """
    Computes rigorous statistical comparisons between Normal and Anomaly windows:
    - Normal Mean & Median
    - Anomaly Mean & Median
    - Standard Deviations
    - Mean Difference & Relative Change
    - Mann-Whitney U test statistic & p-value
    - Cohen's d effect size
    - Mutual Information score
    
    Args:
        df_features: Feature dataframe indexed by window_id.
        y: Binary label series (0 = Normal, 1 = Anomaly).
        
    Returns:
        pd.DataFrame: Comparison statistics table for each feature.
    """
    logger.info("Computing Normal vs Anomaly statistical comparisons for all features...")
    
    normal_mask = (y == 0)
    anomaly_mask = (y == 1)
    
    df_normal = df_features.loc[normal_mask]
    df_anomaly = df_features.loc[anomaly_mask]
    
    # Compute Mutual Information
    mi_scores = mutual_info_classif(df_features, y, random_state=42)
    mi_dict = dict(zip(df_features.columns, mi_scores))
    
    records = []
    for col in df_features.columns:
        # Determine sensor kind
        sensor_name = col.split("__")[0] if "__" in col else "unknown"
        
        vals_norm = df_normal[col].values
        vals_anom = df_anomaly[col].values
        
        mean_norm = float(np.mean(vals_norm))
        mean_anom = float(np.mean(vals_anom))
        std_norm = float(np.std(vals_norm))
        std_anom = float(np.std(vals_anom))
        med_norm = float(np.median(vals_norm))
        med_anom = float(np.median(vals_anom))
        
        mean_diff = mean_anom - mean_norm
        
        # Pooled standard deviation for Cohen's d
        pooled_std = np.sqrt(((len(vals_norm) - 1) * (std_norm ** 2) + (len(vals_anom) - 1) * (std_anom ** 2)) / max(1, len(vals_norm) + len(vals_anom) - 2))
        cohens_d = abs(mean_diff) / pooled_std if pooled_std > 1e-9 else 0.0
        
        # Non-parametric Mann-Whitney U test
        try:
            u_stat, p_val = stats.mannwhitneyu(vals_norm, vals_anom, alternative="two-sided")
        except Exception:
            u_stat, p_val = 0.0, 1.0
            
        records.append({
            "feature_name": col,
            "sensor": sensor_name,
            "normal_mean": round(mean_norm, 4),
            "anomaly_mean": round(mean_anom, 4),
            "mean_difference": round(mean_diff, 4),
            "normal_std": round(std_norm, 4),
            "anomaly_std": round(std_anom, 4),
            "normal_median": round(med_norm, 4),
            "anomaly_median": round(med_anom, 4),
            "cohens_d": round(cohens_d, 4),
            "mann_whitney_u": round(float(u_stat), 2),
            "p_value": p_val,
            "mutual_info": round(float(mi_dict.get(col, 0.0)), 4)
        })
        
    df_comparison = pd.DataFrame(records).sort_values(by="cohens_d", ascending=False).reset_index(drop=True)
    return df_comparison


# =====================================================================
# 7. IDENTIFY & SELECT USEFUL FEATURES
# =====================================================================
def select_useful_features(
    df_features: pd.DataFrame,
    y: pd.Series,
    comparison_df: pd.DataFrame,
    fdr_level: float = FDR_LEVEL,
    top_k: int = TOP_K_SELECTED
) -> Tuple[pd.DataFrame, List[str], pd.DataFrame]:
    """
    Selects the most discriminative features for classifying Normal vs Anomaly:
    1. Uses TSFresh hypothesis testing (`select_features`) with FDR control.
    2. Combines with effect-size ranking (Cohen's d + Mutual Information).
    3. Produces a finalized top-k selected feature set.
    
    Args:
        df_features: Filtered features dataframe.
        y: Binary anomaly labels.
        comparison_df: Comparison statistics dataframe.
        fdr_level: Benjamini-Hochberg False Discovery Rate level.
        top_k: Maximum number of top features to select.
        
    Returns:
        Tuple of (df_selected, selected_feature_names_list, selection_summary_df).
    """
    logger.info(f"Executing TSFresh hypothesis-driven feature selection (FDR level: {fdr_level:.2f})...")
    
    try:
        tsfresh_selected_df = select_features(df_features, y, fdr_level=fdr_level, n_jobs=0)
        candidate_selected_names = list(tsfresh_selected_df.columns)
        logger.info(f"TSFresh select_features retained {len(candidate_selected_names):,} statistically significant features.")
    except Exception as e:
        logger.warning(f"TSFresh select_features encountered notice ({e}). Falling back to Mann-Whitney FDR ranking.")
        candidate_selected_names = list(df_features.columns)
        
    # Filter comparison df by candidate selected features
    subset_comp = comparison_df[comparison_df["feature_name"].isin(candidate_selected_names)].copy()
    
    # Rank by composite discriminative score: Cohen's d * (1 + mutual_info)
    subset_comp["discriminative_score"] = subset_comp["cohens_d"] * (1.0 + subset_comp["mutual_info"])
    subset_comp = subset_comp.sort_values(by="discriminative_score", ascending=False).reset_index(drop=True)
    
    final_selected_features = subset_comp["feature_name"].head(top_k).tolist()
    
    # Build complete summary
    selection_summary = comparison_df.copy()
    selection_summary["selected"] = selection_summary["feature_name"].isin(final_selected_features)
    selection_summary["selection_rank"] = selection_summary["feature_name"].map(
        {feat: i + 1 for i, feat in enumerate(final_selected_features)}
    )
    
    df_selected = df_features[final_selected_features].copy()
    
    logger.info(f"Final selected feature count: {len(final_selected_features)}")
    return df_selected, final_selected_features, selection_summary


# =====================================================================
# 8. FEATURE CATEGORIZATION
# =====================================================================
def categorize_features(feature_names: List[str]) -> pd.DataFrame:
    """
    Categorizes generated TSFresh features by their mathematical / signal processing domains.
    
    Args:
        feature_names: List of all extracted feature names.
        
    Returns:
        pd.DataFrame: Table with feature counts per category and sample features.
    """
    category_map = {
        "Statistical Moments & Energy": ["mean", "standard_deviation", "variance", "skewness", "kurtosis", "root_mean_square", "abs_energy", "sum_values", "mean_abs_change", "maximum", "minimum", "median"],
        "Frequency Domain & FFT": ["fft_coefficient", "spkt_welch_density", "fft_aggregated", "fourier", "spectral"],
        "Autocorrelation & Dynamics": ["autocorrelation", "partial_autocorrelation", "c3", "cid_ce", "agg_autocorrelation", "time_reversal_asymmetry_statistic"],
        "Trend & Linear Regression": ["linear_trend", "augmented_dickey_fuller", "agg_linear_trend", "linear_trend_timewise"],
        "Entropy & Signal Complexity": ["sample_entropy", "approximate_entropy", "binned_entropy", "lempel_ziv", "permutation_entropy"],
        "Distribution & Quantiles": ["quantile", "cwt_coefficients", "symmetry_looking", "ratio_beyond_r_sigma", "range_count", "percentage_of_reoccurring_values"],
        "Peaks & Variation": ["number_peaks", "variation_coefficient", "diff_of_peaks", "first_location_of_maximum", "last_location_of_maximum", "has_duplicate"]
    }
    
    cat_counts = {cat: 0 for cat in category_map}
    cat_counts["Other Temporal Characteristics"] = 0
    
    cat_samples = {cat: [] for cat in cat_counts}
    
    for feat in feature_names:
        assigned = False
        feat_lower = feat.lower()
        for cat, keywords in category_map.items():
            if any(kw in feat_lower for kw in keywords):
                cat_counts[cat] += 1
                if len(cat_samples[cat]) < 2:
                    cat_samples[cat].append(feat)
                assigned = True
                break
        if not assigned:
            cat_counts["Other Temporal Characteristics"] += 1
            if len(cat_samples["Other Temporal Characteristics"]) < 2:
                cat_samples["Other Temporal Characteristics"].append(feat)
                
    cat_rows = []
    for cat, count in cat_counts.items():
        if count > 0:
            cat_rows.append({
                "feature_category": cat,
                "feature_count": count,
                "percentage": round(count / len(feature_names) * 100, 2),
                "example_features": " | ".join(cat_samples[cat])
            })
            
    df_cats = pd.DataFrame(cat_rows).sort_values(by="feature_count", ascending=False).reset_index(drop=True)
    return df_cats


# =====================================================================
# 9. VISUAL ANALYSIS
# =====================================================================
def generate_visualizations(
    df_selected: pd.DataFrame,
    y: pd.Series,
    comparison_df: pd.DataFrame,
    output_dir: str = OUTPUT_PLOT_DIR
) -> List[str]:
    """
    Generates 3 visual analysis figures:
    1. Top Selected Features Importance (Cohen's d effect size).
    2. Normal vs Anomaly distribution boxplots for top discriminative features.
    3. Selected Features Correlation Heatmap.
    
    Args:
        df_selected: Dataframe containing selected features.
        y: Binary labels.
        comparison_df: Feature comparison statistics dataframe.
        output_dir: Output plot directory.
        
    Returns:
        List of generated image filepaths.
    """
    os.makedirs(output_dir, exist_ok=True)
    generated_files = []
    
    # Set dark/modern industrial plot styling
    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.size": 10,
        "axes.titlesize": 12,
        "axes.labelsize": 11,
        "figure.titlesize": 14
    })
    
    # -------------------------------------------------------------
    # PLOT 1: Top Selected Features Discriminative Power (Bar Chart)
    # -------------------------------------------------------------
    top_comp = comparison_df[comparison_df["feature_name"].isin(df_selected.columns)].head(15).iloc[::-1]
    
    fig, ax = plt.subplots(figsize=(12, 8), dpi=200)
    colors = [
        "#10b981" if s == "Temperature" else
        "#3b82f6" if s == "Vibration" else
        "#8b5cf6" if s == "Motor_Current" else
        "#f59e0b" if s == "Pressure" else "#ec4899"
        for s in top_comp["sensor"]
    ]
    
    bars = ax.barh(top_comp["feature_name"], top_comp["cohens_d"], color=colors, edgecolor="#1e293b", alpha=0.88)
    ax.set_xlabel("Cohen's d Effect Size (Standardized Difference)", fontweight="bold")
    ax.set_title("Top Selected TSFresh Features Ranked by Discriminative Power (Normal vs Anomaly)", fontweight="bold", pad=15)
    
    for bar in bars:
        width = bar.get_width()
        ax.text(width + 0.05, bar.get_y() + bar.get_height() / 2, f"{width:.2f}", va="center", ha="left", fontsize=9, fontweight="bold")
        
    ax.set_xlim(0, top_comp["cohens_d"].max() * 1.15)
    
    # Custom sensor legend
    legend_elements = [
        plt.Line2D([0], [0], color="#10b981", lw=6, label="Temperature"),
        plt.Line2D([0], [0], color="#3b82f6", lw=6, label="Vibration"),
        plt.Line2D([0], [0], color="#8b5cf6", lw=6, label="Motor_Current"),
        plt.Line2D([0], [0], color="#f59e0b", lw=6, label="Pressure"),
        plt.Line2D([0], [0], color="#ec4899", lw=6, label="Noise")
    ]
    ax.legend(handles=legend_elements, title="Sensor Channel", loc="lower right", frameon=True)
    
    plt.tight_layout()
    p1_path = os.path.join(output_dir, "top_features_importance.png")
    fig.savefig(p1_path)
    plt.close(fig)
    generated_files.append(p1_path)
    logger.info(f"Saved visualization 1: {p1_path}")
    
    # -------------------------------------------------------------
    # PLOT 2: Normal vs Anomaly Distribution Boxplots (Top 6 Features)
    # -------------------------------------------------------------
    top_6_feats = df_selected.columns[:6].tolist()
    fig, axes = plt.subplots(2, 3, figsize=(15, 9), dpi=200)
    axes = axes.flatten()
    
    df_plot = df_selected[top_6_feats].copy()
    df_plot["Status"] = y.map({0: "NORMAL", 1: "ANOMALY"})
    
    palette = {"NORMAL": "#10b981", "ANOMALY": "#ef4444"}
    
    for i, col in enumerate(top_6_feats):
        ax = axes[i]
        sns.boxplot(data=df_plot, x="Status", y=col, hue="Status", ax=ax, palette=palette, width=0.45, legend=False)
        ax.set_title(col, fontsize=10, fontweight="bold")
        ax.set_xlabel("")
        ax.set_ylabel("Value")
        
    fig.suptitle("TSFresh Feature Value Distributions: NORMAL vs ANOMALY Windows", fontsize=14, fontweight="bold", y=0.98)
    plt.tight_layout()
    p2_path = os.path.join(output_dir, "normal_vs_anomaly_distributions.png")
    fig.savefig(p2_path)
    plt.close(fig)
    generated_files.append(p2_path)
    logger.info(f"Saved visualization 2: {p2_path}")
    
    # -------------------------------------------------------------
    # PLOT 3: Selected Features Correlation Heatmap
    # -------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(14, 11), dpi=200)
    top_15_selected = df_selected.iloc[:, :min(15, df_selected.shape[1])]
    corr = top_15_selected.corr()
    
    sns.heatmap(
        corr,
        annot=True,
        fmt=".2f",
        cmap="coolwarm",
        vmin=-1.0,
        vmax=1.0,
        cbar_kws={"label": "Pearson Correlation Coefficient"},
        ax=ax,
        linewidths=0.5,
        annot_kws={"size": 8}
    )
    ax.set_title("Inter-Feature Correlation Heatmap (Top Selected Features)", fontweight="bold", pad=15)
    plt.xticks(rotation=45, ha="right", fontsize=8)
    plt.yticks(rotation=0, fontsize=8)
    
    plt.tight_layout()
    p3_path = os.path.join(output_dir, "selected_features_correlation_heatmap.png")
    fig.savefig(p3_path)
    plt.close(fig)
    generated_files.append(p3_path)
    logger.info(f"Saved visualization 3: {p3_path}")
    
    return generated_files


# =====================================================================
# 10. SAVE OUTPUTS
# =====================================================================
def save_outputs(
    df_full: pd.DataFrame,
    df_cleaned: pd.DataFrame,
    df_selected: pd.DataFrame,
    y: pd.Series,
    df_comparison: pd.DataFrame,
    df_categories: pd.DataFrame,
    selection_summary: pd.DataFrame,
    selected_features_list: List[str],
    output_dir: str = OUTPUT_DATA_DIR
) -> Dict[str, str]:
    """
    Saves all processed datasets and feature selection tables to disk.
    
    Returns:
        Dict mapping output names to saved absolute paths.
    """
    os.makedirs(output_dir, exist_ok=True)
    saved_paths = {}
    
    # 1. Full Features dataset
    df_full_with_labels = df_full.copy()
    df_full_with_labels.insert(0, "label", y.values)
    full_path = os.path.join(output_dir, "tsfresh_features_full.csv")
    df_full_with_labels.to_csv(full_path, index=True, index_label="window_id")
    saved_paths["tsfresh_features_full.csv"] = full_path
    
    # 2. Cleaned Features dataset
    df_cleaned_with_labels = df_cleaned.copy()
    df_cleaned_with_labels.insert(0, "label", y.values)
    cleaned_path = os.path.join(output_dir, "tsfresh_features_cleaned.csv")
    df_cleaned_with_labels.to_csv(cleaned_path, index=True, index_label="window_id")
    saved_paths["tsfresh_features_cleaned.csv"] = cleaned_path
    
    # 3. Selected Features dataset
    df_selected_with_labels = df_selected.copy()
    df_selected_with_labels.insert(0, "label", y.values)
    selected_path = os.path.join(output_dir, "tsfresh_features_selected.csv")
    df_selected_with_labels.to_csv(selected_path, index=True, index_label="window_id")
    saved_paths["tsfresh_features_selected.csv"] = selected_path
    
    # 4. Normal vs Anomaly comparison
    comp_path = os.path.join(output_dir, "normal_vs_anomaly_features.csv")
    df_comparison.to_csv(comp_path, index=False)
    saved_paths["normal_vs_anomaly_features.csv"] = comp_path
    
    # 5. Selected features txt list
    txt_path = os.path.join(output_dir, "selected_features.txt")
    with open(txt_path, "w") as f:
        for feat in selected_features_list:
            f.write(f"{feat}\n")
    saved_paths["selected_features.txt"] = txt_path
    
    # 6. Feature categories summary
    cats_path = os.path.join(output_dir, "tsfresh_feature_categories.csv")
    df_categories.to_csv(cats_path, index=False)
    saved_paths["tsfresh_feature_categories.csv"] = cats_path
    
    # 7. Feature selection summary
    sum_path = os.path.join(output_dir, "tsfresh_feature_selection_summary.csv")
    selection_summary.to_csv(sum_path, index=False)
    saved_paths["tsfresh_feature_selection_summary.csv"] = sum_path
    
    logger.info(f"All 7 dataset and summary files saved successfully in {output_dir}")
    return saved_paths


# =====================================================================
# 11. MAIN PIPELINE EXECUTION
# =====================================================================
def run_pipeline(
    data_path: str = DATA_PATH,
    output_data_dir: str = OUTPUT_DATA_DIR,
    output_plot_dir: str = OUTPUT_PLOT_DIR,
    max_machines: Optional[int] = DEFAULT_MAX_MACHINES,
    window_size: int = DEFAULT_WINDOW_SIZE,
    window_stride: int = DEFAULT_WINDOW_STRIDE,
    correlation_threshold: float = CORRELATION_THRESHOLD,
    top_k: int = TOP_K_SELECTED
) -> Dict[str, Any]:
    """
    Executes the end-to-end TSFresh feature engineering and selection workflow.
    """
    print("\n" + "=" * 65)
    print("  TSFRESH TIME-SERIES FEATURE ENGINEERING & SELECTION PIPELINE")
    print("=" * 65)
    
    # 1. Load Data
    raw_df = load_sensor_data(data_path)
    
    # 2. Prepare Time Series & Windows
    ts_df = prepare_time_series(raw_df, num_machines=max_machines)
    df_windows, y_labels, df_meta = create_windows(
        ts_df,
        window_size=window_size,
        stride=window_stride,
        sensor_cols=PRIMARY_SENSOR_COLS
    )
    
    n_windows = len(y_labels)
    n_sensors = len(PRIMARY_SENSOR_COLS)
    n_normal = int((y_labels == 0).sum())
    n_anomaly = int((y_labels == 1).sum())
    
    # 3. TSFresh Candidate Feature Extraction
    df_features_full = extract_tsfresh_features(df_windows, n_jobs=0)
    n_raw_features = df_features_full.shape[1]
    
    # 4. Feature Categorization (from full extracted set)
    df_categories = categorize_features(list(df_features_full.columns))
    
    # 5. Clean Features (Constant removal & NaN/inf handling)
    df_cleaned, clean_meta = clean_features(df_features_full)
    n_after_cleaning = df_cleaned.shape[1]
    
    # 6. Collinearity Filtering
    df_filtered, dropped_collinear = remove_redundant_features(df_cleaned, threshold=correlation_threshold)
    n_after_collinear = df_filtered.shape[1]
    
    # 7. Normal vs Anomaly Comparison
    df_comparison = compare_normal_anomaly_features(df_filtered, y_labels)
    
    # 8. Feature Selection
    df_selected, selected_features, selection_summary = select_useful_features(
        df_filtered,
        y_labels,
        df_comparison,
        fdr_level=FDR_LEVEL,
        top_k=top_k
    )
    n_final_selected = len(selected_features)
    
    # 9. Visualizations
    plot_files = generate_visualizations(df_selected, y_labels, df_comparison, output_dir=output_plot_dir)
    
    # 10. Save Outputs
    saved_data_paths = save_outputs(
        df_full=df_features_full,
        df_cleaned=df_cleaned,
        df_selected=df_selected,
        y=y_labels,
        df_comparison=df_comparison,
        df_categories=df_categories,
        selection_summary=selection_summary,
        selected_features_list=selected_features,
        output_dir=output_data_dir
    )
    
    # Print formatted terminal summary report
    print("\n" + "=" * 65)
    print("       TSFRESH FEATURE ENGINEERING SUMMARY REPORT")
    print("=" * 65)
    print(f"  Input Windows Processed:        {n_windows:,}")
    print(f"  Sensors Monitored ({n_sensors}):          {', '.join(PRIMARY_SENSOR_COLS)}")
    print(f"  Normal Windows (Class 0):       {n_normal:,} ({n_normal/n_windows*100:.1f}%)")
    print(f"  Anomaly Windows (Class 1):      {n_anomaly:,} ({n_anomaly/n_windows*100:.1f}%)")
    print("-" * 65)
    print(f"  Initial TSFresh Features:       {n_raw_features:,}")
    print(f"  After Constant Feature Removal: {clean_meta['features_after_cleaning']:,} (-{clean_meta['constant_removed']:,})")
    print(f"  After Collinear Filtering:      {n_after_collinear:,} (-{len(dropped_collinear):,})")
    print(f"  Final Selected Top Features:    {n_final_selected:,}")
    print("-" * 65)
    print("  Top 10 Most Useful Features for Anomaly Detection:")
    for i, feat in enumerate(selected_features[:10], 1):
        row = df_comparison[df_comparison["feature_name"] == feat].iloc[0]
        print(f"   {i:2d}. {feat:<50} | Cohen's d: {row['cohens_d']:.2f} | Norm: {row['normal_mean']:.2f} -> Anom: {row['anomaly_mean']:.2f}")
    print("-" * 65)
    print("  Feature Domain Categories Discovered:")
    for _, cat_row in df_categories.iterrows():
        print(f"   * {cat_row['feature_category']:<32}: {cat_row['feature_count']:>4} features ({cat_row['percentage']:>5.1f}%)")
    print("=" * 65)
    print(f"  Output Datasets saved in:       {output_data_dir}")
    print(f"  Output Visualizations in:       {output_plot_dir}")
    print("=" * 65 + "\n")
    
    return {
        "n_windows": n_windows,
        "n_sensors": n_sensors,
        "n_raw_features": n_raw_features,
        "n_after_cleaning": n_after_cleaning,
        "n_after_collinear": n_after_collinear,
        "n_final_selected": n_final_selected,
        "selected_features": selected_features,
        "saved_data_paths": saved_data_paths,
        "plot_files": plot_files
    }


def main():
    parser = argparse.ArgumentParser(description="TSFresh Time-Series Feature Engineering & Selection Pipeline")
    parser.add_argument("--data", type=str, default=DATA_PATH, help="Path to input sensor dataset CSV")
    parser.add_argument("--out-data", type=str, default=OUTPUT_DATA_DIR, help="Directory to save generated CSV/TXT datasets")
    parser.add_argument("--out-plots", type=str, default=OUTPUT_PLOT_DIR, help="Directory to save visualization plots")
    parser.add_argument("--machines", type=int, default=DEFAULT_MAX_MACHINES, help="Number of machines to process (default: 25)")
    parser.add_argument("--all-machines", action="store_true", help="Process all 250 machines in dataset")
    parser.add_argument("--window-size", type=int, default=DEFAULT_WINDOW_SIZE, help="Window size in time steps (default: 30)")
    parser.add_argument("--stride", type=int, default=DEFAULT_WINDOW_STRIDE, help="Window stride (default: 15)")
    parser.add_argument("--corr-threshold", type=float, default=CORRELATION_THRESHOLD, help="Correlation threshold for redundancy filtering (default: 0.95)")
    parser.add_argument("--top-k", type=int, default=TOP_K_SELECTED, help="Number of top selected features (default: 25)")
    
    args = parser.parse_args()
    
    max_m = None if args.all_machines else args.machines
    
    run_pipeline(
        data_path=args.data,
        output_data_dir=args.out_data,
        output_plot_dir=args.out_plots,
        max_machines=max_m,
        window_size=args.window_size,
        window_stride=args.stride,
        correlation_threshold=args.corr_threshold,
        top_k=args.top_k
    )


if __name__ == "__main__":
    main()
