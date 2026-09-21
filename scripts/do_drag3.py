#!/usr/bin/env python3
"""Drag v3: calibrated to piece-x target using DOM ground truth reads with
settle waits. Reads piece via src-contains selector (class changes mid-drag)."""
import json
import random
import subprocess
import sys
import time

TARGET_PIECE_X = 68.0
SLIDER = (510.0, 575.5)
BG_X = 490.0


def ab(*args, timeout=30):
    r = subprocess.run(["agent-browser", *args], capture_output=True,
                       text=True, timeout=timeout)
    return (r.stdout + r.stderr).strip()


def state():
    out = ab("eval", "JSON.stringify((() => { const p = "
             "[...document.querySelectorAll('img')].find(i=>(i.src||'')"
             ".includes('bitwise')); const s = "
             "document.getElementById('aliyunCaptcha-sliding-slider'); "
             "return {pieceX: p ? +p.getBoundingClientRect().x.toFixed(2) : "
             "null, sliderLeft: s ? s.style.left : null}; })())")
    try:
        return json.loads(json.loads(out))
    except Exception:
        return {"raw": out[:150]}


def main():
    random.seed(6868)
    s0 = state()
    print("rest:", s0)
    if s0.get("pieceX") is None:
        print("piece img missing — abort")
        sys.exit(1)

    ab("mouse", "move", "510", "575")
    time.sleep(0.2)
    ab("mouse", "down", "left")
    time.sleep(0.3)

    # calibration +30 in 5px steps
    x = 510.0
    for i in range(6):
        x += 5
        ab("mouse", "move", f"{x:.0f}", "576" if i % 2 else "575")
        time.sleep(0.08)
    time.sleep(1.1)
    s1 = state()
    print("after +30:", s1)
    disp = s1["pieceX"] - s0["pieceX"]
    ratio = disp / 30.0
    print(f"piece disp={disp:.2f} ratio={ratio:.4f} sliderLeft={s1.get('sliderLeft')}")
    if not (0.7 <= ratio <= 1.3):
        print("ratio out of band — aborting")
        ab("mouse", "up", "left")
        sys.exit(2)

    target_handle_x = 510.0 + (TARGET_PIECE_X - disp) / ratio
    print(f"target handle x={target_handle_x:.1f} remaining="
          f"{target_handle_x - x:.1f}")

    remaining = target_handle_x - x
    n = 20
    prev = 0.0
    for i in range(n):
        frac = (i + 1) / n
        ease = 1 - (1 - frac) ** 2
        cur = remaining * ease
        dx = cur - prev
        prev = cur
        x += dx
        jy = random.choice((-1, 0, 0, 1))
        ab("mouse", "move", f"{x:.1f}", f"{575 + jy}")
        time.sleep(random.uniform(0.02, 0.07))
    ab("mouse", "move", f"{x:.1f}", "575")
    time.sleep(1.0)
    s2 = state()
    print("pre-release:", s2)
    print(f"piece at {s2['pieceX'] - BG_X:.1f} (target {TARGET_PIECE_X})")
    ab("mouse", "up", "left")
    time.sleep(2.5)
    print("post-release:", state())
    snap = ab("snapshot", "-i", "-c")
    print(snap[:700])


if __name__ == "__main__":
    main()
