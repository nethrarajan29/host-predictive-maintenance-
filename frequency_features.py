"""
Person 2 Deliverable: Discrete Fourier Transform (DFT) & FFT Frequency-Domain Analysis Pipeline
---------------------------------------------------------------------------------------------
Converts multi-sensor time-series telemetry into the frequency domain using Fast Fourier Transform (FFT).
Extracts spectral features (dominant frequency, spectral energy, spectral centroid, spectral spread,
spectral skewness, peak power). Produces academic-grade spectral diagnostic plots comparing
NORMAL vs ANOMALOUS operating states.
"""

import os
import sys
import argparse
import logging
from typing import Dict, List, Tuple, Optional

import numpy as np
import pandas as pd
from scipy import stats
import matplotlib  # type: ignore
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # type: ignore

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("frequency_features")

PRIMARY_SENSOR_COLS = ["Temperature", "Vibration", "Motor_Current", "Pressure", "Noise"]
DEFAULT_WINDOW_SIZE = 30
DEFAULT_WINDOW_STRIDE = 15
DEFAULT_MAX_MACHINES = 25
SAMPLING_RATE_HZ = 1.0  # Normalized daily sampling rate (1 sample / unit time)


def load_dataset(filepath: str = "data/sensor_data.csv") -> pd.DataFrame:
    """Loads sensor dataset with fallback path resolution."""
    if not os.path.exists(filepath):
        alt = "datasets/sensor_data.csv"
        if os.path.exists(alt):
            filepath = alt
        else:
            raise FileNotFoundError(f"Sensor dataset not found at {filepath}")
            
    logger.info(f"Loading sensor dataset from {filepath}...")
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
    Segments the continuous sensor telemetry into identical temporal windows.
    Returns window data, labels (0=Normal, 1=Anomaly), and metadata.
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

            sensor_arrays = {
                sensor: window_slice[sensor].values.astype(float)
                for sensor in PRIMARY_SENSOR_COLS
            }

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
                "label": label
            })
            window_counter += 1

    return windows, labels, metadata


def compute_fft_spectral_features(signal: np.ndarray, prefix: str, fs: float = SAMPLING_RATE_HZ) -> Tuple[Dict[str, float], np.ndarray, np.ndarray, np.ndarray]:
    """
    Computes rigorous frequency-domain features using Discrete Fourier Transform via Fast Fourier Transform (FFT).
    
    Returns:
        - feature_dict: Dominant frequency, spectral energy, spectral centroid, spectral spread,
                        spectral skewness, spectral kurtosis, power spectrum peak.
        - freqs: Positive frequency bins.
        - magnitude_spectrum: Normalized magnitude |X(f)|.
        - power_spectrum: Power Spectral Density |X(f)|^2 / N.
    """
    N = len(signal)
    
    # Detrend / center signal to remove 0 Hz DC bias for dynamic frequency analysis
    mean_removed = signal - np.mean(signal)
    
    # Real Fast Fourier Transform (rfft)
    fft_complex = np.fft.rfft(mean_removed)
    freqs = np.fft.rfftfreq(N, d=1.0 / fs)
    
    # Magnitude spectrum (scaled by 2/N)
    magnitude = (2.0 / N) * np.abs(fft_complex)
    if len(magnitude) > 0:
        magnitude[0] = magnitude[0] / 2.0  # DC component adjustment
        
    # Power Spectrum (Power Spectral Density)
    power = (np.abs(fft_complex) ** 2) / float(N)

    # Exclude DC bin (f=0) for peak and centroid metrics
    ac_freqs = freqs[1:] if len(freqs) > 1 else freqs
    ac_mag = magnitude[1:] if len(magnitude) > 1 else magnitude
    ac_power = power[1:] if len(power) > 1 else power

    total_energy = float(np.sum(power))
    total_mag = float(np.sum(ac_mag))

    if len(ac_mag) > 0 and np.max(ac_mag) > 1e-9:
        peak_idx = int(np.argmax(ac_mag))
        dominant_freq = float(ac_freqs[peak_idx])
        peak_amplitude = float(ac_mag[peak_idx])
    else:
        dominant_freq = 0.0
        peak_amplitude = 0.0

    # Spectral Centroid (Center of Mass of spectrum)
    if total_mag > 1e-9:
        spectral_centroid = float(np.sum(ac_freqs * ac_mag) / total_mag)
        # Spectral Spread (Bandwidth)
        spectral_spread = float(np.sqrt(np.sum(((ac_freqs - spectral_centroid) ** 2) * ac_mag) / total_mag))
    else:
        spectral_centroid = 0.0
        spectral_spread = 0.0

    # Spectral Moments: Skewness & Kurtosis
    if spectral_spread > 1e-9 and total_mag > 1e-9:
        spectral_skew = float(np.sum(((ac_freqs - spectral_centroid) ** 3) * ac_mag) / (total_mag * (spectral_spread ** 3)))
        spectral_kurt = float(np.sum(((ac_freqs - spectral_centroid) ** 4) * ac_mag) / (total_mag * (spectral_spread ** 4)))
    else:
        spectral_skew = 0.0
        spectral_kurt = 0.0

    # Mean and Max Power
    mean_power = float(np.mean(ac_power)) if len(ac_power) > 0 else 0.0
    max_power = float(np.max(ac_power)) if len(ac_power) > 0 else 0.0

    feature_dict = {
        f"{prefix}__dominant_freq": dominant_freq,
        f"{prefix}__fft_peak_amplitude": peak_amplitude,
        f"{prefix}__spectral_energy": total_energy,
        f"{prefix}__spectral_centroid": spectral_centroid,
        f"{prefix}__spectral_spread": spectral_spread,
        f"{prefix}__spectral_skewness": spectral_skew,
        f"{prefix}__spectral_kurtosis": spectral_kurt,
        f"{prefix}__mean_power_spectrum": mean_power,
        f"{prefix}__max_power_spectrum": max_power,
    }

    return feature_dict, freqs, magnitude, power


