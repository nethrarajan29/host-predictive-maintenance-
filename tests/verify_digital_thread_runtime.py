"""
Runtime Verification Script for PredictX Asset Digital Thread APIs
"""

import urllib.request
import json
import time

def check_url(url, desc):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "DigitalThreadVerifier/1.0"})
        with urllib.request.urlopen(req, timeout=5) as res:
            code = res.getcode()
            body = res.read().decode('utf-8')
            parsed = json.loads(body)
            print(f"[OK] {desc} (Status {code}): Keys = {list(parsed.keys()) if isinstance(parsed, dict) else len(parsed)}")
            return parsed
    except Exception as e:
        print(f"[FAIL] {desc}: {e}")
        return None

def post_json(url, data, desc):
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode('utf-8'),
            headers={"Content-Type": "application/json", "User-Agent": "DigitalThreadVerifier/1.0"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=5) as res:
            code = res.getcode()
            body = res.read().decode('utf-8')
            parsed = json.loads(body)
            print(f"[OK] {desc} (Status {code}): Keys = {list(parsed.keys()) if isinstance(parsed, dict) else len(parsed)}")
            return parsed
    except Exception as e:
        print(f"[FAIL] {desc}: {e}")
        return None

if __name__ == "__main__":
    time.sleep(1.0)
    print("\n--- 1. VERIFYING EXISTING CORE & DRIFT APIS ---")
    check_url("http://127.0.0.1:8000/api/status", "Core Status API")
    check_url("http://127.0.0.1:8000/api/plcs", "PLCs List API")
    check_url("http://127.0.0.1:8000/api/drift/summary", "Drift Summary API")

    print("\n--- 2. VERIFYING ASSET DIGITAL THREAD APIS ---")
    assets_data = check_url("http://127.0.0.1:8000/api/assets", "Asset Catalog API")
    check_url("http://127.0.0.1:8000/api/assets/COMP-001", "Asset Details API")
    check_url("http://127.0.0.1:8000/api/assets/COMP-001/components", "Asset Components API")
    check_url("http://127.0.0.1:8000/api/assets/COMP-001/sensors", "Asset Sensors API")
    check_url("http://127.0.0.1:8000/api/assets/COMP-001/health", "Asset Health Snapshot API")
    check_url("http://127.0.0.1:8000/api/assets/COMP-001/timeline", "Asset Timeline API")
    check_url("http://127.0.0.1:8000/api/assets/COMP-001/maintenance", "Asset Maintenance History API")

    print("\n--- 3. VERIFYING MAINTENANCE & CLOSED-LOOP OUTCOME POST APIS ---")
    new_maint = post_json(
        "http://127.0.0.1:8000/api/assets/COMP-001/maintenance",
        {
            "maintenance_type": "Bearing Lubrication & Inspection",
            "reason": "Vibration harmonic detected",
            "technician": "Verifier Script",
            "before_health": 80.0,
            "before_rul": 90,
            "downtime_hours": 1.5,
            "cost": 300.0
        },
        "Create Maintenance Record API"
    )

    if new_maint and "maintenance_id" in new_maint:
        m_id = new_maint["maintenance_id"]
        post_json(
            f"http://127.0.0.1:8000/api/assets/COMP-001/maintenance/{m_id}/outcome",
            {
                "after_health": 99.0,
                "after_rul": 248,
                "notes": "Post-maintenance verification confirmed healthy operating state."
            },
            "Record Maintenance Outcome API"
        )
