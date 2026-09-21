#!/usr/bin/env python3
"""Side-by-side simulation: for each candidate D, composite the piece as a
darkened cutout on the actual bg and diff against the actual bg. The TRUE D
will show the smallest visual delta in the mark region."""
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
bg_f = bg[:, :, :3].astype(np.float32)
alpha = pc[:, :, 3].astype(np.float32) / 255.0
ys, xs = np.where(alpha > 0.5)
y0, y1 = int(ys.min()), int(ys.max()) + 1
x0, x1 = int(xs.min()), int(xs.max()) + 1
am = alpha[y0:y1, x0:x1]
H, W = y1 - y0, x1 - x0

# observed "darkness vs local surroundings" map in the row band
bg_gray = cv2.cvtColor(bg[:, :, :3], cv2.COLOR_BGR2GRAY).astype(np.float32)
med = cv2.medianBlur(bg_gray.astype(np.uint8), 15).astype(np.float32)
obs_dark = np.clip(med - bg_gray, 0, None)   # positive = darker than surround

tiles = []
for D in (110, 123, 136, 149, 162, 176):
    canvas = bg[:, :, :3].copy()
    # simulated gap: darken by 45% under the alpha
    reg = canvas[y0:y0 + H, D:D + W].astype(np.float32)
    canvas[y0:y0 + H, D:D + W] = (reg * (1 - 0.45 * am[:, :, None])).astype(np.uint8)
    sim_gray = cv2.cvtColor(canvas, cv2.COLOR_BGR2GRAY).astype(np.float32)
    sim_med = cv2.medianBlur(sim_gray.astype(np.uint8), 15).astype(np.float32)
    sim_dark_full = np.clip(sim_med - sim_gray, 0, None)
    # compare dark-maps in the piece region only
    o = obs_dark[y0:y0 + H, D:D + W]
    sim_dark = sim_dark_full[y0:y0 + H, D:D + W]
    diff = float(np.abs(o - sim_dark).mean())
    t = cv2.resize(canvas, (300, 300), interpolation=cv2.INTER_CUBIC)
    cv2.putText(t, f"D={D} d={diff:.1f}", (8, 26),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
    cv2.rectangle(t, (D, y0), (D + W, y0 + H), (0, 255, 0), 1)
    tiles.append(t)

grid = np.vstack([np.hstack(tiles[:3]), np.hstack(tiles[3:])])
cv2.imwrite("/home/z/my-project/scripts/dbg_sim_diff.png",
            cv2.cvtColor(grid, cv2.COLOR_BGR2RGB))
print("saved dbg_sim_diff.png (2x3 grid)")
for D, t in zip((110, 123, 136, 149, 162, 176), tiles):
    pass
