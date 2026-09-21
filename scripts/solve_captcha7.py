#!/usr/bin/env python3
"""Pendant-to-pendant alignment: find the round pendant blob centroid in the
piece strip AND in the bg (dark blob on light chest), align them."""
import base64
import json

import cv2
import numpy as np


def load_images(path="/home/z/my-project/scripts/captcha_imgs.json"):
    raw = open(path).read().strip()
    data = json.loads(json.loads(raw))
    bg = cv2.imdecode(np.frombuffer(
        base64.b64decode(data["bg"].split(",", 1)[1]), np.uint8),
        cv2.IMREAD_UNCHANGED)
    pc = cv2.imdecode(np.frombuffer(
        base64.b64decode(data["piece"].split(",", 1)[1]), np.uint8),
        cv2.IMREAD_UNCHANGED)
    return bg, pc


bg, pc = load_images()
bg_gray = cv2.cvtColor(bg[:, :, :3], cv2.COLOR_BGR2GRAY)
alpha = pc[:, :, 3]
mask = alpha > 128
ys, xs = np.where(mask)
x0, y0 = int(xs.min()), int(ys.min())
x1, y1 = int(xs.max()) + 1, int(ys.max()) + 1
tpl_gray = cv2.cvtColor(pc[y0:y1, x0:x1, :3], cv2.COLOR_BGR2GRAY)
H, W = y1 - y0, x1 - x0

# --- pendant in the piece: darkest round blob ---
_, th_p = cv2.threshold(tpl_gray, 60, 255, cv2.THRESH_BINARY_INV)
n, lab, stats, cent = cv2.connectedComponentsWithStats(th_p.astype(np.uint8))
print("piece dark blobs (area, bbox, centroid):")
piece_pendant = None
for i in range(1, n):
    a = stats[i, cv2.CC_STAT_AREA]
    if a < 40:
        continue
    bx, by, bw, bh = stats[i, 0], stats[i, 1], stats[i, 2], stats[i, 3]
    cx, cy = cent[i]
    fill = a / float(bw * bh)
    print(f"  blob{i}: area={a} bbox=({bx},{by},{bw}x{bh}) "
          f"c=({cx:.1f},{cy:.1f}) fill={fill:.2f}")
    if fill > 0.55 and bw > 12:      # roundish & large = pendant
        piece_pendant = (cx, cy)
if piece_pendant is None:
    # fallback: darkest 20x20 window
    best = None
    for yy in range(0, H - 20):
        for xx in range(0, W - 20):
            v = float(tpl_gray[yy:yy + 20, xx:xx + 20].mean())
            if best is None or v < best[0]:
                best = (v, xx + 10, yy + 10)
    piece_pendant = (best[1], best[2])
    print(f"  fallback darkest window centroid: {piece_pendant}")
print(f"piece pendant centroid (bbox-relative): {piece_pendant}")

# --- pendant in the bg: dark blob on the light chest, window x=130..210 y=215..285
win = bg_gray[215:285, 130:210]
_, th_b = cv2.threshold(win, 90, 255, cv2.THRESH_BINARY_INV)
n2, lab2, stats2, cent2 = cv2.connectedComponentsWithStats(th_b.astype(np.uint8))
print("\nbg dark blobs in chest window:")
bg_pendant = None
best_area = 0
for i in range(1, n2):
    a = stats2[i, cv2.CC_STAT_AREA]
    if a < 60:
        continue
    bx, by, bw, bh = stats2[i, 0], stats2[i, 1], stats2[i, 2], stats2[i, 3]
    cx, cy = cent2[i]
    fill = a / float(bw * bh)
    print(f"  blob{i}: area={a} bbox=({bx+130},{by+215},{bw}x{bh}) "
          f"c=({cx+130:.1f},{cy+215:.1f}) fill={fill:.2f}")
    # roundish blob in plausible pendant size
    if 60 < a < 1200 and bw > 8 and bh > 8 and (cy + 215) > 228:
        if a > best_area:
            best_area = a
            bg_pendant = (cx + 130, cy + 215)
print(f"bg pendant candidate: {bg_pendant}")

if bg_pendant:
    dx = bg_pendant[0] - piece_pendant[0]
    dy = bg_pendant[1] - piece_pendant[1]
    drag = int(round(dx)) - x0
    print(f"\naligning pendant: piece_left_x = {bg_pendant[0] - piece_pendant[0]:.1f}")
    print(f"strip offset x0={x0}  =>  DRAG = {drag}px  (dy={dy:.1f})")
