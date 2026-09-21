#!/usr/bin/env python3
"""Darkness-weighted matching: the gap is dark-on-light-chest; weight template
pixels by darkness so the pendant/straps dominate the fit."""
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
alpha = pc[:, :, 3]
mask = alpha > 128
ys, xs = np.where(mask)
x0, y0 = int(xs.min()), int(ys.min())
x1, y1 = int(xs.max()) + 1, int(ys.max()) + 1
tpl = cv2.cvtColor(pc[y0:y1, x0:x1, :3], cv2.COLOR_BGR2GRAY).astype(np.float32)
msk = mask[y0:y1, x0:x1]
H, W = tpl.shape[:2]

# darkness weight: template dark pixels weigh most, but only where opaque
w = ((255.0 - tpl) / 255.0) * msk
w = w / w.sum()

print("darkness-weighted fit (lower cost = better):")
cands = []
for gy in range(y0 - 10, y0 + 11):
    if gy < 0 or gy + H > 300:
        continue
    for gx in range(40, 240 - W):
        patch = bg_gray[gy:gy + H, gx:gx + W]
        # cost: weighted mean of patch luminance (want the darkest overlap
        # where the piece's dark pixels would land) MINUS alignment of
        # bright chest pixels with the piece's transparent-ish bright pixels
        cost = float((patch * w).sum())
        cands.append((cost, gx, gy))

cands.sort()
seen = []
print("top candidates:")
for c, gx, gy in cands:
    if any(abs(gx - s) < 12 for s in seen):
        continue
    seen.append((gx))
    print(f"  cost={c:7.1f} x={gx} y={gy} drag={gx - x0}")
    if len(seen) >= 6:
        break

# refine: among the darkness optima, prefer max gradient alignment
best_x = seen[0]
print(f"\ndarkness-optimal first choice: x={best_x} drag={best_x - x0}")
