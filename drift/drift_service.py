"""
Drift Monitoring Service
------------------------
Orchestrates live telemetry windowing per PLC, scheduled/on-demand drift evaluations,
persistence to database, alert generation with cooldown suppression, and controlled
sandbox demonstration mode.
"""

import time
import uuid
import logging
import datetime
from typing import Dict, List, Any, Optional
from collections import defaultdict
import numpy as np

from .config import config
from .database import db
from .baseline import baseline_mgr
from .detector import drift_detector

logger = logging.getLogger("drift_service")


class DriftMonitoringService:
    """Production service managing drift evaluation pipelines across multiple assets."""

    def __init__(self):
        self.config = config
        self.db = db
        self.baseline_mgr = baseline_mgr
        self.detector = drift_detector
        
        # In-memory rolling telemetry buffers per PLC: { "PLC_01": [ {...}, ... ] }
        self.plc_telemetry_windows: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        
        # Telemetry ingestion counter per PLC to trigger checks every N steps
        self.step_counters: Dict[str, int] = defaultdict(int)
        
        # Alert cooldown tracking: { "PLC_01_DATA_DRIFT": last_timestamp }
        self.last_alert_times: Dict[str, float] = {}
        
        # Demonstration Mode Overrides: { "PLC_01": { "mode": "severe_drift", ... } }
        self.demo_overrides: Dict[str, Dict[str, Any]] = {}
        
        # Latest cached evaluation run per PLC for instant query performance
        self.latest_eval_cache: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def _safe_opt_float(val: Any) -> Optional[float]:
        if val is None:
            return None
        try:
            f = float(val)
            if np.isnan(f) or not np.isfinite(f):
                return None
            return f
        except (ValueError, TypeError):
            return None

    def ingest_telemetry_record(self, record: Dict[str, Any]):
        """
        Receives real-time telemetry record from MQTT / simulator and appends to rolling window.
        Triggers evaluation periodically.
        """
        if not isinstance(record, dict):
            return

        plc_id = str(record.get("plc_id", "PLC_01"))
        raw_map = record.get("raw_readings") or {}

        def _extract_feat(keys: List[str], raw_key: str, default_val: float) -> Optional[float]:
            if raw_key in raw_map:
                return self._safe_opt_float(raw_map[raw_key])
            for k in keys:
                if k in record:
                    return self._safe_opt_float(record[k])
            return default_val

        entry = {
            "timestamp": record.get("timestamp", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            "Temperature": _extract_feat(["Motor_Temp", "temperature", "Temperature"], "Motor_Temp", 62.0),
            "Vibration": _extract_feat(["Vibration_X", "vibration", "Vibration"], "Vibration", 0.2),
            "Motor_Current": _extract_feat(["Motor_Current", "motor_current"], "Motor_Current", 8.0),
            "Pressure": _extract_feat(["Pressure_Inlet", "pressure", "Pressure"], "Pressure_Inlet", 5.0),
            "Noise": _extract_feat(["Noise", "noise"], "Noise", 42.0),
            "predicted_rul_days": float(record.get("predicted_rul_days", record.get("Predicted_RUL", 200)) or 200.0),
            "anomaly_status": str(record.get("anomaly_status", record.get("Anomaly_Status", "Normal"))),
            "machine_health": float(record.get("machine_health", record.get("Machine_Health", 100.0)) or 100.0)
        }

        # Apply demo sandbox modifications if active for this PLC
        entry = self._apply_demo_transform(plc_id, entry)

        window = self.plc_telemetry_windows[plc_id]
        window.append(entry)
        if len(window) > self.config.MONITORING_WINDOW_SIZE:
            window.pop(0)

        self.step_counters[plc_id] += 1
        
        # Periodic evaluation trigger
        if self.step_counters[plc_id] >= self.config.CHECK_INTERVAL_STEPS:
            self.step_counters[plc_id] = 0
            if len(window) >= self.config.MIN_SAMPLES_FOR_EVALUATION:
                try:
                    self.evaluate_plc(plc_id)
                except Exception as e:
                    logger.error(f"Error during periodic drift evaluation for {plc_id}: {e}", exc_info=True)

    def evaluate_plc(self, plc_id: str = "PLC_01") -> Dict[str, Any]:
        """
        Executes a full drift & reliability evaluation for a given PLC window,
        persists results to the database, and checks for alert triggers.
        """
        override_mode = (self.demo_overrides.get(plc_id) or {}).get("mode")
        window = self.plc_telemetry_windows.get(plc_id, [])
        if len(window) < 5 and override_mode != "insufficient_data":
            window = self._generate_cold_start_window(plc_id)

        features_to_monitor = ["Temperature", "Vibration", "Motor_Current", "Pressure", "Noise"]
        timestamps = [str(w.get("timestamp", "")) for w in window]
        
        # 1. Feature Drift Evaluation
        feature_results = []
        for feat in features_to_monitor:
            vals = [w.get(feat) for w in window]
            res = self.detector.evaluate_feature_drift(feat, vals)
            feature_results.append(res)

        # 2. Data Quality Evaluation
        quality_results = []
        for feat in features_to_monitor:
            vals = [w.get(feat) for w in window]
            q_res = self.detector.evaluate_data_quality(feat, vals, timestamps=timestamps)
            quality_results.append(q_res)

        # 3. Prediction Drift Evaluation
        ruls = [w.get("predicted_rul_days", 200.0) for w in window]
        anom_statuses = [w.get("anomaly_status", "Normal") for w in window]
        prediction_results = self.detector.evaluate_prediction_drift(ruls, anom_statuses)

        # 4. Model Health Synthesis
        health_summary = self.detector.synthesize_model_health(
            feature_results=feature_results,
            prediction_results=prediction_results,
            quality_results=quality_results
        )

        now_dt = datetime.datetime.now()
        run_id = f"RUN-{now_dt.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
        run_data = {
            "run_id": run_id,
            "plc_id": plc_id,
            "timestamp": now_dt,
            **health_summary
        }

        # 5. Persist to Database
        try:
            self.db.save_monitoring_run(
                run_data=run_data,
                feature_results=feature_results,
                prediction_results=prediction_results,
                quality_results=quality_results
            )
        except Exception as e:
            logger.error(f"Failed to persist drift run {run_id} to DB: {e}")

        # 6. Check Alert Policies (with Cooldown)
        self._check_and_emit_alerts(plc_id, health_summary, feature_results, quality_results)

        eval_payload = {
            "run_id": run_id,
            "plc_id": plc_id,
            "timestamp": now_dt.strftime("%Y-%m-%d %H:%M:%S"),
            **health_summary,
            "features": feature_results,
            "predictions": prediction_results,
            "data_quality": quality_results,
            "window_sample_count": len(window)
        }

        self.latest_eval_cache[plc_id] = eval_payload
        return eval_payload

    def get_latest_evaluation(self, plc_id: str = "PLC_01") -> Dict[str, Any]:
        """Returns latest evaluation for a PLC from cache or DB; runs check if none exists."""
        if plc_id in self.latest_eval_cache:
            return self.latest_eval_cache[plc_id]
        
        db_res = self.db.get_latest_run(plc_id)
        if db_res:
            self.latest_eval_cache[plc_id] = db_res
            return db_res

        return self.evaluate_plc(plc_id)

    def _check_and_emit_alerts(self, plc_id: str, health: Dict[str, Any],
                              feature_results: List[Dict], quality_results: List[Dict]):
        """Evaluates alert conditions with anti-spam cooldown."""
        now = time.time()
        cooldown = self.config.ALERT_COOLDOWN_SECONDS

        overall_status = health.get("overall_status", "HEALTHY")
        if overall_status in ["WARNING", "CRITICAL"]:
            alert_key = f"{plc_id}_{overall_status}"
            last_time = self.last_alert_times.get(alert_key, 0.0)
            
            if (now - last_time) >= cooldown:
                self.last_alert_times[alert_key] = now
                self.db.record_alert(
                    plc_id=plc_id,
                    alert_type="MODEL_HEALTH",
                    severity=overall_status,
                    title=f"{overall_status} Reliability Alert on {plc_id}",
                    message=health.get("reason", "Distribution or quality shift detected."),
                    recommendation=health.get("recommendation", "Inspect sensors.")
                )
                logger.warning(f"DRIFT ALERT ISSUED | {plc_id} | {overall_status} | {health.get('reason')}")

                # Digital Thread Integration Hook
                try:
                    from digital_thread.service import digital_thread_service  # type: ignore
                    digital_thread_service.ingest_drift_event(plc_id, {
                        "overall_status": overall_status,
                        "overall_drift_score": health.get("overall_drift_score", 0.0),
                        "reason": health.get("reason"),
                        "recommendation": health.get("recommendation"),
                        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
                except Exception as dt_err:
                    logger.debug(f"Digital thread drift hook note: {dt_err}")

    def _generate_cold_start_window(self, plc_id: str) -> List[Dict[str, Any]]:
        """Generates initial baseline window for immediate availability upon startup."""
        base = self.baseline_mgr.get_baseline()
        feats = base.get("features", {})
        window = []
        now = datetime.datetime.now()
        
        digits = "".join(ch for ch in plc_id if ch.isdigit())
        num = int(digits) if digits else 1
        
        for i in range(self.config.MIN_SAMPLES_FOR_EVALUATION):
            t_stamp = (now - datetime.timedelta(seconds=(20 - i) * 2)).strftime("%Y-%m-%d %H:%M:%S")
            item = {
                "timestamp": t_stamp,
                "Temperature": feats.get("Temperature", {}).get("mean", 62.0) + (num * 0.5),
                "Vibration": feats.get("Vibration", {}).get("mean", 0.20) + (num * 0.02),
                "Motor_Current": feats.get("Motor_Current", {}).get("mean", 8.0) + (num * 0.2),
                "Pressure": feats.get("Pressure", {}).get("mean", 5.0),
                "Noise": feats.get("Noise", {}).get("mean", 42.0),
                "predicted_rul_days": 240 - i,
                "anomaly_status": "Normal",
                "machine_health": 100.0 - (num * 2.0)
            }
            window.append(item)
        return window

    def set_demonstration_mode(self, plc_id: str, mode: str) -> Dict[str, Any]:
        """
        Safe Demonstration Sandbox Controller.
        Modes:
          - 'normal': Restores normal telemetry
          - 'mild_vibration_drift': Induces mild distribution shift on Vibration (WARNING)
          - 'severe_thermal_drift': Induces large distribution shift on Temperature + Noise (CRITICAL)
          - 'stuck_sensor': Simulates a frozen transducer at constant reading (CRITICAL)
          - 'missing_data': Simulates high packet loss / nulls (CRITICAL)
          - 'prediction_drift': Simulates sharp drop in model RUL outputs (WARNING/CRITICAL)
          - 'reset': Clears all overrides
        """
        if mode == "reset" or mode == "normal":
            self.demo_overrides.pop(plc_id, None)
            res = self.evaluate_plc(plc_id)
            return {"status": "success", "mode": "normal", "message": f"Demonstration mode cleared for {plc_id}.", "evaluation": res}

        self.demo_overrides[plc_id] = {"mode": mode, "activated_at": time.time()}
        
        window = []
        now = datetime.datetime.now()
        base = self.baseline_mgr.get_baseline()
        feats = base.get("features", {})
        
        t_base = feats.get("Temperature", {}).get("mean", 62.0)
        v_base = feats.get("Vibration", {}).get("mean", 0.20)
        c_base = feats.get("Motor_Current", {}).get("mean", 8.0)
        p_base = feats.get("Pressure", {}).get("mean", 5.0)
        n_base = feats.get("Noise", {}).get("mean", 42.0)

        sample_count = 3 if mode == "insufficient_data" else self.config.MONITORING_WINDOW_SIZE

        for i in range(sample_count):
            ts = (now - datetime.timedelta(seconds=(sample_count - i) * 2)).strftime("%Y-%m-%d %H:%M:%S")
            rec = {
                "timestamp": ts,
                "Temperature": t_base + np.random.normal(0, 0.4),
                "Vibration": v_base + np.random.normal(0, 0.02),
                "Motor_Current": c_base + np.random.normal(0, 0.1),
                "Pressure": p_base + np.random.normal(0, 0.05),
                "Noise": n_base + np.random.normal(0, 0.5),
                "predicted_rul_days": 230.0,
                "anomaly_status": "Normal",
                "machine_health": 95.0
            }

            if mode == "mild_vibration_drift":
                rec["Vibration"] = float(0.55 + np.random.normal(0, 0.08))

            elif mode == "severe_thermal_drift":
                rec["Temperature"] = float(95.0 + np.random.normal(0, 2.5))
                rec["Noise"] = float(75.0 + np.random.normal(0, 3.0))
                rec["Vibration"] = float(0.85 + np.random.normal(0, 0.12))

            elif mode == "stuck_sensor":
                rec["Temperature"] = 72.10

            elif mode == "missing_data":
                if i % 4 == 0:
                    rec["Temperature"] = None
                    rec["Vibration"] = None

            elif mode == "abnormal_spike":
                if i in (10, 25, 40):
                    rec["Vibration"] = 4.85
                    rec["Motor_Current"] = 29.5

            elif mode == "out_of_range":
                if i % 6 == 0:
                    rec["Temperature"] = 185.0
                    rec["Pressure"] = 18.5

            elif mode == "prediction_drift":
                rec["predicted_rul_days"] = float(40.0 + np.random.normal(0, 5.0))
                rec["anomaly_status"] = "Anomaly Detected"

            window.append(rec)

        self.plc_telemetry_windows[plc_id] = window
        res = self.evaluate_plc(plc_id)
        return {
            "status": "success",
            "mode": mode,
            "message": f"Demonstration mode '{mode}' activated for {plc_id}.",
            "evaluation": res
        }

    def _apply_demo_transform(self, plc_id: str, entry: Dict[str, Any]) -> Dict[str, Any]:
        """Applies active live demonstration perturbation if enabled."""
        override = self.demo_overrides.get(plc_id)
        if not override:
            return entry

        mode = override.get("mode")
        e = dict(entry)
        if mode == "mild_vibration_drift":
            e["Vibration"] = float((e["Vibration"] or 0.2) + 0.35)
        elif mode == "severe_thermal_drift":
            e["Temperature"] = float((e["Temperature"] or 62.0) + 32.0)
            e["Noise"] = float((e["Noise"] or 42.0) + 30.0)
            e["Vibration"] = float((e["Vibration"] or 0.2) + 0.65)
        elif mode == "stuck_sensor":
            e["Temperature"] = 72.10
        elif mode == "missing_data":
            if np.random.rand() < 0.3:
                e["Temperature"] = None
        elif mode == "abnormal_spike":
            if np.random.rand() < 0.15:
                e["Vibration"] = 4.85
        elif mode == "out_of_range":
            if np.random.rand() < 0.2:
                e["Temperature"] = 185.0
        elif mode == "prediction_drift":
            e["predicted_rul_days"] = 35.0
            e["anomaly_status"] = "Anomaly Detected"
        return e


# Singleton drift service instance
drift_service = DriftMonitoringService()
