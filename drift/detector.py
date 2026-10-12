"""
Statistical Drift & Data Quality Detector
------------------------------------------
Implements production-grade statistical drift detection and data quality validation:
  1. Population Stability Index (PSI) with Laplace Smoothing
  2. Pure NumPy Two-Sample Kolmogorov-Smirnov (KS) Test & Wasserstein Distance
  3. Prediction Drift (RUL Distribution Shift & Anomaly Rate Drift)
  4. Data Quality Checks (Missingness, Stuck Sensors, Physical Out-of-Bounds)
  5. Overall Model Health Synthesis & Root-Cause Explainability
"""

import math
import logging
from typing import Dict, List, Any, Tuple, Optional
import numpy as np

from .config import config
from .baseline import baseline_mgr

logger = logging.getLogger("drift_detector")


def calculate_psi(expected_probs: List[float], actual_values: np.ndarray, bin_edges: List[Any]) -> float:
    """
    Computes Population Stability Index (PSI) using reference baseline bin edges
    with Laplace pseudocount smoothing for sample robustness.
    PSI = sum((Actual% - Expected%) * ln(Actual% / Expected%))
    """
    if len(actual_values) == 0 or len(expected_probs) == 0:
        return 0.0

    # Parse numeric edges
    numeric_edges = []
    for b in bin_edges:
        if b == "-inf":
            numeric_edges.append(-np.inf)
        elif b == "inf":
            numeric_edges.append(np.inf)
        else:
            numeric_edges.append(float(b))

    # Count observed samples per baseline bin
    actual_counts, _ = np.histogram(actual_values, bins=numeric_edges)
    total_actual = len(actual_values)
    n_bins = len(expected_probs)
    
    # Calculate actual probabilities with Laplace pseudocount smoothing
    actual_probs = [(c + 1.0) / (total_actual + n_bins) for c in actual_counts]

    psi_val = 0.0
    for exp_p, act_p in zip(expected_probs, actual_probs):
        e_val = max(1e-5, exp_p)
        a_val = max(1e-5, act_p)
        psi_val += (a_val - e_val) * math.log(a_val / e_val)

    return float(max(0.0, psi_val))


def compute_ks_2samp(data1: np.ndarray, data2: np.ndarray) -> Tuple[float, float]:
    """
    Vectorized Two-Sample Kolmogorov-Smirnov Test.
    Returns (statistic, p_value).
    """
    d1 = np.sort(data1[np.isfinite(data1)])
    d2 = np.sort(data2[np.isfinite(data2)])
    n1 = len(d1)
    n2 = len(d2)
    if n1 == 0 or n2 == 0:
        return 0.0, 1.0

    all_data = np.concatenate([d1, d2])
    cdf1 = np.searchsorted(d1, all_data, side='right') / n1
    cdf2 = np.searchsorted(d2, all_data, side='right') / n2
    d_stat = float(np.max(np.abs(cdf1 - cdf2)))

    # Asymptotic Kolmogorov-Smirnov p-value approximation
    en = np.sqrt((n1 * n2) / (n1 + n2))
    lambda_val = (en + 0.12 + 0.11 / max(1e-3, en)) * d_stat
    
    if lambda_val <= 0:
        pval = 1.0
    else:
        k = np.arange(1, 35)
        terms = 2.0 * ((-1.0) ** (k - 1)) * np.exp(-2.0 * (k ** 2) * (lambda_val ** 2))
        pval = float(np.clip(np.sum(terms), 0.0, 1.0))
        
    return round(d_stat, 4), round(pval, 4)


def compute_wasserstein_1d(u: np.ndarray, v: np.ndarray) -> float:
    """
    Computes the 1st Wasserstein Distance (Earth Mover's Distance) between two 1D empirical distributions.
    """
    u_clean = np.sort(u[np.isfinite(u)])
    v_clean = np.sort(v[np.isfinite(v)])
    if len(u_clean) == 0 or len(v_clean) == 0:
        return 0.0

    all_values = np.concatenate([u_clean, v_clean])
    all_values.sort()
    if len(all_values) <= 1:
        return 0.0

    u_cdf = np.searchsorted(u_clean, all_values[:-1], side='right') / len(u_clean)
    v_cdf = np.searchsorted(v_clean, all_values[:-1], side='right') / len(v_clean)
    deltas = np.diff(all_values)
    
    return float(np.sum(np.abs(u_cdf - v_cdf) * deltas))


