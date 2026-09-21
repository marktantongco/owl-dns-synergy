#!/usr/bin/env python3
"""Visual debug: dump piece + bottom band + darkness profile."""
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
piece_rgba = pc[234:290, 0:60]

# save piece (with alpha over checker) and full bg bottom band, upscaled 3x
def over_checker(img_rgba, scale=3):
    h, w = img_rgba.shape[:2]
    chk = np.zeros((h, w, 3), np.uint8)
    for yy in range(h):
        for xx in range(w):
            chk[yy, xx] = 200 if (xx // 8 + yy // 8) % 2 else 120
    a = img_rgba[:, :, 3:4].astype(np.float32) / 255
    out = (img_rgba[:, :, :3].astype(np.float32) * a +
           chk.astype(np.float32) * (1 - a)).astype(np.uint8)
    return cv2.resize(out, (w * scale, h * scale),
                      interpolation=cv2.INTER_NEAREST)

cv2.imwrite("/home/z/my-project/scripts/dbg_piece.png",
            cv2.cvtColor(over_checker(piece_rgba), cv2.COLOR_BGR2RGB))

band = bg_bgr[220:300]
band3 = cv2.resize(band, (900, 240), interpolation=cv2.INTER_NEAREST)
cv2.imwrite("/home/z/my-project/scripts/dbg_band.png",
            cv2.cvtColor(band3, cv2.COLOR_BGR2RGB))

# enhanced-contrast view of the band to expose the darkened gap
lab = cv2.cvtColor(band, cv2.COLOR_BGR2LAB)
l = lab[:, :, 0]
l_eq = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8)).apply(l)
lab[:, :, 0] = l_eq
enh = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
enh3 = cv2.resize(enh, (900, 240), interpolation=cv2.INTER_NEAREST)
cv2.imwrite("/home/z/my-project/scripts/dbg_band_enhanced.png",
            cv2.cvtColor(enh3, cv2.COLOR_BGR2RGB))

# column darkness profile of the exact piece band (234-290)
prof = bg_bgr[234:290].astype(np.float32).mean(axis=(0, 2))
print("column luminance 0..299 (only 0..200 shown), *,v marks local minima:")
for x0 in range(0, 200, 10):
    seg = " ".join(f"{v:5.1f}" for v in prof[x0:x0 + 10])
    print(f"x={x0:3d}: {seg}")
print(f"\nglobal darkest column in 0..240: {int(np.argmin(prof[:240]))} "
      f"lum={prof[:240].min():.1f}; median lum={np.median(prof):.1f}")
