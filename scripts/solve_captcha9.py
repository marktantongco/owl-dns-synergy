#!/usr/bin/env python3
"""Darkening-anomaly map + alpha-shape correlation. The gap is bg*(1-k*a):
pixel minus large-kernel median = -k*a inside the piece shape. Correlate the
shape-aligned anomaly with the piece alpha to find D."""
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
bg_gray = cv2.cvtColor(bg[:, :, :3], cv2.COLOR_BGR2GRAY).astype(np.float32)
alpha = pc[:, :, 3].astype(np.float32)
ys, xs = np.where(alpha > 128)
x0, y0 = int(xs.min()), int(ys.min())
x1, y1 = int(xs.max()) + 1, int(ys.max()) + 1
am = alpha[y0:y1, x0:x1] / 255.0
H, W = y1 - y0, x1 - x0

# anomaly: pixel - large median (bg estimate)
med = cv2.medianBlur(bg_gray.astype(np.uint8), 21).astype(np.float32)
anom = bg_gray - med            # negative where darker than surroundings

print("scan D (piece left) with per-D optimal k:")
best = []
for D in range(100, 200):
    for dy in range(-6, 7):
        gy = y0 + dy
        if gy < 0 or gy + H > 300:
            continue
        a = anom[gy:gy + H, D:D + W]
        if a.shape != am.shape:
            continue
        # model: anom ≈ -k*am  ->  k = -(a*am).sum/(am*am).sum
        denom = float((am * am).sum())
        k = -float((a * am).sum()) / denom
        if not (0.02 < k < 0.75):
            continue
        resid = a + k * am
        r = float((resid * resid).sum())
        best.append((r, D, gy, k))
best.sort()
print("top 6 fits: (resid, D, gy, k)")
for r, D, gy, k in best[:6]:
    print(f"  resid={r:10.1f} D={D} gy={gy} k={k:.3f}")
if best:
    r, D, gy, k = best[0]
    print(f"\n==> DRAG = {D - x0}px (D={D}, strip x0={x0}, darken k={k:.2f}, gy={gy} vs y0={y0})")
    vis = cv2.cvtColor(bg[:, :, :3], cv2.COLOR_BGR2RGB).copy()
    cv2.rectangle(vis, (D, gy), (D + W, gy + H), (255, 0, 0), 2)
    cv2.imwrite("/home/z/my-project/scripts/dbg_anom_best.png", vis)
    print("overlay: scripts/dbg_anom_best.png")
