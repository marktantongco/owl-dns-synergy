#!/usr/bin/env python3
"""Robust gap detection: multi-method voting (SQDIFF masked, edge matching,
brightness-anomaly scan). Prints per-method verdicts + consensus."""
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


def piece_crop(pc):
    alpha = pc[:, :, 3]
    mask = (alpha > 128).astype(np.uint8) * 255
    ys, xs = np.where(mask > 0)
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    return pc[y0:y1, x0:x1, :3], mask[y0:y1, x0:x1], x0, y0


def method_sqdiff(bg_bgr, tpl, msk):
    res = cv2.matchTemplate(bg_bgr, tpl, cv2.TM_SQDIFF_NORMED, mask=msk)
    res = np.nan_to_num(res, nan=9e9, posinf=9e9, neginf=9e9)
    _, _, min_loc, _ = cv2.minMaxLoc(res)
    return int(min_loc[0]), int(min_loc[1]), float(res[min_loc[1], min_loc[0]])


def method_ccorr(bg_bgr, tpl, msk):
    res = cv2.matchTemplate(bg_bgr, tpl, cv2.TM_CCORR_NORMED, mask=msk)
    res = np.nan_to_num(res, nan=-1, posinf=-1, neginf=-1)
    _, _, _, max_loc = cv2.minMaxLoc(res)
    return int(max_loc[0]), int(max_loc[1]), float(res[max_loc[1], max_loc[0]])


def method_edges(bg_bgr, tpl, msk):
    bg_gray = cv2.cvtColor(bg_bgr, cv2.COLOR_BGR2GRAY)
    tpl_gray = cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY)
    bg_e = cv2.Canny(bg_gray, 60, 160)
    tpl_e = cv2.Canny(tpl_gray, 60, 160)
    tpl_e = cv2.bitwise_and(tpl_e, msk)
    if tpl_e.sum() == 0:
        return -1, -1, 0.0
    res = cv2.matchTemplate(bg_e, tpl_e, cv2.TM_CCORR_NORMED)
    _, _, _, max_loc = cv2.minMaxLoc(res)
    return int(max_loc[0]), int(max_loc[1]), float(res[max_loc[1], max_loc[0]])


def method_darkness(bg_bgr, tpl, msk):
    """Aliyun gaps are rendered as a darkened copy of the piece.
    Compute per-candidate-column darkness anomaly at the piece's y-band."""
    h, w = tpl.shape[:2]
    y0 = 234  # known piece y-band start in strip == gap y in bg (same layout)
    band = bg_bgr[y0:y0 + h].astype(np.float32)
    lum = band.mean(axis=(0, 2))  # per-column brightness
    # gap columns are darker than the local median
    med = np.median(lum)
    anom = med - lum  # positive = darker than median
    # restrict to plausible range (piece can't be at x<5)
    anom[:5] = -1
    x = int(np.argmax(anom))
    return x, y0, float(anom[x])


def main():
    bg, pc = load_images()
    bg_bgr = bg[:, :, :3]
    tpl, msk, px0, py0 = piece_crop(pc)
    print(f"piece crop: x0={px0} y0={py0} size={tpl.shape[1]}x{tpl.shape[0]}")

    results = {}
    x, y, s = method_sqdiff(bg_bgr, tpl, msk)
    results["sqdiff"] = (x, y, s)
    print(f"SQDIFF(masked):  x={x}  y={y}  score={s:.4f}  (lower=better)")
    x, y, s = method_ccorr(bg_bgr, tpl, msk)
    results["ccorr"] = (x, y, s)
    print(f"CCORR(masked):   x={x}  y={y}  score={s:.4f}  (higher=better)")
    x, y, s = method_edges(bg_bgr, tpl, msk)
    results["edges"] = (x, y, s)
    print(f"EDGES:           x={x}  y={y}  score={s:.4f}  (higher=better)")
    x, y, s = method_darkness(bg_bgr, tpl, msk)
    results["darkness"] = (x, y, s)
    print(f"DARKNESS:        x={x}  y={y}  score={s:.4f}  (higher=better)")

    # consensus: median of x votes from the 3 most reliable
    votes = sorted([results[k][0] for k in ("sqdiff", "edges", "darkness")])
    med = int(votes[len(votes) // 2])
    print(f"\nCONSENSUS drag distance: {med - px0}px "
          f"(median x={med}, piece strip offset={px0})")
    for k, (x, y, s) in results.items():
        print(f"  {k}: drag={x - px0}")
    return med - px0


if __name__ == "__main__":
    main()