def plot_frequency_domain_comparison(
    normal_sig: np.ndarray,
    anomaly_sig: np.ndarray,
    sensor_name: str,
    output_dir: str = "outputs/frequency"
):
    """
    Generates 3 academic comparison plots:
      1. Time-Domain Signal (Normal vs Anomaly)
      2. FFT Magnitude Spectrum (Normal vs Anomaly)
      3. Power Spectral Density (Normal vs Anomaly)
    """
    os.makedirs(output_dir, exist_ok=True)
    _, norm_freqs, norm_mag, norm_psd = compute_fft_spectral_features(normal_sig, sensor_name)
    _, anom_freqs, anom_mag, anom_psd = compute_fft_spectral_features(anomaly_sig, sensor_name)

    time_steps = np.arange(len(normal_sig))

    fig, axes = plt.subplots(3, 1, figsize=(10, 11), dpi=200)
    plt.subplots_adjust(hspace=0.45)

    # 1. Time-Domain Waveforms
    axes[0].plot(time_steps, normal_sig, label="Normal Operation", color="#10B981", lw=2, alpha=0.9)
    axes[0].plot(time_steps, anomaly_sig, label="Anomalous / Degraded", color="#EF4444", lw=2, ls="--", alpha=0.9)
    axes[0].set_title(f"Time-Domain Telemetry Comparison — {sensor_name}", fontsize=13, fontweight="bold", pad=10)
    axes[0].set_xlabel("Time Step (Days)", fontsize=11)
    axes[0].set_ylabel(f"{sensor_name} Value", fontsize=11)
    axes[0].grid(True, linestyle=":", alpha=0.6)
    axes[0].legend(loc="upper right", framealpha=0.9)

    # 2. FFT Magnitude Spectrum
    axes[1].plot(norm_freqs[1:], norm_mag[1:], label="Normal FFT Magnitude", color="#10B981", lw=2)
    axes[1].plot(anom_freqs[1:], anom_mag[1:], label="Anomaly FFT Magnitude", color="#EF4444", lw=2, ls="--")
    axes[1].set_title(f"FFT Magnitude Spectrum |X(f)| — {sensor_name}", fontsize=13, fontweight="bold", pad=10)
    axes[1].set_xlabel("Normalized Frequency (Cycles / Day)", fontsize=11)
    axes[1].set_ylabel("Normalized Magnitude", fontsize=11)
    axes[1].grid(True, linestyle=":", alpha=0.6)
    axes[1].legend(loc="upper right", framealpha=0.9)

    # 3. Power Spectral Density (PSD)
    axes[2].semilogy(norm_freqs[1:], norm_psd[1:] + 1e-6, label="Normal PSD (Power)", color="#10B981", lw=2)
    axes[2].semilogy(anom_freqs[1:], anom_psd[1:] + 1e-6, label="Anomaly PSD (Power)", color="#EF4444", lw=2, ls="--")
    axes[2].set_title(f"Power Spectral Density (Log-Scale) — {sensor_name}", fontsize=13, fontweight="bold", pad=10)
    axes[2].set_xlabel("Normalized Frequency (Cycles / Day)", fontsize=11)
    axes[2].set_ylabel("Power Density (|X(f)|² / N)", fontsize=11)
    axes[2].grid(True, linestyle=":", alpha=0.6)
    axes[2].legend(loc="upper right", framealpha=0.9)

    plot_path = os.path.join(output_dir, f"{sensor_name.lower()}_fft_psd_comparison.png")
    plt.savefig(plot_path, bbox_inches="tight")
    plt.close()
    logger.info(f"Saved frequency diagnostic plot: {plot_path}")


