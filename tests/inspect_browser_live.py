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

async def inspect_url(target_url):
    print(f"\n=======================================================")
    print(f"  LAUNCHING HEADLESS CHROME -> {target_url}")
    print(f"=======================================================")
    
    cmd = [
        CHROME_PATH,
        "--headless=new",
        "--remote-debugging-port=9222",
        "--disable-gpu",
        "--no-sandbox",
        "--disable-extensions",
        "about:blank"
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    await asyncio.sleep(2.0)

    try:
        tabs_res = urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=5.0)
        tabs = json.loads(tabs_res.read().decode())
        if not tabs:
            print("No tabs found")
            return
        ws_url = tabs[0]["webSocketDebuggerUrl"]
        print("Connected to CDP:", ws_url)

        async with websockets.connect(ws_url) as ws:
            # 1. Enable Runtime, Page, Network, Console
            msg_id = 1
            await ws.send(json.dumps({"id": 1, "method": "Runtime.enable"}))
            await ws.send(json.dumps({"id": 2, "method": "Page.enable"}))
            await ws.send(json.dumps({"id": 3, "method": "Network.enable"}))
            await ws.send(json.dumps({"id": 4, "method": "Console.enable"}))

            # 2. Navigate to target URL
            await ws.send(json.dumps({
                "id": 5,
                "method": "Page.navigate",
                "params": {"url": target_url}
            }))

            console_logs = []
            runtime_exceptions = []
            failed_requests = []
            page_loaded = False

            # Listen for events for 4 seconds
            start_t = time.time()
            while time.time() - start_t < 4.0:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=0.5)
                    data = json.loads(raw)
                    method = data.get("method", "")
                    
                    if method == "Runtime.exceptionThrown":
                        details = data.get("params", {}).get("exceptionDetails", {})
                        runtime_exceptions.append(details)
                    elif method == "Runtime.consoleAPICalled":
                        params = data.get("params", {})
                        args = [a.get("value", a.get("description", "")) for a in params.get("args", [])]
                        console_logs.append(f"[{params.get('type')}] {' '.join(str(x) for x in args)}")
                    elif method == "Network.responseReceived":
                        resp = data.get("params", {}).get("response", {})
                        status = resp.get("status")
                        url = resp.get("url")
                        if status >= 400:
                            failed_requests.append(f"HTTP {status} on {url}")
                    elif method == "Page.loadEventFired":
                        page_loaded = True
                except asyncio.TimeoutError:
                    pass

            # 3. Evaluate #root content
            eval_req = {
                "id": 100,
                "method": "Runtime.evaluate",
                "params": {
                    "expression": "JSON.stringify({ innerHTML: document.getElementById('root') ? document.getElementById('root').innerHTML : 'NO ROOT', title: document.title, bodyText: document.body.innerText })",
                    "returnByValue": True
                }
            }
            await ws.send(json.dumps(eval_req))
            dom_res = await asyncio.wait_for(ws.recv(), timeout=2.0)
            dom_data = json.loads(dom_res).get("result", {}).get("result", {}).get("value", "{}")
            dom_obj = json.loads(dom_data) if isinstance(dom_data, str) else dom_data

            print("\n--- RESULTS ---")
            print(f"Page Title: {dom_obj.get('title')}")
            print(f"Body Text Length: {len(dom_obj.get('bodyText', ''))} chars")
            print(f"Root innerHTML Length: {len(dom_obj.get('innerHTML', ''))} chars")
            if dom_obj.get('bodyText'):
                print(f"Rendered Body Snippet:\n{dom_obj.get('bodyText')[:400]}")

            print(f"\n--- CONSOLE LOGS ({len(console_logs)}) ---")
            for l in console_logs:
                print(" ", l)

            print(f"\n--- RUNTIME EXCEPTIONS ({len(runtime_exceptions)}) ---")
            for ex in runtime_exceptions:
                text = ex.get("text", "")
                ex_obj = ex.get("exception", {}).get("description", "")
                print(f"  EX: {text} -> {ex_obj}")

            print(f"\n--- FAILED REQUESTS ({len(failed_requests)}) ---")
            for req in failed_requests:
                print(" ", req)

    finally:
        try:
            proc.terminate()
            proc.kill()
        except Exception:
            pass

if __name__ == "__main__":
    asyncio.run(inspect_url("http://127.0.0.1:8000"))
    asyncio.run(inspect_url("http://127.0.0.1:5173"))
