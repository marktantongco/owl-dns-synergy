#!/usr/bin/env python3
"""Fully automated captcha loop:
  extract puzzle -> detect hole geometrically (smooth run of piece width)
                 + shadow-model cross-check -> humanized drag -> verdict
  retry on failure (fresh puzzle each round). Stops on success.
"""
import base64
import json
import random
import subprocess
import sys
import time
import urllib.request

import cv2
import numpy as np

SLIDER_Y = 575
SLIDER_X0 = 510.0
MAX_ROUNDS = 6


def ab(*args, timeout=30):
    r = subprocess.run(["agent-browser", *[str(a) for a in args]],
                       capture_output=True, text=True, timeout=timeout)
    out = (r.stdout + r.stderr).strip()
    if "Usage:" in out or "rror" in out:
        raise RuntimeError(f"ab {args}: {out[:100]}")
    return out


def ev(js):
    out = ab("eval", f"JSON.stringify({js})")
    v = json.loads(out)
    if isinstance(v, str):        # CLI double-encodes
        v = json.loads(v)
    return v


def fwd(s):
    return 0.077 * s + 0.00355 * s * s


def inv(P):
    return (-0.077 + (0.077 ** 2 + 4 * 0.00355 * P) ** 0.5) / (2 * 0.00355)


def fetch_puzzle():
    d = ev('(() => { const b = document.querySelector("img.puzzle");'
           ' const p = document.getElementById("aliyunCaptcha-puzzle");'
           ' return {bg: b ? b.src : null, piece: p ? p.src : null}; })()')
    if not d.get("piece"):
        return None, None
    imgs = []
    for key in ("bg", "piece"):
        data = d[key]
        if data.startswith("data:"):
            raw = base64.b64decode(data.split(",", 1)[1])
        else:
            req = urllib.request.Request(data, headers={"User-Agent": "Mozilla/5.0"})
            raw = urllib.request.urlopen(req, timeout=15).read()
        imgs.append(raw)
    bg = cv2.imdecode(np.frombuffer(imgs[0], np.uint8), cv2.IMREAD_COLOR)
    piece = cv2.imdecode(np.frombuffer(imgs[1], np.uint8), cv2.IMREAD_UNCHANGED)
    return bg, piece