def extract_frequency_features(
    data_path: str = "data/sensor_data.csv",
    output_path: str = "data/frequency_features.csv",
    summary_path: str = "data/frequency_features_summary.csv",
    plot_dir: str = "outputs/frequency"
) -> pd.DataFrame:
    """
    Executes end-to-end frequency feature extraction, normal vs anomaly statistical testing,
    and generates spectral comparison plots.
    """
    df = load_dataset(data_path)
    windows, labels, metadata = segment_time_windows(df)
    logger.info(f"Segmented telemetry into {len(windows)} windows ({labels.count(0)} Normal, {labels.count(1)} Anomaly)")

    feature_rows = []
    first_normal_window = None
    first_anomaly_window = None

    for w_idx, (sensor_data, label) in enumerate(zip(windows, labels)):
        if label == 0 and first_normal_window is None:
            first_normal_window = sensor_data
        elif label == 1 and first_anomaly_window is None:
            first_anomaly_window = sensor_data

        row = {
            "window_id": w_idx,
            "label": label
        }
        for sensor_name, sig in sensor_data.items():
            f_dict, _, _, _ = compute_fft_spectral_features(sig, prefix=sensor_name)
            row.update(f_dict)
        feature_rows.append(row)

    df_features = pd.DataFrame(feature_rows)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df_features.to_csv(output_path, index=False)
    logger.info(f"Saved {len(df_features)} frequency feature vectors to {output_path} ({df_features.shape[1] - 2} features per window)")

    # Generate comparison plots for key sensors (Vibration & Motor_Current)
    if first_normal_window and first_anomaly_window:
        for sensor in ["Vibration", "Motor_Current", "Temperature"]:
            plot_frequency_domain_comparison(
                first_normal_window[sensor],
                first_anomaly_window[sensor],
                sensor,
                output_dir=plot_dir
            )

    # Statistical comparison: Normal vs Anomaly
    feature_cols = [c for c in df_features.columns if c not in ["window_id", "label"]]
    summary_rows = []

    norm_mask = df_features["label"] == 0
    anom_mask = df_features["label"] == 1

    for col in feature_cols:
        norm_vals = df_features.loc[norm_mask, col].values
        anom_vals = df_features.loc[anom_mask, col].values

        n_mean, a_mean = float(np.mean(norm_vals)), float(np.mean(anom_vals))
        n_std, a_std = float(np.std(norm_vals, ddof=1)), float(np.std(anom_vals, ddof=1))

        n1, n2 = len(norm_vals), len(anom_vals)
        pooled_std = np.sqrt(((n1 - 1) * n_std**2 + (n2 - 1) * a_std**2) / (n1 + n2 - 2))
        cohen_d = abs(a_mean - n_mean) / pooled_std if pooled_std > 1e-9 else 0.0

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
            "metric": stat_name,
            "normal_mean": round(n_mean, 4),
            "anomaly_mean": round(a_mean, 4),
            "mean_difference": round(a_mean - n_mean, 4),
            "cohens_d": round(cohen_d, 4),
            "p_value": p_val,
            "significant": p_val < 0.01 and cohen_d > 0.8
        })

    df_summary = pd.DataFrame(summary_rows).sort_values(by="cohens_d", ascending=False)
    df_summary.to_csv(summary_path, index=False)
    logger.info(f"Saved frequency-domain statistical summary to {summary_path}")

    print("\n" + "="*70)
    print(" PERSON 2: TOP 10 DISCRIMINATIVE FREQUENCY/FFT FEATURES (COHEN'S D)")
    print("="*70)
    top_10 = df_summary.head(10)[["feature", "normal_mean", "anomaly_mean", "cohens_d", "p_value"]]
    print(top_10.to_string(index=False))
    print("="*70 + "\n")

    return df_features


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract FFT & Frequency-Domain Features")
    parser.add_argument("--data", default="data/sensor_data.csv", help="Input sensor dataset")
    parser.add_argument("--output", default="data/frequency_features.csv", help="Output frequency feature CSV")
    parser.add_argument("--summary", default="data/frequency_features_summary.csv", help="Output summary CSV")
    parser.add_argument("--plot-dir", default="outputs/frequency", help="Directory for spectral plots")
    args = parser.parse_args()

    extract_frequency_features(args.data, args.output, args.summary, args.plot_dir)
