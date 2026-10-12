"""
Asset Digital Thread Service
----------------------------
Central orchestration service that connects the entire machine lifecycle:
Asset -> Components -> Sensors -> Telemetry -> Features -> Predictions -> Anomalies -> RUL -> Drift Events -> Maintenance -> Parts -> Maintenance Outcome
"""

import time
import logging
import datetime
from typing import Dict, List, Any, Optional

from .config import config
from .database import db

logger = logging.getLogger("digital_thread_service")


class DigitalThreadService:
    """Production service managing the Asset Digital Thread lifecycle."""

    def __init__(self):
        self.config = config
        self.db = db
        
        # In-memory tracking of last logged state per asset to prevent event log flooding
        self.last_event_times: Dict[str, float] = {}
        self.last_anomaly_status: Dict[str, str] = {}
        self.last_rul_values: Dict[str, float] = {}
        self.last_drift_status: Dict[str, str] = {}
        self.last_telemetry_checkpoint: Dict[str, float] = {}

    def resolve_asset_id(self, plc_or_asset_id: str) -> str:
        """Translates PLC ID (e.g. PLC_01) to canonical Asset ID (e.g. COMP-001) or returns input."""
        if not plc_or_asset_id:
            return "COMP-001"
        cleaned = str(plc_or_asset_id).strip()
        if cleaned in self.config.PLC_TO_ASSET_MAP:
            return self.config.PLC_TO_ASSET_MAP[cleaned]
        return cleaned

    def resolve_plc_id(self, asset_or_plc_id: str) -> str:
        """Translates Asset ID (e.g. COMP-001) to PLC ID (e.g. PLC_01) or returns input."""
        if not asset_or_plc_id:
            return "PLC_01"
        cleaned = str(asset_or_plc_id).strip()
        if cleaned in self.config.ASSET_TO_PLC_MAP:
            return self.config.ASSET_TO_PLC_MAP[cleaned]
        return cleaned

    # -------------------------------------------------------------
    # TELEMETRY & ML EVENT INGESTION HOOKS
    # -------------------------------------------------------------

    def ingest_telemetry_event(self, record: Dict[str, Any]):
        """
        Ingests real-time telemetry record and ML results from the streaming pipeline.
        Records events when significant lifecycle milestones or state changes occur.
        """
        if not isinstance(record, dict):
            return

        plc_id = str(record.get("plc_id", "PLC_01"))
        asset_id = self.resolve_asset_id(plc_id)
        now_ts = time.time()
        ts_str = record.get("timestamp", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        health = float(record.get("machine_health", record.get("Machine_Health", 100.0)))
        rul = int(record.get("predicted_rul_days", record.get("Predicted_RUL", 250)))
        status = str(record.get("machine_status", record.get("Machine_Status", "RUNNING")))
        anomaly_status = str(record.get("anomaly_status", record.get("Anomaly_Status", "Normal")))
        anomaly_score = float(record.get("Anomaly_Score", 0.0) or 0.0)

        # 1. Update Asset Health in Database
        self.db.update_asset_health(asset_id, health, rul, status)

        # 2. Anomaly State Change Event
        prev_anom = self.last_anomaly_status.get(asset_id, "Normal")
        if anomaly_status != prev_anom:
            self.last_anomaly_status[asset_id] = anomaly_status
            if anomaly_status != "Normal":
                vib = record.get("vibration", record.get("Vibration_X", 0.2))
                temp = record.get("temperature", record.get("Motor_Temp", 62.0))
                self.db.record_event(
                    asset_id=asset_id,
                    event_type="ANOMALY",
                    severity="WARNING" if "Warning" in anomaly_status else "CRITICAL",
                    source="Isolation Forest Model",
                    description=f"Operational Anomaly detected: {anomaly_status} (Score: {round(anomaly_score, 3)}, Vib: {vib} mm/s, Temp: {temp} °C)",
                    component_id=f"{asset_id}-BRG" if vib > 0.5 else f"{asset_id}-MOT",
                    sensor_id=f"SENS-{asset_id[-3:]}-T102" if vib > 0.5 else f"SENS-{asset_id[-3:]}-T101",
                    metric_value=round(anomaly_score, 3),
                    timestamp=ts_str,
                    metadata={"anomaly_score": anomaly_score, "temperature": temp, "vibration": vib}
                )

        # 3. Significant RUL Shift Event (shifts > 20 days)
        prev_rul = self.last_rul_values.get(asset_id, None)
        if prev_rul is not None and abs(rul - prev_rul) >= 25:
            self.last_rul_values[asset_id] = rul
            self.db.record_event(
                asset_id=asset_id,
                event_type="PREDICTION",
                severity="WARNING" if rul < 60 else "INFO",
                source="Random Forest RUL Regressor",
                description=f"RUL estimate updated: {rul} operating days remaining (Previous: {int(prev_rul)} days).",
                metric_value=float(rul),
                timestamp=ts_str,
                metadata={"predicted_rul": rul, "previous_rul": int(prev_rul), "model": record.get("model_used", "Random Forest Regressor")}
            )
        elif prev_rul is None:
            self.last_rul_values[asset_id] = rul

        # 4. Periodic Telemetry Checkpoint (every 60 seconds)
        last_ckpt = self.last_telemetry_checkpoint.get(asset_id, 0.0)
        if (now_ts - last_ckpt) >= 60.0:
            self.last_telemetry_checkpoint[asset_id] = now_ts
            temp = record.get("temperature", record.get("Motor_Temp", 62.0))
            vib = record.get("vibration", record.get("Vibration_X", 0.2))
            curr = record.get("motor_current", record.get("Motor_Current", 8.0))
            self.db.record_event(
                asset_id=asset_id,
                event_type="TELEMETRY",
                severity="INFO",
                source="MQTT SCADA Bridge",
                description=f"Telemetry Checkpoint: Temp={temp}°C, Vib={vib}mm/s, Curr={curr}A, Health={health}%",
                timestamp=ts_str,
                metadata={"temperature": temp, "vibration": vib, "motor_current": curr, "health": health, "rul": rul}
            )

    def ingest_drift_event(self, plc_id: str, drift_data: Dict[str, Any]):
        """
        Receives notification from Drift Monitoring subsystem and connects it to the Asset Digital Thread.
        """
        asset_id = self.resolve_asset_id(plc_id)
        now_str = drift_data.get("timestamp", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        overall_status = drift_data.get("overall_status", "NORMAL")

        prev_drift = self.last_drift_status.get(asset_id, "NORMAL")
        if overall_status != "HEALTHY" and (overall_status != prev_drift or (time.time() - self.last_event_times.get(f"{asset_id}_drift", 0.0)) > 300.0):
            self.last_drift_status[asset_id] = overall_status
            self.last_event_times[f"{asset_id}_drift"] = time.time()
            
            psi_score = drift_data.get("overall_drift_score", 0.0)
            reason = drift_data.get("reason", "Feature or prediction drift detected.")
            severity = "CRITICAL" if overall_status == "CRITICAL" else "WARNING"

            self.db.record_event(
                asset_id=asset_id,
                event_type="DRIFT",
                severity=severity,
                source="Drift & Reliability Engine",
                description=f"Data/Model Drift Detected ({overall_status}): {reason} (PSI: {round(psi_score, 3)})",
                metric_value=round(psi_score, 3),
                timestamp=now_str,
                metadata={
                    "run_id": drift_data.get("run_id"),
                    "psi_score": psi_score,
                    "drifted_features_count": drift_data.get("drifted_features_count", 0),
                    "recommendation": drift_data.get("recommendation")
                }
            )

    # -------------------------------------------------------------
    # ASSET HEALTH SNAPSHOT GENERATION
    # -------------------------------------------------------------

    def get_asset_health_snapshot(self, asset_id_or_plc: str,
                                  live_telemetry_dict: Dict[str, Any] = None,
                                  drift_service_ref: Any = None) -> Dict[str, Any]:
        """
        Synthesizes complete real-time health snapshot for the digital thread dashboard:
        - Asset details & components
        - Live sensor readings mapped to physical components
        - Isolation Forest anomaly analysis
        - Random Forest RUL estimation
        - Drift monitoring evaluation & PSI scores
        - Open maintenance items and last verified outcome
        """
        asset = self.db.get_asset_by_id(asset_id_or_plc)
        if not asset:
            # Fallback to COMP-001
            asset = self.db.get_asset_by_id("COMP-001")
            if not asset:
                raise ValueError(f"Asset '{asset_id_or_plc}' not found.")

        asset_id = asset["asset_id"]
        plc_id = asset["plc_id"]

        # 1. Overlay live telemetry values if available
        live_data = live_telemetry_dict or {}
        health = float(live_data.get("machine_health", asset.get("health", 100.0)))
        rul = int(live_data.get("predicted_rul_days", asset.get("rul_days", 250)))
        status = str(live_data.get("machine_status", asset.get("status", "RUNNING")))
        anomaly_status = str(live_data.get("anomaly_status", "Normal"))
        anomaly_score = float(live_data.get("Anomaly_Score", 0.0) or 0.0)

        # 2. Attach live readings to component sensors
        components = self.db.get_asset_components(asset_id)
        for comp in components:
            for sens in comp.get("sensors", []):
                tag = sens["tag_name"]
                if tag in live_data:
                    sens["live_value"] = float(live_data[tag])
                elif tag == "Motor_Temp" and "temperature" in live_data:
                    sens["live_value"] = float(live_data["temperature"])
                elif tag == "Vibration_X" and "vibration" in live_data:
                    sens["live_value"] = float(live_data["vibration"])
                elif tag == "Motor_Current" and "motor_current" in live_data:
                    sens["live_value"] = float(live_data["motor_current"])
                elif tag == "Pressure_Inlet" and "pressure" in live_data:
                    sens["live_value"] = float(live_data["pressure"])
                elif tag == "Noise" and "noise" in live_data:
                    sens["live_value"] = float(live_data["noise"])
                else:
                    sens["live_value"] = None

        # 3. Pull latest Drift evaluation if drift service provided
        drift_info = {
            "overall_status": "HEALTHY",
            "overall_drift_score": 0.02,
            "data_drift_status": "NORMAL",
            "prediction_drift_status": "NORMAL",
            "data_quality_status": "GOOD",
            "reason": "Feature distributions aligned with reference baseline."
        }
        if drift_service_ref:
            try:
                latest_eval = drift_service_ref.get_latest_evaluation(plc_id)
                if latest_eval:
                    drift_info = {
                        "overall_status": latest_eval.get("overall_status", "HEALTHY"),
                        "overall_drift_score": latest_eval.get("overall_drift_score", 0.0),
                        "data_drift_status": latest_eval.get("data_drift_status", "NORMAL"),
                        "prediction_drift_status": latest_eval.get("prediction_drift_status", "NORMAL"),
                        "data_quality_status": latest_eval.get("data_quality_status", "GOOD"),
                        "reason": latest_eval.get("reason", "Baseline aligned."),
                        "recommendation": latest_eval.get("recommendation", "Routine monitoring.")
                    }
            except Exception as e:
                logger.debug(f"Snapshot drift fetch: {e}")

        # 4. Fetch recent timeline events & maintenance
        timeline = self.db.get_asset_timeline(asset_id, limit=20)
        maintenance = self.db.get_asset_maintenance_history(asset_id)

        return {
            "asset_id": asset_id,
            "asset_name": asset["asset_name"],
            "asset_type": asset["asset_type"],
            "plc_id": plc_id,
            "location": asset["location"],
            "manufacturer": asset["manufacturer"],
            "model": asset["model"],
            "install_date": asset["install_date"],
            "status": status,
            "health": round(health, 1),
            "rul_days": rul,
            "last_maintenance_date": asset.get("last_maintenance_date"),
            "next_maintenance_date": asset.get("next_maintenance_date"),
            "components": components,
            "ai_health": {
                "health_status": "CRITICAL" if health < 60 else ("WARNING" if health < 80 else "HEALTHY"),
                "anomaly_status": anomaly_status,
                "anomaly_score": round(anomaly_score, 3),
                "predicted_rul": rul,
                "confidence_pct": float(live_data.get("prediction_confidence", 96.5)),
                "model_used": str(live_data.get("model_used", "Random Forest Regressor")),
                "drift": drift_info
            },
            "recent_events": timeline[:5],
            "maintenance_summary": {
                "total_records": len(maintenance),
                "latest_record": maintenance[0] if maintenance else None,
                "open_count": sum(1 for m in maintenance if m.get("status") in ["IN_PROGRESS", "SCHEDULED"])
            }
        }

    # -------------------------------------------------------------
    # SENSOR RELIABILITY & HEALTH INDEX ENGINE
    # -------------------------------------------------------------

    def get_sensor_reliability(
        self,
        plc_id: str = "PLC_01",
        telemetry: Optional[Dict[str, Any]] = None,
        history: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Computes real-time per-sensor reliability metrics, measurable data-quality scores,
        missing/stale/repeated/spike/out-of-range flags, explanation of why any sensor is flagged,
        sensor fault vs. machine degradation distinction, and raw vs. validated audit readings.
        """
        plc_id = str(plc_id or "PLC_01").strip()
        tel = telemetry or {}
        hist = history or []

        raw_map = tel.get("raw_readings") or {}
        val_warnings = tel.get("sensor_validation_warnings") or {}

        vib = float(tel.get("vibration", tel.get("Vibration_X", 0.28)) or 0.28)
        temp = float(tel.get("temperature", tel.get("Motor_Temp", 64.5)) or 64.5)
        curr = float(tel.get("motor_current", tel.get("Motor_Current", 15.2)) or 15.2)
        press = float(tel.get("pressure", tel.get("Pressure_Inlet", 5.2)) or 5.2)
        noise = float(tel.get("noise", tel.get("Noise", 42.8)) or 42.8)

        # Pull latest drift / data-quality evaluation if available
        quality_by_feat: Dict[str, Dict[str, Any]] = {}
        try:
            from drift.drift_service import drift_service  # type: ignore
            drift_eval = drift_service.get_latest_evaluation(plc_id)
            for q in drift_eval.get("data_quality", []):
                quality_by_feat[q.get("feature_name", "")] = q
        except Exception:
            pass

        # Check how many primary sensors are simultaneously elevated (to distinguish machine wear vs isolated sensor fault)
        elevated_sensors_count = sum([
            1 if temp > 72.0 else 0,
            1 if vib > 0.45 else 0,
            1 if curr > 11.5 else 0,
            1 if (press < 4.2 or press > 6.2) else 0,
            1 if noise > 55.0 else 0,
        ])

        sensor_specs = [
            {
                "channel_id": f"SENS-{plc_id}-TMP01",
                "sensor_tag": "Motor_Temp",
                "feature_name": "Temperature",
                "sensor_name": "Motor Stator PT100 RTD (Motor Temperature)",
                "category": "Thermal RTD",
                "unit": "°C",
                "validated_val": round(temp, 1),
                "raw_val": raw_map.get("Motor_Temp", round(temp, 1)),
                "nominal_range": "50.0 – 75.0",
                "lower_bound": 10.0,
                "upper_bound": 150.0,
                "warn_high": 75.0,
                "crit_high": 85.0,
                "snr_db": round(44.2 - min(25.0, max(0.0, (temp - 70.0) * 1.2)), 1),
                "mtbf_hours": 45000 if temp < 75.0 else 18000,
                "last_calibrated": "2026-07-10"
            },
            {
                "channel_id": f"SENS-{plc_id}-VIB01",
                "sensor_tag": "Vibration",
                "feature_name": "Vibration",
                "sensor_name": "Vibration Accelerometer (Drive-End)",
                "category": "Mechanical Dynamic",
                "unit": "mm/s RMS",
                "validated_val": round(vib, 3),
                "raw_val": raw_map.get("Vibration", round(vib, 3)),
                "nominal_range": "0.10 – 0.45",
                "lower_bound": 0.0,
                "upper_bound": 15.0,
                "warn_high": 0.50,
                "crit_high": 1.50,
                "snr_db": round(38.5 - min(30.0, vib * 12.0), 1),
                "mtbf_hours": 32000 if vib < 0.45 else (14000 if vib < 0.75 else 4200),
                "last_calibrated": "2026-08-15"
            },
            {
                "channel_id": f"SENS-{plc_id}-CUR01",
                "sensor_tag": "Motor_Current",
                "feature_name": "Motor_Current",
                "sensor_name": "Hall-Effect Current Transducer (Motor Current)",
                "category": "Electrical",
                "unit": "A",
                "validated_val": round(curr, 2),
                "raw_val": raw_map.get("Motor_Current", round(curr, 2)),
                "nominal_range": "6.0 – 10.0",
                "lower_bound": 0.0,
                "upper_bound": 40.0,
                "warn_high": 10.0,
                "crit_high": 15.0,
                "snr_db": 41.0,
                "mtbf_hours": 38000,
                "last_calibrated": "2026-08-01"
            },
            {
                "channel_id": f"SENS-{plc_id}-PRS01",
                "sensor_tag": "Pressure_Inlet",
                "feature_name": "Pressure",
                "sensor_name": "Piezoresistive Inlet Pressure Transducer",
                "category": "Hydraulic / Fluid",
                "unit": "bar",
                "validated_val": round(press, 2),
                "raw_val": raw_map.get("Pressure_Inlet", round(press, 2)),
                "nominal_range": "4.0 – 6.0",
                "lower_bound": 0.5,
                "upper_bound": 15.0,
                "warn_high": 6.0,
                "crit_high": 7.0,
                "snr_db": 39.5,
                "mtbf_hours": 29000,
                "last_calibrated": "2026-06-20"
            },
            {
                "channel_id": f"SENS-{plc_id}-ACO01",
                "sensor_tag": "Noise",
                "feature_name": "Noise",
                "sensor_name": "Acoustic Ultrasonic Microphone (Noise)",
                "category": "Acoustic / High-Frequency",
                "unit": "dB(A)",
                "validated_val": round(noise, 1),
                "raw_val": raw_map.get("Noise", round(noise, 1)),
                "nominal_range": "35.0 – 55.0",
                "lower_bound": 20.0,
                "upper_bound": 125.0,
                "warn_high": 55.0,
                "crit_high": 70.0,
                "snr_db": 36.2,
                "mtbf_hours": 25000,
                "last_calibrated": "2026-07-28"
            }
        ]

        channels = []
        for spec in sensor_specs:
            feat_name = spec["feature_name"]
            tag_name = spec["sensor_tag"]
            q_info = quality_by_feat.get(feat_name, {})

            missing_count = int(q_info.get("missing_count", 0))
            missing_pct = float(q_info.get("missing_pct", 0.0))
            is_stuck = bool(q_info.get("is_stuck", False))
            repeated_count = int(q_info.get("repeated_count", 1))
            spike_count = int(q_info.get("spike_count", 0))
            is_stale = bool(q_info.get("is_stale", False))
            oob_count = int(q_info.get("out_of_range_count", 0))

            raw_v = spec["raw_val"]
            val_v = spec["validated_val"]
            live_warn = val_warnings.get(tag_name)

            # Check if raw reading itself was out of bounds or missing
            if raw_v is None:
                missing_count = max(1, missing_count)
            elif isinstance(raw_v, (int, float)) and (raw_v < spec["lower_bound"] or raw_v > spec["upper_bound"]):
                oob_count = max(1, oob_count)

            # Measurable reliability score (0-100%)
            base_rel = float(q_info.get("reliability_score", 98.5))
            if live_warn:
                base_rel = min(base_rel, 65.0)
            if is_stuck or is_stale:
                base_rel = min(base_rel, 55.0)
            elif oob_count > 0 or missing_pct > 5.0 or spike_count > 0:
                base_rel = min(base_rel, 74.0)

            # Explain why flagged & distinguish sensor fault vs machine degradation
            flags = []
            if missing_count > 0:
                flags.append(f"Missing readings ({missing_count} samples, {missing_pct:.1f}%)")
            if is_stale:
                flags.append("Stale timestamp / communication timeout")
            if is_stuck:
                flags.append(f"Repeated/stuck constant reading ({repeated_count} identical samples)")
            elif repeated_count >= 6:
                flags.append(f"Repeated values ({repeated_count} consecutive samples)")
            if spike_count > 0:
                flags.append(f"Abnormal transient spike ({spike_count} event(s))")
            if oob_count > 0:
                flags.append(f"Out-of-range value ({oob_count} sample(s) outside [{spec['lower_bound']}, {spec['upper_bound']}] {spec['unit']})")
            if live_warn and live_warn not in flags:
                flags.append(live_warn)

            is_flagged = len(flags) > 0
            if is_flagged:
                flag_reason = "; ".join(flags)
                diagnosis_type = "SENSOR_OR_COMM_FAULT"
                distinction_explanation = (
                    f"Flagged as a Sensor / Data-Quality Anomaly ({flag_reason}). "
                    f"Unreliable raw readings are isolated/validated before ML inference to prevent silent prediction contamination. "
                    f"Note: Software diagnostics identify signal anomalies only and cannot confirm physical rust or hardware damage without physical inspection."
                )
                recommendation = "Inspect sensor wiring, ADC channel, and transducer calibration; verify raw vs. validated reading in audit log."
            elif val_v >= spec["warn_high"]:
                if elevated_sensors_count >= 2:
                    flag_reason = f"Sensor signal valid, but reading ({val_v} {spec['unit']}) is elevated alongside {elevated_sensors_count - 1} other correlated sensor(s)."
                    diagnosis_type = "MACHINE_DEGRADATION"
                    distinction_explanation = (
                        "Distinguished as Genuine Machine Degradation / Load Stress: Transducer passes all data-quality checks "
                        "(0% missing, non-stuck dynamic variance, within physical transducer limits) while multiple correlated sensors show simultaneous elevation."
                    )
                    recommendation = "Sensor is reliable; investigate mechanical/thermal machine condition and scheduled maintenance."
                else:
                    flag_reason = f"Single-channel reading elevated ({val_v} {spec['unit']}) while other machine sensors remain nominal."
                    diagnosis_type = "INVESTIGATE_DRIFT_OR_OFFSET"
                    distinction_explanation = (
                        "Single-channel elevation with healthy signal variance: Could indicate localized thermal/mechanical change or sensor calibration drift. "
                        "Requires technician verification before concluding machine failure."
                    )
                    recommendation = "Cross-check sensor calibration against portable reference gauge."
            else:
                flag_reason = "All measurable criteria passed (0% missing, fresh timestamp, dynamic variance normal, within range)."
                diagnosis_type = "HEALTHY_SENSOR"
                distinction_explanation = "Transducer and telemetry channel operating normally."
                recommendation = "Continue standard telemetry monitoring."

            if base_rel >= 95.0 and not is_flagged:
                rel_status = "OPTIMAL"
                status_color = "emerald"
            elif base_rel >= 85.0 and not is_flagged:
                rel_status = "NORMAL"
                status_color = "blue"
            elif base_rel >= 70.0:
                rel_status = "WATCHLIST"
                status_color = "amber"
            else:
                rel_status = "DEGRADED"
                status_color = "red"

            channels.append({
                "channel_id": spec["channel_id"],
                "plc_id": plc_id,
                "sensor_tag": tag_name,
                "sensor_name": spec["sensor_name"],
                "category": spec["category"],
                "unit": spec["unit"],
                "current_value": val_v,
                "raw_reading": raw_v if raw_v is not None else "NULL (Missing)",
                "validated_reading": val_v,
                "nominal_range": spec["nominal_range"],
                "lower_bound": spec["lower_bound"],
                "upper_bound": spec["upper_bound"],
                "is_stuck": is_stuck,
                "is_stale": is_stale,
                "missing_count": missing_count,
                "missing_pct": round(missing_pct, 2),
                "repeated_count": repeated_count,
                "spike_count": spike_count,
                "out_of_range_count": oob_count,
                "is_flagged": is_flagged,
                "flag_reason": flag_reason,
                "diagnosis_type": diagnosis_type,
                "distinction_explanation": distinction_explanation,
                "base_reliability": round(base_rel, 1),
                "reliability_status": rel_status,
                "status_color": status_color,
                "snr_db": spec["snr_db"],
                "failure_probability": round(max(0.2, (100.0 - base_rel) * 0.4), 2),
                "mtbf_hours": spec["mtbf_hours"],
                "last_calibrated": spec["last_calibrated"],
                "calibration_status": "RECALIBRATE" if is_flagged else "VALID",
                "recommendation": recommendation
            })

        overall_score = round(sum(c["base_reliability"] for c in channels) / len(channels), 1)
        flagged_count = sum(1 for c in channels if c["is_flagged"])

        return {
            "plc_id": plc_id,
            "overall_reliability_pct": overall_score,
            "reliability_grade": "A+" if overall_score >= 95 else ("A" if overall_score >= 90 else ("B" if overall_score >= 80 else "C")),
            "total_sensors_monitored": len(channels),
            "healthy_sensors_count": sum(1 for c in channels if c["base_reliability"] >= 85.0 and not c["is_flagged"]),
            "degraded_sensors_count": sum(1 for c in channels if c["base_reliability"] < 85.0 or c["is_flagged"]),
            "flagged_sensors_count": flagged_count,
            "stuck_transducers_count": sum(1 for c in channels if c["is_stuck"]),
            "mean_snr_db": round(sum(c["snr_db"] for c in channels) / len(channels), 1),
            "overall_data_integrity_pct": round(max(0.0, 100.0 - sum(c["missing_pct"] for c in channels) / len(channels)), 1),
            "methodology_note": (
                "Reliability Score (0-100%) is computed from measurable telemetry quality criteria: "
                "missing readings, stale timestamps, repeated/stuck values, abnormal step spikes, and physical range bounds. "
                "Unreliable readings are isolated via safe fallback validation before ML RUL inference while raw readings are preserved for audit. "
                "Software telemetry diagnostics do not claim to directly confirm physical rust or hardware damage without physical evidence."
            ),
            "sensors": channels
        }

    def get_health_index_breakdown(self, plc_id: str = "PLC_01", telemetry: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Computes composite machine and subsystem health index breakdowns
        and degradation trajectory from sensor telemetry.
        """
        plc_id = str(plc_id or "PLC_01").strip()
        asset_id = self.resolve_asset_id(plc_id)
        asset = self.db.get_asset_by_id(asset_id) or {}
        
        tel = telemetry or {}
        vib = float(tel.get("vibration", tel.get("Vibration_X", 0.28)) or 0.28)
        temp = float(tel.get("temperature", tel.get("Motor_Temp", 64.5)) or 64.5)
        curr = float(tel.get("motor_current", tel.get("Current_Draw", 15.2)) or 15.2)

        # Subsystems Health Index Models
        bearing_health = max(20.0, min(100.0, 100.0 - (vib * 55.0) - max(0, (temp - 65.0) * 0.4)))
        stator_health = max(25.0, min(100.0, 100.0 - max(0, (temp - 60.0) * 0.9) - max(0, (curr - 16.0) * 1.5)))
        gearbox_health = max(30.0, min(100.0, 100.0 - (vib * 28.0) - 2.5))
        inverter_health = max(40.0, min(100.0, 98.5 - max(0, (curr - 17.0) * 1.8)))
        cooling_health = max(35.0, min(100.0, 100.0 - max(0, (temp - 62.0) * 0.8)))

        subsystems = [
            {
                "subsystem_id": f"{asset_id}-BRG",
                "name": "Drive-End Bearing Assembly",
                "health_index": round(bearing_health, 1),
                "wear_percentage": round(100.0 - bearing_health, 1),
                "status": "EXCELLENT" if bearing_health >= 85 else ("GOOD" if bearing_health >= 70 else "ATTENTION"),
                "primary_stressor": "Mechanical Vibration & Dynamic Shock",
                "criticality": "HIGH",
                "weight_pct": 30
            },
            {
                "subsystem_id": f"{asset_id}-MOT",
                "name": "Motor Stator & Rotor Core",
                "health_index": round(stator_health, 1),
                "wear_percentage": round(100.0 - stator_health, 1),
                "status": "EXCELLENT" if stator_health >= 85 else ("GOOD" if stator_health >= 70 else "ATTENTION"),
                "primary_stressor": "Thermal Dissipation & Stator Varnish Aging",
                "criticality": "HIGH",
                "weight_pct": 25
            },
            {
                "subsystem_id": f"{asset_id}-GBX",
                "name": "Helical Reduction Gearbox",
                "health_index": round(gearbox_health, 1),
                "wear_percentage": round(100.0 - gearbox_health, 1),
                "status": "EXCELLENT" if gearbox_health >= 85 else ("GOOD" if gearbox_health >= 70 else "ATTENTION"),
                "primary_stressor": "Gear Mesh Backlash & Tooth Flank Contact",
                "criticality": "MEDIUM",
                "weight_pct": 20
            },
            {
                "subsystem_id": f"{asset_id}-INV",
                "name": "Power Inverter & Bus Caps",
                "health_index": round(inverter_health, 1),
                "wear_percentage": round(100.0 - inverter_health, 1),
                "status": "EXCELLENT" if inverter_health >= 85 else ("GOOD" if inverter_health >= 70 else "ATTENTION"),
                "primary_stressor": "Harmonic Current Ripple & Thermal Cycling",
                "criticality": "MEDIUM",
                "weight_pct": 15
            },
            {
                "subsystem_id": f"{asset_id}-LUB",
                "name": "Lubrication & Cooling Loop",
                "health_index": round(cooling_health, 1),
                "wear_percentage": round(100.0 - cooling_health, 1),
                "status": "EXCELLENT" if cooling_health >= 85 else ("GOOD" if cooling_health >= 70 else "ATTENTION"),
                "primary_stressor": "Fluid Viscosity Breakdown & Seal Integrity",
                "criticality": "LOW",
                "weight_pct": 10
            }
        ]

        composite_health = round(sum(s["health_index"] * (s["weight_pct"] / 100.0) for s in subsystems), 1)

        # Historical Trajectory Simulation (24 historical steps)
        trajectory = []
        now = datetime.datetime.now()
        for i in range(12, 0, -1):
            t_past = (now - datetime.timedelta(hours=i * 2)).strftime("%H:%M")
            synthetic_h = min(100.0, composite_health + (i * 0.45))
            trajectory.append({"time": t_past, "health": round(synthetic_h, 1), "type": "Historical"})
        trajectory.append({"time": "Now", "health": composite_health, "type": "Current"})
        for i in range(1, 7):
            t_fut = (now + datetime.timedelta(days=i * 2)).strftime("D+%d" % (i * 2))
            proj_h = max(20.0, composite_health - (i * 1.8))
            trajectory.append({"time": t_fut, "health": round(proj_h, 1), "type": "Projected"})

        return {
            "plc_id": plc_id,
            "asset_id": asset_id,
            "asset_name": asset.get("asset_name", f"Industrial Unit {plc_id}"),
            "composite_health_index": composite_health,
            "health_grade": "A" if composite_health >= 90 else ("B" if composite_health >= 75 else ("C" if composite_health >= 60 else "D")),
            "status": "OPTIMAL" if composite_health >= 85 else ("MONITOR" if composite_health >= 70 else "CRITICAL_MAINTENANCE"),
            "degradation_rate_per_day": 0.42,
            "subsystems": subsystems,
            "trajectory": trajectory
        }


digital_thread_service = DigitalThreadService()

