#!/usr/bin/env python3
"""Stealth browser daemon for the AutoClaw/autoglm.ai login flow.

Engine-level stealth:
  - headed Chromium under Xvfb (real window, real Chrome UA, no Headless*)
  - --disable-blink-features=AutomationControlled  -> navigator.webdriver gone
  - persistent profile (cookie history accumulates across attempts)
  - locale en-US, timezone Asia/Hong_Kong (matches Alibaba-HK egress IP)
  - init scripts: chrome runtime, plugins, languages, WebGL vendor

Token capture:
  - every response matching google-oauth-login / zai-oauth-login / v1/refresh
    is saved (url, status, JSON body) -> captured_responses.jsonl

Control: command FIFO  /home/z/my-project/scripts/browser_cmd
Output:  log file       /home/z/my-project/scripts/browser_out.log

Commands (one per line):
  open <url>            goto url (domcontentloaded)
  shot <abs-path>       viewport screenshot
  click <x> <y>         mouse click at viewport coords
  move <x> <y>          mouse move
  type <css> <text>     humanized typing into css selector
  press <key>           keyboard press (Enter, Tab, ...)
  wait <ms>             sleep
  waitcss <css> <ms>    wait for selector (visible)
  eval <js>             evaluate JS, print result (single line, no newlines)
  url                   print current URL
  cookies               print cookie count + names for current domain
  lslocal               dump localStorage keys for current origin
  getlocal <key>        print localStorage[key]
  watch                 print captured token responses so far
  quit                  close browser and exit
"""
import asyncio, os, sys, time, json, random, re

BASE = "/home/z/my-project/scripts"
CMD_FIFO = f"{BASE}/browser_cmd"
OUT_LOG = f"{BASE}/browser_out.log"
CAPTURE = f"{BASE}/captured_responses.jsonl"
PROFILE = f"{BASE}/browser_profile"

def log(msg):
    with open(OUT_LOG, "a") as f:
        f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")

STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
window.chrome = window.chrome || {runtime: {}, loadTimes: () => {}, csi: () => {}};
const _q = QueryInterfaceSVG = undefined;
try {
  const getParams = WebGLRenderingContext.prototype.getParameter;
  WebGLRenderingContext.prototype.getParameter = function(p) {
    if (p === 37445) return 'Intel Inc.';
    if (p === 37446) return 'Intel Iris OpenGL Engine';
    return getParams.call(this, p);
  };
} catch (e) {}
"""

WATCH_PATTERNS = ("google-oauth-login", "zai-oauth-login", "/userapi/v1/refresh",
                  "oauth-callback", "token")

class Daemon:
    def __init__(self):
        self.pw = None
        self.ctx = None
        self.page = None
        self.captured = []

    async def start(self):
        from playwright.async_api import async_playwright
        self.pw = await async_playwright().start()
        self.ctx = await self.pw.chromium.launch_persistent_context(
            user_data_dir=PROFILE,
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-infobars",
                "--window-size=1366,850",
                "--lang=en-US",
                "--disable-features=IsolateOrigins,site-per-process",
            ],
            locale="en-US",
            timezone_id="Asia/Hong_Kong",
            viewport=None,
        )
        await self.ctx.add_init_script(STEALTH_JS)
        self.page = self.ctx.pages[0] if self.ctx.pages else await self.ctx.new_page()
        self.page.set_default_timeout(45000)
        self.page.on("response", self._on_response)
        log("daemon started (headed chromium, profile=%s)" % PROFILE)

    async def _on_response(self, resp):
        try:
            url = resp.url
            if not any(p in url for p in WATCH_PATTERNS):
                return
            if "fengkongcloud" in url or "volccdn" in url:
                return
            body = ""
            try:
                body = await resp.text()
            except Exception:
                pass
            rec = {"ts": time.time(), "url": url[:300],
                   "status": resp.status, "body": body[:4000]}
            self.captured.append(rec)
            with open(CAPTURE, "a") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            log(f"CAPTURED {resp.status} {url[:120]}")
        except Exception as e:
            log(f"capture error: {e}")

    async def human_type(self, selector, text):
        el = self.page.locator(selector).first
        await el.click()
        await asyncio.sleep(0.3)
        for ch in text:
            await el.type(ch, delay=random.randint(40, 110))
            if random.random() < 0.08:
                await asyncio.sleep(random.uniform(0.2, 0.5))
        await asyncio.sleep(0.3)

    async def handle(self, line):
        parts = line.strip().split(" ", 2)
        if not parts or not parts[0]:
            return
        cmd, args = parts[0], parts[1:]
        log(f"cmd: {line.strip()[:120]}")
        if cmd == "open":
            await self.page.goto(args[0], wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(2)
            print(f"URL: {self.page.url}")
        elif cmd == "shot":
            await self.page.screenshot(path=args[0])
            print(f"SHOT {args[0]}")
        elif cmd == "click":
            x, y = int(args[0]), int(args[1])
            await self.page.mouse.move(x + random.uniform(-2, 2), y + random.uniform(-2, 2))
            await asyncio.sleep(random.uniform(0.15, 0.4))
            await self.page.mouse.down()
            await asyncio.sleep(random.uniform(0.04, 0.12))
            await self.page.mouse.up()
            print(f"CLICKED {x},{y}")
        elif cmd == "move":
            await self.page.mouse.move(int(args[0]), int(args[1]))
            print("MOVED")
        elif cmd == "type":
            await self.human_type(args[0], args[1] if len(args) > 1 else "")
            print("TYPED")
        elif cmd == "press":
            await self.page.keyboard.press(args[0])
            print(f"PRESSED {args[0]}")
        elif cmd == "wait":
            await asyncio.sleep(int(args[0]) / 1000)
            print("WAITED")
        elif cmd == "waitcss":
            await self.page.wait_for_selector(args[0], state="visible",
                                              timeout=int(args[1]) if len(args) > 1 else 30000)
            print("CSS_OK")
        elif cmd == "eval":
            res = await self.page.evaluate(args[0])
            print(f"EVAL: {json.dumps(res, ensure_ascii=False)[:2000]}")
        elif cmd == "url":
            print(f"URL: {self.page.url}")
        elif cmd == "cookies":
            cookies = await self.ctx.cookies()
            names = [c["name"] for c in cookies if "google" in c["domain"] or "autoglm" in c["domain"]]
            print(f"COOKIES: {len(cookies)} total; relevant: {names[:40]}")
        elif cmd == "lslocal":
            res = await self.page.evaluate("JSON.stringify(Object.keys(localStorage))")
            print(f"LOCALKEYS: {res}")
        elif cmd == "getlocal":
            res = await self.page.evaluate(f"localStorage.getItem({json.dumps(args[0])})")
            print(f"LOCAL: {res[:2400] if res else 'null'}")
        elif cmd == "watch":
            print(f"CAPTURED_N: {len(self.captured)}")
            for r in self.captured:
                print(f"  {r['status']} {r['url'][:100]}")
        elif cmd == "quit":
            await self.ctx.close()
            await self.pw.stop()
            print("BYE")
            os._exit(0)
        else:
            print(f"UNKNOWN {cmd}")

async def main():
    os.makedirs(BASE, exist_ok=True)
    if not os.path.exists(CMD_FIFO):
        os.mkfifo(CMD_FIFO)
    d = Daemon()
    await d.start()
    print("READY")
    while True:
        try:
            fd = os.open(CMD_FIFO, os.O_RDONLY | os.O_NONBLOCK)
        except OSError:
            await asyncio.sleep(0.2)
            continue
        try:
            data = b""
            while True:
                try:
                    chunk = os.read(fd, 65536)
                except BlockingIOError:
                    break
                if not chunk:
                    break
                data += chunk
            if data:
                for line in data.decode("utf-8", "ignore").splitlines():
                    if line.strip():
                        try:
                            await d.handle(line)
                        except Exception as e:
                            print(f"ERROR: {str(e)[:300]}")
                            log(f"cmd error: {e}")
        finally:
            os.close(fd)
        await asyncio.sleep(0.3)

if __name__ == "__main__":
    asyncio.run(main())
