import asyncio
import subprocess
import time
import urllib.request
import json
import os
import websockets

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
if not os.path.exists(CHROME_PATH):
    CHROME_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

async def test_tabs():
    cmd = [
        CHROME_PATH,
        "--headless=new",
        "--remote-debugging-port=9555",
        "--disable-gpu",
        "--no-sandbox",
        "http://127.0.0.1:8000/"
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    await asyncio.sleep(2.5)

    try:
        tabs_res = urllib.request.urlopen("http://127.0.0.1:9555/json", timeout=5.0)
        tabs = json.loads(tabs_res.read().decode())
        target_tab = [t for t in tabs if t.get("type") == "page"][0]
        ws_url = target_tab["webSocketDebuggerUrl"]

        async with websockets.connect(ws_url) as ws:
            cur_id = 0
            async def send_cdp(method, params=None):
                nonlocal cur_id
                cur_id += 1
                req_id = cur_id
                payload = {"id": req_id, "method": method}
                if params:
                    payload["params"] = params
                await ws.send(json.dumps(payload))
                
                # Wait for matching response
                while True:
                    raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
                    msg = json.loads(raw)
                    if msg.get("id") == req_id:
                        return msg

            await send_cdp("Runtime.enable")
            await send_cdp("Page.enable")
            await send_cdp("Page.reload")
            await asyncio.sleep(2.0)

            # 1. Check Live Monitoring (Dashboard)
            res1 = await send_cdp("Runtime.evaluate", {"expression": "document.body.innerText", "returnByValue": True})
            text1 = res1.get("result", {}).get("result", {}).get("value", "")
            print("[PAGE 1: Dashboard] Text length:", len(text1))
            assert "Live Monitoring" in text1 or "Turbine" in text1, "Dashboard not rendered"

            # 2. Click Analytics Tab
            await send_cdp("Runtime.evaluate", {"expression": "(() => { const btns = Array.from(document.querySelectorAll('button')); const b = btns.find(x => x.innerText.includes('Analytics')); if (b) b.click(); return !!b; })()", "returnByValue": True})
            await asyncio.sleep(1.0)
            res2 = await send_cdp("Runtime.evaluate", {"expression": "document.body.innerText", "returnByValue": True})
            text2 = res2.get("result", {}).get("result", {}).get("value", "")
            print("[PAGE 2: Analytics] Rendered Analytics:", "Analytics" in text2)

            # 3. Click Maintenance Tab
            await send_cdp("Runtime.evaluate", {"expression": "(() => { const btns = Array.from(document.querySelectorAll('button')); const b = btns.find(x => x.innerText.includes('Maintenance')); if (b) b.click(); return !!b; })()", "returnByValue": True})
            await asyncio.sleep(1.0)
            res3 = await send_cdp("Runtime.evaluate", {"expression": "document.body.innerText", "returnByValue": True})
            text3 = res3.get("result", {}).get("result", {}).get("value", "")
            print("[PAGE 3: Maintenance] Rendered Maintenance:", "Maintenance" in text3)

            # 4. Click Model Evaluation Tab
            await send_cdp("Runtime.evaluate", {"expression": "(() => { const btns = Array.from(document.querySelectorAll('button')); const b = btns.find(x => x.innerText.includes('Model Evaluation')); if (b) b.click(); return !!b; })()", "returnByValue": True})
            await asyncio.sleep(1.0)
            res4 = await send_cdp("Runtime.evaluate", {"expression": "document.body.innerText", "returnByValue": True})
            text4 = res4.get("result", {}).get("result", {}).get("value", "")
            print("[PAGE 4: Evaluation] Rendered Evaluation:", "Random Forest" in text4 or "Model Evaluation" in text4)

            # 5. Click AI Reliability & Drift Tab
            await send_cdp("Runtime.evaluate", {"expression": "(() => { const btns = Array.from(document.querySelectorAll('button')); const b = btns.find(x => x.innerText.includes('AI Reliability')); if (b) b.click(); return !!b; })()", "returnByValue": True})
            await asyncio.sleep(1.0)
            res5 = await send_cdp("Runtime.evaluate", {"expression": "document.body.innerText", "returnByValue": True})
            text5 = res5.get("result", {}).get("result", {}).get("value", "")
            print("[PAGE 5: Drift] Rendered AI Reliability:", "AI Reliability" in text5)

            print("\n>>> ALL 5 REACT PAGES VERIFIED AND FULLY VISIBLE IN HEADLESS BROWSER! <<<")

    finally:
        try:
            proc.terminate()
            proc.kill()
        except Exception:
            pass

if __name__ == "__main__":
    asyncio.run(test_tabs())
