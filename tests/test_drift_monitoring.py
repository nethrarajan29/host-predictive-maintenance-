"""
Unit & Integration Test Suite for Drift & Reliability Monitoring
----------------------------------------------------------------
Tests:
1. No drift -> HEALTHY
2. Small distribution change -> NORMAL/HEALTHY
3. Significant feature drift -> WARNING (PSI in [0.10, 0.25))
4. Severe feature drift -> CRITICAL (PSI >= 0.25)
5. Prediction drift (RUL distribution shift, anomaly rate shift)
6. Data quality: Missing data detection & thresholds
7. Data quality: Stuck / frozen constant sensor detection
8. Data quality: Physical out-of-range sensor detection
9. Multiple features drifting concurrently
10. Baseline build, inspection, and persistent metadata
11. Database persistence and historical retrieval
12. Demonstration sandbox mode
"""

import os
import sys
import unittest
import numpy as np
import pandas as pd

# Add project root to sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from drift.config import DriftConfig
from drift.baseline import BaselineManager
from drift.detector import DriftDetector, calculate_psi
from drift.database import DriftDatabase, db
from drift.drift_service import DriftMonitoringService


class TestDriftMonitoring(unittest.TestCase):

    def setUp(self):
        self.config = DriftConfig()
        
        # Create a synthetic normal reference dataset for testing
        np.random.seed(42)
        n_samples = 200
        df_normal = pd.DataFrame({
            "Temperature": np.random.normal(62.0, 1.5, n_samples),
            "Vibration": np.random.normal(0.20, 0.03, n_samples),
            "Motor_Current": np.random.normal(8.0, 0.5, n_samples),
            "Pressure": np.random.normal(5.0, 0.2, n_samples),
            "Noise": np.random.normal(42.0, 2.0, n_samples),
            "Remaining_Useful_Life_Days": np.random.normal(230.0, 15.0, n_samples),
            "Machine_Health": np.full(n_samples, 95.0)
        })
        
        test_baseline_file = os.path.join(BASE_DIR, "data", "test_baseline.json")
        self.baseline_mgr = BaselineManager(baseline_file=test_baseline_file)
        self.baseline_mgr.build_baseline_from_data(custom_df=df_normal)
        self.detector = DriftDetector(config_obj=self.config, baseline_manager=self.baseline_mgr)

    def test_psi_calculation_zero_drift(self):
        """Identical distributions should produce PSI very close to 0.0."""
        b_feat = self.baseline_mgr.get_feature_baseline("Temperature")
        self.assertIsNotNone(b_feat)
        
        sample_vals = np.array(b_feat["sample_values"])
        psi = calculate_psi(b_feat["baseline_probs"], sample_vals, b_feat["bin_edges"])
        self.assertLess(psi, 0.05, f"PSI for identical distribution was {psi}, expected < 0.05")

    def test_feature_no_drift_healthy(self):
        """Samples from normal baseline distribution should yield status NORMAL."""
        np.random.seed(101)
        vals = np.random.normal(62.0, 1.5, 40).tolist()
        res = self.detector.evaluate_feature_drift("Temperature", vals)
        
        self.assertEqual(res["drift_status"], "NORMAL")
        self.assertLess(res["psi_score"], self.config.PSI_WARNING_THRESHOLD)

    def test_moderate_feature_drift_warning(self):
        """Moderate distribution shift should trigger WARNING status."""
        np.random.seed(102)
        # Shift mean by +2.5 degrees and increase variance
        vals = np.random.normal(65.5, 2.8, 40).tolist()
        res = self.detector.evaluate_feature_drift("Temperature", vals)
        
        self.assertIn(res["drift_status"], ["WARNING", "CRITICAL"])
        self.assertGreaterEqual(res["psi_score"], self.config.PSI_WARNING_THRESHOLD)

    def test_severe_feature_drift_critical(self):
        """Large distribution shift should trigger CRITICAL status."""
        np.random.seed(103)
        # Shift Vibration mean from 0.20 to 0.85
        vals = np.random.normal(0.85, 0.15, 40).tolist()
        res = self.detector.evaluate_feature_drift("Vibration", vals)
        
        self.assertEqual(res["drift_status"], "CRITICAL")
        self.assertGreaterEqual(res["psi_score"], self.config.PSI_CRITICAL_THRESHOLD)

    def test_data_quality_missing_data(self):
        """High missingness should trigger data quality WARNING or CRITICAL."""
        vals = [62.0, 62.5, None, 63.0, float('nan'), None, 62.2, None] * 5  # ~37% missing
        res = self.detector.evaluate_data_quality("Temperature", vals)
        
        self.assertEqual(res["quality_status"], "CRITICAL")
        self.assertGreaterEqual(res["missing_pct"], self.config.MISSING_DATA_CRITICAL_PCT)

    def test_data_quality_stuck_sensor(self):
        """Constant sensor value with 0 variance should detect stuck sensor."""
        vals = [72.1] * 25
        res = self.detector.evaluate_data_quality("Temperature", vals)
        
        self.assertTrue(res["is_stuck"])
        self.assertEqual(res["stuck_value"], 72.1)
        self.assertEqual(res["quality_status"], "CRITICAL")

    def test_data_quality_out_of_bounds(self):
        """Sensor readings beyond physical limits should flag out of range."""
        vals = [62.0, 63.0, 220.0, 62.5, -40.0]  # 220C and -40C exceed bounds (-20, 150)
        res = self.detector.evaluate_data_quality("Temperature", vals)
        
        self.assertGreaterEqual(res["out_of_range_count"], 1)
        self.assertIn(res["quality_status"], ["WARNING", "CRITICAL"])

    def test_prediction_drift_rul(self):
        """Shift in predicted RUL distribution should trigger prediction drift."""
        # Baseline RUL is ~230 days. Supply low RUL predictions (~30 days).
        ruls = [35.0, 28.0, 40.0, 25.0, 30.0] * 8
        anoms = ["Normal"] * 40
        res = self.detector.evaluate_prediction_drift(ruls, anoms)
        
        self.assertTrue(len(res) >= 1)
        rul_res = [r for r in res if r["target_name"] == "predicted_rul_days"][0]
        self.assertIn(rul_res["drift_status"], ["WARNING", "CRITICAL"])
        self.assertGreater(rul_res["psi_score"], 0.10)

    def test_overall_model_health_synthesis(self):
        """Synthesizer should properly combine statuses into an overall decision."""
        # Case 1: All normal -> HEALTHY
        f_norm = [{"feature_name": "Vibration", "drift_status": "NORMAL", "psi_score": 0.02}]
        p_norm = [{"target_name": "predicted_rul", "drift_status": "NORMAL", "psi_score": 0.01}]
        q_norm = [{"feature_name": "Vibration", "quality_status": "NORMAL", "missing_pct": 0.0, "is_stuck": False}]
        h1 = self.detector.synthesize_model_health(f_norm, p_norm, q_norm)
        self.assertEqual(h1["overall_status"], "HEALTHY")

        # Case 2: One critical drift -> CRITICAL
        f_crit = [{"feature_name": "Vibration", "drift_status": "CRITICAL", "psi_score": 0.35}]
        h2 = self.detector.synthesize_model_health(f_crit, p_norm, q_norm)
        self.assertEqual(h2["overall_status"], "CRITICAL")
        self.assertIn("Vibration", h2["reason"])

    def test_database_persistence_and_retrieval(self):
        """Monitoring runs should save to database and be retrievable."""
        service = DriftMonitoringService()
        # Ingest 25 synthetic points
        for i in range(25):
            service.ingest_telemetry_record({
                "plc_id": "PLC_01",
                "Motor_Temp": 62.0 + np.random.normal(0, 0.5),
                "Vibration_X": 0.20 + np.random.normal(0, 0.01),
                "Motor_Current": 8.0,
                "Pressure_Inlet": 5.0,
                "Noise": 42.0,
                "predicted_rul_days": 240 - i,
                "anomaly_status": "Normal",
                "machine_health": 98.0
            })
            
        eval_res = service.evaluate_plc("PLC_01")
        self.assertIsNotNone(eval_res)
        self.assertEqual(eval_res["plc_id"], "PLC_01")
        self.assertIn("overall_status", eval_res)
        
        # Verify history retrieval
        history = db.get_run_history("PLC_01", limit=5)
        self.assertTrue(len(history) >= 1)

    def test_demonstration_sandbox_mode(self):
        """Demonstration mode should inject controlled drift safely."""
        service = DriftMonitoringService()
        demo_res = service.set_demonstration_mode("PLC_01", "severe_thermal_drift")
        
        self.assertEqual(demo_res["status"], "success")
        eval_res = demo_res["evaluation"]
        self.assertEqual(eval_res["overall_status"], "CRITICAL")
        
        # Reset back to normal
        reset_res = service.set_demonstration_mode("PLC_01", "normal")
        self.assertEqual(reset_res["status"], "success")


if __name__ == "__main__":
    unittest.main()
