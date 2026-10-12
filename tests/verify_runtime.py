import urllib.request
import re
import json

def check_url(url, label):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        res = urllib.request.urlopen(req, timeout=5.0)
        body = res.read()
        print(f"[PASS] {label} -> HTTP {res.status} ({len(body)} bytes)")
        return body
    except Exception as e:
        print(f"[FAIL] {label} -> {e}")
        return None

print("=== VERIFYING RUNTIME INTEGRATION ===")
html = check_url("http://127.0.0.1:8000/", "HTML Root")
check_url("http://127.0.0.1:8000/docs", "FastAPI Docs")
check_url("http://127.0.0.1:8000/api/status", "PredictX Status API")
check_url("http://127.0.0.1:8000/api/plcs", "PredictX PLCs API")
check_url("http://127.0.0.1:8000/api/current", "PredictX Current API")
check_url("http://127.0.0.1:8000/api/drift/summary", "Drift Summary API")
check_url("http://127.0.0.1:8000/api/drift/features", "Drift Features API")
check_url("http://127.0.0.1:8000/api/drift/predictions", "Drift Predictions API")
check_url("http://127.0.0.1:8000/api/drift/data-quality", "Drift Quality API")
check_url("http://127.0.0.1:8000/api/drift/history", "Drift History API")
check_url("http://127.0.0.1:8000/api/drift/alerts", "Drift Alerts API")
check_url("http://127.0.0.1:8000/api/drift/baseline", "Drift Baseline API")

if html:
    html_str = html.decode('utf-8', errors='ignore')
    js_match = re.search(r'src="(/assets/[^"]+\.js)"', html_str)
    css_match = re.search(r'href="(/assets/[^"]+\.css)"', html_str)
    if js_match:
        check_url("http://127.0.0.1:8000" + js_match.group(1), "Compiled JS Asset")
    if css_match:
        check_url("http://127.0.0.1:8000" + css_match.group(1), "Compiled CSS Asset")
