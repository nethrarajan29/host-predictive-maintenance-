"""
Drift Monitoring Configuration
------------------------------
Defines configurable statistical thresholds, window sizes, and alert policies.
Avoids hardcoded magic numbers across the drift monitoring subsystem.
"""

import os
from dataclasses import dataclass, field
from typing import Dict, Tuple

@dataclass
class DriftConfig:
    # Storage & Persistence
    DB_URL: str = os.getenv("DRIFT_DATABASE_URL", "sqlite:///./data/drift_monitoring.db")
    BASELINE_FILE_PATH: str = os.getenv("DRIFT_BASELINE_PATH", "data/drift_baseline.json")
    HISTORICAL_SENSOR_DATA: str = os.getenv("SENSOR_DATA_PATH", "data/sensor_data.csv")
    
    # Telemetry Windowing
    MONITORING_WINDOW_SIZE: int = int(os.getenv("DRIFT_WINDOW_SIZE", "50"))
    MIN_SAMPLES_FOR_EVALUATION: int = int(os.getenv("DRIFT_MIN_SAMPLES", "20"))
    CHECK_INTERVAL_STEPS: int = int(os.getenv("DRIFT_CHECK_INTERVAL", "10"))
    
    # Statistical Data Drift Thresholds (PSI - Population Stability Index)
    # PSI < 0.10: No significant distribution change (NORMAL)
    # 0.10 <= PSI < 0.25: Moderate distribution change (WARNING)
    # PSI >= 0.25: Significant distribution change (CRITICAL)
    PSI_WARNING_THRESHOLD: float = 0.10
    PSI_CRITICAL_THRESHOLD: float = 0.25
    
    # KS-Test Alpha Significance Level (p-value < alpha indicates drift)
    KS_PVALUE_THRESHOLD: float = 0.05
    
    # Prediction Drift Thresholds
    PREDICTION_RUL_PSI_WARNING: float = 0.12
    PREDICTION_RUL_PSI_CRITICAL: float = 0.25
    ANOMALY_RATE_SHIFT_WARNING: float = 0.20  # 20% absolute delta in anomaly percentage
    ANOMALY_RATE_SHIFT_CRITICAL: float = 0.40
    
    # Data Quality Thresholds
    MISSING_DATA_WARNING_PCT: float = 2.0     # > 2% missing values in window
    MISSING_DATA_CRITICAL_PCT: float = 10.0   # > 10% missing values
    STUCK_SENSOR_STD_THRESHOLD: float = 0.001 # Standard deviation below this indicates frozen/stuck sensor
    STUCK_SENSOR_MIN_POINTS: int = 15         # Number of consecutive constant readings
    
    # Physical Sensor Plausibility Bounds (Domain Constraints)
    # Readings outside these physical limits indicate hardware/transducer failure
    SENSOR_BOUNDS: Dict[str, Tuple[float, float]] = field(default_factory=lambda: {
        "Temperature": (-20.0, 150.0),    # deg C
        "Motor_Temp": (-20.0, 150.0),
        "Vibration": (0.0, 50.0),         # mm/s or g
        "Vibration_X": (0.0, 50.0),
        "Motor_Current": (0.0, 100.0),    # Amperes
        "Pressure": (0.0, 100.0),         # bar
        "Pressure_Inlet": (0.0, 100.0),
        "Noise": (20.0, 150.0)            # dB
    })
    
    # Alert Cooldown & Suppression (Avoid alert spam)
    ALERT_COOLDOWN_SECONDS: int = 60
    MAX_HISTORY_RUNS_RETAINED: int = 500

config = DriftConfig()
