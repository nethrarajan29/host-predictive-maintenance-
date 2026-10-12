import subprocess
import time
import urllib.request
import json
import os

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
if not os.path.exists(CHROME_PATH):
    CHROME_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

# Launch Chrome in headless mode with remote debugging on port 9222
cmd = [
    CHROME_PATH,
    "--headless=new",
    "--remote-debugging-port=9222",
    "--disable-gpu",
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "http://127.0.0.1:8000"
]

proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
time.sleep(2.5)

try:
    # Query Chrome Debugging API
    version_res = urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=5.0)
    tabs = json.loads(version_res.read().decode())
    print("Open tabs in Chrome:", len(tabs))
    target_tab = tabs[0]
    ws_url = target_tab.get("webSocketDebuggerUrl")
    print("Target WebSocket:", ws_url)
    
except Exception as e:
    print("Error querying Chrome DevTools:", e)
finally:
    try:
        proc.terminate()
        proc.kill()
    except Exception:
        pass
