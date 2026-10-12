"""
Asset Digital Thread Database Persistence Layer (Pure Python Standard Library SQLite)
-------------------------------------------------------------------------------------
Provides robust relational persistence using standard library `sqlite3`.
Tables:
  - assets
  - asset_components
  - asset_sensors
  - asset_events (Chronological Lifecycle Timeline)
  - maintenance_records (Closed-Loop Maintenance & Outcome)
  - maintenance_parts (Parts Replaced & Cost Accounting)
"""

import os
import json
import sqlite3
import logging
import datetime
import uuid
from typing import Dict, List, Optional, Any

from .config import config

logger = logging.getLogger("digital_thread_db")


class DigitalThreadDatabase:
    """Manages SQLite relational database storage for the Asset Digital Thread."""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = config.DB_PATH
        
        self.db_path = os.path.abspath(db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()
        self._seed_default_assets()
        logger.info(f"Digital Thread SQLite database initialized at: {self.db_path}")

    def get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=15.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Assets Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS assets (
                asset_id TEXT PRIMARY KEY,
                asset_name TEXT NOT NULL,
                asset_type TEXT NOT NULL,
                plc_id TEXT UNIQUE NOT NULL,
                location TEXT,
                manufacturer TEXT,
                model TEXT,
                install_date TEXT,
                status TEXT DEFAULT 'RUNNING',
                health REAL DEFAULT 100.0,
                rul_days INTEGER DEFAULT 250,
                last_maintenance_date TEXT,
                next_maintenance_date TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_assets_plc ON assets(plc_id);")

            # 2. Asset Components Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS asset_components (
                component_id TEXT PRIMARY KEY,
                asset_id TEXT NOT NULL,
                component_name TEXT NOT NULL,
                component_type TEXT NOT NULL,
                health REAL DEFAULT 100.0,
                criticality TEXT DEFAULT 'MEDIUM',
                FOREIGN KEY (asset_id) REFERENCES assets(asset_id) ON DELETE CASCADE
            );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_comp_asset ON asset_components(asset_id);")

            # 3. Asset Sensors Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS asset_sensors (
                sensor_id TEXT PRIMARY KEY,
                asset_id TEXT NOT NULL,
                component_id TEXT NOT NULL,
                tag_name TEXT NOT NULL,
                sensor_type TEXT NOT NULL,
                unit TEXT NOT NULL,
                min_val REAL,
                max_val REAL,
                FOREIGN KEY (asset_id) REFERENCES assets(asset_id) ON DELETE CASCADE,
                FOREIGN KEY (component_id) REFERENCES asset_components(component_id) ON DELETE CASCADE
            );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sensor_asset ON asset_sensors(asset_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sensor_comp ON asset_sensors(component_id);")

            # 4. Asset Events (The Core Chronological Lifecycle Timeline)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS asset_events (
                event_id TEXT PRIMARY KEY,
                asset_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                severity TEXT DEFAULT 'INFO',
                source TEXT NOT NULL,
                description TEXT NOT NULL,
                component_id TEXT,
                sensor_id TEXT,
                metric_value REAL,
                metadata_json TEXT,
                FOREIGN KEY (asset_id) REFERENCES assets(asset_id) ON DELETE CASCADE
            );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_event_asset ON asset_events(asset_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_event_time ON asset_events(timestamp);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_event_type ON asset_events(event_type);")

            # 5. Maintenance Records (Closed-Loop Maintenance Tracking)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS maintenance_records (
                maintenance_id TEXT PRIMARY KEY,
                asset_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                maintenance_type TEXT NOT NULL,
                reason TEXT NOT NULL,
                triggered_by TEXT DEFAULT 'Predictive Model',
                technician TEXT,
                finding TEXT,
                action_performed TEXT,
                parts_replaced TEXT,
                downtime_hours REAL DEFAULT 0.0,
                cost REAL DEFAULT 0.0,
                before_health REAL,
                after_health REAL,
                before_rul INTEGER,
                after_rul INTEGER,
                notes TEXT,
                status TEXT DEFAULT 'COMPLETED',
                outcome_verified INTEGER DEFAULT 0,
                outcome_timestamp TEXT,
                FOREIGN KEY (asset_id) REFERENCES assets(asset_id) ON DELETE CASCADE
            );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_maint_asset ON maintenance_records(asset_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_maint_time ON maintenance_records(timestamp);")

            # 6. Maintenance Parts Replaced Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS maintenance_parts (
                part_id TEXT PRIMARY KEY,
                maintenance_id TEXT NOT NULL,
                part_name TEXT NOT NULL,
                part_number TEXT,
                quantity INTEGER DEFAULT 1,
                cost REAL DEFAULT 0.0,
                FOREIGN KEY (maintenance_id) REFERENCES maintenance_records(maintenance_id) ON DELETE CASCADE
            );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_part_maint ON maintenance_parts(maintenance_id);")

            conn.commit()

    def _seed_default_assets(self):
        """Seeds default assets, components, and sensors if database is empty."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM assets;")
            count = cursor.fetchone()[0]
            if count > 0:
                return

            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info("Seeding initial Asset Digital Thread catalog...")

            for asset in config.DEFAULT_ASSETS:
                cursor.execute("""
                INSERT OR IGNORE INTO assets (
                    asset_id, asset_name, asset_type, plc_id, location, manufacturer,
                    model, install_date, status, health, rul_days,
                    last_maintenance_date, next_maintenance_date, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    asset["asset_id"],
                    asset["asset_name"],
                    asset["asset_type"],
                    asset["plc_id"],
                    asset.get("location", "Unknown"),
                    asset.get("manufacturer", "Unknown"),
                    asset.get("model", "Unknown"),
                    asset.get("install_date", "2023-01-01"),
                    asset.get("status", "RUNNING"),
                    asset.get("health", 100.0),
                    asset.get("rul_days", 250),
                    "2026-08-15 08:30:00",
                    "2026-11-15 08:30:00",
                    now_str,
                    now_str
                ))

                for comp in asset.get("components", []):
                    cursor.execute("""
                    INSERT OR IGNORE INTO asset_components (
                        component_id, asset_id, component_name, component_type, health, criticality
                    ) VALUES (?, ?, ?, ?, ?, ?);
                    """, (
                        comp["component_id"],
                        asset["asset_id"],
                        comp["component_name"],
                        comp["component_type"],
                        comp.get("health", 100.0),
                        comp.get("criticality", "MEDIUM")
                    ))

                    for sens in comp.get("sensors", []):
                        cursor.execute("""
                        INSERT OR IGNORE INTO asset_sensors (
                            sensor_id, asset_id, component_id, tag_name, sensor_type, unit, min_val, max_val
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                        """, (
                            sens["sensor_id"],
                            asset["asset_id"],
                            comp["component_id"],
                            sens["tag_name"],
                            sens["sensor_type"],
                            sens["unit"],
                            sens.get("min_val", 0.0),
                            sens.get("max_val", 100.0)
                        ))

            # Add initial historical demonstration maintenance events for COMP-001 and COMP-003
            maint_id_1 = "MAINT-INIT-001"
            cursor.execute("""
            INSERT OR IGNORE INTO maintenance_records (
                maintenance_id, asset_id, timestamp, maintenance_type, reason,
                triggered_by, technician, finding, action_performed, parts_replaced,
                downtime_hours, cost, before_health, after_health, before_rul, after_rul,
                notes, status, outcome_verified, outcome_timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                maint_id_1,
                "COMP-001",
                "2026-08-15 08:30:00",
                "Preventive Lubrication & Bearing Inspection",
                "Quarterly scheduled reliability maintenance",
                "PM Schedule",
                "Reliability Tech Marcus V.",
                "Bearing grease degradation and minor micro-vibration",
                "Flushed housing, repacked with synthetic high-temp grease, balanced coupling",
                "Synthetic Grease Mobil SHC 100, O-ring seal kit",
                2.5,
                480.00,
                82.0,
                99.0,
                160,
                250,
                "Vibration decreased from 0.45 mm/s to 0.18 mm/s post-service.",
                "COMPLETED",
                1,
                "2026-08-15 11:30:00"
            ))

            cursor.execute("""
            INSERT OR IGNORE INTO maintenance_parts (
                part_id, maintenance_id, part_name, part_number, quantity, cost
            ) VALUES (?, ?, ?, ?, ?, ?);
            """, (
                "PART-001",
                maint_id_1,
                "Synthetic Bearing Grease 1kg",
                "MOBIL-SHC-100",
                2,
                120.00
            ))

            # Initial seed events in timeline
            cursor.execute("""
            INSERT OR IGNORE INTO asset_events (
                event_id, asset_id, timestamp, event_type, severity, source,
                description, component_id, sensor_id, metric_value, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                "EVT-INIT-001",
                "COMP-001",
                "2026-08-15 08:30:00",
                "MAINTENANCE",
                "INFO",
                "Maintenance Service",
                "Preventive Lubrication & Bearing Inspection completed by Marcus V.",
                "COMP-001-BRG",
                "SENS-001-T102",
                99.0,
                json.dumps({"maintenance_id": maint_id_1, "outcome": "Vibration restored to baseline"})
            ))

            cursor.execute("""
            INSERT OR IGNORE INTO asset_events (
                event_id, asset_id, timestamp, event_type, severity, source,
                description, component_id, sensor_id, metric_value, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                "EVT-INIT-002",
                "COMP-001",
                "2026-08-15 11:30:00",
                "ALERT",
                "INFO",
                "Reliability Engine",
                "Closed-Loop Outcome Verified: Asset health returned to 99.0% (RUL: 250 days).",
                "COMP-001-BRG",
                None,
                99.0,
                json.dumps({"before_health": 82.0, "after_health": 99.0, "before_rul": 160, "after_rul": 250})
            ))

            conn.commit()

    # -------------------------------------------------------------
    # ASSETS CRUD & QUERIES
    # -------------------------------------------------------------

    def get_all_assets(self) -> List[Dict[str, Any]]:
        """Retrieves list of all registered assets."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM assets ORDER BY asset_id ASC;")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_asset_by_id(self, asset_id_or_plc: str) -> Optional[Dict[str, Any]]:
        """Retrieves asset record by asset_id (e.g. COMP-001) or plc_id (e.g. PLC_01)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT * FROM assets WHERE asset_id = ? OR plc_id = ?;
            """, (asset_id_or_plc, asset_id_or_plc))
            row = cursor.fetchone()
            if not row:
                return None
            asset_data = dict(row)
            
            # Fetch components and sensors
            asset_data["components"] = self.get_asset_components(asset_data["asset_id"])
            return asset_data

    def update_asset_health(self, asset_id_or_plc: str, health: float, rul_days: int, status: str = None):
        """Updates live dynamic health, RUL, and operational status of an asset."""
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if status:
                cursor.execute("""
                UPDATE assets
                SET health = ?, rul_days = ?, status = ?, updated_at = ?
                WHERE asset_id = ? OR plc_id = ?;
                """, (health, rul_days, status, now_str, asset_id_or_plc, asset_id_or_plc))
            else:
                cursor.execute("""
                UPDATE assets
                SET health = ?, rul_days = ?, updated_at = ?
                WHERE asset_id = ? OR plc_id = ?;
                """, (health, rul_days, now_str, asset_id_or_plc, asset_id_or_plc))
            conn.commit()

    # -------------------------------------------------------------
    # COMPONENTS & SENSORS
    # -------------------------------------------------------------

    def get_asset_components(self, asset_id: str) -> List[Dict[str, Any]]:
        """Retrieves components and associated sensors for an asset."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT * FROM asset_components WHERE asset_id = ? ORDER BY component_id ASC;
            """, (asset_id,))
            comps = [dict(c) for c in cursor.fetchall()]

            for c in comps:
                cursor.execute("""
                SELECT * FROM asset_sensors WHERE component_id = ? ORDER BY sensor_id ASC;
                """, (c["component_id"],))
                c["sensors"] = [dict(s) for s in cursor.fetchall()]

            return comps

    def get_asset_sensors(self, asset_id: str) -> List[Dict[str, Any]]:
        """Retrieves all sensors directly associated with an asset."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT s.*, c.component_name
            FROM asset_sensors s
            JOIN asset_components c ON s.component_id = c.component_id
            WHERE s.asset_id = ?
            ORDER BY s.sensor_id ASC;
            """, (asset_id,))
            return [dict(row) for row in cursor.fetchall()]

    # -------------------------------------------------------------
    # TIMELINE & LIFECYCLE EVENTS
    # -------------------------------------------------------------

    def record_event(self, asset_id: str, event_type: str, severity: str,
                     source: str, description: str, component_id: str = None,
                     sensor_id: str = None, metric_value: float = None,
                     metadata: Dict[str, Any] = None, timestamp: str = None) -> Dict[str, Any]:
        """Records a new lifecycle event in the Asset Digital Thread timeline."""
        now_str = timestamp or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        event_id = f"EVT-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
        meta_json = json.dumps(metadata) if metadata else None

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO asset_events (
                event_id, asset_id, timestamp, event_type, severity, source,
                description, component_id, sensor_id, metric_value, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                event_id,
                asset_id,
                now_str,
                event_type.upper(),
                severity.upper(),
                source,
                description,
                component_id,
                sensor_id,
                metric_value,
                meta_json
            ))
            conn.commit()

        return {
            "event_id": event_id,
            "asset_id": asset_id,
            "timestamp": now_str,
            "event_type": event_type.upper(),
            "severity": severity.upper(),
            "source": source,
            "description": description,
            "component_id": component_id,
            "sensor_id": sensor_id,
            "metric_value": metric_value,
            "metadata": metadata
        }

    def get_asset_timeline(self, asset_id_or_plc: str, event_type: str = None,
                           severity: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieves chronological lifecycle timeline for an asset with optional filtering."""
        # Resolve asset_id if plc_id is passed
        asset = self.get_asset_by_id(asset_id_or_plc)
        asset_id = asset["asset_id"] if asset else asset_id_or_plc

        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM asset_events WHERE asset_id = ?"
            params = [asset_id]

            if event_type and event_type.upper() != "ALL":
                query += " AND event_type = ?"
                params.append(event_type.upper())

            if severity and severity.upper() != "ALL":
                query += " AND severity = ?"
                params.append(severity.upper())

            query += " ORDER BY timestamp DESC, rowid DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()

            events = []
            for r in rows:
                item = dict(r)
                if item.get("metadata_json"):
                    try:
                        item["metadata"] = json.loads(item["metadata_json"])
                    except Exception:
                        item["metadata"] = {}
                else:
                    item["metadata"] = {}
                events.append(item)

            return events

    # -------------------------------------------------------------
    # MAINTENANCE & CLOSED-LOOP OUTCOME
    # -------------------------------------------------------------

    def record_maintenance(self, asset_id_or_plc: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Creates a new maintenance record and automatically logs a timeline event."""
        asset = self.get_asset_by_id(asset_id_or_plc)
        if not asset:
            raise ValueError(f"Asset '{asset_id_or_plc}' not found in registry.")
        asset_id = asset["asset_id"]

        now_str = data.get("timestamp") or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        maint_id = data.get("maintenance_id") or f"MAINT-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4]}"

        before_h = data.get("before_health", asset.get("health", 100.0))
        before_r = data.get("before_rul", asset.get("rul_days", 250))
        after_h = data.get("after_health")
        after_r = data.get("after_rul")
        status = data.get("status", "IN_PROGRESS" if after_h is None else "COMPLETED")

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO maintenance_records (
                maintenance_id, asset_id, timestamp, maintenance_type, reason,
                triggered_by, technician, finding, action_performed, parts_replaced,
                downtime_hours, cost, before_health, after_health, before_rul, after_rul,
                notes, status, outcome_verified, outcome_timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                maint_id,
                asset_id,
                now_str,
                data.get("maintenance_type", "Preventive Inspection"),
                data.get("reason", "Condition-based maintenance trigger"),
                data.get("triggered_by", "Predictive Maintenance Engine"),
                data.get("technician"),
                data.get("finding"),
                data.get("action_performed"),
                data.get("parts_replaced"),
                float(data.get("downtime_hours", 0.0) or 0.0),
                float(data.get("cost", 0.0) or 0.0),
                before_h,
                after_h,
                before_r,
                after_r,
                data.get("notes"),
                status,
                1 if after_h is not None else 0,
                now_str if after_h is not None else None
            ))

            # Insert parts if provided
            parts = data.get("parts", [])
            for p in parts:
                p_id = f"PART-{uuid.uuid4().hex[:6]}"
                cursor.execute("""
                INSERT INTO maintenance_parts (
                    part_id, maintenance_id, part_name, part_number, quantity, cost
                ) VALUES (?, ?, ?, ?, ?, ?);
                """, (
                    p_id,
                    maint_id,
                    p.get("part_name", "Component Replacement"),
                    p.get("part_number", "OEM-GENERIC"),
                    p.get("quantity", 1),
                    p.get("cost", 0.0)
                ))

            # Update asset last_maintenance_date
            cursor.execute("""
            UPDATE assets SET last_maintenance_date = ?, updated_at = ? WHERE asset_id = ?;
            """, (now_str, now_str, asset_id))

            conn.commit()

        # Log timeline event
        action_desc = data.get("action_performed") or data.get("maintenance_type")
        self.record_event(
            asset_id=asset_id,
            event_type="MAINTENANCE",
            severity="INFO",
            source="Maintenance Service",
            description=f"Maintenance logged: {action_desc} (Status: {status})",
            timestamp=now_str,
            metadata={"maintenance_id": maint_id, "technician": data.get("technician"), "status": status}
        )

        # If outcome provided, also update asset health
        if after_h is not None and after_r is not None:
            self.update_asset_health(asset_id, float(after_h), int(after_r), status="HEALTHY" if after_h >= 80 else "RUNNING")

        return self.get_maintenance_record_by_id(maint_id)

    def record_maintenance_outcome(self, asset_id_or_plc: str, maintenance_id: str,
                                   data: Dict[str, Any]) -> Dict[str, Any]:
        """Records closed-loop maintenance outcome, updating after-health, after-RUL and asset state."""
        asset = self.get_asset_by_id(asset_id_or_plc)
        if not asset:
            raise ValueError(f"Asset '{asset_id_or_plc}' not found in registry.")
        asset_id = asset["asset_id"]

        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        after_health = float(data.get("after_health", 98.0))
        after_rul = int(data.get("after_rul", 250))
        action_notes = data.get("notes", "Maintenance outcome verified successfully.")
        status = data.get("status", "COMPLETED")

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            UPDATE maintenance_records
            SET after_health = ?,
                after_rul = ?,
                status = ?,
                notes = CASE WHEN notes IS NULL THEN ? ELSE notes || ' | Outcome: ' || ? END,
                outcome_verified = 1,
                outcome_timestamp = ?
            WHERE maintenance_id = ? AND asset_id = ?;
            """, (after_health, after_rul, status, action_notes, action_notes, now_str, maintenance_id, asset_id))

            if cursor.rowcount == 0:
                raise ValueError(f"Maintenance record '{maintenance_id}' for asset '{asset_id}' not found.")

            # Update asset health to post-maintenance level
            asset_status = "HEALTHY" if after_health >= 80 else "RUNNING"
            cursor.execute("""
            UPDATE assets
            SET health = ?, rul_days = ?, status = ?, updated_at = ?
            WHERE asset_id = ?;
            """, (after_health, after_rul, asset_status, now_str, asset_id))

            conn.commit()

        # Log timeline event
        self.record_event(
            asset_id=asset_id,
            event_type="MAINTENANCE",
            severity="INFO",
            source="Closed-Loop Verification",
            description=f"Post-Maintenance Outcome Verified: Health improved to {after_health}% (RUL: {after_rul} days).",
            timestamp=now_str,
            metadata={
                "maintenance_id": maintenance_id,
                "after_health": after_health,
                "after_rul": after_rul,
                "notes": action_notes
            }
        )

        return self.get_maintenance_record_by_id(maintenance_id)

    def get_asset_maintenance_history(self, asset_id_or_plc: str) -> List[Dict[str, Any]]:
        """Retrieves maintenance records for an asset with attached parts."""
        asset = self.get_asset_by_id(asset_id_or_plc)
        asset_id = asset["asset_id"] if asset else asset_id_or_plc

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT * FROM maintenance_records WHERE asset_id = ? ORDER BY timestamp DESC;
            """, (asset_id,))
            records = [dict(r) for r in cursor.fetchall()]

            for rec in records:
                cursor.execute("""
                SELECT * FROM maintenance_parts WHERE maintenance_id = ?;
                """, (rec["maintenance_id"],))
                rec["parts"] = [dict(p) for p in cursor.fetchall()]

            return records

    def get_maintenance_record_by_id(self, maintenance_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single maintenance record with parts."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM maintenance_records WHERE maintenance_id = ?;", (maintenance_id,))
            row = cursor.fetchone()
            if not row:
                return None
            rec = dict(row)
            cursor.execute("SELECT * FROM maintenance_parts WHERE maintenance_id = ?;", (maintenance_id,))
            rec["parts"] = [dict(p) for p in cursor.fetchall()]
            return rec


db = DigitalThreadDatabase()
