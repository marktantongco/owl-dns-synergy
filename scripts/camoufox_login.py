#!/usr/bin/env python3
"""Camoufox login driver (Task 17-c) — FIFO-commanded browser session.

Anti-detect Firefox (Camoufox) to pass Google's "browser not secure" wall,
driving: autoglm.ai login -> icon captcha (operator-solved via screenshots)
-> chat.z.ai SSO -> Google OAuth (spare account) -> token capture.

Protocol:
  commands : JSON lines written to /home/z/my-project/scripts/.camoufox_fifo
  results  : JSON lines appended to /home/z/my-project/scripts/.camoufox_log.jsonl
  network  : all responses whose URL matches oauth/token/userapi/auth are
             captured (URL, status, body head) into CAPTURES, dumped on demand.

Commands:
  {"cmd":"goto","url":...}            {"cmd":"url"}
  {"cmd":"click","selector":...}      {"cmd":"click_text","text":...}
  {"cmd":"click_points","points":[[x,y],...]}   (humanized mouse)
  {"cmd":"fill","selector":...,"value":...}
  {"cmd":"type_slow","selector":...,"value":...,"delay":100}
  {"cmd":"press","key":...}           {"cmd":"wait","ms":...}
  {"cmd":"screenshot","path":...,"clip":[x,y,w,h](opt)}
  {"cmd":"eval","js":...}             {"cmd":"snapshot"}
  {"cmd":"captures"}                  {"cmd":"storage","origin":...}
  {"cmd":"mouse_move","x":...,"y":...} {"cmd":"quit"}
"""
import json
import os
import random
import selectors
import sys
import time

FIFO = "/home/z/my-project/scripts/.camoufox_fifo"
LOG = "/home/z/my-project/scripts/.camoufox_log.jsonl"

logf = open(LOG, "a", buffering=1)
CAPTURES = []
CAPTURE_PAT = ("oauth", "token", "userapi", "/auth", "login", "signin")


def emit(obj):
    logf.write(json.dumps(obj, ensure_ascii=False) + "\n")


