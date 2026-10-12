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

async def test_page_render(url):
    print(f"\n=======================================================")
    print(f"  TESTING BROWSER RENDER -> {url}")
    print(f"=======================================================")
    
    cmd = [
        CHROME_PATH,
        "--headless=new",
        "--remote-debugging-port=9333",
        "--disable-gpu",
        "--no-sandbox",
        "--disable-extensions",
        url
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    await asyncio.sleep(2.5)

    try:
        tabs_res = urllib.request.urlopen("http://127.0.0.1:9333/json", timeout=5.0)
        tabs = json.loads(tabs_res.read().decode())
        page_tabs = [t for t in tabs if t.get("type") == "page"]
        if not page_tabs:
            print("No page tabs found!")
            return
        target_tab = page_tabs[0]
        ws_url = target_tab["webSocketDebuggerUrl"]

        async with websockets.connect(ws_url) as ws:
            await ws.send(json.dumps({"id": 1, "method": "Runtime.enable"}))
            await ws.send(json.dumps({"id": 2, "method": "Log.enable"}))
            await ws.send(json.dumps({"id": 3, "method": "Console.enable"}))
            await ws.send(json.dumps({"id": 4, "method": "Page.enable"}))
            
            # Reload page to capture all initial script evaluations and errors
            await ws.send(json.dumps({"id": 5, "method": "Page.reload"}))

            console_messages = []
            exceptions = []

            start_t = time.time()
            while time.time() - start_t < 3.5:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=0.3)
                    data = json.loads(raw)
                    method = data.get("method", "")
                    if method == "Runtime.exceptionThrown":
                        exceptions.append(data.get("params", {}).get("exceptionDetails", {}))
                    elif method == "Runtime.consoleAPICalled":
                        params = data.get("params", {})
                        args = [str(a.get("value", a.get("description", ""))) for a in params.get("args", [])]
                        console_messages.append(f"[{params.get('type')}] {' '.join(args)}")
                    elif method == "Log.entryAdded":
                        entry = data.get("params", {}).get("entry", {})
                        console_messages.append(f"[Log:{entry.get('level')}] {entry.get('text')}")
                except asyncio.TimeoutError:
                    pass

            # Evaluate DOM
            eval_payload = {
                "id": 50,
                "method": "Runtime.evaluate",
                "params": {
                    "expression": "(() => { const r = document.getElementById('root'); return JSON.stringify({ rootChildNodes: r ? r.childNodes.length : 0, rootText: r ? r.innerText : 'NO_ROOT', rootHtml: r ? r.innerHTML.substring(0, 500) : '' }); })()",
                    "returnByValue": True
                }
            }
            await ws.send(json.dumps(eval_payload))
            res_raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
            res_val = json.loads(res_raw).get("result", {}).get("result", {}).get("value", "{}")
            dom_info = json.loads(res_val) if isinstance(res_val, str) else res_val

            print("\n--- BROWSER DOM STATE ---")
            print("Root Child Nodes:", dom_info.get("rootChildNodes"))
            print("Root Text (first 300 chars):", dom_info.get("rootText", "")[:300])
            print("Root HTML Preview:", dom_info.get("rootHtml", "")[:300])

            print(f"\n--- CONSOLE LOGS ({len(console_messages)}) ---")
            for c in console_messages:
                print(" ", c)

            print(f"\n--- EXCEPTIONS ({len(exceptions)}) ---")
            for ex in exceptions:
                print("  EXCEPTION:", ex.get("text"), ex.get("exception", {}).get("description"))

    finally:
        try:
            proc.terminate()
            proc.kill()
        except Exception:
            pass

if __name__ == "__main__":
    asyncio.run(test_page_render("http://127.0.0.1:8000/"))
    asyncio.run(test_page_render("http://127.0.0.1:5173/"))
