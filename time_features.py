"""
Person 1 Deliverable: Time-Domain Statistical Feature Extraction Pipeline
-----------------------------------------------------------------------
Extracts comprehensive statistical time-domain features from continuous multi-sensor
telemetry across rolling temporal windows. Evaluates discriminative power between
NORMAL and ANOMALOUS machine operation using effect sizes (Cohen's d) and statistical testing.
"""

import os
import sys
import argparse
import logging
from typing import Dict, List, Tuple, Optional

import numpy as np
import pandas as pd
from scipy import stats

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("time_features")

# Primary sensor channels
PRIMARY_SENSOR_COLS = ["Temperature", "Vibration", "Motor_Current", "Pressure", "Noise"]
DEFAULT_WINDOW_SIZE = 30
DEFAULT_WINDOW_STRIDE = 15
DEFAULT_MAX_MACHINES = 25


def load_dataset(filepath: str = "data/sensor_data.csv") -> pd.DataFrame:
    """Loads sensor dataset with fallback path handling."""
    if not os.path.exists(filepath):
        alt = "datasets/sensor_data.csv"
        if os.path.exists(alt):
            filepath = alt
        else:
            raise FileNotFoundError(f"Sensor dataset not found at {filepath}")
            
    logger.info(f"Loading sensor data from {filepath}...")
    df = pd.read_csv(filepath)
    df[PRIMARY_SENSOR_COLS] = df[PRIMARY_SENSOR_COLS].ffill().bfill()
    return df


def segment_time_windows(
    df: pd.DataFrame,
    window_size: int = DEFAULT_WINDOW_SIZE,
    stride: int = DEFAULT_WINDOW_STRIDE,
    max_machines: Optional[int] = DEFAULT_MAX_MACHINES
) -> Tuple[List[Dict[str, np.ndarray]], List[int], List[Dict]]:
    """
    Segments the time series into discrete windows matching Person 3's windowing scheme.
    Returns window data, binary labels (0=Normal, 1=Anomaly), and metadata.
    """
    steps_per_machine = 365
    total_records = len(df)
    total_machines = total_records // steps_per_machine

    machine_ids = []
    for m in range(total_machines):
        machine_ids.extend([m + 1] * steps_per_machine)
    if len(machine_ids) < total_records:
        machine_ids.extend([total_machines + 1] * (total_records - len(machine_ids)))
    
    df_ts = df.copy()
    df_ts["Machine_ID"] = machine_ids[:total_records]
    
    if max_machines is not None and max_machines < total_machines:
        df_ts = df_ts[df_ts["Machine_ID"] <= max_machines].copy()

    windows = []
    labels = []
    metadata = []
    window_counter = 0

    grouped = df_ts.groupby("Machine_ID")
    for machine_id, group in grouped:
        group = group.reset_index(drop=True)
        n_steps = len(group)
        for start_idx in range(0, n_steps - window_size + 1, stride):
            end_idx = start_idx + window_size
            window_slice = group.iloc[start_idx:end_idx]

            # Sensor arrays
            sensor_arrays = {
                sensor: window_slice[sensor].values.astype(float)
                for sensor in PRIMARY_SENSOR_COLS
            }
            
            # Ground truth label
            status_series = window_slice["Machine_Status"].astype(str)
            has_anomaly = not (status_series == "Healthy").all()
            mean_health = float(window_slice["Machine_Health"].mean()) if "Machine_Health" in window_slice else 100.0
            label = 1 if (has_anomaly or mean_health < 80.0) else 0

            windows.append(sensor_arrays)
            labels.append(label)
            metadata.append({
                "window_id": window_counter,
                "machine_id": machine_id,
                "start_step": start_idx,
                "end_step": end_idx,
                "mean_health": round(mean_health, 2),
                "label": label,
                "label_name": "ANOMALY" if label == 1 else "NORMAL"
            })
            window_counter += 1

    return windows, labels, metadata


def compute_time_domain_stats(signal: np.ndarray, prefix: str) -> Dict[str, float]:
    """
    Computes rigorous statistical time-domain features for a 1D signal vector.
    Features:
      - mean, median, min, max, range
      - variance, std, rms
      - skewness, kurtosis
      - peak_to_peak, crest_factor, shape_factor
    """
    mean_val = float(np.mean(signal))
    median_val = float(np.median(signal))
    min_val = float(np.min(signal))
    max_val = float(np.max(signal))
    range_val = float(max_val - min_val)
    var_val = float(np.var(signal, ddof=1)) if len(signal) > 1 else 0.0
    std_val = float(np.std(signal, ddof=1)) if len(signal) > 1 else 0.0
    rms_val = float(np.sqrt(np.mean(signal ** 2)))
    
    # Skewness & Kurtosis
    skew_val = float(stats.skew(signal, bias=False)) if std_val > 1e-9 else 0.0
    kurt_val = float(stats.kurtosis(signal, bias=False)) if std_val > 1e-9 else 0.0
    peak_val = float(np.max(np.abs(signal)))
    
    # Industrial vibration & mechanical shape factors
    crest_factor = float(peak_val / rms_val) if rms_val > 1e-9 else 1.0
    shape_factor = float(rms_val / abs(mean_val)) if abs(mean_val) > 1e-9 else 1.0

    return {
        f"{prefix}__mean": mean_val,
        f"{prefix}__median": median_val,
        f"{prefix}__min": min_val,
        f"{prefix}__max": max_val,
        f"{prefix}__range": range_val,
        f"{prefix}__variance": var_val,
        f"{prefix}__std": std_val,
        f"{prefix}__rms": rms_val,
        f"{prefix}__skewness": skew_val,
        f"{prefix}__kurtosis": kurt_val,
        f"{prefix}__peak_to_peak": range_val,
        f"{prefix}__crest_factor": crest_factor,
        f"{prefix}__shape_factor": shape_factor,
    }


