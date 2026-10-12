import sys
import os
import time
import json
import asyncio
import logging
import datetime
import threading
import paho.mqtt.client as mqtt
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any, Union
import re
import math
import warnings
import pandas as pd
import numpy as np

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

# Set up logging for debugging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("uvicorn.error")

# Ensure project modules are discoverable
base_dir = os.path.dirname(os.path.abspath(__file__))
for folder in ['simulator', 'preprocessing', 'model', 'utils']:
    folder_path = os.path.join(base_dir, folder)
    if os.path.exists(folder_path) and folder_path not in sys.path:
        sys.path.append(folder_path)
if base_dir not in sys.path:
    sys.path.append(base_dir)

try:
    from simulator import RealTimeMachineSimulator  # type: ignore
except ImportError:
    from simulator.simulator import RealTimeMachineSimulator  # type: ignore

try:
    from model.predict import PredictiveMaintenanceModel, get_future_trend, filter_displayed_rul  # type: ignore
except ImportError:
    from predict import PredictiveMaintenanceModel, get_future_trend, filter_displayed_rul  # type: ignore

try:
    from model.maintenance_engine import get_maintenance_recommendation  # type: ignore
except ImportError:
    from maintenance_engine import get_maintenance_recommendation  # type: ignore

try:
    from model.cost_energy_engine import (  # type: ignore
        cost_energy_config,
        generate_total_maintenance_decision,
        calculate_energy_consumption,
        detect_energy_anomaly
    )
except ImportError:
    from cost_energy_engine import (  # type: ignore
        cost_energy_config,
        generate_total_maintenance_decision,
        calculate_energy_consumption,
        detect_energy_anomaly
    )

try:
    from preprocessing import load_data, preprocess_data  # type: ignore
except ImportError:
    from preprocessing.preprocessing import load_data, preprocess_data  # type: ignore


try:
    from utils import get_status_color  # type: ignore
except ImportError:
    from utils.utils import get_status_color  # type: ignore


try:
    from drift.drift_service import drift_service  # type: ignore
    from drift.baseline import baseline_mgr  # type: ignore
    from drift.database import db as drift_db  # type: ignore
except ImportError:
    try:
        from drift_service import drift_service  # type: ignore
        from baseline import baseline_mgr  # type: ignore
        from database import db as drift_db  # type: ignore
    except Exception as drift_imp_err:
        logger.warning(f"Drift module import: {drift_imp_err}")

try:
    from digital_thread.service import digital_thread_service  # type: ignore
    from digital_thread.database import db as dt_db  # type: ignore
    from digital_thread.config import config as dt_config  # type: ignore
except ImportError:
    try:
        from digital_thread_service import digital_thread_service  # type: ignore
        from database import db as dt_db  # type: ignore
        from config import config as dt_config  # type: ignore
    except Exception as dt_imp_err:
        logger.warning(f"Digital Thread module import: {dt_imp_err}")


# OWASP Security Headers Middleware
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' data: https://fonts.gstatic.com; "
            "img-src 'self' data: blob:; "
            "connect-src 'self' http://localhost:* http://127.0.0.1:* ws://localhost:* ws://127.0.0.1:*;"
        )
        return response

# Dynamic Tag Specifications for PLC telemetry (Requirements 23, 25, 28)
TAG_SPECS = [
    {"tag_id": "T101", "tag_name": "Motor_Temp", "label": "Motor Temperature", "unit": "°C", "attr": "temperature"},
    {"tag_id": "T102", "tag_name": "Vibration_X", "label": "Vibration RMS", "unit": "mm/s", "attr": "vibration"},
    {"tag_id": "T103", "tag_name": "Motor_Current", "label": "Motor Current", "unit": "A", "attr": "motor_current"},
    {"tag_id": "T104", "tag_name": "Pressure_Inlet", "label": "Inlet Pressure", "unit": "bar", "attr": "pressure"},
    {"tag_id": "T105", "tag_name": "Noise", "label": "Acoustic Noise", "unit": "dB", "attr": "noise"},
]
TAG_NAME_TO_ATTR = {t["tag_name"]: t["attr"] for t in TAG_SPECS}
TAG_NAME_TO_ATTR.update({
    "Vibration": "vibration",
    "Temperature": "temperature",
    "Current": "motor_current",
    "Pressure": "pressure"
})
ATTR_TO_TAG_NAME = {t["attr"]: t["tag_name"] for t in TAG_SPECS}

# Sensor threshold ranges and engineering specifications
SENSOR_SPECS = {
    "Motor_Temp": {"tag_id": "T101", "name": "Motor Temperature", "unit": "°C", "normal_range": "< 70.0 °C", "warning_range": "70.0 - 85.0 °C", "critical_range": "> 85.0 °C", "warn_thresh": 70.0, "crit_thresh": 85.0},
    "Vibration_X": {"tag_id": "T102", "name": "Vibration RMS", "unit": "mm/s", "normal_range": "< 0.50 mm/s", "warning_range": "0.50 - 1.50 mm/s", "critical_range": "> 1.50 mm/s", "warn_thresh": 0.50, "crit_thresh": 1.50},
    "Vibration": {"tag_id": "T102", "name": "Vibration RMS", "unit": "mm/s", "normal_range": "< 0.50 mm/s", "warning_range": "0.50 - 1.50 mm/s", "critical_range": "> 1.50 mm/s", "warn_thresh": 0.50, "crit_thresh": 1.50},
    "Motor_Current": {"tag_id": "T103", "name": "Motor Current", "unit": "A", "normal_range": "< 10.0 A", "warning_range": "10.0 - 15.0 A", "critical_range": "> 15.0 A", "warn_thresh": 10.0, "crit_thresh": 15.0},
    "Pressure_Inlet": {"tag_id": "T104", "name": "Inlet Pressure", "unit": "bar", "normal_range": "4.0 - 6.0 bar", "warning_range": "3.0 - 4.0 or 6.0 - 7.0 bar", "critical_range": "< 3.0 or > 7.0 bar", "warn_thresh": 6.0, "crit_thresh": 7.0},
    "Pressure": {"tag_id": "T104", "name": "Inlet Pressure", "unit": "bar", "normal_range": "4.0 - 6.0 bar", "warning_range": "3.0 - 4.0 or 6.0 - 7.0 bar", "critical_range": "< 3.0 or > 7.0 bar", "warn_thresh": 6.0, "crit_thresh": 7.0},
    "Noise": {"tag_id": "T105", "name": "Acoustic Noise", "unit": "dB", "normal_range": "< 55.0 dB", "warning_range": "55.0 - 70.0 dB", "critical_range": "> 70.0 dB", "warn_thresh": 55.0, "crit_thresh": 70.0},
}

def is_valid_plc_id(val):
    """
    Validates whether a given PLC identifier is legitimate.
    Rejects: None, empty string, NaN, null, undefined, 0, negative, or non-PLC strings.
    Valid format: PLC_01..PLC_99, PLC1..PLC99, or numeric 1..99.
    """
    if val is None:
        return False
    if isinstance(val, (float, np.floating)) and (math.isnan(val) or not math.isfinite(val)):
        return False
    s = str(val).strip()
    if not s:
        return False
    upper = s.upper()
    if upper in ("NAN", "NONE", "NULL", "UNDEFINED", "EMPTY", "PLC_NAN", "PLC NAN", "PLC_NULL", "PLC_UNDEFINED") or "NAN" in upper:
        return False
    m = re.match(r"^PLC[_\s-]?0*([1-9]\d*)$", s, re.IGNORECASE)
    if m:
        return int(m.group(1)) > 0
    if s.isdigit():
        return int(s) > 0
    return False

def normalize_plc_id(val, fallback="PLC_01"):
    """
    Standardizes PLC IDs to canonical (str_id, int_id), e.g. ('PLC_01', 1).
    If val is invalid, returns (None, None) when fallback is None, or normalized fallback.
    """
    if not is_valid_plc_id(val):
        if fallback and is_valid_plc_id(fallback):
            return normalize_plc_id(fallback, fallback=None)
        return None, None
    s = str(val).strip()
    m = re.match(r"^PLC[_\s-]?0*([1-9]\d*)$", s, re.IGNORECASE)
    if m:
        num = int(m.group(1))
        return f"PLC_{num:02d}", num
    if s.isdigit():
        num = int(s)
        return f"PLC_{num:02d}", num
    if fallback and is_valid_plc_id(fallback):
        return normalize_plc_id(fallback, fallback=None)
    return None, None

def get_plc_desc(id_num):
    if not id_num or not isinstance(id_num, int) or id_num <= 0:
        return "Turbine Motor Unit"
    descs = {
        1: "Healthy Baseline Unit",
        2: "High Operating Load",
        3: "Bearing Degradation Unit",
        4: "Elevated Thermal Stress",
        5: "Normal Dynamic Variation"
    }
    return descs.get(id_num, f"Turbine Motor Unit {id_num}")

model_service = PredictiveMaintenanceModel()
sim_engines = [
    RealTimeMachineSimulator(plc_id=1, deg_init=0.04, base_load=0.55),
    RealTimeMachineSimulator(plc_id=2, deg_init=0.20, base_load=0.65, temp_offset=3.0),
    RealTimeMachineSimulator(plc_id=3, deg_init=0.45, base_load=0.72, vib_offset=0.2),
    RealTimeMachineSimulator(plc_id=4, deg_init=0.10, base_load=0.50),
    RealTimeMachineSimulator(plc_id=5, deg_init=0.75, base_load=0.85, temp_offset=8.0, vib_offset=0.6)
]
sim_engine = sim_engines[0]

df_eval = load_data()
df_eval.ffill(inplace=True)

class SimulationState:
    """
    State container maintaining strict isolation across multiple PLCs and tags.
    history_by_plc_tag[plc_id][tag_name] stores dedicated sensor streams (Requirement 23 & 26).
    """
    def __init__(self):
        self.auto_play = True
        self.simulation_speed = 1.0
        # Dedicated per-PLC per-tag history: { "PLC_01": { "Motor_Temp": [...], "Vibration_X": [...] } }
        self.history_by_plc_tag = {}
        # Dedicated per-PLC records list: { "PLC_01": [ ... ] }
        self.plc_history_records = {}
        # Legacy flat buffer
        self.history_records = []
        # Latest record per PLC: { "PLC_01": {...}, 1: {...} }
        self.plc_records = {}
        self.prev_displayed_rul = {} # { plc_id: val }
        self.prev_status_level = {} # { plc_id: level }
        self.prev_notification_state = {} # { plc_id: state }
        self.suspect_sensors = {} # { plc_id: { sensor_name: True } }

    def is_sensor_suspect(self, plc_id, sensor_name):
        plc_str, _ = normalize_plc_id(plc_id, fallback="PLC_01")
        return bool(self.suspect_sensors.get(plc_str, {}).get(sensor_name, False))

    def set_sensor_suspect(self, plc_id, sensor_name, is_suspect=True):
        plc_str, _ = normalize_plc_id(plc_id, fallback="PLC_01")
        if plc_str not in self.suspect_sensors:
            self.suspect_sensors[plc_str] = {}
        self.suspect_sensors[plc_str][sensor_name] = is_suspect

    def reset(self):
        self.auto_play = True
        self.history_records = []
        self.plc_records = {}
        self.plc_history_records = {}
        self.history_by_plc_tag = {}
        self.prev_displayed_rul = {}
        self.prev_status_level = {}
        self.prev_notification_state = {}

    def get_plc_status(self, plc_id="PLC_01"):
        plc_str, plc_num = normalize_plc_id(plc_id)
        if plc_str in self.plc_records:
            return self.plc_records[plc_str]
        if plc_num in self.plc_records:
            return self.plc_records[plc_num]
        
        # Default baseline record for this PLC (differentiated by PLC number)
        default_temp = round(60.0 + (plc_num * 1.8), 1)
        default_vib = round(0.20 + (plc_num * 0.08), 2)
        default_curr = round(7.5 + (plc_num * 0.4), 1)
        default_press = round(5.0 + (plc_num * 0.05), 1)
        default_noise = round(41.0 + (plc_num * 1.5), 1)

        rec = {
            "plc_id": plc_str,
            "plc_id_num": plc_num,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "temperature": default_temp,
            "vibration": default_vib,
            "motor_current": default_curr,
            "pressure": default_press,
            "noise": default_noise,
            "Motor_Temp": default_temp,
            "Vibration_X": default_vib,
            "Motor_Current": default_curr,
            "Pressure_Inlet": default_press,
            "Noise": default_noise,
            "tags": {
                "Motor_Temp": default_temp,
                "Vibration_X": default_vib,
                "Motor_Current": default_curr,
                "Pressure_Inlet": default_press,
                "Noise": default_noise
            },
            "machine_health": 100.0,
            "machine_status": "Healthy",
            "machine_condition": "Healthy",
            "predicted_rul_days": 250,
            "actual_rul_days": 250,
            "failure_risk_pct": 0.0,
            "anomaly_status": "Normal",
            "prediction_confidence": 98.5,
            "model_used": "Random Forest Regressor"
        }
        
        # Add baseline cost and energy decision
        try:
            total_dec = generate_total_maintenance_decision(
                plc_id=plc_str,
                plc_id_num=plc_num,
                sensor_readings={
                    "temperature": default_temp,
                    "vibration": default_vib,
                    "motor_current": default_curr,
                    "pressure": default_press,
                    "noise": default_noise
                },
                machine_health=100.0,
                machine_status="Healthy",
                failure_risk_pct=0.0,
                predicted_rul_days=250,
                is_anomaly=False,
                config=cost_energy_config
            )
            rec.update({
                "energy": total_dec["energy"],
                "energy_anomaly": total_dec["energy_anomaly"],
                "energy_status": total_dec["energy_anomaly"]["energy_status"],
                "energy_kwh_day": total_dec["energy"]["energy_kwh_day"],
                "baseline_energy_kwh_day": total_dec["energy"]["baseline_energy_kwh_day"],
                "excess_energy_pct": total_dec["energy"]["excess_pct"],
                "additional_energy_cost_day": total_dec["energy"]["additional_energy_cost_day"],
                "cost_optimization": total_dec["cost_optimization"],
                "preventive_cost": total_dec["cost_optimization"]["preventive_cost"],
                "expected_failure_cost": total_dec["cost_optimization"]["expected_failure_cost"],
                "potential_savings": total_dec["cost_optimization"]["potential_savings"],
                "financial_decision": total_dec["cost_optimization"]["decision"],
                "probable_issue": total_dec["main_issue"],
                "issue_detail": total_dec["issue_detail"],
                "q1_what_is_wrong": total_dec["q1_what_is_wrong"],
                "q2_when_maintain": total_dec["q2_when_maintain"],
                "q3_why_now": total_dec["q3_why_now"],
                "concise_alert": total_dec["concise_alert"],
                "transparency_points": total_dec["transparency_points"],
                "maintenance_priority": total_dec["priority"],
                "rul_deadline_text": total_dec["rul_recommendation"]["recommended_deadline_str"]
            })
        except Exception:
            pass

        return rec

