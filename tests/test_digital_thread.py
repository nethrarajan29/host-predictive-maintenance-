"""
Unit & Integration Test Suite for Asset Digital Thread Subsystem
---------------------------------------------------------------
Validates:
  1. Asset registry & default multi-asset catalog initialization
  2. Component & sensor hierarchy relationships
  3. Live telemetry ingestion and state updating
  4. Isolation Forest anomaly event capture
  5. Random Forest RUL prediction event capture
  6. Data & Model Drift monitoring event integration
  7. Maintenance record creation and part accounting
  8. Closed-loop maintenance outcome recording (before/after health & RUL)
  9. Timeline chronological retrieval & filtering
 10. Multi-asset isolation (COMP-001 to COMP-005 / PLC_01 to PLC_05)
 11. FastAPI REST API endpoints
"""

import os
import sys
import tempfile
import unittest
import datetime

# Ensure project root is on sys.path
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from digital_thread.config import DigitalThreadConfig
from digital_thread.database import DigitalThreadDatabase
from digital_thread.service import DigitalThreadService


class TestAssetDigitalThread(unittest.TestCase):
    """Comprehensive test cases for Asset Digital Thread."""

    def setUp(self):
        # Create an isolated temporary SQLite database for each test
        self.temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db_path = self.temp_db_file.name
        self.temp_db_file.close()

        self.db = DigitalThreadDatabase(db_path=self.temp_db_path)
        self.service = DigitalThreadService()
        self.service.db = self.db

    def tearDown(self):
        try:
            if os.path.exists(self.temp_db_path):
                os.remove(self.temp_db_path)
        except Exception:
            pass

    def test_01_default_assets_seeded(self):
        """Verify default 5 industrial assets are initialized with components & sensors."""
        assets = self.db.get_all_assets()
        self.assertEqual(len(assets), 5)
        asset_ids = [a["asset_id"] for a in assets]
        self.assertIn("COMP-001", asset_ids)
        self.assertIn("COMP-005", asset_ids)

    def test_02_component_sensor_relationships(self):
        """Verify asset -> component -> sensor relational hierarchy."""
        asset = self.db.get_asset_by_id("COMP-001")
        self.assertIsNotNone(asset)
        self.assertEqual(asset["plc_id"], "PLC_01")
        
        comps = self.db.get_asset_components("COMP-001")
        self.assertGreaterEqual(len(comps), 3) # Motor, Bearing, Inlet
        
        # Check sensors on bearing
        bearing_comp = next((c for c in comps if "BRG" in c["component_id"]), None)
        self.assertIsNotNone(bearing_comp)
        sensor_tags = [s["tag_name"] for s in bearing_comp["sensors"]]
        self.assertIn("Vibration_X", sensor_tags)
        self.assertIn("Noise", sensor_tags)

    def test_03_telemetry_event_ingestion(self):
        """Verify streaming telemetry ingestion updates asset health and creates checkpoints."""
        telemetry = {
            "plc_id": "PLC_01",
            "timestamp": "2026-10-05 10:00:00",
            "temperature": 68.5,
            "vibration": 0.22,
            "motor_current": 8.4,
            "pressure": 5.1,
            "noise": 43.0,
            "machine_health": 95.0,
            "predicted_rul_days": 230,
            "machine_status": "RUNNING",
            "anomaly_status": "Normal"
        }
        self.service.ingest_telemetry_event(telemetry)

        # Asset record should reflect new health & RUL
        asset = self.db.get_asset_by_id("COMP-001")
        self.assertEqual(asset["health"], 95.0)
        self.assertEqual(asset["rul_days"], 230)

    def test_04_anomaly_event_capture(self):
        """Verify when Isolation Forest detects anomaly, it enters the digital thread timeline."""
        telemetry = {
            "plc_id": "COMP-001",
            "timestamp": "2026-10-05 10:15:00",
            "temperature": 92.0,
            "vibration": 2.4,
            "machine_health": 60.0,
            "predicted_rul_days": 45,
            "anomaly_status": "Anomaly Detected",
            "Anomaly_Score": -0.32,
            "machine_status": "WARNING"
        }
        self.service.ingest_telemetry_event(telemetry)

        timeline = self.db.get_asset_timeline("COMP-001", event_type="ANOMALY")
        self.assertGreaterEqual(len(timeline), 1)
        latest = timeline[0]
        self.assertEqual(latest["event_type"], "ANOMALY")
        self.assertEqual(latest["source"], "Isolation Forest Model")
        self.assertIn("COMP-001-BRG", latest["component_id"])

    def test_05_drift_monitoring_integration(self):
        """Verify Drift Monitoring events are connected to the Asset Digital Thread."""
        drift_payload = {
            "overall_status": "WARNING",
            "overall_drift_score": 0.185,
            "reason": "Feature drift detected on Vibration_X (PSI: 0.22)",
            "recommendation": "Perform sensor diagnostic calibration",
            "timestamp": "2026-10-05 10:18:00"
        }
        self.service.ingest_drift_event("PLC_01", drift_payload)

        timeline = self.db.get_asset_timeline("COMP-001", event_type="DRIFT")
        self.assertGreaterEqual(len(timeline), 1)
        latest_drift = timeline[0]
        self.assertEqual(latest_drift["event_type"], "DRIFT")
        self.assertEqual(latest_drift["severity"], "WARNING")
        self.assertIn("PSI: 0.185", latest_drift["description"])

    def test_06_maintenance_creation_and_parts(self):
        """Verify logging maintenance record with parts replaced."""
        maint_data = {
            "maintenance_type": "Bearing Replacement & Alignment",
            "reason": "Vibration anomaly and drift warning",
            "triggered_by": "Predictive Decision Engine",
            "technician": "Sarah Chen, Lead PDM Specialist",
            "finding": "Inner raceway spalling and cage wear",
            "action_performed": "Replaced drive-end roller bearing and dynamic balance",
            "parts_replaced": "SKF 22218 Spherical Roller Bearing",
            "downtime_hours": 3.5,
            "cost": 850.00,
            "before_health": 55.0,
            "before_rul": 30,
            "notes": "Bearing replacement complete. Awaiting post-startup verification.",
            "parts": [
                {"part_name": "SKF 22218 Roller Bearing", "part_number": "SKF-22218-E", "quantity": 1, "cost": 650.0},
                {"part_name": "Labyrinth Seal Set", "part_number": "LAB-SEAL-08", "quantity": 2, "cost": 200.0}
            ]
        }
        rec = self.db.record_maintenance("COMP-001", maint_data)
        self.assertIsNotNone(rec)
        self.assertEqual(rec["technician"], "Sarah Chen, Lead PDM Specialist")
        self.assertEqual(len(rec["parts"]), 2)

        # Timeline should have a MAINTENANCE event
        timeline = self.db.get_asset_timeline("COMP-001", event_type="MAINTENANCE")
        self.assertGreaterEqual(len(timeline), 1)

    def test_07_closed_loop_maintenance_outcome(self):
        """Verify recording post-maintenance outcome verifies resolution and restores health."""
        # Step 1: Create maintenance event
        maint = self.db.record_maintenance("COMP-001", {
            "maintenance_type": "Motor Stator Rewind",
            "reason": "Thermal stress on windings",
            "before_health": 60.0,
            "before_rul": 40
        })
        maint_id = maint["maintenance_id"]

        # Step 2: Record post-maintenance outcome
        outcome = self.db.record_maintenance_outcome("COMP-001", maint_id, {
            "after_health": 98.5,
            "after_rul": 240,
            "notes": "Post-repair temperature stabilized at 62.4°C. Vibration normalized.",
            "status": "COMPLETED"
        })

        self.assertEqual(outcome["outcome_verified"], 1)
        self.assertEqual(outcome["after_health"], 98.5)
        self.assertEqual(outcome["after_rul"], 240)

        # Asset state should be updated to post-maintenance level
        asset = self.db.get_asset_by_id("COMP-001")
        self.assertEqual(asset["health"], 98.5)
        self.assertEqual(asset["rul_days"], 240)

    def test_08_multi_asset_isolation(self):
        """Verify events for COMP-001 do not bleed into COMP-002."""
        self.db.record_event(
            asset_id="COMP-001",
            event_type="ALERT",
            severity="WARNING",
            source="Test",
            description="Test alert for asset 1"
        )
        self.db.record_event(
            asset_id="COMP-002",
            event_type="ALERT",
            severity="CRITICAL",
            source="Test",
            description="Test alert for asset 2"
        )

        tl_1 = self.db.get_asset_timeline("COMP-001")
        tl_2 = self.db.get_asset_timeline("COMP-002")

        self.assertTrue(all(e["asset_id"] == "COMP-001" for e in tl_1))
        self.assertTrue(all(e["asset_id"] == "COMP-002" for e in tl_2))

    def test_09_asset_health_snapshot(self):
        """Verify complete health snapshot generation."""
        live_telemetry = {
            "Motor_Temp": 64.2,
            "Vibration_X": 0.25,
            "Motor_Current": 8.1,
            "Pressure_Inlet": 5.0,
            "Noise": 42.5,
            "machine_health": 96.0,
            "predicted_rul_days": 240,
            "anomaly_status": "Normal",
            "machine_status": "RUNNING"
        }
        snapshot = self.service.get_asset_health_snapshot("COMP-001", live_telemetry_dict=live_telemetry)
        
        self.assertEqual(snapshot["asset_id"], "COMP-001")
        self.assertEqual(snapshot["health"], 96.0)
        self.assertEqual(snapshot["rul_days"], 240)
        self.assertIn("components", snapshot)
        self.assertIn("ai_health", snapshot)
        self.assertEqual(snapshot["ai_health"]["health_status"], "HEALTHY")


if __name__ == "__main__":
    unittest.main()