def solve(bg, piece):
    gray = cv2.cvtColor(bg, cv2.COLOR_BGR2GRAY).astype(np.float32)
    alpha = piece[:, :, 3]
    ys, xs = np.where(alpha > 128)
    py0, py1 = int(ys.min()), int(ys.max()) + 1
    px0, px1 = int(xs.min()), int(xs.max()) + 1
    H, W = py1 - py0, px1 - px0
    am = (alpha[py0:py1, px0:px1] > 128).astype(np.float32)

    # A) hole detection: smooth column runs of width ~W in the piece band
    lap = np.abs(cv2.Laplacian(gray, cv2.CV_32F))
    smooth = cv2.boxFilter(lap, -1, (5, 5)) < 6.0   # smooth columns
    holes = []
    for dy in (-14, -10, -6, 0, 6, 10, 14):
        gy = py0 + dy
        if gy < 5 or gy + H > 295:
            continue
        rowband = smooth[gy:gy + H]
        col_ok = rowband.mean(axis=0) > 0.85
        x = 45
        while x < 295 - W:
            if col_ok[x]:
                x2 = x
                while x2 < 295 and col_ok[x2]:
                    x2 += 1
                run = x2 - x
                if abs(run - W) <= 3:
                    holes.append((x + (run - W) // 2, gy))
                x = x2 + 1
            else:
                x += 1

    # B) shadow model
    med = cv2.medianBlur(gray.astype(np.uint8), 15).astype(np.float32)
    dark = np.clip(med - gray, 0, None)
    best_shadow = None
    for dy in range(-20, 21):
        gy = py0 + dy
        if gy < 5 or gy + H > 295:
            continue
        band = dark[gy:gy + H]
        for D in range(45, 256 - W):
            win = band[:, D:D + W]
            k = float((win * am).sum() / max((am * am).sum(), 1))
            if not (0.1 < k < 1.1):
                continue
            r = win - k * am
            sc = float((r * r).sum())
            if best_shadow is None or sc < best_shadow[0]:
                best_shadow = (sc, D, gy, k)

    # consensus
    verdict = {"W": W, "H": H, "py0": py0, "px0": px0,
               "holes": holes[:8], "shadow": best_shadow}
    cands = [h[0] for h in holes]
    if best_shadow and best_shadow[0] < 3000 and best_shadow[3] > 0.15:
        cands.append(best_shadow[1])
    if not cands:
        return None, verdict
    cands.sort()
    D = int(cands[len(cands) // 2])   # median
    verdict["D"] = D
    return D, verdict


def drag(D, rng):
    P = float(D)
    s_int = round(inv(P))
    land = fwd(s_int)
    print(f"  drag: D={D} slider={s_int} lands={land:.2f}")
    t0 = time.time()
    try:
        ax, ay = 690.0, 460.0
        for i in range(12):
            t_ = (i + 1) / 12.0
            ab("mouse", "move", int(round(ax + (510 - ax) * t_)),
               int(round(ay + (SLIDER_Y - ay) * t_)))
            time.sleep(rng.uniform(0.01, 0.03))
        ab("mouse", "move", 510, SLIDER_Y)
        time.sleep(rng.uniform(0.1, 0.2))
        ab("mouse", "down", "left")
        time.sleep(rng.uniform(0.1, 0.16))
        overshoot = rng.uniform(3, 6)
        s_peak = min(259, s_int + overshoot)
        wps = []
        cur = 0.0
        for frac in (0.4, 0.85, 1.0):
            goal = s_peak * frac
            while cur < goal - 0.5:
                step = rng.uniform(2, 9) * (1 if goal - cur > 6 else 0.5)
                cur = min(cur + step, goal)
                wps.append(cur)
        while cur < s_peak:
            cur = min(cur + rng.uniform(1, 3), s_peak)
            wps.append(cur)
        for k in range(3):
            wps.append(s_peak - (s_peak - s_int) * (k + 1) / 3.0)
        wps.append(s_int)
        for i, s in enumerate(wps):
            yj = rng.choices((-1, 0, 0, 0, 1), weights=(1, 4, 4, 4, 1))[0]
            ab("mouse", "move", int(round(SLIDER_X0 + s)), SLIDER_Y + yj)
            time.sleep(rng.uniform(0.006, 0.03) if i >= 3
                       else rng.uniform(0.02, 0.05))
        ab("mouse", "move", int(round(SLIDER_X0 + s_int)), SLIDER_Y)
        time.sleep(rng.uniform(0.12, 0.25))
    finally:
        try:
            pl = float(ev(
                'document.getElementById("aliyunCaptcha-puzzle").style.left'
            ).replace("px", ""))
            print(f"  landed piece={pl:.2f} elapsed={time.time()-t0:.1f}s")
        except Exception:
            print("  (piece read unavailable)")
        ab("mouse", "up", "left")


def main():
    rng = random.Random(int(time.time()))
    # hook XHR once
    ev('(() => { if (window.__vh2) return 1; const o = '
       'XMLHttpRequest.prototype.open; XMLHttpRequest.prototype.open = '
       'function(m,u){this.__u=u; return o.apply(this,arguments);}; '
       'const s = XMLHttpRequest.prototype.send; XMLHttpRequest.prototype.send '
       '= function(b){ this.addEventListener("load", function(){ if(this.__u && '
       'this.__u.includes("verify")){ (window.__vlog=window.__vlog||[]).push('
       'this.responseText); } }); return s.apply(this,arguments);}; '
       'window.__vh2=1; return 1; })()')
    n0 = len(ev("window.__vlog || []"))
    print(f"pre-existing verify entries: {n0}")

    for rnd in range(1, MAX_ROUNDS + 1):
        print(f"== round {rnd} ==")
        bg, piece = fetch_puzzle()
        if bg is None:
            print("  no puzzle in DOM — reopening captcha")
            ab("find", "text", "Click to start verification", "click")
            time.sleep(3)
            bg, piece = fetch_puzzle()
            if bg is None:
                continue
        D, info = solve(bg, piece)
        print(f"  verdict: {json.dumps(info)[:220]}")
        if D is None:
            print("  no verdict — refreshing captcha")
            try:
                ab("find", "text", "刷新验证码", "click")
            except Exception:
                pass
            time.sleep(2.5)
            continue
        drag(D, rng)
        time.sleep(2.0)
        log = ev("window.__vlog || []")
        if len(log) > n0:
            try:
                res = json.loads(log[-1])["Result"]
                print(f"  VERIFY: {res}")
                if res.get("VerifyResult") is True:
                    print("SUCCESS!")
                    return 0
            except Exception as e:
                print("  log parse err", e)
            n0 = len(log)
        else:
            print("  no verify call observed")
    print("exhausted rounds")
    return 1


if __name__ == "__main__":
    sys.exit(main())
