#!/usr/bin/env python3
"""Slider drag v2: slow calibration with settle time, then complete to target.
Reads both piece rect and slider transform for ground truth."""
import json
import random
import subprocess
import sys
import time

TARGET_PIECE_X = 177.0
SLIDER = (510.0, 575.5)


def ab(*args, timeout=30):
    r = subprocess.run(["agent-browser", *args], capture_output=True,
                       text=True, timeout=timeout)
    return (r.stdout + r.stderr).strip()


def rects():
    out = ab("eval", "JSON.stringify((() => { const p = "
             "[...document.querySelectorAll('img')].find(i=>i.width===60&&"
             "i.height===300); const s = document.querySelector('.slider-move'"
             "); const rb = el => { if (!el) return null; const b = "
             "el.getBoundingClientRect(); return {x: +b.x.toFixed(2), "
             "y: +b.y.toFixed(2)}; }; return {piece: rb(p), slider: rb(s), "
             "pieceTf: p.style.transform || null, sliderTf: s ? "
             "(s.style.transform || null) : null}; })())")
    try:
        return json.loads(json.loads(out))
    except Exception:
        return {"raw": out[:200]}


def main():
    random.seed(1771)
    print("== rest state ==")
    r0 = rects()
    print(json.dumps(r0))
    px0 = r0["piece"]["x"]
    sx0 = r0["slider"]["x"] if r0.get("slider") else None

    ab("mouse", "move", str(int(SLIDER[0])), str(int(SLIDER[1])))
    time.sleep(0.1)
    ab("mouse", "down", "left")
    time.sleep(0.25)

    # slow calibration: +30px in 6px steps (100ms apart)
    x, y = SLIDER
    for i in range(5):
        x += 6
        ab("mouse", "move", f"{x:.0f}", f"{y + (1 if i % 2 else -1)}")
        time.sleep(0.1)
    time.sleep(1.0)   # let any transition settle
    r1 = rects()
    print("after +30 (settled):", json.dumps(r1))
    pdisp = r1["piece"]["x"] - px0
    sdisp = (r1["slider"]["x"] - sx0) if sx0 is not None else None
    print(f"piece disp={pdisp:.2f}  slider disp={sdisp}  "
          f"ratio_piece={pdisp/30:.4f}")

    ratio = pdisp / 30.0
    if ratio <= 0.05 or ratio > 2:
        print("unusable ratio — aborting drag (will re-press)")
        ab("mouse", "up", "left")
        sys.exit(2)

    target_handle_x = SLIDER[0] + (TARGET_PIECE_X - pdisp) / ratio
    print(f"target handle x={target_handle_x:.1f} "
          f"(remaining {target_handle_x - x:.1f})")

    # human-like completion with ease-out + jitter
    remaining = target_handle_x - x
    n = 26
    prev = 0.0
    for i in range(n):
        frac = (i + 1) / n
        ease = 1 - (1 - frac) ** 2
        cur = remaining * ease
        dx = cur - prev
        prev = cur
        x += dx
        jy = random.choice((-2, -1, 0, 0, 1, 2))
        ab("mouse", "move", f"{x:.1f}", f"{y + jy}")
        time.sleep(random.uniform(0.015, 0.06))
    ab("mouse", "move", f"{x:.1f}", f"{y}")
    time.sleep(1.0)
    r2 = rects()
    print("pre-release (settled):", json.dumps(r2))
    final_piece = r2["piece"]["x"] - px0
    print(f"piece will land at {final_piece:.1f} (target {TARGET_PIECE_X})")

    ab("mouse", "up", "left")
    time.sleep(2.5)
    snap = ab("snapshot", "-i", "-c")
    print("== post-release snapshot ==")
    print(snap[:800])


if __name__ == "__main__":
    main()
