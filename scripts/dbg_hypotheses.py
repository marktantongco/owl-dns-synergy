#!/usr/bin/env python3
"""Composite hypothesis test: render the piece as a darkened overlay at
candidate x positions; save side-by-side for visual judgment."""
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
bg_bgr = bg[:, :, :3].astype(np.float32)
alpha = pc[:, :, 3]
mask = alpha > 128
ys, xs = np.where(mask)
x0, y0 = int(xs.min()), int(ys.min())
x1, y1 = int(xs.max()) + 1, int(ys.max()) + 1
tpl = pc[y0:y1, x0:x1, :3].astype(np.float32)
am = (alpha[y0:y1, x0:x1:x1] if False else alpha[y0:y1, x0:x1]).astype(np.float32) / 255.0
H, W = tpl.shape[:2]

CANDS = [114, 126, 139, 152, 163, 176]
tiles = []
for cx in CANDS:
    canvas = bg_bgr.copy()
    gy = y0  # keep the natural y band
    # simulate the gap: darken the bg by the piece alpha at this position
    region = canvas[gy:gy + H, cx:cx + W]
    canvas[gy:gy + H, cx:cx + W] = region * (1 - 0.55 * am[:, :, None])
    # outline
    cv2.rectangle(canvas, (cx, gy), (cx + W, gy + H), (0, 255, 0), 1)
    t = cv2.resize(canvas, (450, 450), interpolation=cv2.INTER_CUBIC)
    cv2.putText(t, f"x={cx}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                1.0, (0, 255, 255), 2)
    tiles.append(t)

grid = np.hstack(tiles)
cv2.imwrite("/home/z/my-project/scripts/dbg_hypotheses.png",
            cv2.cvtColor(grid.astype(np.uint8), cv2.COLOR_BGR2RGB))
print("saved dbg_hypotheses.png with candidates:", CANDS)
