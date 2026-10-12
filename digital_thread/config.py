"""
Asset Digital Thread Configuration
----------------------------------
Defines default assets, component hierarchies, sensor mappings, and event types
for the PredictX Asset Digital Thread subsystem.
"""

import os
from typing import Dict, List, Any

class DigitalThreadConfig:
    """Configuration and taxonomy definitions for Asset Digital Thread."""
    
    DB_PATH = os.getenv("DIGITAL_THREAD_DB_PATH", os.path.join("data", "digital_thread.db"))
    
    # Pre-seeded Industrial Assets mapped to PLCs
    DEFAULT_ASSETS: List[Dict[str, Any]] = [
        {
            "asset_id": "COMP-001",
            "asset_name": "Turbine Motor Unit A1",
            "asset_type": "Centrifugal Gas Compressor",
            "plc_id": "PLC_01",
            "location": "Bay 1 - High Pressure Train",
            "manufacturer": "Siemens Energy",
            "model": "STC-SV (08-7)",
            "install_date": "2023-03-15",
            "status": "RUNNING",
            "health": 98.5,
            "rul_days": 245,
            "components": [
                {
                    "component_id": "COMP-001-MOT",
                    "component_name": "Electric Motor Drive",
                    "component_type": "Induction Motor 75kW",
                    "health": 99.0,
                    "criticality": "HIGH",
                    "sensors": [
                        {"sensor_id": "SENS-001-T101", "tag_name": "Motor_Temp", "sensor_type": "RTD PT100", "unit": "°C", "min_val": 20.0, "max_val": 120.0},
                        {"sensor_id": "SENS-001-T103", "tag_name": "Motor_Current", "sensor_type": "Hall Current CT", "unit": "A", "min_val": 0.0, "max_val": 50.0}
                    ]
                },
                {
                    "component_id": "COMP-001-BRG",
                    "component_name": "Drive-End Bearing Assembly",
                    "component_type": "SKF Roller Bearing 22218",
                    "health": 98.0,
                    "criticality": "CRITICAL",
                    "sensors": [
                        {"sensor_id": "SENS-001-T102", "tag_name": "Vibration_X", "sensor_type": "IEPE Accelerometer", "unit": "mm/s", "min_val": 0.0, "max_val": 10.0},
                        {"sensor_id": "SENS-001-T105", "tag_name": "Noise", "sensor_type": "Acoustic Transducer", "unit": "dB", "min_val": 30.0, "max_val": 110.0}
                    ]
                },
                {
                    "component_id": "COMP-001-INL",
                    "component_name": "Inlet Compression Stage",
                    "component_type": "Centrifugal Impeller",
                    "health": 99.5,
                    "criticality": "MEDIUM",
                    "sensors": [
                        {"sensor_id": "SENS-001-T104", "tag_name": "Pressure_Inlet", "sensor_type": "Piezoresistive Transmitter", "unit": "bar", "min_val": 0.0, "max_val": 25.0}
                    ]
                }
            ]
        },
        {
            "asset_id": "COMP-002",
            "asset_name": "Heavy Duty Booster B2",
            "asset_type": "High Operating Load Compressor",
            "plc_id": "PLC_02",
            "location": "Bay 2 - Booster Station",
            "manufacturer": "Atlas Copco",
            "model": "ZH 1000-4",
            "install_date": "2022-08-10",
            "status": "RUNNING",
            "health": 88.0,
            "rul_days": 180,
            "components": [
                {
                    "component_id": "COMP-002-MOT",
                    "component_name": "Booster Motor 90kW",
                    "component_type": "Three-Phase Induction Motor",
                    "health": 89.0,
                    "criticality": "HIGH",
                    "sensors": [
                        {"sensor_id": "SENS-002-T101", "tag_name": "Motor_Temp", "sensor_type": "RTD PT100", "unit": "°C", "min_val": 20.0, "max_val": 120.0},
                        {"sensor_id": "SENS-002-T103", "tag_name": "Motor_Current", "sensor_type": "Hall Current CT", "unit": "A", "min_val": 0.0, "max_val": 60.0}
                    ]
                },
                {
                    "component_id": "COMP-002-BRG",
                    "component_name": "Thrust Bearing Assembly",
                    "component_type": "Hydrodynamic Tilting-Pad",
                    "health": 86.5,
                    "criticality": "CRITICAL",
                    "sensors": [
                        {"sensor_id": "SENS-002-T102", "tag_name": "Vibration_X", "sensor_type": "IEPE Accelerometer", "unit": "mm/s", "min_val": 0.0, "max_val": 12.0},
                        {"sensor_id": "SENS-002-T105", "tag_name": "Noise", "sensor_type": "Acoustic Transducer", "unit": "dB", "min_val": 30.0, "max_val": 110.0}
                    ]
                },
                {
                    "component_id": "COMP-002-INL",
                    "component_name": "Multi-Stage Vane Guide",
                    "component_type": "Variable Inlet Guide Vanes",
                    "health": 91.0,
                    "criticality": "MEDIUM",
                    "sensors": [
                        {"sensor_id": "SENS-002-T104", "tag_name": "Pressure_Inlet", "sensor_type": "Piezoresistive Transmitter", "unit": "bar", "min_val": 0.0, "max_val": 30.0}
                    ]
                }
            ]
        },
        {
            "asset_id": "COMP-003",
            "asset_name": "Feedwater Pumping System P3",
            "asset_type": "Centrifugal Slurry Pump",
            "plc_id": "PLC_03",
            "location": "Bay 3 - Utility Core",
            "manufacturer": "Sulzer",
            "model": "CP-400X",
            "install_date": "2021-11-20",
            "status": "WARNING",
            "health": 72.0,
            "rul_days": 85,
            "components": [
                {
                    "component_id": "COMP-003-MOT",
                    "component_name": "Stator & Winding Core",
                    "component_type": "Heavy Duty Stator",
                    "health": 80.0,
                    "criticality": "HIGH",
                    "sensors": [
                        {"sensor_id": "SENS-003-T101", "tag_name": "Motor_Temp", "sensor_type": "Thermocouple Type K", "unit": "°C", "min_val": 20.0, "max_val": 130.0},
                        {"sensor_id": "SENS-003-T103", "tag_name": "Motor_Current", "sensor_type": "Hall Current CT", "unit": "A", "min_val": 0.0, "max_val": 50.0}
                    ]
                },
                {
                    "component_id": "COMP-003-BRG",
                    "component_name": "Deep-Groove Ball Bearings",
                    "component_type": "NSK Angular Contact 7314",
                    "health": 65.0,
                    "criticality": "CRITICAL",
                    "sensors": [
                        {"sensor_id": "SENS-003-T102", "tag_name": "Vibration_X", "sensor_type": "IEPE Accelerometer", "unit": "mm/s", "min_val": 0.0, "max_val": 15.0},
                        {"sensor_id": "SENS-003-T105", "tag_name": "Noise", "sensor_type": "Acoustic Transducer", "unit": "dB", "min_val": 30.0, "max_val": 115.0}
                    ]
                },
                {
                    "component_id": "COMP-003-INL",
                    "component_name": "Suction Suction Volute",
                    "component_type": "Cast Iron Volute Casing",
                    "health": 78.0,
                    "criticality": "MEDIUM",
                    "sensors": [
                        {"sensor_id": "SENS-003-T104", "tag_name": "Pressure_Inlet", "sensor_type": "Pressure Transducer", "unit": "bar", "min_val": 0.0, "max_val": 20.0}
                    ]
                }
            ]
        },
        {
            "asset_id": "COMP-004",
            "asset_name": "Thermal Gas Turbine T4",
            "asset_type": "Combustion Gas Turbine",
            "plc_id": "PLC_04",
            "location": "Bay 4 - Power Island",
            "manufacturer": "GE Power",
            "model": "LM2500+",
            "install_date": "2020-05-18",
            "status": "RUNNING",
            "health": 94.0,
            "rul_days": 210,
            "components": [
                {
                    "component_id": "COMP-004-MOT",
                    "component_name": "Gas Generator Rotor",
                    "component_type": "High Pressure Rotor Shaft",
                    "health": 93.0,
                    "criticality": "CRITICAL",
                    "sensors": [
                        {"sensor_id": "SENS-004-T101", "tag_name": "Motor_Temp", "sensor_type": "High Temp RTD", "unit": "°C", "min_val": 20.0, "max_val": 150.0},
                        {"sensor_id": "SENS-004-T103", "tag_name": "Motor_Current", "sensor_type": "Current Transducer", "unit": "A", "min_val": 0.0, "max_val": 70.0}
                    ]
                },
                {
                    "component_id": "COMP-004-BRG",
                    "component_name": "Journal Bearing 1 & 2",
                    "component_type": "Sleeve Bearing Babbitt",
                    "health": 94.5,
                    "criticality": "HIGH",
                    "sensors": [
                        {"sensor_id": "SENS-004-T102", "tag_name": "Vibration_X", "sensor_type": "Proximity Probe Vib", "unit": "mm/s", "min_val": 0.0, "max_val": 10.0},
                        {"sensor_id": "SENS-004-T105", "tag_name": "Noise", "sensor_type": "Acoustic Transducer", "unit": "dB", "min_val": 30.0, "max_val": 120.0}
                    ]
                },
                {
                    "component_id": "COMP-004-INL",
                    "component_name": "Combustor Liner & Nozzles",
                    "component_type": "Dry Low Emission Combustor",
                    "health": 95.0,
                    "criticality": "MEDIUM",
                    "sensors": [
                        {"sensor_id": "SENS-004-T104", "tag_name": "Pressure_Inlet", "sensor_type": "Static Pressure Sensor", "unit": "bar", "min_val": 0.0, "max_val": 35.0}
                    ]
                }
            ]
        },
        {
            "asset_id": "COMP-005",
            "asset_name": "Multi-Stage Screw Compressor C5",
            "asset_type": "Rotary Screw Compressor",
            "plc_id": "PLC_05",
            "location": "Bay 5 - Air Separation Unit",
            "manufacturer": "Ingersoll Rand",
            "model": "Nirvana 160",
            "install_date": "2024-01-12",
            "status": "CRITICAL",
            "health": 48.0,
            "rul_days": 28,
            "components": [
                {
                    "component_id": "COMP-005-MOT",
                    "component_name": "Permanent Magnet Motor",
                    "component_type": "Synchronous VFD Motor",
                    "health": 55.0,
                    "criticality": "HIGH",
                    "sensors": [
                        {"sensor_id": "SENS-005-T101", "tag_name": "Motor_Temp", "sensor_type": "RTD PT100", "unit": "°C", "min_val": 20.0, "max_val": 130.0},
                        {"sensor_id": "SENS-005-T103", "tag_name": "Motor_Current", "sensor_type": "Hall Current CT", "unit": "A", "min_val": 0.0, "max_val": 60.0}
                    ]
                },
                {
                    "component_id": "COMP-005-BRG",
                    "component_name": "Rotor Bearings & Gears",
                    "component_type": "Tapered Roller Bearings",
                    "health": 42.0,
                    "criticality": "CRITICAL",
                    "sensors": [
                        {"sensor_id": "SENS-005-T102", "tag_name": "Vibration_X", "sensor_type": "Triaxial Accelerometer", "unit": "mm/s", "min_val": 0.0, "max_val": 15.0},
                        {"sensor_id": "SENS-005-T105", "tag_name": "Noise", "sensor_type": "Acoustic Microphone", "unit": "dB", "min_val": 30.0, "max_val": 115.0}
                    ]
                },
                {
                    "component_id": "COMP-005-INL",
                    "component_name": "Screw Airend Element",
                    "component_type": "Twin Helical Screws",
                    "health": 50.0,
                    "criticality": "CRITICAL",
                    "sensors": [
                        {"sensor_id": "SENS-005-T104", "tag_name": "Pressure_Inlet", "sensor_type": "Pressure Transducer", "unit": "bar", "min_val": 0.0, "max_val": 20.0}
                    ]
                }
            ]
        }
    ]

    # Map PLC IDs to Asset IDs
    PLC_TO_ASSET_MAP = {
        "PLC_01": "COMP-001",
        "PLC_02": "COMP-002",
        "PLC_03": "COMP-003",
        "PLC_04": "COMP-004",
        "PLC_05": "COMP-005"
    }
    
    ASSET_TO_PLC_MAP = {v: k for k, v in PLC_TO_ASSET_MAP.items()}

config = DigitalThreadConfig()
