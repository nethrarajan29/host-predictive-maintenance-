"""
Drift Monitoring Database Persistence Layer (Pure Python Standard Library SQLite)
----------------------------------------------------------------------------------
Provides robust relational persistence using standard library `sqlite3`.
Zero external dependencies required.
Tables:
  - drift_monitoring_runs
  - drift_feature_results
  - prediction_drift_results
  - data_quality_results
  - drift_alerts
"""

import os
import sqlite3
import logging
import datetime
from typing import Dict, List, Optional, Any

from .config import config

logger = logging.getLogger("drift_database")


class DriftDatabase:
    """Manages SQLite relational database storage for drift monitoring runs and alerts."""

    def __init__(self, db_path: str = None):
        if db_path is None:
            raw_url = config.DB_URL
            db_path = raw_url.replace("sqlite:///", "").replace("sqlite://", "")
        
        self.db_path = os.path.abspath(db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()
        logger.info(f"Drift SQLite database initialized at: {self.db_path}")

    def get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=15.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Monitoring Runs Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS drift_monitoring_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT UNIQUE NOT NULL,
                plc_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                overall_status TEXT NOT NULL,
                data_drift_status TEXT NOT NULL,
                prediction_drift_status TEXT NOT NULL,
                data_quality_status TEXT NOT NULL,
                overall_drift_score REAL DEFAULT 0.0,
                drifted_features_count INTEGER DEFAULT 0,
                total_features_monitored INTEGER DEFAULT 0,
                rul_psi REAL DEFAULT 0.0,
                anomaly_rate_current REAL DEFAULT 0.0,
                anomaly_rate_baseline REAL DEFAULT 0.0,
                missing_pct_overall REAL DEFAULT 0.0,
                stuck_sensors_count INTEGER DEFAULT 0,
                out_of_bounds_count INTEGER DEFAULT 0,
                summary TEXT,
                reason TEXT,
                recommendation TEXT
            );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_runs_plc ON drift_monitoring_runs(plc_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_runs_time ON drift_monitoring_runs(timestamp);")

            # 2. Feature Results Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS drift_feature_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                plc_id TEXT NOT NULL,
                feature_name TEXT NOT NULL,
                baseline_mean REAL DEFAULT 0.0,
                baseline_std REAL DEFAULT 0.0,
                current_mean REAL DEFAULT 0.0,
                current_std REAL DEFAULT 0.0,
                psi_score REAL DEFAULT 0.0,
                ks_statistic REAL DEFAULT 0.0,
                ks_pvalue REAL DEFAULT 1.0,
                wasserstein_distance REAL DEFAULT 0.0,
                drift_status TEXT DEFAULT 'NORMAL',
                explanation TEXT,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES drift_monitoring_runs(run_id) ON DELETE CASCADE
            );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_feat_run ON drift_feature_results(run_id);")

            # 3. Prediction Drift Results Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS prediction_drift_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                plc_id TEXT NOT NULL,
                target_name TEXT NOT NULL,
                baseline_mean REAL DEFAULT 0.0,
                current_mean REAL DEFAULT 0.0,
                psi_score REAL DEFAULT 0.0,
                drift_status TEXT DEFAULT 'NORMAL',
                details TEXT,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES drift_monitoring_runs(run_id) ON DELETE CASCADE
            );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pred_run ON prediction_drift_results(run_id);")

            # 4. Data Quality Results Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS data_quality_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                plc_id TEXT NOT NULL,
                feature_name TEXT NOT NULL,
                missing_count INTEGER DEFAULT 0,
                missing_pct REAL DEFAULT 0.0,
                is_stuck INTEGER DEFAULT 0,
                stuck_value REAL,
                out_of_range_count INTEGER DEFAULT 0,
                quality_status TEXT DEFAULT 'NORMAL',
                issue_description TEXT,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES drift_monitoring_runs(run_id) ON DELETE CASCADE
            );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_qual_run ON data_quality_results(run_id);")

            # 5. Drift Alerts Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS drift_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plc_id TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                recommendation TEXT,
                timestamp TEXT NOT NULL,
                resolved INTEGER DEFAULT 0
            );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_plc ON drift_alerts(plc_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_time ON drift_alerts(timestamp);")
            
            conn.commit()

    def save_monitoring_run(self, run_data: Dict[str, Any], feature_results: List[Dict],
                            prediction_results: List[Dict], quality_results: List[Dict]):
        """Persists a complete evaluation run with child tables atomically."""
        run_id = run_data.get("run_id")
        plc_id = run_data.get("plc_id", "PLC_01")
        ts = run_data.get("timestamp")
        ts_str = ts.strftime("%Y-%m-%d %H:%M:%S") if isinstance(ts, datetime.datetime) else str(ts)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Insert parent run
            cursor.execute("""
            INSERT INTO drift_monitoring_runs (
                run_id, plc_id, timestamp, overall_status, data_drift_status,
                prediction_drift_status, data_quality_status, overall_drift_score,
                drifted_features_count, total_features_monitored, rul_psi,
                anomaly_rate_current, anomaly_rate_baseline, missing_pct_overall,
                stuck_sensors_count, out_of_bounds_count, summary, reason, recommendation
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                run_id, plc_id, ts_str,
                run_data.get("overall_status", "HEALTHY"),
                run_data.get("data_drift_status", "NORMAL"),
                run_data.get("prediction_drift_status", "NORMAL"),
                run_data.get("data_quality_status", "NORMAL"),
                float(run_data.get("overall_drift_score", 0.0)),
                int(run_data.get("drifted_features_count", 0)),
                int(run_data.get("total_features_monitored", 0)),
                float(run_data.get("rul_psi", 0.0)),
                float(run_data.get("anomaly_rate_current", 0.0)),
                float(run_data.get("anomaly_rate_baseline", 0.0)),
                float(run_data.get("missing_pct_overall", 0.0)),
                int(run_data.get("stuck_sensors_count", 0)),
                int(run_data.get("out_of_bounds_count", 0)),
                run_data.get("summary", ""),
                run_data.get("reason", ""),
                run_data.get("recommendation", "")
            ))

            # Insert feature results
            for f in feature_results:
                cursor.execute("""
                INSERT INTO drift_feature_results (
                    run_id, plc_id, feature_name, baseline_mean, baseline_std,
                    current_mean, current_std, psi_score, ks_statistic,
                    ks_pvalue, wasserstein_distance, drift_status, explanation, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    run_id, plc_id, f.get("feature_name"),
                    float(f.get("baseline_mean", 0.0)), float(f.get("baseline_std", 0.0)),
                    float(f.get("current_mean", 0.0)), float(f.get("current_std", 0.0)),
                    float(f.get("psi_score", 0.0)), float(f.get("ks_statistic", 0.0)),
                    float(f.get("ks_pvalue", 1.0)), float(f.get("wasserstein_distance", 0.0)),
                    f.get("drift_status", "NORMAL"), f.get("explanation", ""), ts_str
                ))

            # Insert prediction results
            for p in prediction_results:
                cursor.execute("""
                INSERT INTO prediction_drift_results (
                    run_id, plc_id, target_name, baseline_mean, current_mean,
                    psi_score, drift_status, details, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    run_id, plc_id, p.get("target_name"),
                    float(p.get("baseline_mean", 0.0)), float(p.get("current_mean", 0.0)),
                    float(p.get("psi_score", 0.0)), p.get("drift_status", "NORMAL"),
                    p.get("details", ""), ts_str
                ))

            # Insert quality results
            for q in quality_results:
                cursor.execute("""
                INSERT INTO data_quality_results (
                    run_id, plc_id, feature_name, missing_count, missing_pct,
                    is_stuck, stuck_value, out_of_range_count, quality_status,
                    issue_description, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    run_id, plc_id, q.get("feature_name"),
                    int(q.get("missing_count", 0)), float(q.get("missing_pct", 0.0)),
                    1 if q.get("is_stuck") else 0,
                    float(q["stuck_value"]) if q.get("stuck_value") is not None else None,
                    int(q.get("out_of_range_count", 0)), q.get("quality_status", "NORMAL"),
                    q.get("issue_description", ""), ts_str
                ))

            conn.commit()

    def get_latest_run(self, plc_id: str = "PLC_01") -> Optional[Dict[str, Any]]:
        """Retrieves most recent evaluation run for a PLC."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT * FROM drift_monitoring_runs
            WHERE plc_id = ?
            ORDER BY id DESC LIMIT 1;
            """, (plc_id,))
            run = cursor.fetchone()
            if not run:
                return None

            run_dict = dict(run)
            run_id = run_dict["run_id"]

            cursor.execute("SELECT * FROM drift_feature_results WHERE run_id = ?;", (run_id,))
            features = [dict(r) for r in cursor.fetchall()]

            cursor.execute("SELECT * FROM prediction_drift_results WHERE run_id = ?;", (run_id,))
            predictions = [dict(r) for r in cursor.fetchall()]

            cursor.execute("SELECT * FROM data_quality_results WHERE run_id = ?;", (run_id,))
            qualities = [dict(r) for r in cursor.fetchall()]
            for q in qualities:
                q["is_stuck"] = bool(q.get("is_stuck", 0))

            return {
                "run_id": run_dict["run_id"],
                "plc_id": run_dict["plc_id"],
                "timestamp": run_dict["timestamp"],
                "overall_status": run_dict["overall_status"],
                "data_drift_status": run_dict["data_drift_status"],
                "prediction_drift_status": run_dict["prediction_drift_status"],
                "data_quality_status": run_dict["data_quality_status"],
                "overall_drift_score": round(float(run_dict["overall_drift_score"]), 3),
                "drifted_features_count": run_dict["drifted_features_count"],
                "total_features_monitored": run_dict["total_features_monitored"],
                "rul_psi": round(float(run_dict["rul_psi"]), 3),
                "anomaly_rate_current": round(float(run_dict["anomaly_rate_current"]), 1),
                "anomaly_rate_baseline": round(float(run_dict["anomaly_rate_baseline"]), 1),
                "missing_pct_overall": round(float(run_dict["missing_pct_overall"]), 2),
                "stuck_sensors_count": run_dict["stuck_sensors_count"],
                "out_of_bounds_count": run_dict["out_of_bounds_count"],
                "summary": run_dict["summary"],
                "reason": run_dict["reason"],
                "recommendation": run_dict["recommendation"],
                "features": [
                    {
                        "feature_name": f["feature_name"],
                        "baseline_mean": round(float(f["baseline_mean"]), 2),
                        "baseline_std": round(float(f["baseline_std"]), 2),
                        "current_mean": round(float(f["current_mean"]), 2),
                        "current_std": round(float(f["current_std"]), 2),
                        "psi_score": round(float(f["psi_score"]), 3),
                        "ks_pvalue": round(float(f["ks_pvalue"]), 4),
                        "wasserstein_distance": round(float(f["wasserstein_distance"]), 3),
                        "drift_status": f["drift_status"],
                        "explanation": f["explanation"]
                    } for f in features
                ],
                "predictions": [
                    {
                        "target_name": p["target_name"],
                        "baseline_mean": round(float(p["baseline_mean"]), 2),
                        "current_mean": round(float(p["current_mean"]), 2),
                        "psi_score": round(float(p["psi_score"]), 3),
                        "drift_status": p["drift_status"],
                        "details": p["details"]
                    } for p in predictions
                ],
                "data_quality": [
                    {
                        "feature_name": q["feature_name"],
                        "missing_count": q["missing_count"],
                        "missing_pct": round(float(q["missing_pct"]), 2),
                        "is_stuck": q["is_stuck"],
                        "stuck_value": q["stuck_value"],
                        "out_of_range_count": q["out_of_range_count"],
                        "quality_status": q["quality_status"],
                        "issue_description": q["issue_description"]
                    } for q in qualities
                ]
            }

    def get_run_history(self, plc_id: str = "PLC_01", limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves chronological series of monitoring run summaries."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if plc_id and plc_id.upper() != "ALL":
                cursor.execute("""
                SELECT * FROM drift_monitoring_runs
                WHERE plc_id = ?
                ORDER BY id DESC LIMIT ?;
                """, (plc_id, limit))
            else:
                cursor.execute("""
                SELECT * FROM drift_monitoring_runs
                ORDER BY id DESC LIMIT ?;
                """, (limit,))
            
            runs = [dict(r) for r in cursor.fetchall()]
            result = []
            for r in reversed(runs):
                result.append({
                    "run_id": r["run_id"],
                    "plc_id": r["plc_id"],
                    "timestamp": r["timestamp"],
                    "overall_status": r["overall_status"],
                    "data_drift_status": r["data_drift_status"],
                    "prediction_drift_status": r["prediction_drift_status"],
                    "data_quality_status": r["data_quality_status"],
                    "overall_drift_score": round(float(r["overall_drift_score"]), 3),
                    "drifted_features_count": r["drifted_features_count"],
                    "rul_psi": round(float(r["rul_psi"]), 3),
                    "missing_pct_overall": round(float(r["missing_pct_overall"]), 2),
                    "reason": r["reason"]
                })
            return result

    def record_alert(self, plc_id: str, alert_type: str, severity: str,
                     title: str, message: str, recommendation: str = ""):
        """Records an operational drift or data reliability alert."""
        ts_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO drift_alerts (
                plc_id, alert_type, severity, title, message, recommendation, timestamp, resolved
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 0);
            """, (plc_id, alert_type, severity, title, message, recommendation, ts_str))
            conn.commit()

    def get_recent_alerts(self, plc_id: str = None, limit: int = 30) -> List[Dict[str, Any]]:
        """Retrieves recent alerts with optional PLC filtering."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if plc_id and plc_id.upper() != "ALL":
                cursor.execute("""
                SELECT * FROM drift_alerts
                WHERE plc_id = ?
                ORDER BY id DESC LIMIT ?;
                """, (plc_id, limit))
            else:
                cursor.execute("""
                SELECT * FROM drift_alerts
                ORDER BY id DESC LIMIT ?;
                """, (limit,))
            
            alerts = [dict(r) for r in cursor.fetchall()]
            return [
                {
                    "id": a["id"],
                    "plc_id": a["plc_id"],
                    "alert_type": a["alert_type"],
                    "severity": a["severity"],
                    "title": a["title"],
                    "message": a["message"],
                    "recommendation": a["recommendation"],
                    "timestamp": a["timestamp"],
                    "resolved": bool(a["resolved"])
                } for a in alerts
            ]


# Shared singleton database instance
db = DriftDatabase()
