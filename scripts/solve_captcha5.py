#!/usr/bin/env python3
"""Affine-invariant gap scan: patch = a*piece + b per candidate; the true gap
minimizes residual. Uses masked pixels, gray + RGB variants."""
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
tv = tpl[msk]
tv_c = tv - tv.mean()

results = []
for gy in range(y0 - 10, y0 + 11):
    if gy < 0 or gy + H > 300:
        continue
    for gx in range(40, 240 - W):
        patch = bg_gray[gy:gy + H, gx:gx + W][msk]
        pv = patch - patch.mean()
        denom = float((pv * pv).sum())
        if denom < 1e-6:
            continue
        a = float((pv * tv_c).sum()) / denom
        b = float(patch.mean() - a * tv.mean())
        resid_full = (patch - (a * tv + b)) ** 2
        resid = float(resid_full.sum() / len(patch))
        results.append((resid, gx, gy, a, b))

results.sort()
print("top 8 affine fits (resid, x, y, a, b):")
for r in results[:8]:
    print(f"  resid={r[0]:8.1f} x={r[1]:3d} y={r[2]:3d} a={r[3]:.3f} b={r[4]:7.1f}")

# the true gap: lowest residual with plausible darkening 0.2<a<0.95
plaus = [r for r in results if 0.2 < r[3] < 0.95]
best = plaus[0] if plaus else results[0]
print(f"\nBEST plausible: x={best[1]} y={best[2]} resid={best[0]:.1f} "
      f"darken-a={best[3]:.3f}")
print(f"DRAG DISTANCE = {best[1] - x0}px")

vis = cv2.cvtColor(bg[:, :, :3], cv2.COLOR_BGR2RGB).copy()
cv2.rectangle(vis, (best[1], best[2]), (best[1] + W, best[2] + H),
              (255, 0, 0), 2)
cv2.imwrite("/home/z/my-project/scripts/dbg_affine_best.png", vis)
print("overlay: scripts/dbg_affine_best.png")
