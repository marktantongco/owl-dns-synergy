#!/usr/bin/env python3
"""Humanized drag v2: irregular bursty trajectory, overshoot+settle,
sub-pixel target via integer-slider nearest landing. Args: --D <piece target>"""
import json
import random
import subprocess
import sys
import time

import cv2
import numpy as np
import urllib.request

SLIDER_Y = 575
SLIDER_X0 = 510.0


def ab(*args, timeout=30):
    r = subprocess.run(["agent-browser", *[str(a) for a in args]],
                       capture_output=True, text=True, timeout=timeout)
    out = (r.stdout + r.stderr).strip()
    if "Usage:" in out or "rror" in out:
        raise RuntimeError(f"ab {args}: {out[:100]}")
    return out


def piece_left():
    out = ab("eval", "JSON.stringify(document.getElementById("
             "'aliyunCaptcha-puzzle').style.left)")
    return float(json.loads(out).replace("px", ""))


def fwd(s):
    return 0.077 * s + 0.00355 * s * s


def inv(P):
    return (-0.077 + (0.077 ** 2 + 4 * 0.00355 * P) ** 0.5) / (2 * 0.00355)


def main():
    D = float(sys.argv[sys.argv.index("--D") + 1])
    no_approach = "--no-approach" in sys.argv
    s_final = inv(D)
    # integer slider landing: choose the int whose fwd(s) is closest to D
    s_int = round(s_final)
    land = fwd(s_int)
    print(f"D={D}  s_exact={s_final:.2f}  -> slider {s_int} lands piece at "
          f"{land:.2f} (err {land - D:+.2f})")

    rng = random.Random(int(time.time() * 1000) % 10 ** 6)

    t_start = time.time()
    try:
        if not no_approach:
            # smooth continuous approach to the handle (no cursor teleport)
            ax, ay = 700.0, 450.0
            for i in range(14):
                t_ = (i + 1) / 14.0
                mx = ax + (510 - ax) * t_ + rng.uniform(-3, 3)
                my = ay + (SLIDER_Y - ay) * t_ + rng.uniform(-3, 3)
                ab("mouse", "move", int(round(mx)), int(round(my)))
                time.sleep(rng.uniform(0.015, 0.04))
        ab("mouse", "move", 510, SLIDER_Y)
        time.sleep(rng.uniform(0.1, 0.2))
        ab("mouse", "down", "left")
        time.sleep(rng.uniform(0.1, 0.18))

        # build a human-ish waypoint plan to overshoot then settle
        overshoot = rng.uniform(3, 7)
        s_peak = min(259, s_int + overshoot)
        waypoints = []
        cur = 0.0
        target_seq = [0.40, 0.85, 1.0]
        for frac in target_seq:
            goal = s_peak * frac
            while cur < goal - 0.5:
                step = rng.uniform(2, 9) * (1 if goal - cur > 6 else 0.5)
                cur = min(cur + step, goal)
                waypoints.append(cur)
                if rng.random() < 0.12:
                    waypoints.append(cur + rng.uniform(-0.8, 0.8))
        while cur < s_peak:
            cur = min(cur + rng.uniform(1, 3), s_peak)
            waypoints.append(cur)
        for k in range(rng.randint(2, 3)):
            back = s_peak - (s_peak - s_int) * (k + 1) / 3.0
            waypoints.append(back)
        waypoints.append(s_int)

        for i, s in enumerate(waypoints):
            x = SLIDER_X0 + s
            yj = rng.choices((-1, 0, 0, 0, 1), weights=(1, 4, 4, 4, 1))[0]
            ab("mouse", "move", int(round(x)), SLIDER_Y + yj)
            # compact human dwell: total drag < ~3s
            if i < 3:
                time.sleep(rng.uniform(0.02, 0.05))
            elif s > s_peak - 12:
                time.sleep(rng.uniform(0.02, 0.06))
            else:
                time.sleep(rng.uniform(0.006, 0.02))
            if rng.random() < 0.06:
                time.sleep(rng.uniform(0.03, 0.08))
        ab("mouse", "move", int(round(SLIDER_X0 + s_int)), SLIDER_Y)
        time.sleep(rng.uniform(0.15, 0.3))
    finally:
        try:
            pl = piece_left()
            print(f"pre-release piece={pl:.2f} (expected {land:.2f}) "
              f"elapsed={time.time()-t_start:.1f}s")
        except Exception:
            pass
        ab("mouse", "up", "left")
    time.sleep(2.5)
    out = ab("snapshot", "-i", "-c")
    print(out[:600])


if __name__ == "__main__":
    main()
