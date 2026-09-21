#!/usr/bin/env python3
"""Row-band matching: for the bg dark mark at y=238-258, find which piece
x-occupancy pattern (at those same rows) aligns. Slides the piece alpha
column-profile over the bg darkness profile at those rows only."""
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

# The bg mark: find dark pixels (<180, i.e. darker than the 198-median chest)
# inside window x=145..195, y=232..262
wy0, wy1, wx0, wx1 = 232, 262, 145, 195
win = bg_gray[wy0:wy1, wx0:wx1]
mark = (win < 175).astype(np.float32)
print(f"bg mark pixels: {int(mark.sum())} of {mark.size}")
mcols = mark.sum(axis=0)   # per-column occupancy
print("bg mark column profile (x:count):")
print("  " + " ".join(f"{wx0+i}:{int(v)}" for i, v in enumerate(mcols) if v > 0))

# Piece alpha column-occupancy at the SAME rows
band = (alpha[wy0:wy1] > 128).astype(np.float32)   # shape (30, 60)
pcols = band.sum(axis=0)
print("\npiece alpha column profile at rows 232-262:")
print("  " + " ".join(f"{i}:{int(v)}" for i, v in enumerate(pcols) if v > 0))

# Slide: piece columns c map to bg column c+D. Score = overlap of mark
# columns with piece columns. 1D correlation.
scores = []
for D in range(100, 200):
    tot = 0.0
    for c in range(60):
        if wx0 <= c + D < wx1:
            tot += pcols[c] * mcols[c + D - wx0]
    # normalize by piece occupancy inside the window
    inside = sum(pcols[c] for c in range(60)
                 if wx0 <= c + D < wx1)
    if inside > 0:
        scores.append((tot / inside, D))
scores.sort(reverse=True)
print("\ntop 10 1D alignment scores (piece-alpha vs bg-mark, rows 232-262):")
for s, D in scores[:10]:
    print(f"  D={D} score={s:.3f}")
