#!/usr/bin/env python3
"""Gradient-based gap matching (brightness-invariant) + candidate visualization."""
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
bg_bgr = bg[:, :, :3]
alpha = pc[:, :, 3]
mask_full = (alpha > 128).astype(np.uint8) * 255
ys, xs = np.where(mask_full > 0)
x0, y0 = int(xs.min()), int(ys.min())
x1, y1 = int(xs.max()) + 1, int(ys.max()) + 1
tpl = pc[y0:y1, x0:x1, :3]
msk = mask_full[y0:y1, x0:x1]
H, W = tpl.shape[:2]

# Sobel magnitude on gray
def sobel_mag(gray):
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    return cv2.magnitude(gx, gy)

bg_gray = cv2.cvtColor(bg_bgr, cv2.COLOR_BGR2GRAY)
tpl_gray = cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY)
bg_mag = sobel_mag(bg_gray)
tpl_mag = sobel_mag(tpl_gray)

# masked normalized cross-correlation of gradient magnitudes
res = cv2.matchTemplate(bg_mag.astype(np.float32),
                        tpl_mag.astype(np.float32),
                        cv2.TM_CCORR_NORMED, mask=msk.astype(np.float32))
res = np.nan_to_num(res, nan=-1, posinf=-1, neginf=-1)

# top 5 candidates
flat = res.flatten()
top = np.argsort(flat)[::-1][:8]
print("top gradient-NCC candidates:")
seen = []
for idx in top:
    gy, gx = divmod(int(idx), res.shape[1])
    if gx < 40:          # skip piece start area
        continue
    if any(abs(gx - s) < 15 for s in seen):
        continue
    seen.append(gx)
    print(f"  x={gx} y={gy} score={flat[idx]:.4f} drag={gx - x0}")
    if len(seen) == 5:
        break

# visualize top-3 on the background
vis = bg_bgr.copy()
colors = [(0, 0, 255), (0, 255, 255), (255, 0, 255)]
for i, gx in enumerate(seen[:3]):
    cv2.rectangle(vis, (gx, y0), (gx + W, y0 + H), colors[i], 2)
    cv2.putText(vis, str(i), (gx + 2, y0 + 14),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, colors[i], 1)
cv2.imwrite("/home/z/my-project/scripts/dbg_grad_candidates.png",
            cv2.cvtColor(vis, cv2.COLOR_BGR2RGB))
print("\ncandidates overlay: scripts/dbg_grad_candidates.png (red=0, yellow=1, magenta=2)")
