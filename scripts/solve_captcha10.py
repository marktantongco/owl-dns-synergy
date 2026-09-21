#!/usr/bin/env python3
"""Alpha-outline contour matching: the cutout border must appear as edges in
the bg. Score each candidate D by edge support along the piece's outline."""
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
ys, xs = np.where(alpha > 128)
x0, y0 = int(xs.min()), int(ys.min())
x1, y1 = int(xs.max()) + 1, int(ys.max()) + 1
am = (alpha[y0:y1, x0:x1] > 128).astype(np.uint8)
H, W = y1 - y0, x1 - x0

# outline of the piece shape (boundary band, 3px)
outline = am - cv2.erode(am, np.ones((3, 3), np.uint8))
outline = np.clip(outline, 0, 1).astype(np.float32)

# bg edges (magnitude, normalized)
bg_mag = cv2.magnitude(*[cv2.Sobel(bg_gray, cv2.CV_32F, dx, dy, ksize=3)
                         for dx, dy in ((1, 0), (0, 1))])
bg_mag = bg_mag / (bg_mag.max() + 1e-6)

print("outline-support scan (fraction of outline on strong bg edges):")
results = []
for D in range(60, 245):
    for dy in range(-8, 9):
        gy = y0 + dy
        if gy < 0 or gy + H > 300 or D + W > 300:
            continue
        band = bg_mag[gy:gy + H, D:D + W]
        # outline pixels with support
        sup = float((band * outline).sum())
        frac = sup / float(outline.sum())
        results.append((frac, D, gy))
results.sort(reverse=True)
seen = []
print("top support candidates:")
for frac, D, gy in results:
    if any(abs(D - s) <= 6 for s in seen):
        continue
    seen.append(D)
    print(f"  support={frac:.4f} D={D} gy={gy}")
    if len(seen) >= 8:
        break