sim_state = SimulationState()


# WebSocket Connection Manager for Live Real-Time Push to Frontend
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Total active connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket client disconnected. Total active connections: {len(self.active_connections)}")

    async def broadcast(self, data: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(data)
            except Exception:
                self.disconnect(connection)

ws_manager = ConnectionManager()
global_event_loop = None

def broadcast_telemetry(record: dict):
    """Thread-safe telemetry broadcast from MQTT background thread to WebSocket clients."""
    global global_event_loop
    if global_event_loop and global_event_loop.is_running():
        try:
            asyncio.run_coroutine_threadsafe(
                ws_manager.broadcast({
                    "type": "telemetry",
                    "plc_id": record.get("plc_id", 1),
                    "data": record
                }),
                global_event_loop
            )
        except Exception as e:
            logger.debug(f"Broadcast error: {e}")


def process_mqtt_telemetry(payload_dict, topic=""):
    """
    Processes incoming MQTT telemetry payload for a specific PLC.
    Supports both:
    1. Tag-specific messages (Requirement 25): {"plc_id": "PLC_01", "tag_name": "Motor_Temp", "val": 62.4}
    2. Composite PLC telemetry packets.
    Maintains strict per-PLC and per-tag isolation (Requirements 23, 26, 28).
    """
    try:
        if not isinstance(payload_dict, dict):
            return None

        # Extract PLC ID from payload or MQTT topic
        plc_id_val = payload_dict.get("plc_id", payload_dict.get("plc", payload_dict.get("machine_id", None)))
        if not is_valid_plc_id(plc_id_val) and topic:
            for part in topic.split("/"):
                if is_valid_plc_id(part):
                    plc_id_val = part
                    break

        # Requirement 3 & 7: Never create a PLC record when plc_id is null, undefined, empty, NaN, or missing
        if not is_valid_plc_id(plc_id_val):
            logger.debug(f"Ignoring telemetry with invalid or missing plc_id: {plc_id_val} on topic '{topic}'")
            return None

        plc_str, plc_num = normalize_plc_id(plc_id_val, fallback=None)
        if not plc_str or not plc_num:
            return None

        # Get existing baseline record for this specific PLC
        cur_rec = dict(sim_state.get_plc_status(plc_str))

        ts_val = payload_dict.get("timestamp", payload_dict.get("Timestamp", payload_dict.get("time", payload_dict.get("Time", None))))
        ts = str(ts_val) if ts_val is not None else datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Check if this is an individual tag message (Requirement 25)
        tag_name_in = payload_dict.get("tag_name")
        val_in = payload_dict.get("val", payload_dict.get("value"))
        
        if tag_name_in and val_in is not None:
            try:
                numeric_val = float(val_in)
                attr_name = TAG_NAME_TO_ATTR.get(tag_name_in, tag_name_in.lower())
                cur_rec[attr_name] = numeric_val
                cur_rec[tag_name_in] = numeric_val
                if "tags" not in cur_rec:
                    cur_rec["tags"] = {}
                cur_rec["tags"][tag_name_in] = numeric_val

                # Store into isolated history by PLC + TAG (Requirement 26)
                if plc_str not in sim_state.history_by_plc_tag:
                    sim_state.history_by_plc_tag[plc_str] = {t["tag_name"]: [] for t in TAG_SPECS}
                tag_hist = sim_state.history_by_plc_tag[plc_str].setdefault(tag_name_in, [])
                tag_hist.append({"timestamp": ts, "val": numeric_val})
                if len(tag_hist) > 100:
                    tag_hist.pop(0)
            except (ValueError, TypeError):
                pass

        # 1. Temperature Extraction
        temp_val = None
        for k in ["Motor_Temp", "temperature", "Temperature", "temp", "Temp", "TEMP"]:
            if k in payload_dict and payload_dict[k] is not None:
                try:
                    temp_val = float(payload_dict[k])
                    break
                except (ValueError, TypeError):
                    pass
        temp = temp_val if temp_val is not None else float(cur_rec.get("temperature", 62.0))

        # 2. Vibration Extraction
        vib_val = None
        for k in ["Vibration_X", "vibration", "Vibration", "vib", "Vib", "VIB"]:
            if k in payload_dict and payload_dict[k] is not None:
                try:
                    vib_val = float(payload_dict[k])
                    break
                except (ValueError, TypeError):
                    pass
        vib = vib_val if vib_val is not None else float(cur_rec.get("vibration", 0.2))

        # 3. Motor Current Extraction
        curr_val = None
        for k in ["Motor_Current", "motor_current", "Motor_Current", "motorCurrent", "current", "Current", "curr"]:
            if k in payload_dict and payload_dict[k] is not None:
                try:
                    curr_val = float(payload_dict[k])
                    break
                except (ValueError, TypeError):
                    pass
        curr = curr_val if curr_val is not None else float(cur_rec.get("motor_current", 8.0))

        # 4. Pressure Extraction
        press_val = None
        for k in ["Pressure_Inlet", "pressure", "Pressure", "press", "Press"]:
            if k in payload_dict and payload_dict[k] is not None:
                try:
                    press_val = float(payload_dict[k])
                    break
                except (ValueError, TypeError):
                    pass
        press = press_val if press_val is not None else float(cur_rec.get("pressure", 5.0))

        # 5. Noise Extraction
        noise_val = None
        for k in ["Noise", "noise", "Acoustic_Noise", "acoustic_noise"]:
            if k in payload_dict and payload_dict[k] is not None:
                try:
                    noise_val = float(payload_dict[k])
                    break
                except (ValueError, TypeError):
                    pass
        raw_readings = {
            "Motor_Temp": temp_val,
            "Vibration": vib_val,
            "Motor_Current": curr_val,
            "Pressure_Inlet": press_val,
            "Noise": noise_val
        }
        sensor_validation_warnings = {}

        def _validate_sensor_reading(tag: str, raw_v: Optional[float], fallback_v: float, low_b: float, high_b: float, unit: str) -> float:
            if raw_v is None or np.isnan(raw_v) or not np.isfinite(raw_v):
                sensor_validation_warnings[tag] = f"Missing/invalid reading on {tag} — substituted last valid reading ({fallback_v} {unit}) for safe prediction"
                sim_state.set_sensor_suspect(plc_str, tag, True)
                return fallback_v
            if raw_v < low_b or raw_v > high_b:
                clamped_v = float(max(low_b, min(high_b, fallback_v)))
                sensor_validation_warnings[tag] = f"Out-of-range reading ({raw_v} {unit} outside [{low_b}, {high_b}] {unit}) — isolated from ML prediction"
                sim_state.set_sensor_suspect(plc_str, tag, True)
                return clamped_v
            return float(raw_v)

        temp = _validate_sensor_reading("Motor_Temp", temp_val, float(cur_rec.get("temperature", 62.0)), 10.0, 150.0, "°C")
        vib = _validate_sensor_reading("Vibration", vib_val, float(cur_rec.get("vibration", 0.2)), 0.0, 15.0, "mm/s")
        curr = _validate_sensor_reading("Motor_Current", curr_val, float(cur_rec.get("motor_current", 8.0)), 0.0, 40.0, "A")
        press = _validate_sensor_reading("Pressure_Inlet", press_val, float(cur_rec.get("pressure", 5.0)), 0.5, 15.0, "bar")
        noise = _validate_sensor_reading("Noise", noise_val, float(cur_rec.get("noise", 42.0)), 20.0, 125.0, "dB")

        health = float(payload_dict.get("Machine_Health", payload_dict.get("health", cur_rec.get("machine_health", 100.0))))
        active_event = str(payload_dict.get("Active_Event", cur_rec.get("active_event", cur_rec.get("Active_Event", "None"))))

        # Stage Log: MQTT Received
        logger.info(f"MQTT RECEIVED | {plc_str} | Temp={round(temp, 1)}°C, Vib={round(vib, 2)}g, Curr={round(curr, 1)}A, Press={round(press, 1)}bar, Noise={round(noise, 1)}dB")

        # Isolation Forest Anomaly Detection (PLC-specific)
        anomaly_res = model_service.detect_anomaly(temp, vib, curr, pressure=press, noise=noise)
        is_anomaly = anomaly_res["is_anomaly"]
        anomaly_status = anomaly_res["anomaly_status"]
        
        # Deviation calculation for decision engine
        t_dev = max(0.0, (temp - 62.0) / 15.0)
        v_dev = max(0.0, (vib - 0.20) / 4.0)
        c_dev = max(0.0, (curr - 8.0) / 7.2)
        p_dev = max(0.0, (press - 5.0) / 3.0)
        n_dev = max(0.0, (noise - 42.0) / 30.0)
        sensor_anomaly_score = 0.25 * t_dev + 0.30 * v_dev + 0.15 * c_dev + 0.15 * p_dev + 0.15 * n_dev

        # Random Forest RUL Prediction (PLC-specific)
        raw_pred_rul, model_used, raw_pred_float, confidence_pct, ci = model_service.predict_rul(
            temp, vib, curr, pressure=press, noise=noise, return_full_info=True
        )

        prev_rul = sim_state.prev_displayed_rul.get(plc_str, None)
        val_float, displayed_rul = filter_displayed_rul(
            raw_prediction=raw_pred_rul,
            prev_displayed_rul=prev_rul,
            health=health
        )
        sim_state.prev_displayed_rul[plc_str] = val_float
        sim_state.prev_displayed_rul[plc_num] = val_float

        logger.info(f"RANDOM FOREST | {plc_str} | PREDICTION: {displayed_rul} Days (Confidence: {confidence_pct}%)")
        logger.info(f"ISOLATION FOREST | {plc_str} | ANOMALY: {anomaly_status} (Score: {anomaly_res['anomaly_score']})")

        # Maintenance Decision Engine (PLC-specific)
        prev_level = sim_state.prev_status_level.get(plc_str, 0)
        maint_info = get_maintenance_recommendation(
            predicted_rul=displayed_rul,
            machine_health=health,
            active_event=active_event,
            max_lifespan_days=250,
            prev_status_level=prev_level,
            sensor_anomaly_score=sensor_anomaly_score,
            is_anomaly=is_anomaly
        )
        sim_state.prev_status_level[plc_str] = maint_info.get("status_level", 0)
        sim_state.prev_status_level[plc_num] = maint_info.get("status_level", 0)

        # Critical alert handling
        prev_notif_state = sim_state.prev_notification_state.get(plc_str, "NORMAL")
        current_notif_state = "CRITICAL" if maint_info["maintenance_status"] in ["Critical", "Maintenance Required", "Critical Warning"] or maint_info.get("status_level", 0) >= 3 else "NORMAL"
        
        if current_notif_state == "CRITICAL" and prev_notif_state != "CRITICAL":
            logger.warning(f"CRITICAL ALERT | {plc_str} | NOTIFICATION SENT -> {maint_info['recommended_action']}")
        
        sim_state.prev_notification_state[plc_str] = current_notif_state
        sim_state.prev_notification_state[plc_num] = current_notif_state

        # Maintenance Cost Optimization + Energy-Aware Decision Engine (PLC-specific)
        total_decision = generate_total_maintenance_decision(
            plc_id=plc_str,
            plc_id_num=plc_num,
            sensor_readings={
                "temperature": temp,
                "vibration": vib,
                "motor_current": curr,
                "pressure": press,
                "noise": noise
            },
            machine_health=health,
            machine_status=maint_info["maintenance_status"],
            failure_risk_pct=maint_info["failure_risk_pct"],
            predicted_rul_days=displayed_rul,
            is_anomaly=is_anomaly,
            config=cost_energy_config
        )

        record = {
            "plc_id": plc_str,
            "plc_id_num": plc_num,
            "timestamp": ts,
            "Timestamp": ts,
            "temperature": round(temp, 1),
            "vibration": round(vib, 2),
            "motor_current": round(curr, 1),
            "pressure": round(press, 1),
            "noise": round(noise, 1),
            "Temperature": round(temp, 1),
            "Vibration": round(vib, 2),
            "Motor_Current": round(curr, 1),
            "Pressure": round(press, 1),
            "Noise": round(noise, 1),
            "Motor_Temp": round(temp, 1),
            "Vibration_X": round(vib, 2),
            "Pressure_Inlet": round(press, 1),
            "raw_readings": raw_readings,
            "sensor_validation_warnings": sensor_validation_warnings,
            "tags": {
                "Motor_Temp": round(temp, 1),
                "Vibration_X": round(vib, 2),
                "Vibration": round(vib, 2),
                "Motor_Current": round(curr, 1),
                "Pressure_Inlet": round(press, 1),
                "Noise": round(noise, 1)
            },
            "sensor_details": {
                "Motor_Temp": {
                    "tag_id": "T101",
                    "tag_name": "Motor_Temp",
                    "label": "Motor Temperature",
                    "val": round(temp, 1),
                    "unit": "°C",
                    "normal_range": "< 70.0 °C",
                    "warning_range": "70.0 - 85.0 °C",
                    "critical_range": "> 85.0 °C",
                    "status": "CRITICAL" if temp > 85.0 else "WARNING" if temp > 70.0 else "NORMAL",
                    "integrity": "SUSPECT" if sim_state.is_sensor_suspect(plc_str, "Motor_Temp") else "NORMAL",
                    "timestamp": ts,
                    "topic": f"plc/{plc_str}/Motor_Temp"
                },
                "Vibration_X": {
                    "tag_id": "T102",
                    "tag_name": "Vibration_X",
                    "label": "Vibration RMS",
                    "val": round(vib, 2),
                    "unit": "mm/s",
                    "normal_range": "< 0.50 mm/s",
                    "warning_range": "0.50 - 1.50 mm/s",
                    "critical_range": "> 1.50 mm/s",
                    "status": "CRITICAL" if vib > 1.50 else "WARNING" if vib > 0.50 else "NORMAL",
                    "integrity": "SUSPECT" if sim_state.is_sensor_suspect(plc_str, "Vibration_X") or sim_state.is_sensor_suspect(plc_str, "Vibration") else "NORMAL",
                    "timestamp": ts,
                    "topic": f"plc/{plc_str}/Vibration_X"
                },
                "Vibration": {
                    "tag_id": "T102",
                    "tag_name": "Vibration",
                    "label": "Vibration RMS",
                    "val": round(vib, 2),
                    "unit": "mm/s",
                    "normal_range": "< 0.50 mm/s",
                    "warning_range": "0.50 - 1.50 mm/s",
                    "critical_range": "> 1.50 mm/s",
                    "status": "CRITICAL" if vib > 1.50 else "WARNING" if vib > 0.50 else "NORMAL",
                    "integrity": "SUSPECT" if sim_state.is_sensor_suspect(plc_str, "Vibration_X") or sim_state.is_sensor_suspect(plc_str, "Vibration") else "NORMAL",
                    "timestamp": ts,
                    "topic": f"plc/{plc_str}/Vibration"
                },
                "Motor_Current": {
                    "tag_id": "T103",
                    "tag_name": "Motor_Current",
                    "label": "Motor Current",
                    "val": round(curr, 1),
                    "unit": "A",
                    "normal_range": "< 10.0 A",
                    "warning_range": "10.0 - 15.0 A",
                    "critical_range": "> 15.0 A",
                    "status": "CRITICAL" if curr > 15.0 else "WARNING" if curr > 10.0 else "NORMAL",
                    "integrity": "SUSPECT" if sim_state.is_sensor_suspect(plc_str, "Motor_Current") else "NORMAL",
                    "timestamp": ts,
                    "topic": f"plc/{plc_str}/Motor_Current"
                },
                "Pressure_Inlet": {
                    "tag_id": "T104",
                    "tag_name": "Pressure_Inlet",
                    "label": "Inlet Pressure",
                    "val": round(press, 1),
                    "unit": "bar",
                    "normal_range": "4.0 - 6.0 bar",
                    "warning_range": "3.0 - 4.0 or 6.0 - 7.0 bar",
                    "critical_range": "< 3.0 or > 7.0 bar",
                    "status": "CRITICAL" if (press < 3.0 or press > 7.0) else "WARNING" if (press < 4.0 or press > 6.0) else "NORMAL",
                    "integrity": "SUSPECT" if sim_state.is_sensor_suspect(plc_str, "Pressure_Inlet") else "NORMAL",
                    "timestamp": ts,
                    "topic": f"plc/{plc_str}/Pressure_Inlet"
                },
                "Noise": {
                    "tag_id": "T105",
                    "tag_name": "Noise",
                    "label": "Acoustic Noise",
                    "val": round(noise, 1),
                    "unit": "dB",
                    "normal_range": "< 55.0 dB",
                    "warning_range": "55.0 - 70.0 dB",
                    "critical_range": "> 70.0 dB",
                    "status": "CRITICAL" if noise > 70.0 else "WARNING" if noise > 55.0 else "NORMAL",
                    "integrity": "SUSPECT" if sim_state.is_sensor_suspect(plc_str, "Noise") else "NORMAL",
                    "timestamp": ts,
                    "topic": f"plc/{plc_str}/Noise"
                }
            },
            "Machine_Health": round(health, 1),
            "machine_health": round(health, 1),
            "Machine_Status": maint_info["maintenance_status"],
            "machine_status": maint_info["maintenance_status"],
            "Machine_Condition": maint_info["machine_condition"],
            "machine_condition": maint_info["machine_condition"],
            "Failure_Risk_Pct": maint_info["failure_risk_pct"],
            "failure_risk_pct": maint_info["failure_risk_pct"],
            "failure_risk_probability": maint_info["failure_risk_pct"],
            "recommendation": maint_info["recommended_action"],
            "Anomaly_Status": anomaly_status,
            "anomaly_status": anomaly_status,
            "Anomaly_Score": anomaly_res["anomaly_score"],
            "Prediction_Confidence": confidence_pct,
            "prediction_confidence": confidence_pct,
            "Model_Used": model_used,
            "model_used": model_used,
            "Predicted_RUL": displayed_rul,
            "predicted_rul_days": displayed_rul,
            "actual_rul_days": int(payload_dict.get("Remaining_Useful_Life_Days", cur_rec.get("actual_rul_days", 250))),
            "Remaining_Useful_Life_Days": int(payload_dict.get("Remaining_Useful_Life_Days", cur_rec.get("actual_rul_days", 250))),
            "Recommended_Action": maint_info["recommended_action"],
            "Inspection_Priority": maint_info["inspection_priority"],
            "Next_Inspection_Window": maint_info["next_inspection_window"],
            "Active_Event": active_event,

            # Cost Optimization and Energy Decision Additions
            "energy": total_decision["energy"],
            "energy_anomaly": total_decision["energy_anomaly"],
            "energy_status": total_decision["energy_anomaly"]["energy_status"],
            "energy_kwh_day": total_decision["energy"]["energy_kwh_day"],
            "baseline_energy_kwh_day": total_decision["energy"]["baseline_energy_kwh_day"],
            "excess_energy_pct": total_decision["energy"]["excess_pct"],
            "additional_energy_cost_day": total_decision["energy"]["additional_energy_cost_day"],
            "cost_optimization": total_decision["cost_optimization"],
            "preventive_cost": total_decision["cost_optimization"]["preventive_cost"],
            "expected_failure_cost": total_decision["cost_optimization"]["expected_failure_cost"],
            "potential_savings": total_decision["cost_optimization"]["potential_savings"],
            "financial_decision": total_decision["cost_optimization"]["decision"],
            "probable_issue": total_decision["main_issue"],
            "issue_detail": total_decision["issue_detail"],
            "q1_what_is_wrong": total_decision["q1_what_is_wrong"],
            "q2_when_maintain": total_decision["q2_when_maintain"],
            "q3_why_now": total_decision["q3_why_now"],
            "concise_alert": total_decision["concise_alert"],
            "transparency_points": total_decision["transparency_points"],
            "maintenance_priority": total_decision["priority"],
            "rul_deadline_text": total_decision["rul_recommendation"]["recommended_deadline_str"]
        }

        # Store latest record for both canonical string and numeric ID
        sim_state.plc_records[plc_str] = record
        sim_state.plc_records[plc_num] = record

        # Maintain isolated per-PLC record list (Requirement 26 & 28)
        if plc_str not in sim_state.plc_history_records:
            sim_state.plc_history_records[plc_str] = []
        sim_state.plc_history_records[plc_str].append(record)
        if len(sim_state.plc_history_records[plc_str]) > 200:
            sim_state.plc_history_records[plc_str].pop(0)

        # Maintain isolated per-PLC per-tag stream (Requirement 23 & 26)
        if plc_str not in sim_state.history_by_plc_tag:
            sim_state.history_by_plc_tag[plc_str] = {t["tag_name"]: [] for t in TAG_SPECS}
        for t in TAG_SPECS:
            t_name = t["tag_name"]
            val_to_store = record.get(t_name, record.get(t["attr"], 0.0))
            tag_stream = sim_state.history_by_plc_tag[plc_str].setdefault(t_name, [])
            tag_stream.append({"timestamp": ts, "val": val_to_store})
            if len(tag_stream) > 200:
                tag_stream.pop(0)

        # Legacy flat buffer
        sim_state.history_records.append(record)

        # Ingest into Data Drift & Model Reliability Monitoring subsystem
        try:
            drift_service.ingest_telemetry_record(record)
        except Exception as drift_e:
            logger.debug(f"Drift telemetry ingestion note: {drift_e}")

        # Ingest into Asset Digital Thread lifecycle subsystem
        try:
            digital_thread_service.ingest_telemetry_event(record)
        except Exception as dt_e:
            logger.debug(f"Digital Thread telemetry ingestion note: {dt_e}")

        if len(sim_state.history_records) > 1000:
            sim_state.history_records.pop(0)

        # Broadcast update in real time to connected WebSocket clients
        broadcast_telemetry(record)

        return record

    except Exception as e:
        logger.error(f"Error processing MQTT telemetry payload: {e}", exc_info=True)


# Resilient MQTT Backend Subscriber with continuous auto-reconnect and local broker fallback
class BackendMqttSubscriber:
    def __init__(self, broker=None, port=1883):
        self.default_broker = broker or os.getenv("MQTT_BROKER", "127.0.0.1")
        self.port = int(os.getenv("MQTT_PORT", port))
        self.client = None
        self.running = True
        self.connected = False
        self.mini_broker = None

    def start(self):
        t = threading.Thread(target=self._run_loop, daemon=True, name="MQTT_Subscriber_Thread")
        t.start()

    def _run_loop(self):
        # 1. Attempt local mini broker startup if not already running
        if self.mini_broker is None and self.default_broker in ("127.0.0.1", "localhost"):
            try:
                from simulator.simulator import MiniMqttBroker  # type: ignore
                mb = MiniMqttBroker(host="127.0.0.1", port=self.port)
                if mb.start():
                    self.mini_broker = mb
                    logger.info(f"Local Mini MQTT Broker started successfully on 127.0.0.1:{self.port}")
                    time.sleep(0.2)
            except Exception as mb_err:
                logger.debug(f"Mini broker startup check: {mb_err}")

        candidate_brokers = [self.default_broker, "127.0.0.1", "localhost"]
        seen = set()
        unique_brokers = [b for b in candidate_brokers if b and not (b in seen or seen.add(b))]

        while self.running:
            if not self.connected:
                # Clean up any lingering previous client
                if self.client:
                    try:
                        self.client.loop_stop()
                        self.client.disconnect()
                    except Exception:
                        pass
                    self.client = None

                connected_any = False
                for host in unique_brokers:
                    if not self.running:
                        break
                    try:
                        logger.info(f"MQTT Subscriber attempting connection to {host}:{self.port}...")
                        client_tag = f"Sub_{os.getpid()}_{int(time.time()*1000)%100000}"
                        try:
                            c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_tag)
                        except Exception:
                            c = mqtt.Client(client_id=client_tag)
                        c.on_connect = self.on_connect
                        c.on_disconnect = self.on_disconnect
                        c.on_message = self.on_message
                        c.connect(host, self.port, keepalive=60)
                        c.loop_start()
                        self.client = c
                        self.connected = True
                        connected_any = True
                        logger.info(f"MQTT Subscriber connected successfully to {host}:{self.port}")
                        break
                    except Exception as e:
                        logger.debug(f"Connection to {host}:{self.port} failed: {e}")

                if not connected_any and self.mini_broker is None:
                    try:
                        from simulator.simulator import MiniMqttBroker  # type: ignore
                        mb = MiniMqttBroker(host="127.0.0.1", port=self.port)
                        if mb.start():
                            self.mini_broker = mb
                            logger.info(f"Local Mini MQTT Broker started successfully on 127.0.0.1:{self.port}")
                            time.sleep(0.3)
                            continue
                    except Exception as mb_err:
                        logger.debug(f"Mini broker fallback not started: {mb_err}")

            time.sleep(3.0)

    def on_connect(self, client, userdata, flags, rc, properties=None):
        self.connected = True
        logger.info("MQTT Subscriber connected. Subscribing to telemetry topics (plc/#)...")
        for topic in ["plc/#"]:
            try:
                client.subscribe(topic)
            except Exception:
                pass

    def on_disconnect(self, client, userdata, rc=None, *args, **kwargs):
        self.connected = False
        logger.warning(f"MQTT Subscriber disconnected (rc={rc}). Will auto-reconnect...")

    def on_message(self, client, userdata, msg):
        try:
            payload_str = msg.payload.decode("utf-8")
            data = json.loads(payload_str)
            if isinstance(data, dict):
                process_mqtt_telemetry(data, topic=msg.topic)
        except Exception as e:
            logger.error(f"Error processing MQTT message on topic {msg.topic}: {e}")

