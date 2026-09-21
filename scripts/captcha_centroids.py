#!/usr/bin/env python3
"""Shumei icon-select captcha solver: red-icon centroid detection.

Downloads the captcha bg image, finds red icon clusters, converts centroids
to page CSS coordinates. Operator (me) supplies the click ORDER after
identifying glyph shapes from the zoomed crops.
"""
import json
import sys
import urllib.request

import numpy as np
from PIL import Image

meta = json.load(open("/home/z/my-project/scripts/.captcha_meta.json"))
src = meta["src"]
rect_x, rect_y, rect_w, rect_h = meta["x"], meta["y"], meta["w"], meta["h"]

req = urllib.request.Request(src, headers={"User-Agent": "Mozilla/5.0"})
raw = urllib.request.urlopen(req, timeout=15).read()
open("/home/z/my-project/scripts/captcha_bg.jpg", "wb").write(raw)
im = Image.open("/home/z/my-project/scripts/captcha_bg.jpg").convert("RGB")
W, H = im.size
a = np.asarray(im).astype(int)
R, G, B = a[..., 0], a[..., 1], a[..., 2]

# red glyph mask (icons are pure red #e64x3x-ish on photo)
mask = (R > 140) & (R - G > 60) & (R - B > 60)
ys, xs = np.nonzero(mask)
print(f"image {W}x{H}, red px: {len(xs)}")

# connected clusters via simple grid binning + BFS on downsampled mask
from scipy import ndimage
lbl, n = ndimage.label(mask)
cents = []
for i in range(1, n + 1):
    yy, xx = np.nonzero(lbl == i)
    if len(xx) < 80:  # noise filter
        continue
    cents.append((xx.mean(), yy.mean(), len(xx)))
cents.sort(key=lambda c: -c[2])
print(f"clusters: {len(cents)}")

# merge close clusters (icon may split), then map to page coords
merged = []
for cx, cy, sz in cents:
    for m in merged:
        if abs(cx - m[0]) < 25 and abs(cy - m[1]) < 25:
            m[2] += sz
            break
    else:
        merged.append([cx, cy, sz])
merged.sort(key=lambda m: m[0])

pts = []
for cx, cy, sz in merged:
    px = rect_x + cx * rect_w / W
    py = rect_y + cy * rect_h / H
    pts.append((round(px), round(py), int(sz)))
    print(f"  cluster({int(cx)},{int(cy)}) size={sz} -> page({px:.0f},{py:.0f})")

json.dump({"points": [(p[0], p[1]) for p in pts]},
          open("/home/z/my-project/scripts/.captcha_points.json", "w"))
print("saved -> .captcha_points.json")

# also emit an annotated crop for ID
im2 = Image.open("/home/z/my-project/scripts/captcha_bg.jpg").convert("RGB")
im2.resize((W * 3, H * 3), Image.LANCZOS).save(
    "/home/z/my-project/scripts/captcha_bg_3x.png")