def main():
    if os.path.exists(FIFO):
        os.unlink(FIFO)
    os.mkfifo(FIFO)

    from camoufox.sync_api import Camoufox
    emit({"ev": "boot", "ts": time.time()})

    with Camoufox(headless="virtual", humanize=True, geoip=False) as browser:
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        def on_response(resp):
            try:
                u = resp.url
                if any(p in u for p in CAPTURE_PAT):
                    body = ""
                    try:
                        body = resp.text()[:4000]
                    except Exception:
                        pass
                    CAPTURES.append({"url": u, "status": resp.status,
                                     "body": body, "ts": time.time()})
                    emit({"ev": "resp", "url": u[:180],
                          "status": resp.status, "body_head": body[:500]})
            except Exception:
                pass

        page.on("response", on_response)
        emit({"ev": "ready"})

        sel = selectors.DefaultSelector()
        # O_RDWR self-writer: select() blocks properly (never EOF-spins)
        fd = os.open(FIFO, os.O_RDWR | os.O_NONBLOCK)
        sel.register(fd, selectors.EVENT_READ)
        running = True
        last_hb = time.time()
        while running:
            for key, _ in sel.select(timeout=0.5):
                raw = os.read(fd, 65536)
                if not raw:
                    continue
                for line in raw.decode("utf-8", "ignore").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        cmd = json.loads(line)
                    except Exception as e:
                        emit({"ev": "badcmd", "err": str(e)})
                        continue
                    try:
                        c = cmd.get("cmd")
                        if c == "goto":
                            page.goto(cmd["url"], timeout=45000,
                                      wait_until="domcontentloaded")
                            emit({"ev": "ok", "cmd": c, "url": page.url})
                        elif c == "url":
                            emit({"ev": "ok", "cmd": c, "url": page.url})
                        elif c == "click":
                            page.click(cmd["selector"], timeout=8000)
                            emit({"ev": "ok", "cmd": c})
                        elif c == "click_text":
                            page.get_by_text(cmd["text"],
                                             exact=cmd.get("exact", False)
                                             ).first.click(timeout=8000)
                            emit({"ev": "ok", "cmd": c})
                        elif c == "click_points":
                            pts = cmd["points"]
                            for (x, y) in pts:
                                # humanized approach: 2-stage move + click
                                page.mouse.move(x - random.randint(20, 45),
                                                y + random.randint(12, 30))
                                time.sleep(random.uniform(0.15, 0.4))
                                page.mouse.move(x, y)
                                time.sleep(random.uniform(0.25, 0.5))
                                page.mouse.down()
                                time.sleep(random.uniform(0.06, 0.14))
                                page.mouse.up()
                                time.sleep(random.uniform(0.5, 0.9))
                                emit({"ev": "clicked", "x": x, "y": y})
                        elif c == "fill":
                            page.fill(cmd["selector"], cmd["value"],
                                      timeout=8000)
                            emit({"ev": "ok", "cmd": c})
                        elif c == "type_slow":
                            page.click(cmd["selector"], timeout=8000)
                            d = cmd.get("delay", 90)
                            page.type(cmd["selector"], cmd["value"],
                                      delay=d, timeout=30000)
                            emit({"ev": "ok", "cmd": c})
                        elif c == "press":
                            page.keyboard.press(cmd["key"])
                            emit({"ev": "ok", "cmd": c})
                        elif c == "mouse_move":
                            page.mouse.move(cmd["x"], cmd["y"])
                            emit({"ev": "ok", "cmd": c})
                        elif c == "wait":
                            time.sleep(cmd.get("ms", 1000) / 1000.0)
                            emit({"ev": "ok", "cmd": c})
                        elif c == "screenshot":
                            path = cmd["path"]
                            clip = cmd.get("clip")
                            kw = {"clip": {"x": clip[0], "y": clip[1],
                                           "width": clip[2],
                                           "height": clip[3]}} if clip else {}
                            page.screenshot(path=path, **kw)
                            emit({"ev": "ok", "cmd": c, "path": path})
                        elif c == "eval":
                            val = page.evaluate(cmd["js"])
                            emit({"ev": "ok", "cmd": c, "value": val})
                        elif c == "snapshot":
                            items = page.locator(
                                "button, a, input, [role=button], "
                                "[onclick]").all()
                            out = []
                            for el in items[:40]:
                                try:
                                    out.append({
                                        "tag": el.evaluate(
                                            "e => e.tagName.toLowerCase()"),
                                        "text": (el.inner_text() or "")[:60],
                                        "sel": el.evaluate(
                                            "e => {const r=e.getBoundingClientRect();"
                                            "return [Math.round(r.x+r.width/2),"
                                            "Math.round(r.y+r.height/2)];}")})
                                except Exception:
                                    pass
                            emit({"ev": "ok", "cmd": c, "elements": out})
                        elif c == "captures":
                            emit({"ev": "ok", "cmd": c,
                                  "captures": CAPTURES[-30:]})
                        elif c == "storage":
                            origin = cmd.get("origin",
                                             "https://autoglm.ai")
                            # switch to a tab of that origin if open
                            target = None
                            for pg in ctx.pages:
                                if origin in pg.url:
                                    target = pg
                                    break
                            target = target or page
                            data = target.evaluate(
                                "() => JSON.stringify(localStorage)")
                            emit({"ev": "ok", "cmd": c, "url": target.url,
                                  "storage": json.loads(data) if data
                                  else {}})
                        elif c == "tabs":
                            emit({"ev": "ok", "cmd": c,
                                  "pages": [p.url for p in ctx.pages]})
                        elif c == "quit":
                            emit({"ev": "bye"})
                            running = False
                            break
                        else:
                            emit({"ev": "unknown", "cmd": c})
                    except Exception as e:
                        emit({"ev": "err", "cmd": cmd.get("cmd"),
                              "err": str(e)[:300]})
            if not running:
                break
            if time.time() - last_hb > 10:
                last_hb = time.time()
                emit({"ev": "hb", "url": page.url[:120],
                      "pages": len(ctx.pages)})
    emit({"ev": "exit"})


if __name__ == "__main__":
    main()
