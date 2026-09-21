#!/usr/bin/env python3
"""Execute the slider drag: calibrate handle->piece ratio mid-drag, then
complete to the target piece offset (177px), human-like trajectory.
Uses agent-browser mouse commands driven from Python via subprocess."""
import json
import subprocess
import sys
import time

TARGET_PIECE_X = 177.0
SLIDER = (510.0, 575.5)  # handle center at rest (page coords)


def ab(*args, timeout=30):
    r = subprocess.run(["agent-browser", *args], capture_output=True,
                       text=True, timeout=timeout)
    return (r.stdout + r.stderr).strip()


def piece_x():
    out = ab("eval", "JSON.stringify((() => { const p = "
             "[...document.querySelectorAll('img')].find(i=>i.width===60&&"
             "i.height===300); const b = p.getBoundingClientRect(); "
             "return {x: b.x, tf: p.style.transform}; })())")
    try:
        d = json.loads(json.loads(out))
        return float(d["x"]), d.get("tf", "")
    except Exception:
        return None, out[:120]


def main():
    print("== pre-drag state ==")
    px, tf = piece_x()
    print(f"piece x at rest: {px}  transform: {tf}")

    # press on the handle
    print(f"mousedown at {SLIDER}")
    ab("mouse", "move", str(int(SLIDER[0])), str(int(SLIDER[1])))
    ab("mouse", "down", "left")
    time.sleep(0.15)

    # calibration move +40 with small steps
    x, y = SLIDER
    for step in (8, 12, 20):
        x += step
        ab("mouse", "move", str(int(x)), str(int(y + (2 if step % 2 else -1))))
        time.sleep(0.05)
    time.sleep(0.15)
    px40, tf40 = piece_x()
    print(f"after +40: piece x={px40} transform={tf40}")
    if px40 is None:
        print("FATAL: no piece rect mid-drag")
        sys.exit(1)
    disp = px40 - px
    ratio = disp / 40.0
    print(f"piece displaced {disp:.1f}px for 40px handle move -> ratio={ratio:.4f}")

    target_handle = SLIDER[0] + (TARGET_PIECE_X - disp) / ratio
    print(f"target handle x: {target_handle:.1f} "
          f"(remaining {target_handle - x:.1f}px)")

    # human-like completion: variable steps with ease-out + y jitter
    import random
    random.seed(177)
    remaining = target_handle - x
    steps = []
    n = 22
    for i in range(n):
        frac = (i + 1) / n
        ease = 1 - (1 - frac) ** 2          # ease-out quad
        steps.append(remaining * ease)
    prev = 0.0
    for i, s in enumerate(steps):
        dx = s - prev
        prev = s
        x += dx
        jy = random.choice((-2, -1, 0, 1, 1, 2, 0))
        ab("mouse", "move", f"{x:.1f}", f"{y + jy:.1f}")
        time.sleep(random.uniform(0.012, 0.05))
    # settle exactly on target line
    ab("mouse", "move", f"{x:.1f}", f"{y}")
    time.sleep(0.2)
    pxf, tff = piece_x()
    print(f"pre-release piece x: {pxf} transform: {tff}")

    print("mouse up")
    ab("mouse", "up", "left")
    time.sleep(2.0)
    print(ab("snapshot", "-i", "-c")[:600])


if __name__ == "__main__":
    main()
