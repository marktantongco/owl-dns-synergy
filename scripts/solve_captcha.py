#!/usr/bin/env python3
"""Aliyun jigsaw slider solver: find gap x-offset via masked template matching."""
import base64
import json
import sys

import cv2
import numpy as np


def load_images(path="/home/z/my-project/scripts/captcha_imgs.json"):
    raw = open(path).read().strip()
    data = json.loads(json.loads(raw))  # CLI wraps in an extra JSON string
    bg_b64 = data["bg"].split(",", 1)[1]
    pc_b64 = data["piece"].split(",", 1)[1]
    bg = cv2.imdecode(np.frombuffer(base64.b64decode(bg_b64), np.uint8),
                      cv2.IMREAD_UNCHANGED)
    pc = cv2.imdecode(np.frombuffer(base64.b64decode(pc_b64), np.uint8),
                      cv2.IMREAD_UNCHANGED)
    return bg, pc


def solve(bg, pc, verbose=True):
    """Return (gap_x_in_bg, piece_x_in_strip) — drag = gap_x - piece_x."""
    # BGR + alpha for both
    if bg.shape[2] == 4:
        bg_bgr = bg[:, :, :3]
    else:
        bg_bgr = bg
    pc_bgr = pc[:, :, :3]
    pc_alpha = pc[:, :, 3] if pc.shape[2] == 4 else None

    # The piece strip is 60 wide: the actual jigsaw shape occupies part of it.
    if pc_alpha is not None:
        mask = (pc_alpha > 128).astype(np.uint8) * 255
        # Crop to the opaque bounding box
        ys, xs = np.where(mask > 0)
        x0, x1 = xs.min(), xs.max() + 1
        y0, y1 = ys.min(), ys.max() + 1
        tpl = pc_bgr[y0:y1, x0:x1]
        msk = mask[y0:y1, x0:x1]
        piece_left_in_strip = int(x0)
    else:
        tpl, msk, piece_left_in_strip = pc_bgr, None, 0

    # Masked template matching over the background
    res = cv2.matchTemplate(bg_bgr, tpl, cv2.TM_CCORR_NORMED, mask=msk)
    res = np.nan_to_num(res, nan=-1.0, posinf=-1.0, neginf=-1.0)
    _, _, _, max_loc = cv2.minMaxLoc(res)
    gap_x = int(max_loc[0])
    if verbose:
        print(f"piece bbox in strip: x0={x0} y0={y0} w={x1-x0} h={y1-y0}")
        print(f"best match (gap) at bg x={gap_x} y={max_loc[1]}")
        conf = float(res[max_loc[1], gap_x])
        print(f"match confidence: {conf:.4f}")
    return gap_x, piece_left_in_strip, max_loc[1], (x1 - x0), (y1 - y0)


if __name__ == "__main__":
    bg, pc = load_images()
    print(f"bg: {bg.shape}, piece: {pc.shape}")
    gap_x, piece_x, gap_y, w, h = solve(bg, pc)
    drag = gap_x - piece_x
    print(f"\nDRAG DISTANCE: {drag}px  (gap_x={gap_x} - piece_x={piece_x})")
    print(f"gap_y={gap_y} piece_w={w} piece_h={h}")
    # Save a debug composite
    dbg = bg.copy()
    cv2.rectangle(dbg, (gap_x, gap_y), (gap_x + w, gap_y + h), (0, 0, 255), 2)
    cv2.imwrite("/home/z/my-project/scripts/captcha_debug.png",
                cv2.cvtColor(dbg, cv2.COLOR_BGR2RGB))
    print("debug overlay: scripts/captcha_debug.png")
