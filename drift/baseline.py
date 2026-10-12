"""
Drift Baseline Manager
----------------------
Manages the reference baseline statistical distribution derived from historical
known-normal industrial telemetry and ML predictions.

Rules:
- The baseline represents normal operational state.
- The baseline does NOT auto-update automatically to prevent drift masking.
- Rebuilding or updating the baseline requires an explicit intentional operation.
- Persisted to disk as JSON metadata + quantiles for fast PSI/KS computations.
"""

import os
import json
import logging
import datetime
from typing import Dict, List, Any, Optional
import numpy as np
import pandas as pd

from .config import config

logger = logging.getLogger("drift_baseline")


class BaselineManager:
    """Calculates, serializes, and inspects the reference baseline dataset."""

    def __init__(self, baseline_file: str = None, historical_data_file: str = None):
        self.baseline_file = baseline_file or config.BASELINE_FILE_PATH
        self.historical_data_file = historical_data_file or config.HISTORICAL_SENSOR_DATA
        self.baseline_data: Optional[Dict[str, Any]] = None
        self.load_or_build_baseline()

    def load_or_build_baseline(self, force_rebuild: bool = False) -> Dict[str, Any]:
        """Loads baseline from file, or builds it from historical sensor data if not present."""
        if not force_rebuild and os.path.exists(self.baseline_file):
            try:
                with open(self.baseline_file, "r") as f:
                    self.baseline_data = json.load(f)
                logger.info(f"Loaded existing drift baseline from {self.baseline_file}")
                return self.baseline_data
            except Exception as e:
                logger.warning(f"Failed to read baseline file {self.baseline_file}: {e}. Rebuilding...")

        logger.info("Building new reference baseline dataset from historical data...")
        return self.build_baseline_from_data()

    def build_baseline_from_data(self, custom_df: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Computes baseline statistics and reference quantile bin edges for each feature
        using normal operating state records.
        """
        if custom_df is not None:
            df = custom_df.copy()
        else:
            if not os.path.exists(self.historical_data_file):
                raise FileNotFoundError(f"Historical sensor dataset not found at {self.historical_data_file}")
            df = pd.read_csv(self.historical_data_file)

        # Standardize column naming
        col_rename = {
            "Motor_Temp": "Temperature",
            "Vibration_X": "Vibration",
            "Pressure_Inlet": "Pressure"
        }
        for old_k, new_k in col_rename.items():
            if old_k in df.columns and new_k not in df.columns:
                df[new_k] = df[old_k]

        # Target primary telemetry features
        monitored_features = ["Temperature", "Vibration", "Motor_Current", "Pressure", "Noise"]
        available_features = [f for f in monitored_features if f in df.columns]

        if not available_features:
            raise ValueError(f"No monitored features found in dataset. Expected one of {monitored_features}")

        # Filter to normal health operational regime if Machine_Health / degradation present
        if "Machine_Health" in df.columns:
            normal_df = df[df["Machine_Health"] >= 75.0]
            if len(normal_df) > 50:
                df = normal_df
        elif "Health" in df.columns:
            normal_df = df[df["Health"] >= 75.0]
            if len(normal_df) > 50:
                df = normal_df

        features_meta: Dict[str, Any] = {}
        n_bins = 5

        for col in available_features:
            vals = pd.to_numeric(df[col], errors="coerce").dropna().values
            if len(vals) < 10:
                continue

            vals_clean = vals[np.isfinite(vals)]
            mean_val = float(np.mean(vals_clean))
            std_val = float(np.std(vals_clean))
            min_val = float(np.min(vals_clean))
            max_val = float(np.max(vals_clean))
            median_val = float(np.median(vals_clean))
            q25 = float(np.percentile(vals_clean, 25))
            q75 = float(np.percentile(vals_clean, 75))

            # Generate 5 quantile bin edges for PSI calculation (ensures robust small-window behavior)
            quantiles = np.linspace(0, 100, n_bins + 1)
            bin_edges = np.percentile(vals_clean, quantiles)
            bin_edges[0] = -np.inf
            bin_edges[-1] = np.inf
            for i in range(1, len(bin_edges) - 1):
                if bin_edges[i] <= bin_edges[i - 1]:
                    bin_edges[i] = bin_edges[i - 1] + 1e-4

            # Baseline bin frequencies with Laplace smoothing
            counts, _ = np.histogram(vals_clean, bins=bin_edges)
            total_n = len(vals_clean)
            baseline_probs = [(c + 1) / (total_n + n_bins) for c in counts]

            # Pre-saved reference values (subsampled up to 500 points for fast 2-sample KS tests)
            subsample = vals_clean if len(vals_clean) <= 500 else np.random.choice(vals_clean, size=500, replace=False)

            features_meta[col] = {
                "mean": round(mean_val, 4),
                "std": round(std_val, 4),
                "min": round(min_val, 4),
                "max": round(max_val, 4),
                "median": round(median_val, 4),
                "q25": round(q25, 4),
                "q75": round(q75, 4),
                "bin_edges": [round(b, 6) if np.isfinite(b) else ("-inf" if b < 0 else "inf") for b in bin_edges],
                "baseline_probs": [round(p, 6) for p in baseline_probs],
                "sample_values": [round(float(x), 4) for x in subsample.tolist()]
            }

        # Baseline predictions distribution (Normal regime RUL: 200-250 days, Anomaly rate: ~0%)
        rul_vals = df["Remaining_Useful_Life_Days"].dropna().values if "Remaining_Useful_Life_Days" in df.columns else np.array([250.0, 240.0, 230.0, 220.0, 210.0])
        rul_clean = rul_vals[np.isfinite(rul_vals)]
        rul_bins = np.linspace(0, 300, 6)
        rul_bins[0] = -np.inf
        rul_bins[-1] = np.inf
        rul_counts, _ = np.histogram(rul_clean, bins=rul_bins)
        rul_probs = [(c + 1) / (len(rul_clean) + 5) for c in rul_counts]

        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        baseline_record = {
            "baseline_id": f"BL-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}",
            "version": "1.0.0",
            "created_at": now_str,
            "source_dataset": os.path.basename(self.historical_data_file),
            "sample_count": len(df),
            "feature_count": len(features_meta),
            "feature_names": list(features_meta.keys()),
            "features": features_meta,
            "prediction_baseline": {
                "target": "predicted_rul_days",
                "mean": round(float(np.mean(rul_clean)), 2),
                "std": round(float(np.std(rul_clean)), 2),
                "bin_edges": [round(b, 2) if np.isfinite(b) else ("-inf" if b < 0 else "inf") for b in rul_bins],
                "baseline_probs": [round(p, 6) for p in rul_probs],
                "expected_anomaly_rate_pct": 2.0
            }
        }

        # Persist to disk
        os.makedirs(os.path.dirname(os.path.abspath(self.baseline_file)), exist_ok=True)
        with open(self.baseline_file, "w") as f:
            json.dump(baseline_record, f, indent=2)

        self.baseline_data = baseline_record
        logger.info(f"Successfully generated and saved baseline metadata to {self.baseline_file}")
        return self.baseline_data

    def get_baseline(self) -> Dict[str, Any]:
        """Returns active baseline dictionary."""
        if self.baseline_data is None:
            self.load_or_build_baseline()
        return self.baseline_data

    def get_feature_baseline(self, feature_name: str) -> Optional[Dict[str, Any]]:
        """Returns baseline statistics for a single feature."""
        b = self.get_baseline()
        if not b or "features" not in b:
            return None
        
        aliases = {
            "Motor_Temp": "Temperature",
            "Vibration_X": "Vibration",
            "Pressure_Inlet": "Pressure"
        }
        resolved = aliases.get(feature_name, feature_name)
        return b["features"].get(resolved, b["features"].get(feature_name, None))


# Singleton baseline manager instance
baseline_mgr = BaselineManager()