def extract_time_features(
    data_path: str = "data/sensor_data.csv",
    output_path: str = "data/time_features.csv",
    summary_path: str = "data/time_features_summary.csv"
) -> pd.DataFrame:
    """
    Executes end-to-end time-domain feature extraction, statistical testing,
    and saves output files.
    """
    df = load_dataset(data_path)
    windows, labels, metadata = segment_time_windows(df)
    logger.info(f"Segmented telemetry into {len(windows)} windows ({labels.count(0)} Normal, {labels.count(1)} Anomaly)")

    feature_rows = []
    for w_idx, (sensor_data, label) in enumerate(zip(windows, labels)):
        row = {
            "window_id": w_idx,
            "label": label
        }
        for sensor_name, sig in sensor_data.items():
            stats_dict = compute_time_domain_stats(sig, prefix=sensor_name)
            row.update(stats_dict)
        feature_rows.append(row)

    df_features = pd.DataFrame(feature_rows)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df_features.to_csv(output_path, index=False)
    logger.info(f"Saved {len(df_features)} extracted time-domain feature vectors to {output_path} ({df_features.shape[1] - 2} features per window)")

    # Statistical comparison: Normal vs Anomaly
    feature_cols = [c for c in df_features.columns if c not in ["window_id", "label"]]
    summary_rows = []

    norm_mask = df_features["label"] == 0
    anom_mask = df_features["label"] == 1

    for col in feature_cols:
        norm_vals = df_features.loc[norm_mask, col].values
        anom_vals = df_features.loc[anom_mask, col].values

        n_mean, a_mean = np.mean(norm_vals), np.mean(anom_vals)
        n_std, a_std = np.std(norm_vals, ddof=1), np.std(anom_vals, ddof=1)

        # Pooled standard deviation & Cohen's d
        n1, n2 = len(norm_vals), len(anom_vals)
        pooled_std = np.sqrt(((n1 - 1) * n_std**2 + (n2 - 1) * a_std**2) / (n1 + n2 - 2))
        cohen_d = abs(a_mean - n_mean) / pooled_std if pooled_std > 1e-9 else 0.0

        # Mann-Whitney U test for non-parametric significance
        try:
            stat_res = stats.mannwhitneyu(norm_vals, anom_vals, alternative='two-sided')
            p_val = float(stat_res.pvalue)
        except Exception:
            p_val = 1.0

        sensor_origin = col.split("__")[0]
        stat_name = col.split("__")[1]

        summary_rows.append({
            "feature": col,
            "sensor": sensor_origin,
            "statistic": stat_name,
            "normal_mean": round(n_mean, 4),
            "anomaly_mean": round(a_mean, 4),
            "mean_difference": round(a_mean - n_mean, 4),
            "normal_std": round(n_std, 4),
            "anomaly_std": round(a_std, 4),
            "cohens_d": round(cohen_d, 4),
            "p_value": p_val,
            "significant": p_val < 0.01 and cohen_d > 0.8
        })

    df_summary = pd.DataFrame(summary_rows).sort_values(by="cohens_d", ascending=False)
    df_summary.to_csv(summary_path, index=False)
    logger.info(f"Saved Normal vs Anomaly statistical summary to {summary_path}")

    # Log Top 10 discriminative features
    print("\n" + "="*70)
    print(" PERSON 1: TOP 10 DISCRIMINATIVE TIME-DOMAIN FEATURES (COHEN'S D)")
    print("="*70)
    top_10 = df_summary.head(10)[["feature", "normal_mean", "anomaly_mean", "cohens_d", "p_value"]]
    print(top_10.to_string(index=False))
    print("="*70 + "\n")

    return df_features


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract Time-Domain Features")
    parser.add_argument("--data", default="data/sensor_data.csv", help="Input sensor dataset")
    parser.add_argument("--output", default="data/time_features.csv", help="Output feature CSV")
    parser.add_argument("--summary", default="data/time_features_summary.csv", help="Output summary CSV")
    args = parser.parse_args()

    extract_time_features(args.data, args.output, args.summary)
