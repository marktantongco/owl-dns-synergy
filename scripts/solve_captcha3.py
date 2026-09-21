#!/usr/bin/env python3
"""Precise gap location: match the piece's distinctive subregions (pendant +
strap) over the search range x=40..240, using masked SQDIFF (unnormalized
accumulation for discriminativeness) + per-subregion consensus."""
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
mask_full = (alpha > 128).astype(np.uint8) * 255
ys, xs = np.where(mask_full > 0)
x0, x1, y0, y1 = int(xs.min()), int(xs.max()) + 1, int(ys.min()), int(ys.max()) + 1
tpl_full = pc[y0:y1, x0:x1, :3].astype(np.float32)
msk_full = mask_full[y0:y1, x0:x1]
H, W = tpl_full.shape[:2]
print(f"piece bbox: x0={x0} y0={y0} w={W} h={H}")

SEARCH_X0, SEARCH_X1 = 40, 240  # gap must be right of the piece start region

def match_region(tpl, msk, label):
    """Sliding masked SQDIFF (sum) over bg, return best (x,y,score,dark_gain)."""
    th, tw = tpl.shape[:2]
    best = (None, None, 1e18)
    for gy in range(y0 - 8, y0 + 9):          # y should be near the piece band
        if gy < 0 or gy + th > 300:
            continue
        for gx in range(SEARCH_X0, SEARCH_X1 - tw):
            patch = bg_bgr[gy:gy + th, gx:gx + tw]
            d = ((patch - tpl) ** 2).sum(axis=2)
            score = float((d * (msk > 0)).sum() / (msk > 0).sum())
            if score < best[2]:
                best = (gx, gy, score)
    print(f"{label}: x={best[0]} y={best[1]} mse={best[2]:.1f}")
    return best

# subregion A: pendant (right-bottom quadrant of the piece bbox)
subA = tpl_full[H // 2:, W // 2:]
mskA = msk_full[H // 2:, W // 2:]
bA = match_region(subA, mskA, "pendant-only   ")

# subregion B: full piece
bB = match_region(tpl_full, msk_full, "full-piece     ")

# consensus: pendant placement implies full-piece x = bA.x - W/2
implied_full_x = bA[0] - (W - W // 2)  # pendant offset inside full bbox
print(f"\npendant implies full-piece gap x = {implied_full_x}")
print(f"full-piece direct match x        = {bB[0]}")
final = (implied_full_x + bB[0]) // 2
print(f"\nFINAL drag distance: {final}px")