mqtt_sub = BackendMqttSubscriber()


sim_worker_thread = None

def generate_next_telemetry_step(target_plc=None):
    latest_rec = None
    for eng in sim_engines:
        try:
            rec = eng.step()
            processed = process_mqtt_telemetry(rec)
            if target_plc is None or getattr(eng, 'plc_id', 1) == target_plc:
                latest_rec = processed
        except Exception as e:
            logger.error(f"Error stepping simulator for PLC {getattr(eng, 'plc_id', '?')}: {e}")
    return latest_rec


def simulation_worker_loop():
    logger.info("Simulation background worker loop running.")
    while True:
        try:
            if getattr(sim_state, "auto_play", False):
                generate_next_telemetry_step()
            speed = getattr(sim_state, "simulation_speed", 1.0)
            sleep_time = max(0.2, min(5.0, float(speed) if speed > 0 else 1.0))
            time.sleep(sleep_time)
        except Exception as e:
            logger.error(f"Error in simulation background loop: {e}", exc_info=True)
            time.sleep(1.0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global global_event_loop, sim_worker_thread
    global_event_loop = asyncio.get_running_loop()
    if not sim_state.history_records:
        generate_next_telemetry_step()
    mqtt_sub.start()
    if sim_worker_thread is None or not sim_worker_thread.is_alive():
        sim_worker_thread = threading.Thread(target=simulation_worker_loop, daemon=True, name="Sim_Worker_Thread")
        sim_worker_thread.start()
    yield

app = FastAPI(
    title="AI-Based Predictive Maintenance Platform",
    description="Digital Twin SCADA & Predictive Maintenance ML Engine with Random Forest Regressor & Isolation Forest",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(SecurityHeadersMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "*"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

frontend_dist = os.path.join(base_dir, "frontend", "dist")
assets_dir = os.path.join(frontend_dist, "assets")
if os.path.exists(assets_dir):
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

outputs_dir = os.path.join(base_dir, "outputs")
if os.path.exists(outputs_dir):
    app.mount("/outputs", StaticFiles(directory=outputs_dir), name="outputs")


@app.get("/api/status")
def get_status():
    try:
        active_ids = []
        for eng in sim_engines:
            pid = getattr(eng, 'plc_id', 1)
            _, num = normalize_plc_id(pid, fallback=None)
            if num and num not in active_ids:
                active_ids.append(num)
        for k in sim_state.plc_records.keys():
            if is_valid_plc_id(k):
                _, num = normalize_plc_id(k, fallback=None)
                if num and num not in active_ids:
                    active_ids.append(num)
        for i in range(1, 6):
            if i not in active_ids:
                active_ids.append(i)
        active_ids.sort()

        return {
            "status": "online",
            "machine_id": "MCH-802X",
            "machine_name": "Turbine Motor Unit A1",
            "data_source": f"{len(active_ids)}-PLC MQTT Telemetry Engine (broker.hivemq.com:1883)",
            "model": model_service.best_model_name,
            "available_models": ["Random Forest Regressor"],
            "active_plcs": active_ids,
            "features": ["Temperature", "Vibration", "Motor Current", "Pressure", "Noise"],
            "current_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        logger.error(f"Error in GET /api/status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch system status: {str(e)}")


@app.get("/api/plcs")
def get_all_plcs():
    try:
        # Dynamic discovery of PLCs strictly filtered to valid identifiers
        known_plcs = set()
        for eng in sim_engines:
            pid = getattr(eng, 'plc_id', 1)
            plc_str, _ = normalize_plc_id(pid, fallback=None)
            if plc_str:
                known_plcs.add(plc_str)
        for k in sim_state.plc_records.keys():
            if is_valid_plc_id(k):
                plc_str, _ = normalize_plc_id(k, fallback=None)
                if plc_str:
                    known_plcs.add(plc_str)
        for i in range(1, 6):
            known_plcs.add(f"PLC_{i:02d}")
            
        sorted_plcs = sorted([p for p in known_plcs if is_valid_plc_id(p)], key=lambda x: normalize_plc_id(x, fallback=None)[1] or 0)
        plcs_data = []
        for plc_str in sorted_plcs:
            if not is_valid_plc_id(plc_str):
                continue
            rec = sim_state.get_plc_status(plc_str)
            _, num = normalize_plc_id(plc_str, fallback=None)
            if not num:
                continue

            plcs_data.append({
                "plc_id": plc_str,
                "plc_id_num": num,
                "name": f"{plc_str} ({get_plc_desc(num)})",
                "temperature": round(float(rec.get("temperature", 62.0)), 1),
                "vibration": round(float(rec.get("vibration", 0.2)), 2),
                "motor_current": round(float(rec.get("motor_current", 8.0)), 1),
                "pressure": round(float(rec.get("pressure", 5.0)), 1),
                "noise": round(float(rec.get("noise", 42.0)), 1),
                "predicted_rul_days": int(rec.get("predicted_rul_days", 200)),
                "machine_status": str(rec.get("machine_status", "Healthy")),
                "anomaly_status": str(rec.get("anomaly_status", "Normal")),
                "failure_risk_pct": float(rec.get("failure_risk_pct", 0.0)),
                "main_issue": str(rec.get("probable_issue", "Normal Operation")),
                "energy_status": str(rec.get("energy_status", "Normal")),
                "excess_energy_pct": float(rec.get("excess_energy_pct", 0.0)),
                "preventive_cost": float(rec.get("preventive_cost", 8000.0)),
                "expected_failure_cost": float(rec.get("expected_failure_cost", 0.0)),
                "potential_savings": float(rec.get("potential_savings", 0.0)),
                "priority": str(rec.get("maintenance_priority", "Low")),
                "concise_alert": rec.get("concise_alert"),
                "tags": [t["tag_name"] for t in TAG_SPECS]
            })
        return {"plcs": plcs_data}
    except Exception as e:
        logger.error(f"Error in GET /api/plcs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch PLC status: {str(e)}")


@app.get("/api/tags")
def get_tags(plc_id: str = "PLC_01"):
    try:
        plc_str, _ = normalize_plc_id(plc_id, fallback="PLC_01")
        if not plc_str:
            plc_str = "PLC_01"
        cur = sim_state.get_plc_status(plc_str)
        tags_info = []
        for t in TAG_SPECS:
            name = t["tag_name"]
            tags_info.append({
                "tag_id": t["tag_id"],
                "tag_name": name,
                "label": t["label"],
                "unit": t["unit"],
                "current_val": cur.get(name, cur.get(t["attr"], 0.0))
            })
        return {
            "plc_id": plc_str,
            "tags": tags_info
        }
    except Exception as e:
        logger.error(f"Error in GET /api/tags: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch tags: {str(e)}")



@app.get("/api/current")
def get_current(plc_id: str = "PLC_01"):
    try:
        plc_str, plc_num = normalize_plc_id(plc_id, fallback="PLC_01")
        if not plc_str or not plc_num:
            plc_str, plc_num = "PLC_01", 1
        
        # Build machines summary dynamically for all discovered valid PLCs
        known_plcs = set()
        for eng in sim_engines:
            pid = getattr(eng, 'plc_id', 1)
            p_str, _ = normalize_plc_id(pid, fallback=None)
            if p_str:
                known_plcs.add(p_str)
        for k in sim_state.plc_records.keys():
            if is_valid_plc_id(k):
                p_str, _ = normalize_plc_id(k, fallback=None)
                if p_str:
                    known_plcs.add(p_str)
        for i in range(1, 6):
            known_plcs.add(f"PLC_{i:02d}")
            
        sorted_plcs = sorted([p for p in known_plcs if is_valid_plc_id(p)], key=lambda x: normalize_plc_id(x, fallback=None)[1] or 0)
        machines_data = []
        for p_key in sorted_plcs:
            if not is_valid_plc_id(p_key):
                continue
            rec = sim_state.get_plc_status(p_key)
            _, p_num = normalize_plc_id(p_key, fallback=None)
            if not p_num:
                continue
            machines_data.append({
                "plc_id": p_key,
                "plc_id_num": p_num,
                "name": f"{p_key} ({get_plc_desc(p_num)})",
                "temperature": round(float(rec.get("temperature", 62.0)), 1),
                "vibration": round(float(rec.get("vibration", 0.2)), 2),
                "motor_current": round(float(rec.get("motor_current", 8.0)), 1),
                "pressure": round(float(rec.get("pressure", 5.0)), 1),
                "noise": round(float(rec.get("noise", 42.0)), 1),
                "predicted_rul_days": int(rec.get("predicted_rul_days", 200)),
                "machine_status": str(rec.get("machine_status", "Healthy")),
                "anomaly_status": str(rec.get("anomaly_status", "Normal")),
                "failure_risk_pct": float(rec.get("failure_risk_pct", 0.0)),
                "main_issue": str(rec.get("probable_issue", "Normal Operation")),
                "energy_status": str(rec.get("energy_status", "Normal")),
                "excess_energy_pct": float(rec.get("excess_energy_pct", 0.0)),
                "preventive_cost": float(rec.get("preventive_cost", 8000.0)),
                "expected_failure_cost": float(rec.get("expected_failure_cost", 0.0)),
                "potential_savings": float(rec.get("potential_savings", 0.0)),
                "priority": str(rec.get("maintenance_priority", "Low")),
                "concise_alert": rec.get("concise_alert"),
                "sensor_integrity": "SUSPECT" if any(sim_state.is_sensor_suspect(p_key, s) for s in ["Motor_Temp", "Vibration", "Vibration_X", "Motor_Current", "Pressure_Inlet", "Noise"]) else "NORMAL"
            })
            
        row = sim_state.get_plc_status(plc_str)
        temp = float(row.get("temperature", 62.0))
        vib = float(row.get("vibration", 0.2))
        curr = float(row.get("motor_current", 8.0))
        press = float(row.get("pressure", 5.0))
        noise = float(row.get("noise", 42.0))
        health = float(row.get("machine_health", 100.0))
        predicted_rul = int(row.get("predicted_rul_days", 0))
        machine_status = str(row.get("machine_status", "Healthy"))
        machine_condition = str(row.get("machine_condition", "Healthy"))
        anomaly_status = str(row.get("anomaly_status", "Normal"))
        failure_risk = float(row.get("failure_risk_pct", 0.0))
        confidence = float(row.get("prediction_confidence", 95.0))
        model_used = str(row.get("model_used", model_service.best_model_name))
        
        plc_hist = sim_state.plc_history_records.get(plc_str, [])

        return {
            "machines": machines_data,
            "plc_id": plc_str,
            "plc_id_num": plc_num,
            "current_idx": max(0, len(plc_hist) - 1),
            "total_records": max(1000, len(plc_hist)),
            "timestamp": str(row.get("timestamp", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))),
            "temperature": round(temp, 2),
            "vibration": round(vib, 2),
            "motor_current": round(curr, 2),
            "pressure": round(press, 2),
            "noise": round(noise, 2),
            "Motor_Temp": round(temp, 2),
            "Vibration_X": round(vib, 2),
            "Motor_Current": round(curr, 2),
            "Pressure_Inlet": round(press, 2),
            "Noise": round(noise, 2),
            "raw_readings": row.get("raw_readings", {
                "Motor_Temp": round(temp, 2),
                "Vibration": round(vib, 2),
                "Motor_Current": round(curr, 2),
                "Pressure_Inlet": round(press, 2),
                "Noise": round(noise, 2)
            }),
            "sensor_validation_warnings": row.get("sensor_validation_warnings", {}),
            "tags": row.get("tags", {
                "Motor_Temp": round(temp, 2),
                "Vibration_X": round(vib, 2),
                "Motor_Current": round(curr, 2),
                "Pressure_Inlet": round(press, 2),
                "Noise": round(noise, 2)
            }),
            "sensor_details": {
                k: {
                    **v,
                    "integrity": "SUSPECT" if sim_state.is_sensor_suspect(plc_str, k) or (k == "Vibration" and sim_state.is_sensor_suspect(plc_str, "Vibration_X")) or (k == "Vibration_X" and sim_state.is_sensor_suspect(plc_str, "Vibration")) else "NORMAL"
                } if isinstance(v, dict) else v
                for k, v in row.get("sensor_details", {}).items()
            },
            "sensor_integrity": "SUSPECT" if any(sim_state.is_sensor_suspect(plc_str, s) for s in ["Motor_Temp", "Vibration", "Vibration_X", "Motor_Current", "Pressure_Inlet", "Noise"]) else "NORMAL",

            "machine_health": round(health, 1),
            "machine_status": machine_status,
            "machine_condition": machine_condition,
            "predicted_rul_days": predicted_rul,
            "actual_rul_days": int(row.get("actual_rul_days", 250)),
            "failure_risk_pct": round(failure_risk, 1),
            "failure_risk_probability": round(failure_risk, 1),
            "recommendation": str(row.get("recommendation", row.get("Recommended_Action", "Continue routine monitoring"))),
            "anomaly_status": anomaly_status,
            "prediction_confidence": round(confidence, 1),
            "model_used": model_used,

            # Cost Optimization & Energy Insights
            "energy": row.get("energy", calculate_energy_consumption(curr, plc_id_num=plc_num, config=cost_energy_config)),
            "energy_anomaly": row.get("energy_anomaly"),
            "energy_status": row.get("energy_status", "Normal"),
            "energy_summary": row.get("energy_summary"),
            "cost_optimization": row.get("cost_optimization"),
            "preventive_cost": row.get("preventive_cost", 8000.0),
            "expected_failure_cost": row.get("expected_failure_cost", 0.0),
            "potential_savings": row.get("potential_savings", 0.0),
            "financial_decision": row.get("financial_decision"),
            "probable_issue": row.get("probable_issue", "Normal Operation"),
            "issue_detail": row.get("issue_detail", ""),
            "q1_what_is_wrong": row.get("q1_what_is_wrong", "Normal baseline operation"),
            "q2_when_maintain": row.get("q2_when_maintain", f"{predicted_rul} days remaining"),
            "q3_why_now": row.get("q3_why_now", "Normal operation"),
            "concise_alert": row.get("concise_alert"),
            "transparency_points": row.get("transparency_points", []),
            "maintenance_priority": row.get("maintenance_priority", "Low"),
            "rul_deadline_text": row.get("rul_deadline_text", "Monitor normally")
        }
    except Exception as e:
        logger.error(f"Error in GET /api/current: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch telemetry state: {str(e)}")



@app.websocket("/ws/telemetry")
async def websocket_telemetry(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        cur_plc_str = "PLC_01"
        cur = sim_state.get_plc_status(cur_plc_str)
        recent = sim_state.plc_history_records.get(cur_plc_str, [cur])[-50:]
        await websocket.send_json({
            "type": "init",
            "plc_id": cur_plc_str,
            "data": cur,
            "history": recent
        })
        while True:
            msg_text = await websocket.receive_text()
            try:
                cmd = json.loads(msg_text)
                if cmd.get("action") == "select_plc":
                    req_plc = cmd.get("plc_id", "PLC_01")
                    norm_plc, _ = normalize_plc_id(req_plc, fallback=None)
                    if norm_plc:
                        cur_plc_str = norm_plc
                        cur_plc = sim_state.get_plc_status(cur_plc_str)
                        recent_plc = sim_state.plc_history_records.get(cur_plc_str, [cur_plc])[-50:]
                        await websocket.send_json({
                            "type": "init",
                            "plc_id": cur_plc_str,
                            "data": cur_plc,
                            "history": recent_plc
                        })
            except Exception:
                pass
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)


@app.get("/api/history")
def get_history(plc_id: str = "PLC_01", tag: str = "Motor_Temp"):
    try:
        plc_str, plc_num = normalize_plc_id(plc_id, fallback="PLC_01")
        if not plc_str or not plc_num:
            plc_str, plc_num = "PLC_01", 1
        
        # Get strictly isolated records for this specific PLC (Requirement 26 & 28)
        plc_records = sim_state.plc_history_records.get(plc_str, [])
        if not plc_records:
            cur = sim_state.get_plc_status(plc_str)
            plc_records = [cur]

        recent_records = plc_records[-100:]

        # Extract per-sensor arrays strictly from this PLC
        temps = [float(r.get("Motor_Temp", r.get("temperature", 62.0))) for r in recent_records]
        vibs = [float(r.get("Vibration_X", r.get("vibration", 0.2))) for r in recent_records]
        currs = [float(r.get("Motor_Current", r.get("motor_current", 8.0))) for r in recent_records]
        presses = [float(r.get("Pressure_Inlet", r.get("pressure", 5.0))) for r in recent_records]
        noises = [float(r.get("Noise", r.get("noise", 42.0))) for r in recent_records]
        healths = [float(r.get("machine_health", 100.0)) for r in recent_records]
        ruls = [int(r.get("predicted_rul_days", 200)) for r in recent_records]
        timestamps = [str(r.get("timestamp", "")) for r in recent_records]

        # ML Predictions: Polynomial trend extrapolation (solid = actual, dashed = prediction)
        temp_future = get_future_trend(temps, steps=20)
        vib_future = get_future_trend(vibs, steps=20)
        curr_future = get_future_trend(currs, steps=20)
        press_future = get_future_trend(presses, steps=20)
        noise_future = get_future_trend(noises, steps=20)
        health_future = get_future_trend(healths, steps=20)
        rul_future = get_future_trend(ruls, steps=20)

        tag_data_map = {
            "Motor_Temp": (temps, temp_future, "°C", "Motor Temperature"),
            "Temperature": (temps, temp_future, "°C", "Motor Temperature"),
            "Vibration_X": (vibs, vib_future, "mm/s", "Vibration RMS"),
            "Vibration": (vibs, vib_future, "mm/s", "Vibration RMS"),
            "Motor_Current": (currs, curr_future, "A", "Motor Current"),
            "Pressure_Inlet": (presses, press_future, "bar", "Inlet Pressure"),
            "Pressure": (presses, press_future, "bar", "Inlet Pressure"),
            "Noise": (noises, noise_future, "dB", "Acoustic Noise"),
            "Machine_Health": (healths, health_future, "%", "Machine Health"),
            "Predicted_RUL": (ruls, rul_future, "Days", "Remaining Useful Life")
        }

        selected_tag_normalized = tag if tag in tag_data_map else "Motor_Temp"
        act_vals, pred_vals, tag_unit, tag_label = tag_data_map[selected_tag_normalized]

        logger.info(f"API HISTORY | PLC={plc_str} | tag={selected_tag_normalized} | points={len(recent_records)}")

        return {
            "plc_id": plc_str,
            "plc_id_num": plc_num,
            "selected_tag": selected_tag_normalized,
            "tag_label": tag_label,
            "tag_unit": tag_unit,
            "tags": [t["tag_name"] for t in TAG_SPECS],
            "actual": act_vals,
            "predicted_future": pred_vals,
            "timestamps": timestamps,
            "history": recent_records,
            "total_records": len(recent_records),
            "temperature_trend": {"actual": temps, "predicted_future": temp_future, "timestamps": timestamps},
            "vibration_trend": {"actual": vibs, "predicted_future": vib_future, "timestamps": timestamps},
            "motor_current_trend": {"actual": currs, "predicted_future": curr_future, "timestamps": timestamps},
            "pressure_trend": {"actual": presses, "predicted_future": press_future, "timestamps": timestamps},
            "noise_trend": {"actual": noises, "predicted_future": noise_future, "timestamps": timestamps},
            "machine_health_trend": {"actual": healths, "predicted_future": health_future, "timestamps": timestamps},
            "rul_trend": {"actual": ruls, "predicted_future": rul_future, "timestamps": timestamps}
        }
    except Exception as e:
        logger.error(f"Error in GET /api/history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch history telemetry: {str(e)}")


@app.get("/api/maintenance")
def get_maintenance_status(plc_id: str = "PLC_01"):
    try:
        plc_str, plc_num = normalize_plc_id(plc_id, fallback="PLC_01")
        if not plc_str or not plc_num:
            plc_str, plc_num = "PLC_01", 1
        row = sim_state.get_plc_status(plc_str)
        
        temp = float(row.get("temperature", 62.0))
        vib = float(row.get("vibration", 0.2))
        curr = float(row.get("motor_current", 8.0))
        press = float(row.get("pressure", 5.0))
        noise = float(row.get("noise", 42.0))
        health = float(row.get("machine_health", 100.0))
        predicted_rul = int(row.get("predicted_rul_days", 0))
        machine_status = str(row.get("machine_status", "Healthy"))
        machine_condition = str(row.get("machine_condition", "Healthy"))
        anomaly_status = str(row.get("anomaly_status", "Normal"))
        failure_risk = float(row.get("failure_risk_pct", 0.0))
        is_anom = anomaly_status == "Anomaly Detected"

        # Calculate current total decision dynamically using current config
        decision = generate_total_maintenance_decision(
            plc_id=plc_str,
            plc_id_num=plc_num,
            sensor_readings={
                "temperature": temp,
                "vibration": vib,
                "motor_current": curr,
                "pressure": press,
                "noise": noise
            },
            machine_health=health,
            machine_status=machine_status,
            failure_risk_pct=failure_risk,
            predicted_rul_days=predicted_rul,
            is_anomaly=is_anom,
            config=cost_energy_config
        )
        
        return {
            "plc_id": plc_str,
            "plc_id_num": plc_num,
            "machine_health": round(health, 1),
            "machine_status": machine_status,
            "machine_condition": machine_condition,
            "anomaly_status": anomaly_status,
            "failure_risk_pct": failure_risk,
            "predicted_rul_days": predicted_rul,
            "recommended_action": str(row.get("Recommended_Action", decision["rul_recommendation"]["recommended_deadline_str"])),
            "inspection_priority": decision["priority"],
            "next_inspection_window": decision["rul_recommendation"]["recommended_deadline_str"],
            "timestamp": str(row.get("timestamp", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))),
            "temperature": round(temp, 2),
            "vibration": round(vib, 2),
            "motor_current": round(curr, 2),
            "pressure": round(press, 2),
            "noise": round(noise, 2),

            # Added Cost Optimization & Energy Insights
            "total_decision": decision,
            "energy": decision["energy"],
            "energy_anomaly": decision["energy_anomaly"],
            "cost_optimization": decision["cost_optimization"],
            "concise_alert": decision["concise_alert"],
            "q1_what_is_wrong": decision["q1_what_is_wrong"],
            "q2_when_maintain": decision["q2_when_maintain"],
            "q3_why_now": decision["q3_why_now"],
            "transparency_points": decision["transparency_points"],
            "maintenance_priority": decision["priority"],
            "probable_issue": decision["main_issue"],
            "issue_detail": decision["issue_detail"]
        }
    except Exception as e:
        logger.error(f"Error in GET /api/maintenance: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch maintenance status: {str(e)}")


@app.get("/api/maintenance/optimization")
def get_maintenance_optimization(plc_id: str = "PLC_01"):
    try:
        plc_str, plc_num = normalize_plc_id(plc_id, fallback="PLC_01")
        if not plc_str or not plc_num:
            plc_str, plc_num = "PLC_01", 1

        # Discover all valid PLCs
        known_plcs = set()
        for eng in sim_engines:
            pid = getattr(eng, 'plc_id', 1)
            p_str, _ = normalize_plc_id(pid, fallback=None)
            if p_str:
                known_plcs.add(p_str)
        for k in sim_state.plc_records.keys():
            if is_valid_plc_id(k):
                p_str, _ = normalize_plc_id(k, fallback=None)
                if p_str:
                    known_plcs.add(p_str)
        for i in range(1, 6):
            known_plcs.add(f"PLC_{i:02d}")

        sorted_plcs = sorted([p for p in known_plcs if is_valid_plc_id(p)], key=lambda x: normalize_plc_id(x, fallback=None)[1] or 0)

        table_rows = []
        cost_chart = []
        energy_chart = []

        total_prev_cost_needed = 0.0
        total_fail_cost_all = 0.0
        total_savings_positive = 0.0
        excess_pct_list = []
        total_add_energy_cost = 0.0
        critical_count = 0
        req_maint_count = 0
        rul_sum = 0
        valid_count = 0

        selected_decision = None

        for p_key in sorted_plcs:
            if not is_valid_plc_id(p_key):
                continue
            rec = sim_state.get_plc_status(p_key)
            _, p_num = normalize_plc_id(p_key, fallback=None)
            if not p_num:
                continue

            temp = float(rec.get("temperature", 62.0))
            vib = float(rec.get("vibration", 0.2))
            curr = float(rec.get("motor_current", 8.0))
            press = float(rec.get("pressure", 5.0))
            noise = float(rec.get("noise", 42.0))
            health = float(rec.get("machine_health", 100.0))
            rul = int(rec.get("predicted_rul_days", 200))
            m_status = str(rec.get("machine_status", "Healthy"))
            f_risk = float(rec.get("failure_risk_pct", 0.0))
            is_anom = rec.get("anomaly_status") == "Anomaly Detected"

            decision = generate_total_maintenance_decision(
                plc_id=p_key,
                plc_id_num=p_num,
                sensor_readings={"temperature": temp, "vibration": vib, "motor_current": curr, "pressure": press, "noise": noise},
                machine_health=health,
                machine_status=m_status,
                failure_risk_pct=f_risk,
                predicted_rul_days=rul,
                is_anomaly=is_anom,
                config=cost_energy_config
            )

            if p_key == plc_str:
                selected_decision = decision

            # Table row for Section 11
            p_cost = decision["cost_optimization"]["preventive_cost"]
            f_cost = decision["cost_optimization"]["expected_failure_cost"]
            sav = decision["cost_optimization"]["potential_savings"]
            p_urgency = decision["priority"]
            excess_p = decision["energy"]["excess_pct"]
            add_e_cost = decision["energy"]["additional_energy_cost_day"]

            table_rows.append({
                "plc_id": p_key,
                "plc_id_num": p_num,
                "name": f"{p_key} ({get_plc_desc(p_num)})",
                "machine_health": health,
                "machine_status": m_status,
                "main_issue": decision["main_issue"],
                "predicted_rul_days": rul,
                "rul_time_str": decision["rul_recommendation"]["time_short"],
                "failure_risk_pct": f_risk,
                "energy_status": decision["energy_anomaly"]["energy_status"],
                "energy_status_color": decision["energy_anomaly"]["status_color"],
                "excess_energy_pct": excess_p,
                "current_energy_kwh": decision["energy"]["energy_kwh_day"],
                "baseline_energy_kwh": decision["energy"]["baseline_energy_kwh_day"],
                "preventive_cost": p_cost,
                "expected_failure_cost": f_cost,
                "potential_savings": sav,
                "priority": p_urgency,
                "recommendation": decision["cost_optimization"]["decision"],
                "action": decision["rul_recommendation"]["action_short"],
                "deadline": decision["rul_recommendation"]["recommended_deadline_str"],
                "why_now": decision["q3_why_now"]
            })

            # Cost chart item (Section 14)
            cost_chart.append({
                "plc_id": p_key,
                "preventive_cost": p_cost,
                "expected_failure_cost": f_cost,
                "potential_savings": sav,
                "is_cost_effective": sav > 0
            })

            # Energy chart item (Section 15)
            energy_chart.append({
                "plc_id": p_key,
                "baseline_energy": decision["energy"]["baseline_energy_kwh_day"],
                "current_energy": decision["energy"]["energy_kwh_day"],
                "excess_energy": decision["energy"]["excess_energy_kwh_day"],
                "excess_pct": excess_p,
                "additional_energy_cost_day": add_e_cost
            })

            # Aggregate stats for summary cards (Section 13)
            rul_sum += rul
            valid_count += 1
            total_fail_cost_all += f_cost
            excess_pct_list.append(excess_p)
            total_add_energy_cost += add_e_cost

            if p_urgency == "Critical":
                critical_count += 1
            if p_urgency in ["Critical", "High"] or sav > 0 or health < 75.0:
                req_maint_count += 1
                total_prev_cost_needed += p_cost

            if sav > 0:
                total_savings_positive += sav

        # Sort priority ranking: Critical -> High -> Medium -> Low
        priority_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
        priority_ranking = sorted(table_rows, key=lambda x: (priority_order.get(x["priority"], 4), -x["failure_risk_pct"]))

        summary_cards = {
            "machines_requiring_maintenance": req_maint_count,
            "critical_plcs": critical_count,
            "average_rul": round(rul_sum / max(1, valid_count), 1) if valid_count > 0 else 0,
            "estimated_maintenance_cost": round(total_prev_cost_needed, 0),
            "expected_failure_cost": round(total_fail_cost_all, 0),
            "potential_cost_savings": round(total_savings_positive, 0),
            "energy_inefficiency_pct": round(sum(excess_pct_list) / max(1, len(excess_pct_list)), 1) if excess_pct_list else 0.0,
            "additional_energy_cost_daily": round(total_add_energy_cost, 0),
            "total_plcs": valid_count
        }

        if not selected_decision:
            rec_sel = sim_state.get_plc_status(plc_str)
            selected_decision = generate_total_maintenance_decision(
                plc_id=plc_str,
                plc_id_num=plc_num,
                sensor_readings={
                    "temperature": float(rec_sel.get("temperature", 62.0)),
                    "vibration": float(rec_sel.get("vibration", 0.2)),
                    "motor_current": float(rec_sel.get("motor_current", 8.0)),
                    "pressure": float(rec_sel.get("pressure", 5.0)),
                    "noise": float(rec_sel.get("noise", 42.0))
                },
                machine_health=float(rec_sel.get("machine_health", 100.0)),
                machine_status=str(rec_sel.get("machine_status", "Healthy")),
                failure_risk_pct=float(rec_sel.get("failure_risk_pct", 0.0)),
                predicted_rul_days=int(rec_sel.get("predicted_rul_days", 200)),
                is_anomaly=rec_sel.get("anomaly_status") == "Anomaly Detected",
                config=cost_energy_config
            )

        return {
            "summary_cards": summary_cards,
            "plcs_maintenance_table": table_rows,
            "cost_chart_data": cost_chart,
            "energy_chart_data": energy_chart,
            "priority_ranking": priority_ranking,
            "selected_plc": plc_str,
            "selected_plc_decision": selected_decision,
            "config": cost_energy_config.to_dict()
        }
    except Exception as e:
        logger.error(f"Error in GET /api/maintenance/optimization: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


class MaintenanceConfigRequest(BaseModel):
    labour_cost: Optional[float] = None
    spare_parts_cost: Optional[float] = None
    inspection_cost: Optional[float] = None
    service_cost: Optional[float] = None
    other_expenses: Optional[float] = None
    repair_replacement_cost: Optional[float] = None
    downtime_cost: Optional[float] = None
    production_loss: Optional[float] = None
    emergency_labour_cost: Optional[float] = None
    electricity_rate: Optional[float] = None
    nominal_voltage: Optional[float] = None
    power_factor: Optional[float] = None
    operating_hours_per_day: Optional[float] = None
    rul_critical_days: Optional[float] = None
    rul_urgent_days: Optional[float] = None
    rul_schedule_days: Optional[float] = None
    rul_plan_days: Optional[float] = None


@app.get("/api/maintenance/config")
def get_maintenance_config():
    return cost_energy_config.to_dict()


@app.post("/api/maintenance/config")
def update_maintenance_config(req: MaintenanceConfigRequest):
    try:
        req_dict = req.model_dump() if hasattr(req, 'model_dump') else req.dict()
        data = {k: v for k, v in req_dict.items() if v is not None}
        cost_energy_config.update(data)
        cost_energy_config.save_to_file()
        return {
            "status": "success",
            "message": "Maintenance cost and energy configuration updated successfully",
            "config": cost_energy_config.to_dict()
        }
    except Exception as e:
        logger.error(f"Error updating maintenance config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class AddPlcRequest(BaseModel):
    plc_id: Optional[str] = None
    name: Optional[str] = None
    deg_init: Optional[float] = 0.05
    base_load: Optional[float] = 0.60
    temp_offset: Optional[float] = 0.0
    vib_offset: Optional[float] = 0.0


@app.post("/api/plcs/add")
def add_new_plc(req: AddPlcRequest):
    try:
        # Determine next ID if not provided
        existing_nums = [getattr(eng, 'plc_id', 1) for eng in sim_engines]
        for k in sim_state.plc_records.keys():
            if is_valid_plc_id(k):
                _, n = normalize_plc_id(k, fallback=None)
                if n:
                    existing_nums.append(n)
        
        next_num = max(existing_nums, default=0) + 1
        
        req_id = req.plc_id
        if req_id and is_valid_plc_id(req_id):
            p_str, p_num = normalize_plc_id(req_id, fallback=None)
        else:
            p_str, p_num = f"PLC_{next_num:02d}", next_num
            
        # Check if already in sim_engines
        already_exists = any(getattr(eng, 'plc_id', None) == p_num for eng in sim_engines)
        if already_exists:
            return {"status": "exists", "plc_id": p_str, "plc_id_num": p_num, "message": f"{p_str} is already registered"}
            
        new_eng = RealTimeMachineSimulator(
            plc_id=p_num,
            deg_init=req.deg_init if req.deg_init is not None else 0.05,
            base_load=req.base_load if req.base_load is not None else 0.60,
            temp_offset=req.temp_offset if req.temp_offset is not None else 0.0,
            vib_offset=req.vib_offset if req.vib_offset is not None else 0.0
        )
        sim_engines.append(new_eng)
        
        # Immediately step and process telemetry for the new PLC
        rec = new_eng.step()
        processed = process_mqtt_telemetry(rec)
        
        logger.info(f"Dynamically registered new {p_str} (Total engines: {len(sim_engines)})")
        
        return {
            "status": "success",
            "plc_id": p_str,
            "plc_id_num": p_num,
            "name": f"{p_str} (Added Unit #{p_num})",
            "data": processed
        }
    except Exception as e:
        logger.error(f"Error adding PLC: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))



class PredictRequest(BaseModel):
    temperature: float = Field(..., ge=-50.0, le=250.0, description="Operating temperature in deg C")
    vibration: float = Field(..., ge=0.0, le=50.0, description="Vibration amplitude in mm/s")
    motor_current: float = Field(..., ge=0.0, le=100.0, description="Motor current in Amperes")
    pressure: float = Field(default=5.0, ge=0.0, le=1000.0, description="Pressure reading in bar")
    noise: float = Field(default=42.0, ge=0.0, le=200.0, description="Acoustic noise in dB")
    model: str = Field(default="auto", description="Model selector: 'Random Forest Regressor' or 'auto'")

@app.post("/api/predict")
def predict_rul(req: PredictRequest):
    try:
        rul, model_name, raw_pred, confidence, ci = model_service.predict_rul(
            req.temperature,
            req.vibration,
            req.motor_current,
            pressure=req.pressure,
            noise=req.noise,
            model_name=req.model,
            return_full_info=True
        )
        anomaly_info = model_service.detect_anomaly(
            req.temperature,
            req.vibration,
            req.motor_current,
            pressure=req.pressure,
            noise=req.noise
        )
        return {
            "predicted_rul": rul,
            "model": model_name,
            "raw_prediction": round(raw_pred, 2),
            "confidence_pct": confidence,
            "confidence_interval": ci,
            "anomaly_status": anomaly_info["anomaly_status"],
            "is_anomaly": anomaly_info["is_anomaly"]
        }
    except Exception as e:
        logger.error(f"Error in POST /api/predict: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to calculate RUL prediction: {str(e)}")

@app.get("/api/model")
def get_model_evaluation():
    try:
        comp_data = model_service.get_comparison_data()
        if comp_data:
            return comp_data
        raise HTTPException(status_code=500, detail="Model evaluation metadata not loaded. Please train models first.")
    except Exception as e:
        logger.error(f"Error in GET /api/model: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch model metrics: {str(e)}")


def _clean_domain_name(label: Any) -> str:
    s = str(label or "")
    s = re.sub(r"\s*\(Person\s*\d+[^)]*\)", "", s, flags=re.IGNORECASE).strip()
    low = s.lower()
    if "time" in low:
        return "Time-Domain Analysis"
    if "freq" in low or "fft" in low:
        return "Frequency-Domain Analysis (FFT)"
    if "tsfresh" in low:
        return "TSFresh Feature Engineering"
    return s or "Sensor Domain"


@app.get("/api/ml/metrics")
def get_ml_metrics():
    try:
        metrics_file = os.path.join(base_dir, "models", "classification_metrics.json")
        if os.path.exists(metrics_file):
            with open(metrics_file, "r") as f:
                payload = json.load(f)
            if isinstance(payload, dict):
                if isinstance(payload.get("domain_importance_share_percent"), dict):
                    payload["domain_importance_share_percent"] = {
                        _clean_domain_name(k): v
                        for k, v in payload["domain_importance_share_percent"].items()
                    }
                if isinstance(payload.get("top_10_features"), list):
                    for item in payload["top_10_features"]:
                        if isinstance(item, dict) and "domain" in item:
                            item["domain"] = _clean_domain_name(item["domain"])
            return payload
        raise HTTPException(status_code=404, detail="Classification metrics not found. Run ml_pipeline.py first.")
    except Exception as e:
        logger.error(f"Error in GET /api/ml/metrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/features/summary")
def get_features_summary():
    try:
        time_sum = os.path.join(base_dir, "data", "time_features_summary.csv")
        freq_sum = os.path.join(base_dir, "data", "frequency_features_summary.csv")
        ranked_features = os.path.join(base_dir, "data", "top_features_ranked.csv")
        
        t_data = pd.read_csv(time_sum).head(10).to_dict(orient="records") if os.path.exists(time_sum) else []
        f_data = pd.read_csv(freq_sum).head(10).to_dict(orient="records") if os.path.exists(freq_sum) else []
        r_data = pd.read_csv(ranked_features).head(15).to_dict(orient="records") if os.path.exists(ranked_features) else []
        for item in r_data:
            if isinstance(item, dict) and "domain" in item:
                item["domain"] = _clean_domain_name(item["domain"])
        
        return {
            "top_time_features": t_data,
            "top_frequency_features": f_data,
            "top_overall_features": r_data
        }
    except Exception as e:
        logger.error(f"Error in GET /api/features/summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/logs")
def get_logs(plc_id: str = None):
    try:
        if plc_id is not None and is_valid_plc_id(plc_id):
            plc_str, _ = normalize_plc_id(plc_id, fallback="PLC_01")
            records = sim_state.plc_history_records.get(plc_str, [])
            if not records:
                cur = sim_state.get_plc_status(plc_str)
                records = [cur]
        else:
            records = sim_state.history_records
        recent = records[-10:] if records else []
        logs = []
        for r in recent:
            p_val = r.get("plc_id", "PLC_01")
            if not is_valid_plc_id(p_val):
                continue
            p_str, _ = normalize_plc_id(p_val, fallback=None)
            if not p_str:
                continue

            temp = float(r.get("Motor_Temp", r.get("temperature", 62.0)))
            vib = float(r.get("Vibration_X", r.get("vibration", 0.2)))
            curr = float(r.get("Motor_Current", r.get("motor_current", 8.0)))
            press = float(r.get("Pressure_Inlet", r.get("pressure", 5.0)))
            noise = float(r.get("Noise", r.get("noise", 42.0)))
            health = float(r.get("machine_health", 100.0))
            pred_rul = int(r.get("predicted_rul_days", 0))
            status, _ = get_status_color(health)
            
            logs.append({
                "plc_id": p_str,
                "timestamp": str(r.get("timestamp", "")),
                "temperature": round(temp, 2),
                "vibration": round(vib, 2),
                "motor_current": round(curr, 2),
                "pressure": round(press, 2),
                "noise": round(noise, 2),
                "predicted_rul": pred_rul,
                "machine_health": round(health, 1),
                "machine_condition": r.get("machine_condition", "Healthy"),
                "anomaly_status": r.get("anomaly_status", "Normal"),
                "failure_risk_pct": r.get("failure_risk_pct", 0.0),
                "status": str(r.get("machine_status", status)),
                "active_event": r.get("Active_Event", "None")
            })
            
        return {"logs": logs}
    except Exception as e:
        logger.error(f"Error in GET /api/logs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch recent logs: {str(e)}")


class ControlAction(BaseModel):
    action: str = Field(..., pattern="^(start|pause|next|reset|set_speed)$")
    speed: float = Field(default=1.0, ge=0.05, le=10.0)

@app.post("/api/control")
def control_simulation(action: ControlAction):
    try:
        if action.action == "start":
            sim_state.auto_play = True
            logger.info("POST /api/control: Simulation Started (auto_play = True)")
        elif action.action == "pause":
            sim_state.auto_play = False
            logger.info("POST /api/control: Simulation Paused (auto_play = False)")
        elif action.action == "next":
            rec = generate_next_telemetry_step()
            logger.info(f"POST /api/control: Advanced Next Step")
        elif action.action == "reset":
            sim_state.reset()
            for eng in sim_engines:
                try:
                    eng.reset()
                except Exception:
                    pass
            logger.info("POST /api/control: Simulation Reset")
        elif action.action == "set_speed":
            sim_state.simulation_speed = action.speed
            logger.info(f"POST /api/control: Simulation Speed set to {action.speed}")
                
        return {
            "status": "success",
            "action": action.action,
            "current_idx": max(0, len(sim_state.history_records) - 1),
            "auto_play": sim_state.auto_play,
            "simulation_speed": sim_state.simulation_speed
        }
    except Exception as e:
        logger.error(f"Error in POST /api/control: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to process control action: {str(e)}")

@app.post("/api/simulation/start")
@app.post("/api/start")
def start_simulation():
    return control_simulation(ControlAction(action="start"))

@app.post("/api/simulation/pause")
@app.post("/api/pause")
def pause_simulation():
    return control_simulation(ControlAction(action="pause"))

@app.post("/api/simulation/next")
@app.post("/api/next")
def next_simulation():
    return control_simulation(ControlAction(action="next"))

@app.post("/api/simulation/reset")
@app.post("/api/reset")
def reset_simulation():
    return control_simulation(ControlAction(action="reset"))

@app.get("/api/download/project")
@app.get("/download")
def download_project_archive():
    """Serves the complete project ZIP archive for easy download."""
    zip_path = os.path.join(os.path.dirname(base_dir), "predictive_maintenance_final.zip")
    if not os.path.exists(zip_path):
        # Auto-create if not present
        import zipfile
        exclude_dirs = {'node_modules', '__pycache__', '.git'}
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(base_dir):
                dirs[:] = [d for d in dirs if d not in exclude_dirs]
                for f in files:
                    if f.endswith('.pyc') or f.endswith('.log'):
                        continue
                    full_p = os.path.join(root, f)
                    zipf.write(full_p, os.path.relpath(full_p, base_dir))
    return FileResponse(
        path=zip_path,
        filename="predictive_maintenance_final.zip",
        media_type="application/zip"
    )


# =====================================================================
# DATA DRIFT & MODEL RELIABILITY MONITORING REST ENDPOINTS
# =====================================================================

@app.get("/api/drift/status")
@app.get("/api/drift/summary")
def get_drift_summary(plc_id: str = "PLC_01"):
    """
    Returns high-level reliability assessment: overall health, data drift,
    prediction drift, data quality, PSI scores, and recommendations.
    """
    try:
        plc_str, _ = normalize_plc_id(plc_id, fallback="PLC_01")
        plc_target = plc_str or "PLC_01"
        eval_res = drift_service.get_latest_evaluation(plc_target)
        return eval_res
    except Exception as e:
        logger.error(f"Error in GET /api/drift/summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch drift summary: {str(e)}")


@app.get("/api/drift/features")
def get_drift_features(plc_id: str = "PLC_01"):
    """Returns detailed per-feature statistical drift metrics (PSI, KS-Test, Wasserstein)."""
    try:
        plc_str, _ = normalize_plc_id(plc_id, fallback="PLC_01")
        plc_target = plc_str or "PLC_01"
        eval_res = drift_service.get_latest_evaluation(plc_target)
        return {
            "plc_id": plc_target,
            "timestamp": eval_res.get("timestamp"),
            "data_drift_status": eval_res.get("data_drift_status"),
            "overall_drift_score": eval_res.get("overall_drift_score"),
            "features": eval_res.get("features", [])
        }
    except Exception as e:
        logger.error(f"Error in GET /api/drift/features: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch feature drift: {str(e)}")


@app.get("/api/drift/predictions")
def get_drift_predictions(plc_id: str = "PLC_01"):
    """Returns model output prediction drift (RUL distribution & anomaly rate divergence)."""
    try:
        plc_str, _ = normalize_plc_id(plc_id, fallback="PLC_01")
        plc_target = plc_str or "PLC_01"
        eval_res = drift_service.get_latest_evaluation(plc_target)
        return {
            "plc_id": plc_target,
            "timestamp": eval_res.get("timestamp"),
            "prediction_drift_status": eval_res.get("prediction_drift_status"),
            "rul_psi": eval_res.get("rul_psi"),
            "predictions": eval_res.get("predictions", [])
        }
    except Exception as e:
        logger.error(f"Error in GET /api/drift/predictions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch prediction drift: {str(e)}")


@app.get("/api/drift/data-quality")
def get_drift_data_quality(plc_id: str = "PLC_01"):
    """Returns data quality diagnostics (missingness %, stuck sensors, physical bounds)."""
    try:
        plc_str, _ = normalize_plc_id(plc_id, fallback="PLC_01")
        plc_target = plc_str or "PLC_01"
        eval_res = drift_service.get_latest_evaluation(plc_target)
        return {
            "plc_id": plc_target,
            "timestamp": eval_res.get("timestamp"),
            "data_quality_status": eval_res.get("data_quality_status"),
            "missing_pct_overall": eval_res.get("missing_pct_overall"),
            "stuck_sensors_count": eval_res.get("stuck_sensors_count"),
            "out_of_bounds_count": eval_res.get("out_of_bounds_count"),
            "data_quality": eval_res.get("data_quality", [])
        }
    except Exception as e:
        logger.error(f"Error in GET /api/drift/data-quality: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch data quality: {str(e)}")


@app.get("/api/drift/history")
def get_drift_history(plc_id: str = "PLC_01", limit: int = 40):
    """Returns chronological timeline of historical drift evaluations for charts."""
    try:
        plc_str, _ = normalize_plc_id(plc_id, fallback="PLC_01")
        plc_target = plc_str or "PLC_01"
        history = drift_db.get_run_history(plc_target, limit=limit)
        return {
            "plc_id": plc_target,
            "count": len(history),
            "history": history
        }
    except Exception as e:
        logger.error(f"Error in GET /api/drift/history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch drift history: {str(e)}")


@app.get("/api/drift/alerts")
def get_drift_alerts(plc_id: str = None, limit: int = 30):
    """Returns recent drift and data quality operational alerts."""
    try:
        plc_filter = None
        if plc_id and plc_id.upper() != "ALL":
            plc_str, _ = normalize_plc_id(plc_id, fallback=None)
            plc_filter = plc_str
        alerts = drift_db.get_recent_alerts(plc_id=plc_filter, limit=limit)
        return {"alerts": alerts, "total": len(alerts)}
    except Exception as e:
        logger.error(f"Error in GET /api/drift/alerts: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch drift alerts: {str(e)}")


@app.get("/api/drift/baseline")
def get_drift_baseline():
    """Returns active reference baseline metadata, distribution percentiles, and sample sizes."""
    try:
        return baseline_mgr.get_baseline()
    except Exception as e:
        logger.error(f"Error in GET /api/drift/baseline: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch baseline info: {str(e)}")


@app.post("/api/drift/baseline/rebuild")
def rebuild_drift_baseline():
    """Intentional administrative endpoint to recalculate reference baseline from historical data."""
    try:
        new_baseline = baseline_mgr.build_baseline_from_data()
        return {
            "status": "success",
            "message": "Reference baseline recomputed and saved.",
            "baseline_id": new_baseline.get("baseline_id"),
            "sample_count": new_baseline.get("sample_count")
        }
    except Exception as e:
        logger.error(f"Error in POST /api/drift/baseline/rebuild: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to rebuild baseline: {str(e)}")


class SimulateDriftRequest(BaseModel):
    plc_id: str = Field(default="PLC_01", description="Target PLC identifier")
    mode: str = Field(..., description="Demo mode: normal, mild_vibration_drift, severe_thermal_drift, stuck_sensor, missing_data, prediction_drift, reset")

@app.post("/api/drift/simulate-drift")
def simulate_drift_event(req: SimulateDriftRequest):
    """
    Controlled Demonstration Sandbox Endpoint.
    Introduces controlled distribution changes for review and evaluation without corrupting reference baseline.
    """
    try:
        plc_str, _ = normalize_plc_id(req.plc_id, fallback="PLC_01")
        plc_target = plc_str or "PLC_01"
        result = drift_service.set_demonstration_mode(plc_target, req.mode)
        return result
    except Exception as e:
        logger.error(f"Error in POST /api/drift/simulate-drift: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to trigger demonstration drift: {str(e)}")


@app.post("/api/drift/check")
def trigger_immediate_drift_check(plc_id: str = "PLC_01"):
    """Triggers an immediate evaluation of the current telemetry window for a PLC."""
    try:
        plc_str, _ = normalize_plc_id(plc_id, fallback="PLC_01")
        plc_target = plc_str or "PLC_01"
        eval_res = drift_service.evaluate_plc(plc_target)
        return eval_res
    except Exception as e:
        logger.error(f"Error in POST /api/drift/check: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to run drift check: {str(e)}")


# =====================================================================
# ASSET DIGITAL THREAD REST API ENDPOINTS
# =====================================================================

@app.get("/api/assets")
def get_assets():
    """Returns list of all industrial assets in the Digital Thread."""
    try:
        assets = dt_db.get_all_assets()
        return {"assets": assets, "total": len(assets)}
    except Exception as e:
        logger.error(f"Error in GET /api/assets: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch assets: {str(e)}")


@app.get("/api/assets/{asset_id}")
def get_asset_details(asset_id: str):
    """Returns comprehensive asset identity, topology, components, and current status."""
    try:
        asset = dt_db.get_asset_by_id(asset_id)
        if not asset:
            raise HTTPException(status_code=404, detail=f"Asset '{asset_id}' not found.")
        return asset
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in GET /api/assets/{asset_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch asset details: {str(e)}")


@app.get("/api/assets/{asset_id}/components")
def get_asset_components_endpoint(asset_id: str):
    """Returns physical component hierarchy and assigned sensor tags for an asset."""
    try:
        asset = dt_db.get_asset_by_id(asset_id)
        if not asset:
            raise HTTPException(status_code=404, detail=f"Asset '{asset_id}' not found.")
        comps = dt_db.get_asset_components(asset["asset_id"])
        return {"asset_id": asset["asset_id"], "components": comps}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in GET /api/assets/{asset_id}/components: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch components: {str(e)}")


@app.get("/api/assets/{asset_id}/sensors")
def get_asset_sensors_endpoint(asset_id: str):
    """Returns all sensors associated with an asset."""
    try:
        asset = dt_db.get_asset_by_id(asset_id)
        if not asset:
            raise HTTPException(status_code=404, detail=f"Asset '{asset_id}' not found.")
        sensors = dt_db.get_asset_sensors(asset["asset_id"])
        return {"asset_id": asset["asset_id"], "sensors": sensors}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in GET /api/assets/{asset_id}/sensors: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch sensors: {str(e)}")


@app.get("/api/assets/{asset_id}/health")
def get_asset_health_snapshot_endpoint(asset_id: str):
    """
    Returns complete live health snapshot connecting telemetry, ML models,
    Isolation Forest anomaly status, RUL predictions, drift status, and maintenance.
    """
    try:
        # Resolve corresponding PLC status
        asset = dt_db.get_asset_by_id(asset_id)
        if not asset:
            raise HTTPException(status_code=404, detail=f"Asset '{asset_id}' not found.")
        
        plc_str = asset["plc_id"]
        live_record = sim_state.get_plc_status(plc_str)
        
        snapshot = digital_thread_service.get_asset_health_snapshot(
            asset_id_or_plc=asset["asset_id"],
            live_telemetry_dict=live_record,
            drift_service_ref=drift_service
        )
        return snapshot
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in GET /api/assets/{asset_id}/health: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch asset health snapshot: {str(e)}")


@app.get("/api/assets/{asset_id}/timeline")
def get_asset_timeline_endpoint(asset_id: str, event_type: str = None, severity: str = None, limit: int = 100):
    """
    Returns the chronological lifecycle event timeline for an asset.
    Supports filtering by event_type (TELEMETRY, PREDICTION, ANOMALY, DRIFT, MAINTENANCE, ALERT).
    """
    try:
        asset = dt_db.get_asset_by_id(asset_id)
        if not asset:
            raise HTTPException(status_code=404, detail=f"Asset '{asset_id}' not found.")
        
        events = dt_db.get_asset_timeline(
            asset_id_or_plc=asset["asset_id"],
            event_type=event_type,
            severity=severity,
            limit=limit
        )
        return {
            "asset_id": asset["asset_id"],
            "plc_id": asset["plc_id"],
            "total_events": len(events),
            "events": events
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in GET /api/assets/{asset_id}/timeline: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch timeline: {str(e)}")


@app.get("/api/assets/{asset_id}/maintenance")
def get_asset_maintenance_endpoint(asset_id: str):
    """Returns full maintenance history and closed-loop outcome records for an asset."""
    try:
        asset = dt_db.get_asset_by_id(asset_id)
        if not asset:
            raise HTTPException(status_code=404, detail=f"Asset '{asset_id}' not found.")
        
        records = dt_db.get_asset_maintenance_history(asset["asset_id"])
        return {
            "asset_id": asset["asset_id"],
            "total_records": len(records),
            "maintenance_records": records
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in GET /api/assets/{asset_id}/maintenance: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch maintenance history: {str(e)}")


class MaintenanceCreateRequest(BaseModel):
    maintenance_type: str = Field(..., description="e.g. Preventive Lubrication, Bearing Replacement, Inspection")
    reason: str = Field(..., description="Reason for maintenance trigger")
    triggered_by: str = Field(default="Predictive Maintenance Engine")
    technician: Optional[str] = Field(default="Assigned Reliability Specialist")
    finding: Optional[str] = Field(default=None)
    action_performed: Optional[str] = Field(default=None)
    parts_replaced: Optional[str] = Field(default=None)
    downtime_hours: float = Field(default=0.0)
    cost: float = Field(default=0.0)
    before_health: Optional[float] = Field(default=None)
    after_health: Optional[float] = Field(default=None)
    before_rul: Optional[int] = Field(default=None)
    after_rul: Optional[int] = Field(default=None)
    notes: Optional[str] = Field(default=None)
    status: str = Field(default="COMPLETED")
    parts: Optional[List[Dict[str, Any]]] = Field(default=[])


@app.post("/api/assets/{asset_id}/maintenance")
def create_maintenance_record_endpoint(asset_id: str, req: MaintenanceCreateRequest):
    """Logs a new maintenance action and links it to the asset's digital thread."""
    try:
        asset = dt_db.get_asset_by_id(asset_id)
        if not asset:
            raise HTTPException(status_code=404, detail=f"Asset '{asset_id}' not found.")
        
        data_dict = req.model_dump() if hasattr(req, "model_dump") else req.dict()
        created = dt_db.record_maintenance(asset["asset_id"], data_dict)
        return created
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in POST /api/assets/{asset_id}/maintenance: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create maintenance record: {str(e)}")


class MaintenanceOutcomeRequest(BaseModel):
    after_health: float = Field(..., ge=0.0, le=100.0, description="Measured post-maintenance health %")
    after_rul: int = Field(..., ge=1, le=500, description="Updated RUL estimate post-maintenance in days")
    notes: Optional[str] = Field(default="Post-maintenance outcome verified.")
    status: str = Field(default="COMPLETED")


@app.post("/api/assets/{asset_id}/maintenance/{maintenance_id}/outcome")
def record_maintenance_outcome_endpoint(asset_id: str, maintenance_id: str, req: MaintenanceOutcomeRequest):
    """
    Records closed-loop post-maintenance feedback:
    Updates before vs after health and RUL, verifying repair effectiveness.
    """
    try:
        asset = dt_db.get_asset_by_id(asset_id)
        if not asset:
            raise HTTPException(status_code=404, detail=f"Asset '{asset_id}' not found.")
        
        data_dict = req.model_dump() if hasattr(req, "model_dump") else req.dict()
        updated = dt_db.record_maintenance_outcome(asset["asset_id"], maintenance_id, data_dict)
        return updated
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in POST /api/assets/{asset_id}/maintenance/{maintenance_id}/outcome: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to record maintenance outcome: {str(e)}")


# =====================================================================
# SENSOR RELIABILITY, DATA QUALITY & HEALTH INDEX API
# =====================================================================

@app.get("/api/sensor-reliability", summary="Sensor Reliability & Data Quality Diagnostics")
def get_sensor_reliability_endpoint(plc_id: str = Query("PLC_01", description="PLC identifier")):
    """
    Returns real-time per-sensor reliability ratings, measurable data-quality scores,
    missing/stale/repeated/spike/out-of-range flags, explanation of why any sensor is flagged,
    sensor fault vs. machine degradation distinction, and raw vs. validated readings.
    """
    try:
        p_str, _ = normalize_plc_id(plc_id, fallback="PLC_01")
        p_str = p_str or "PLC_01"
        live_telemetry = sim_state.get_plc_status(p_str)
        history = sim_state.plc_history_records.get(p_str, [])
        data = digital_thread_service.get_sensor_reliability(p_str, live_telemetry, history)
        return data
    except Exception as e:
        logger.error(f"Error in GET /api/sensor-reliability: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch sensor reliability diagnostics: {str(e)}")


@app.get("/api/health-index", summary="Composite Machine & Subsystem Health Index")
def get_health_index_endpoint(plc_id: str = Query("PLC_01", description="PLC identifier")):
    """
    Returns composite machine health index, multi-subsystem wear percentages,
    degradation velocity, and historical vs projected health index trajectory.
    """
    try:
        p_str, _ = normalize_plc_id(plc_id, fallback="PLC_01")
        p_str = p_str or "PLC_01"
        live_telemetry = sim_state.get_plc_status(p_str)
        data = digital_thread_service.get_health_index_breakdown(p_str, live_telemetry)
        return data
    except Exception as e:
        logger.error(f"Error in GET /api/health-index: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch health index breakdown: {str(e)}")







@app.get("/favicon.ico", include_in_schema=False)
@app.get("/favicon.svg", include_in_schema=False)
def get_favicon():
    fav_svg = os.path.join(frontend_dist, "favicon.svg")
    if os.path.exists(fav_svg):
        return FileResponse(fav_svg, media_type="image/svg+xml")
    fav_ico = os.path.join(frontend_dist, "favicon.ico")
    if os.path.exists(fav_ico):
        return FileResponse(fav_ico, media_type="image/x-icon")
    return Response(status_code=204)

@app.get("/icons.svg", include_in_schema=False)
def get_icons():
    icons_path = os.path.join(frontend_dist, "icons.svg")
    if os.path.exists(icons_path):
        return FileResponse(icons_path, media_type="image/svg+xml")
    return Response(status_code=404)

@app.get("/{full_path:path}", include_in_schema=False)
def serve_spa(full_path: str):
    safe_path = os.path.normpath(os.path.join(frontend_dist, full_path))
    if safe_path.startswith(frontend_dist) and os.path.isfile(safe_path):
        return FileResponse(safe_path)
    index_file = os.path.join(frontend_dist, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return JSONResponse(
        status_code=404,
        content={"detail": "Frontend build not found. Run 'npm run build' in the frontend directory."}
    )

if __name__ == "__main__":
    reload_flag = os.getenv("UVICORN_RELOAD", "false").lower() in ("true", "1", "yes")
    ssl_cert = "cert.pem" if os.path.exists("cert.pem") else None
    ssl_key = "key.pem" if os.path.exists("key.pem") else None
    
    print("\n=======================================================")
    print("  SCADA PREDICTIVE MAINTENANCE DASHBOARD")
    print("  -> Direct HTTP Link : http://127.0.0.1:8000")
    if ssl_cert and ssl_key:
        print("  -> Secure HTTPS Link: https://127.0.0.1:8443")
    print("=======================================================\n")
    
    if ssl_cert and ssl_key:
        def start_https():
            try:
                uvicorn.run("main:app", host="127.0.0.1", port=8443, ssl_keyfile=ssl_key, ssl_certfile=ssl_cert, log_level="warning")
            except Exception as e:
                logger.error(f"HTTPS server error: {e}")
        t = threading.Thread(target=start_https, daemon=True)
        t.start()
        
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=reload_flag, timeout_keep_alive=65)