class DriftDetector:
    """Evaluates telemetry windows against baseline distributions."""

    def __init__(self, config_obj=None, baseline_manager=None):
        self.config = config_obj or config
        self.baseline_manager = baseline_manager or baseline_mgr

    def evaluate_feature_drift(self, feature_name: str, current_values: List[float]) -> Dict[str, Any]:
        """
        Runs statistical tests (PSI, KS-Test, Wasserstein) for a single feature.
        """
        base_feat = self.baseline_manager.get_feature_baseline(feature_name)
        if not base_feat:
            arr = np.array(current_values, dtype=float)
            arr = arr[np.isfinite(arr)]
            return {
                "feature_name": feature_name,
                "baseline_mean": 0.0,
                "baseline_std": 0.0,
                "current_mean": round(float(np.mean(arr)), 2) if len(arr) > 0 else 0.0,
                "current_std": round(float(np.std(arr)), 2) if len(arr) > 0 else 0.0,
                "psi_score": 0.0,
                "ks_statistic": 0.0,
                "ks_pvalue": 1.0,
                "wasserstein_distance": 0.0,
                "drift_status": "NORMAL",
                "explanation": "No baseline registered for this feature."
            }

        raw_vals = [float(v) for v in current_values if v is not None and isinstance(v, (int, float)) and not np.isnan(v) and np.isfinite(v)]
        min_samples = max(5, getattr(self.config, "MIN_SAMPLES_FOR_EVALUATION", 10) // 2)
        if len(raw_vals) < min_samples:
            return {
                "feature_name": feature_name,
                "baseline_mean": base_feat["mean"],
                "baseline_std": base_feat["std"],
                "current_mean": round(float(np.mean(raw_vals)), 2) if len(raw_vals) > 0 else base_feat["mean"],
                "current_std": round(float(np.std(raw_vals)), 2) if len(raw_vals) > 0 else base_feat["std"],
                "psi_score": 0.0,
                "ks_statistic": 0.0,
                "ks_pvalue": 1.0,
                "wasserstein_distance": 0.0,
                "drift_status": "INSUFFICIENT_DATA",
                "status_label": "Insufficient Data",
                "valid_sample_count": len(raw_vals),
                "required_sample_count": min_samples,
                "drift_vs_failure_note": "Insufficient valid samples to confirm statistical distribution drift.",
                "explanation": f"Insufficient valid data points ({len(raw_vals)}/{min_samples} required) in current window."
            }

        arr_curr = np.array(raw_vals)
        curr_mean = float(np.mean(arr_curr))
        curr_std = float(np.std(arr_curr))

        # 1. Population Stability Index (PSI)
        psi_score = calculate_psi(
            expected_probs=base_feat["baseline_probs"],
            actual_values=arr_curr,
            bin_edges=base_feat["bin_edges"]
        )

        # 2. Two-Sample Kolmogorov-Smirnov (KS) Test
        base_samples = np.array(base_feat.get("sample_values", []))
        if len(base_samples) > 5 and len(arr_curr) > 5:
            ks_stat, ks_pval = compute_ks_2samp(base_samples, arr_curr)
        else:
            ks_stat, ks_pval = 0.0, 1.0

        # 3. Wasserstein Distance
        if len(base_samples) > 5:
            w_dist = compute_wasserstein_1d(base_samples, arr_curr)
        else:
            w_dist = float(abs(curr_mean - base_feat["mean"]))

        # Determine drift status from PSI and KS-test
        if psi_score >= self.config.PSI_CRITICAL_THRESHOLD or (ks_pval < 0.001 and psi_score >= 0.15):
            drift_status = "CRITICAL"
            status_label = "Drift Detected (Critical)"
        elif psi_score >= self.config.PSI_WARNING_THRESHOLD or (ks_pval < self.config.KS_PVALUE_THRESHOLD and psi_score >= 0.08):
            drift_status = "WARNING"
            status_label = "Drift Detected (Warning)"
        else:
            drift_status = "NORMAL"
            status_label = "Normal"

        # Generate explainable human-readable narrative
        delta_pct = ((curr_mean - base_feat["mean"]) / max(0.01, abs(base_feat["mean"]))) * 100.0
        direction = "increased" if delta_pct > 0 else "decreased"
        abs_delta = abs(delta_pct)

        if drift_status == "CRITICAL":
            explanation = (
                f"{feature_name} exhibits severe distribution shift (PSI={psi_score:.3f}, p={ks_pval:.4f}). "
                f"Mean has {direction} by {abs_delta:.1f}% ({base_feat['mean']:.2f} -> {curr_mean:.2f}). "
                f"Note: Data drift indicates distribution change (e.g. operating load regime shift, sensor offset, or developing wear) and should trigger investigation rather than automatically proving equipment failure."
            )
            drift_vs_failure_note = (
                "Drift Detected: Statistical distribution diverges from training reference. "
                "Requires investigation to distinguish operating regime change or sensor calibration shift from physical equipment failure."
            )
        elif drift_status == "WARNING":
            explanation = (
                f"{feature_name} exhibits moderate statistical shift (PSI={psi_score:.3f}, p={ks_pval:.4f}). "
                f"Mean {direction} by {abs_delta:.1f}% ({base_feat['mean']:.2f} -> {curr_mean:.2f}). "
                f"Possible load adjustment, ambient shift, or early wear—investigate before assuming fault."
            )
            drift_vs_failure_note = (
                "Drift Detected: Moderate statistical shift. Trigger diagnostic investigation; does not automatically prove hardware failure."
            )
        else:
            explanation = (
                f"{feature_name} distribution is stable (PSI={psi_score:.3f}, p={ks_pval:.4f}) and matches reference baseline."
            )
            drift_vs_failure_note = "Normal: Incoming sensor distribution is consistent with reference baseline."

        return {
            "feature_name": feature_name,
            "baseline_mean": base_feat["mean"],
            "baseline_std": base_feat["std"],
            "current_mean": round(curr_mean, 2),
            "current_std": round(curr_std, 2),
            "psi_score": round(psi_score, 4),
            "ks_statistic": round(ks_stat, 4),
            "ks_pvalue": round(ks_pval, 4),
            "wasserstein_distance": round(w_dist, 3),
            "drift_status": drift_status,
            "status_label": status_label,
            "valid_sample_count": len(raw_vals),
            "drift_vs_failure_note": drift_vs_failure_note,
            "explanation": explanation
        }

    def evaluate_data_quality(
        self,
        feature_name: str,
        values: List[Any],
        timestamps: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Evaluates measurable sensor reliability and data quality criteria on a sensor window:
        - Missing readings count & percentage
        - Stale data / communication timeout checks
        - Repeated / stuck / frozen sensor checks
        - Abnormal step spikes
        - Physical out-of-range violations
        - Measurable Sensor Reliability Score (0-100%)
        - Sensor Fault vs. Machine Degradation attribution
        """
        total_count = len(values)
        if total_count == 0:
            return {
                "feature_name": feature_name,
                "missing_count": 0,
                "missing_pct": 0.0,
                "is_stuck": False,
                "stuck_value": None,
                "repeated_count": 0,
                "spike_count": 0,
                "is_stale": True,
                "out_of_range_count": 0,
                "reliability_score": 0.0,
                "quality_status": "INSUFFICIENT_DATA",
                "fault_attribution": "COMMUNICATION_FAULT",
                "issue_description": "No telemetry readings received (communication failure or empty buffer)."
            }

        # 1. Missingness
        missing_count = sum(
            1 for v in values
            if v is None or not isinstance(v, (int, float)) or np.isnan(v) or not np.isfinite(v)
        )
        missing_pct = (missing_count / total_count) * 100.0

        valid_vals = [
            float(v) for v in values
            if v is not None and isinstance(v, (int, float)) and not np.isnan(v) and np.isfinite(v)
        ]

        # 2. Stuck / Repeated Values Check
        is_stuck = False
        stuck_val = None
        max_repeated_run = 1
        if len(valid_vals) >= 2:
            cur_run = 1
            for idx in range(1, len(valid_vals)):
                if abs(valid_vals[idx] - valid_vals[idx - 1]) < 1e-5:
                    cur_run += 1
                    if cur_run > max_repeated_run:
                        max_repeated_run = cur_run
                else:
                    cur_run = 1

        if len(valid_vals) >= self.config.STUCK_SENSOR_MIN_POINTS:
            recent_segment = valid_vals[-self.config.STUCK_SENSOR_MIN_POINTS:]
            val_std = float(np.std(recent_segment))
            val_range = float(np.max(recent_segment) - np.min(recent_segment))
            if val_std <= self.config.STUCK_SENSOR_STD_THRESHOLD or val_range < 1e-5:
                is_stuck = True
                stuck_val = float(recent_segment[-1])

        # 3. Range Violations
        bounds = self.config.SENSOR_BOUNDS.get(feature_name)
        out_of_range_count = 0
        if bounds and valid_vals:
            low_b, high_b = bounds
            out_of_range_count = sum(1 for v in valid_vals if v < low_b or v > high_b)

        # 4. Abnormal Spikes (sudden step jump > 4x baseline std)
        base_feat = self.baseline_manager.get_feature_baseline(feature_name) or {}
        base_std = max(0.05, float(base_feat.get("std", 1.0)))
        spike_threshold = max(base_std * 4.5, abs(float(base_feat.get("mean", 10.0))) * 0.30)
        spike_count = 0
        if len(valid_vals) >= 3:
            diffs = np.abs(np.diff(valid_vals))
            spike_count = int(np.sum(diffs > spike_threshold))

        # 5. Stale Data / Communication Check
        is_stale = False
        if timestamps and len(timestamps) >= 2:
            # If the last N timestamps are identical when window has multiple entries
            if len(timestamps) >= 6 and len(set(timestamps[-6:])) == 1:
                is_stale = True

        # 6. Measurable Sensor Reliability / Data Quality Score (0-100%)
        penalty_missing = min(50.0, missing_pct * 1.5)
        penalty_stuck = 35.0 if is_stuck else (10.0 if max_repeated_run >= 6 else 0.0)
        oob_pct = (out_of_range_count / max(1, len(valid_vals))) * 100.0
        penalty_oob = min(40.0, oob_pct * 2.5)
        spike_pct = (spike_count / max(1, len(valid_vals) - 1)) * 100.0
        penalty_spikes = min(25.0, spike_pct * 2.0)
        penalty_stale = 40.0 if is_stale else 0.0

        reliability_score = round(
            max(0.0, 100.0 - penalty_missing - penalty_stuck - penalty_oob - penalty_spikes - penalty_stale),
            1
        )

        # Determine quality status & explain why flagged
        issues = []
        status = "NORMAL"
        fault_attribution = "NORMAL"

        if missing_pct >= self.config.MISSING_DATA_CRITICAL_PCT:
            status = "CRITICAL"
            fault_attribution = "COMMUNICATION_FAULT"
            issues.append(f"Critical missing data ({missing_pct:.1f}% missing / packet drop)")
        elif missing_pct >= self.config.MISSING_DATA_WARNING_PCT:
            status = "WARNING" if status != "CRITICAL" else status
            fault_attribution = "COMMUNICATION_FAULT"
            issues.append(f"Elevated missing data ({missing_pct:.1f}% missing readings)")

        if is_stale:
            status = "CRITICAL"
            fault_attribution = "COMMUNICATION_FAULT"
            issues.append("Stale telemetry timestamp detected (possible PLC/MQTT communication freeze)")

        if is_stuck:
            status = "CRITICAL"
            fault_attribution = "SENSOR_FAULT"
            issues.append(f"Sensor stuck/repeated at constant value {stuck_val:.2f} ({max_repeated_run} consecutive identical samples)")
        elif max_repeated_run >= 6:
            status = "WARNING" if status != "CRITICAL" else status
            fault_attribution = "SENSOR_FAULT"
            issues.append(f"Repeated identical readings ({max_repeated_run} samples) — check ADC quantization or polling")

        if out_of_range_count > 0:
            status = "CRITICAL" if out_of_range_count >= 3 else ("WARNING" if status != "CRITICAL" else status)
            fault_attribution = "SENSOR_FAULT"
            issues.append(f"{out_of_range_count} samples outside physical transducer range {bounds}")

        if spike_count > 0:
            status = "WARNING" if status != "CRITICAL" else status
            if fault_attribution == "NORMAL":
                fault_attribution = "SENSOR_FAULT"
            issues.append(f"{spike_count} abnormal transient step spike(s) (> {spike_threshold:.2f} jump)")

        if issues:
            issue_desc = "; ".join(issues) + ". (Flagged as sensor/telemetry quality issue; software cannot confirm physical rust or hardware damage without physical inspection.)"
        else:
            issue_desc = "All measurable data quality checks passed (0% missing, within physical range, normal dynamic variance)."

        return {
            "feature_name": feature_name,
            "missing_count": missing_count,
            "missing_pct": round(missing_pct, 2),
            "is_stuck": is_stuck,
            "stuck_value": stuck_val,
            "repeated_count": max_repeated_run,
            "spike_count": spike_count,
            "is_stale": is_stale,
            "out_of_range_count": out_of_range_count,
            "reliability_score": reliability_score,
            "quality_status": status,
            "fault_attribution": fault_attribution,
            "issue_description": issue_desc
        }

    def evaluate_prediction_drift(self, rul_predictions: List[float], anomaly_statuses: List[str]) -> List[Dict[str, Any]]:
        """
        Evaluates drift on model outputs:
        - Remaining Useful Life (RUL) distribution change vs baseline RUL
        - Isolation Forest anomaly flag rate divergence
        """
        results = []
        base_meta = self.baseline_manager.get_baseline().get("prediction_baseline", {})
        
        # 1. RUL Prediction Drift
        valid_ruls = [float(r) for r in rul_predictions if r is not None and isinstance(r, (int, float)) and np.isfinite(r)]
        if valid_ruls and "bin_edges" in base_meta:
            arr_rul = np.array(valid_ruls)
            curr_rul_mean = float(np.mean(arr_rul))
            base_rul_mean = float(base_meta.get("mean", 220.0))
            
            rul_psi = calculate_psi(
                expected_probs=base_meta.get("baseline_probs", []),
                actual_values=arr_rul,
                bin_edges=base_meta.get("bin_edges", [])
            )
            
            if rul_psi >= self.config.PREDICTION_RUL_PSI_CRITICAL:
                rul_status = "CRITICAL"
                detail = f"Predicted RUL distribution has drastically shifted (PSI={rul_psi:.3f}, mean: {base_rul_mean:.1f}d -> {curr_rul_mean:.1f}d)."
            elif rul_psi >= self.config.PREDICTION_RUL_PSI_WARNING:
                rul_status = "WARNING"
                detail = f"Predicted RUL distribution indicates accelerated degradation (PSI={rul_psi:.3f}, mean: {base_rul_mean:.1f}d -> {curr_rul_mean:.1f}d)."
            else:
                rul_status = "NORMAL"
                detail = f"Predicted RUL distribution is consistent with normal aging curve (PSI={rul_psi:.3f})."

            results.append({
                "target_name": "predicted_rul_days",
                "baseline_mean": round(base_rul_mean, 2),
                "current_mean": round(curr_rul_mean, 2),
                "psi_score": round(rul_psi, 4),
                "drift_status": rul_status,
                "details": detail
            })

        # 2. Isolation Forest Anomaly Rate Drift
        if anomaly_statuses:
            n_total = len(anomaly_statuses)
            n_anomalies = sum(1 for a in anomaly_statuses if str(a).lower() in ["anomaly detected", "true", "anomaly", "1"])
            curr_rate_pct = (n_anomalies / n_total) * 100.0
            base_rate_pct = float(base_meta.get("expected_anomaly_rate_pct", 2.0))
            rate_delta = curr_rate_pct - base_rate_pct

            if rate_delta >= (self.config.ANOMALY_RATE_SHIFT_CRITICAL * 100.0):
                anom_status = "CRITICAL"
                anom_detail = f"Isolation Forest anomaly frequency surged to {curr_rate_pct:.1f}% (Baseline: {base_rate_pct:.1f}%)."
            elif rate_delta >= (self.config.ANOMALY_RATE_SHIFT_WARNING * 100.0):
                anom_status = "WARNING"
                anom_detail = f"Isolation Forest anomaly frequency elevated at {curr_rate_pct:.1f}% (Baseline: {base_rate_pct:.1f}%)."
            else:
                anom_status = "NORMAL"
                anom_detail = f"Anomaly detection rate ({curr_rate_pct:.1f}%) matches expected normal operational variance."

            results.append({
                "target_name": "anomaly_rate_pct",
                "baseline_mean": round(base_rate_pct, 1),
                "current_mean": round(curr_rate_pct, 1),
                "psi_score": round(max(0.0, rate_delta / 100.0), 4),
                "drift_status": anom_status,
                "details": anom_detail
            })

        return results

    def synthesize_model_health(
        self,
        feature_results: List[Dict[str, Any]],
        prediction_results: List[Dict[str, Any]],
        quality_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Synthesizes Data Drift + Prediction Drift + Data Quality into an authoritative
        Model Health state (HEALTHY | WARNING | CRITICAL | INSUFFICIENT_DATA) with actionable
        explanations distinguishing data drift, sensor faults, and machine degradation.
        """
        insufficient_feats = [f for f in feature_results if f.get("drift_status") == "INSUFFICIENT_DATA"]
        critical_feats = [f for f in feature_results if f.get("drift_status") == "CRITICAL"]
        warning_feats = [f for f in feature_results if f.get("drift_status") == "WARNING"]
        total_feats = len(feature_results)
        
        avg_psi = float(np.mean([f.get("psi_score", 0.0) for f in feature_results])) if feature_results else 0.0
        
        if total_feats > 0 and len(insufficient_feats) == total_feats:
            data_drift_status = "INSUFFICIENT_DATA"
            data_drift_label = "Insufficient Data"
        elif len(critical_feats) >= 2 or (total_feats > 0 and len(critical_feats) / total_feats >= 0.3):
            data_drift_status = "CRITICAL"
            data_drift_label = "Drift Detected (Critical)"
        elif len(critical_feats) >= 1 or len(warning_feats) >= 1 or avg_psi >= self.config.PSI_WARNING_THRESHOLD:
            data_drift_status = "WARNING"
            data_drift_label = "Drift Detected (Warning)"
        else:
            data_drift_status = "NORMAL"
            data_drift_label = "Normal"

        pred_critical = [p for p in prediction_results if p.get("drift_status") == "CRITICAL"]
        pred_warning = [p for p in prediction_results if p.get("drift_status") == "WARNING"]
        
        if pred_critical:
            prediction_drift_status = "CRITICAL"
        elif pred_warning:
            prediction_drift_status = "WARNING"
        else:
            prediction_drift_status = "NORMAL"

        qual_critical = [q for q in quality_results if q.get("quality_status") == "CRITICAL"]
        qual_warning = [q for q in quality_results if q.get("quality_status") == "WARNING"]
        
        stuck_count = sum(1 for q in quality_results if q.get("is_stuck"))
        missing_overall = float(np.mean([q.get("missing_pct", 0.0) for q in quality_results])) if quality_results else 0.0
        oob_count = sum(q.get("out_of_range_count", 0) for q in quality_results)
        spike_count_total = sum(q.get("spike_count", 0) for q in quality_results)
        overall_reliability_score = round(
            float(np.mean([q.get("reliability_score", 100.0) for q in quality_results])) if quality_results else 100.0,
            1
        )

        if qual_critical or stuck_count > 0 or missing_overall >= self.config.MISSING_DATA_CRITICAL_PCT:
            data_quality_status = "CRITICAL"
        elif qual_warning or missing_overall >= self.config.MISSING_DATA_WARNING_PCT or oob_count > 0 or spike_count_total > 0:
            data_quality_status = "WARNING"
        else:
            data_quality_status = "NORMAL"

        if data_drift_status == "INSUFFICIENT_DATA" and data_quality_status == "NORMAL":
            overall_status = "INSUFFICIENT_DATA"
        elif "CRITICAL" in [data_drift_status, prediction_drift_status, data_quality_status]:
            overall_status = "CRITICAL"
        elif "WARNING" in [data_drift_status, prediction_drift_status, data_quality_status]:
            overall_status = "WARNING"
        else:
            overall_status = "HEALTHY"

        reasons = []
        recommendations = []

        if data_quality_status in ["WARNING", "CRITICAL"]:
            stuck_names = [q["feature_name"] for q in quality_results if q.get("is_stuck")]
            if stuck_names:
                reasons.append(f"Sensor fault detected: {', '.join(stuck_names)} stuck/repeated at constant reading.")
                recommendations.append("Inspect sensor wiring, ADC channel, and transducer signal conditioning. Unreliable readings are isolated from ML predictions.")
            if missing_overall >= self.config.MISSING_DATA_WARNING_PCT:
                reasons.append(f"Telemetry missingness detected ({missing_overall:.1f}% missing readings).")
                recommendations.append("Verify PLC-to-MQTT network connectivity and polling intervals.")
            if oob_count > 0:
                reasons.append(f"{oob_count} out-of-range reading(s) outside physical transducer limits.")
                recommendations.append("Validate sensor calibration; out-of-range readings are clamped/isolated to prevent silent prediction contamination.")
            if spike_count_total > 0:
                reasons.append(f"{spike_count_total} abnormal single-sample spike(s) detected.")
                recommendations.append("Check EMI shielding and signal grounding.")

        if data_drift_status in ["WARNING", "CRITICAL"]:
            drifting_names = [f["feature_name"] for f in (critical_feats + warning_feats)]
            if len(drifting_names) >= 2 and data_quality_status == "NORMAL":
                reasons.append(
                    f"Correlated distribution shift across {', '.join(drifting_names)} (Data Quality Score: {overall_reliability_score}%). "
                    f"Because sensors pass quality validation, this shift suggests either an operating regime change or genuine machine degradation—trigger engineering investigation."
                )
            else:
                reasons.append(
                    f"Statistical distribution drift detected on {', '.join(drifting_names)}. "
                    f"Drift triggers investigation and does not automatically prove equipment failure."
                )
            
            if any("vib" in f.lower() for f in drifting_names):
                recommendations.append("Vibration distribution shifted: investigate operating load regime and bearing alignment.")
            if any("temp" in f.lower() for f in drifting_names):
                recommendations.append("Thermal distribution shifted: check ambient cooling conditions and motor load.")
            if any("current" in f.lower() for f in drifting_names):
                recommendations.append("Motor current distribution shifted: verify process load demand and phase balance.")

        if data_drift_status == "INSUFFICIENT_DATA":
            reasons.append("Insufficient telemetry samples in current evaluation window to compute statistical drift.")
            recommendations.append("Continue collecting live PLC telemetry until minimum window size is reached.")

        if prediction_drift_status in ["WARNING", "CRITICAL"]:
            reasons.append("ML model output behavior divergence: RUL / anomaly forecasts have deviated from historical baseline expectations.")
            recommendations.append("Verify whether the machine has transitioned to a new operating regime before scheduling model retraining.")

        if not reasons:
            reasons.append("Telemetry streams, sensor data quality, and model predictions strictly align with reference baseline.")
            recommendations.append("Continue standard autonomous monitoring. No maintenance or retraining intervention required.")

        summary_text = f"System reliability status is {overall_status} (Data Drift: {data_drift_label}, Sensor Quality Score: {overall_reliability_score}%). " + " ".join(reasons[:2])

        return {
            "overall_status": overall_status,
            "data_drift_status": data_drift_status,
            "data_drift_label": data_drift_label,
            "prediction_drift_status": prediction_drift_status,
            "data_quality_status": data_quality_status,
            "overall_drift_score": round(avg_psi, 4),
            "overall_reliability_score": overall_reliability_score,
            "drifted_features_count": len(critical_feats) + len(warning_feats),
            "total_features_monitored": total_feats,
            "rul_psi": round(float(prediction_results[0].get("psi_score", 0.0)) if prediction_results else 0.0, 4),
            "anomaly_rate_current": round(float(prediction_results[1].get("current_mean", 0.0)) if len(prediction_results) > 1 else 0.0, 1),
            "anomaly_rate_baseline": round(float(prediction_results[1].get("baseline_mean", 0.0)) if len(prediction_results) > 1 else 2.0, 1),
            "missing_pct_overall": round(missing_overall, 2),
            "stuck_sensors_count": stuck_count,
            "out_of_bounds_count": oob_count,
            "spike_count_total": spike_count_total,
            "summary": summary_text,
            "reason": " ".join(reasons),
            "recommendation": " ".join(recommendations)
        }


# Singleton detector instance
drift_detector = DriftDetector()
