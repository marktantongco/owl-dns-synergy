#!/usr/bin/env python3
"""Stealth browser daemon v2 — HTTP control instead of FIFO.

Control:  curl "http://127.0.0.1:18899/cmd?name=open&arg=<url>"
          curl "http://127.0.0.1:18899/cmd?name=shot&arg=/abs/path.png"
          curl "http://127.0.0.1:18899/cmd?name=click&arg=786,330"
          curl "http://127.0.0.1:18899/cmd?name=type&arg=css:::text"
          curl "http://127.0.0.1:18899/cmd?name=quit"
Output:   JSON {ok, result} — command outputs in `result`.

Stealth: headed Chromium under Xvfb, --disable-blink-features=AutomationControlled,
persistent profile, locale en-US, TZ Asia/Hong_Kong, init-script masks.
Capture: responses matching token-exchange endpoints -> captured_responses.jsonl
"""
import os, sys, json, time, random, threading, queue as q
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, unquote

BASE = "/home/z/my-project/scripts"
OUT_LOG = f"{BASE}/browser_out.log"
CAPTURE = f"{BASE}/captured_responses.jsonl"
PROFILE = f"{BASE}/browser_profile"
PORT = 18899

CMDQ = q.Queue()

def log(msg):
    with open(OUT_LOG, "a") as f:
        f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")

STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
window.chrome = window.chrome || {runtime: {}, loadTimes: () => {}, csi: () => {}};
try {
  const gp = WebGLRenderingContext.prototype.getParameter;
  WebGLRenderingContext.prototype.getParameter = function(p) {
    if (p === 37445) return 'Intel Inc.';
    if (p === 37446) return 'Intel Iris OpenGL Engine';
    return gp.call(this, p);
  };
} catch (e) {}
"""

WATCH_PATTERNS = ("google-oauth-login", "zai-oauth-login", "/userapi/v1/refresh", "oauth-callback")

class Browser:
    def __init__(self):
        self.pw = None
        self.ctx = None
        self.page = None
        self.captured = []

    def start(self):
        from playwright.sync_api import sync_playwright
        self.pw = sync_playwright().start()
        self.ctx = self.pw.chromium.launch_persistent_context(
            user_data_dir=PROFILE,
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-first-run", "--no-default-browser-check",
                "--disable-infobars", "--window-size=1366,850",
                "--lang=en-US",
                "--disable-features=IsolateOrigins,site-per-process",
            ],
            locale="en-US",
            timezone_id="Asia/Hong_Kong",
            viewport=None,
        )
        self.ctx.add_init_script(STEALTH_JS)
        self.page = self.ctx.pages[0] if self.ctx.pages else self.ctx.new_page()
        self.page.set_default_timeout(45000)
        self.page.on("response", self._on_response)
        log("daemon v2 started (headed, profile=%s)" % PROFILE)

    def _on_response(self, resp):
        try:
            url = resp.url
            if not any(p in url for p in WATCH_PATTERNS):
                return
            body = ""
            try:
                body = resp.text()
            except Exception:
                pass
            rec = {"ts": time.time(), "url": url[:300], "status": resp.status,
                   "body": body[:5000]}
            self.captured.append(rec)
            with open(CAPTURE, "a") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            log(f"CAPTURED {resp.status} {url[:130]}")
        except Exception as e:
            log(f"capture error: {e}")

    def human_type(self, selector, text):
        el = self.page.locator(selector).first
        el.click()
        time.sleep(0.3)
        self.page.keyboard.type(text, delay=random.randint(50, 120))
        time.sleep(0.4)

    def execute(self, name, arg):
        p = self.page
        if name == "open":
            p.goto(arg, wait_until="domcontentloaded", timeout=60000)
            time.sleep(2)
            return f"URL: {p.url}"
        if name == "shot":
            p.screenshot(path=arg)
            return f"SHOT {arg}"
        if name == "click":
            x, y = [int(v) for v in arg.split(",")]
            p.mouse.move(x + random.uniform(-2, 2), y + random.uniform(-2, 2))
            time.sleep(random.uniform(0.15, 0.4))
            p.mouse.down(); time.sleep(random.uniform(0.05, 0.12)); p.mouse.up()
            return f"CLICKED {x},{y}"
        if name == "type":
            sel, _, text = arg.partition(":::")
            self.human_type(sel, text)
            return "TYPED"
        if name == "press":
            p.keyboard.press(arg)
            return f"PRESSED {arg}"
        if name == "wait":
            time.sleep(float(arg) / 1000.0)
            return "WAITED"
        if name == "waitcss":
            sel, _, ms = arg.partition(":::")
            p.wait_for_selector(sel, state="visible",
                                timeout=int(ms) if ms else 30000)
            return "CSS_OK"
        if name == "eval":
            res = p.evaluate(arg)
            return json.dumps(res, ensure_ascii=False)[:3000]
        if name == "url":
            return p.url
        if name == "cookies":
            cs = self.ctx.cookies()
            names = [c["name"] for c in cs
                     if "google" in c["domain"] or "autoglm" in c["domain"]]
            return f"{len(cs)} total; relevant: {names[:40]}"
        if name == "lslocal":
            return p.evaluate("JSON.stringify(Object.keys(localStorage))")
        if name == "getlocal":
            res = p.evaluate(f"localStorage.getItem({json.dumps(arg)})") or "null"
            return res[:4000]
        if name == "watch":
            lines = [f"CAPTURED_N: {len(self.captured)}"]
            for r in self.captured:
                lines.append(f"  {r['status']} {r['url'][:100]}")
            return "\n".join(lines)
        if name == "capturedata":
            return json.dumps(self.captured[-5:], ensure_ascii=False)[:6000]
        if name == "quit":
            try:
                self.ctx.close(); self.pw.stop()
            except Exception:
                pass
            json.dumps({"ok": True, "result": "BYE"})
            os._exit(0)
        return f"UNKNOWN CMD {name}"

B = Browser()

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path != "/cmd":
            self._send(404, {"ok": False, "error": "not found"})
            return
        qs = parse_qs(parsed.query)
        name = (qs.get("name") or [""])[0]
        arg = unquote((qs.get("arg") or [""])[0])
        if not name:
            self._send(400, {"ok": False, "error": "missing name"})
            return
        done = threading.Event()
        box = {}
        CMDQ.put((name, arg, box, done))
        if not done.wait(150):
            self._send(504, {"ok": False, "error": "command timeout"})
            return
        self._send(200, {"ok": box.get("ok", False), "result": box.get("result", "")})

    def _send(self, code, obj):
        try:
            data = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception:
            pass

def main():
    os.makedirs(BASE, exist_ok=True)
    B.start()
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    log(f"control http://127.0.0.1:{PORT}/cmd ready")
    print(f"READY http://127.0.0.1:{PORT}/cmd", flush=True)
    # Playwright greenlet owns this thread: execute all page commands here
    while True:
        name, arg, box, done = CMDQ.get()
        try:
            box["result"] = B.execute(name, arg)
            box["ok"] = True
        except Exception as e:
            box["ok"] = False
            box["result"] = f"ERROR: {str(e)[:400]}"
        log(f"cmd {name} {arg[:60]} -> ok={box.get('ok')}")
        done.set()

if __name__ == "__main__":
    main()
