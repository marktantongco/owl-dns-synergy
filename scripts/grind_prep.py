#!/usr/bin/env python3
"""Grind-round prep: screenshot + rect eval + centroid extraction + crops.

Outputs:
  grind_shot.png        - full page
  grind_icons_3x.png    - icon grid crop at 3x
  grind_inst_6x.png     - instruction bar at 6x
  grind_icon_{i}.png    - individual icon patches at 8x (for template match)
  .captcha_points.json  - clickable page coords (css px)
"""
import json
import sys
import time

sys.path.insert(0, "/home/z/my-project/scripts")
from drive import send

import numpy as np
from PIL import Image

ROUND = sys.argv[1] if len(sys.argv) > 1 else "r"
SHOT = f"/home/z/my-project/scripts/grind_shot_{ROUND}.png"

# 1. fresh screenshot
send({"cmd": "screenshot", "path": SHOT}, 4)

# 2. live rect of the captcha image + css viewport width for DPR handling
r = send({"cmd": "eval", "js":
          '(()=>{const im=document.querySelector("img[src*=fengkongcloud]");'
          "if(!im)return null;const r=im.getBoundingClientRect();"
          'return JSON.stringify({x:r.x,y:r.y,w:r.width,h:r.height,'
          'vw:window.innerWidth,vh:window.innerHeight});})()'}, 3)
rect = None
for e in r:
    if e.get("ev") == "ok" and e.get("cmd") == "eval":
        v = e.get("value")
        rect = json.loads(v) if isinstance(v, str) else v
if not rect:
    print("NO_CAPTCHA")
    sys.exit(1)
print("rect:", rect)

im = Image.open(SHOT).convert("RGB")
print("shot size:", im.size)
# shot px = css px * DPR; derive DPR from viewport width in the same eval
sx = im.size[0] / float(rect.get("vw") or im.size[0])
print("sx (shot/css):", sx)
rect_px = dict(x=rect["x"] * sx, y=rect["y"] * sx,
               w=rect["w"] * sx, h=rect["h"] * sx)
crop = im.crop((int(rect_px["x"]), int(rect_px["y"]),
                int(rect_px["x"] + rect_px["w"]),
                int(rect_px["y"] + rect_px["h"])))
W, H = crop.size
print("crop:", W, H)

a = np.asarray(crop).astype(int)
R, G, B = a[..., 0], a[..., 1], a[..., 2]
mask = (R > 140) & (R - G > 60) & (R - B > 60)
from scipy import ndimage
lbl, n = ndimage.label(mask)
cents = []
for i in range(1, n + 1):
    yy, xx = np.nonzero(lbl == i)
    if len(xx) < 120:
        continue
    cents.append([xx.mean(), yy.mean(), len(xx),
                  xx.min(), xx.max(), yy.min(), yy.max()])
merged = []
for c in sorted(cents, key=lambda c: -c[2]):
    for m in merged:
        if abs(c[0] - m[0]) < 45 and abs(c[1] - m[1]) < 45:
            m[2] += c[2]
            m[0] = (m[0] * m[2] + c[0] * c[2]) / (m[2] + c[2])
            m[1] = (m[1] * m[2] + c[1] * c[2]) / (m[2] + c[2])
            m[4] = max(m[4], c[4]); m[6] = max(m[6], c[6])
            break
    else:
        merged.append(list(c))
merged = [m for m in merged if m[2] >= 200 and m[1] < H * 0.85]
merged.sort(key=lambda m: m[0])

pts = []
for idx, (cx, cy, sz, x0, x1, y0, y1) in enumerate(merged):
    # click coords must be CSS px (Playwright mouse space); crop is device px
    px = rect["x"] + cx * rect["w"] / W
    py = rect["y"] + cy * rect["h"] / H
    pts.append((round(px), round(py)))
    print(f"  icon[{idx}] size={sz} bbox=({x0:.0f}-{x1:.0f},{y0:.0f}-{y1:.0f}) "
          f"-> page({px:.0f},{py:.0f})")

json.dump({"points": pts, "rect": rect_px},
          open("/home/z/my-project/scripts/.captcha_points.json", "w"))

# 3. crops for vision
crop.resize((W * 3, H * 3), Image.LANCZOS).save(
    f"/home/z/my-project/scripts/grind_icons_{ROUND}.png")
bar_y0 = rect_px["y"] + rect_px["h"] + 10 * sx
bar = im.crop((int(rect_px["x"]) + 100 * sx, int(bar_y0),
               int(rect_px["x"] + rect_px["w"]) - 10,
               int(bar_y0 + 40 * sx)))
bw, bh = bar.size
bar.resize((int(bw * 6), int(bh * 6)), Image.LANCZOS).save(
    f"/home/z/my-project/scripts/grind_inst_{ROUND}.png")

# individual icon patches (8x) around each centroid
for idx, (cx, cy, sz, x0, x1, y0, y1) in enumerate(merged):
    pad = 30
    x0p, x1p = max(0, int(x0) - pad), min(W, int(x1) + pad)
    y0p, y1p = max(0, int(y0) - pad), min(H, int(y1) + pad)
    patch = crop.crop((x0p, y0p, x1p, y1p))
    pw, ph = patch.size
    z = 8
    patch.resize((pw * z, ph * z), Image.LANCZOS).save(
        f"/home/z/my-project/scripts/grind_icon_{ROUND}_{idx}.png")

print(f"SAVED {len(pts)} pts, round={ROUND}")
