#!/usr/bin/env python3
"""Shumei icon-select solver v2 — screenshot-based (displayed pixels only).

Pipeline:
  1. driver screenshot -> real-size PNG (1920x986)
  2. re-query img rect from DOM (puzzle may re-render)
  3. crop img rect EXACTLY -> red-cluster centroids -> page CSS coords
  4. crop instruction bar (rect-relative) at 5x for glyph ID
Output: .captcha_points.json + captcha_inst_5x.png
"""
import json
import subprocess

import numpy as np
from PIL import Image
from scipy import ndimage

SHOT = "/home/z/my-project/scripts/cf5_now.png"
EVAL_RES = None


def driver(cmd):
    with open("/home/z/my-project/scripts/.camoufox_fifo", "w") as f:
        f.write(json.dumps(cmd) + "\n")


# 1+2: fresh screenshot + live rect
driver({"cmd": "screenshot", "path": SHOT})
import time
time.sleep(2.5)
driver({"cmd": "eval", "js":
        '(()=>{const im=document.querySelector("img[src*=fengkongcloud]");'
        "const r=im.getBoundingClientRect();"
        'return JSON.stringify({x:r.x,y:r.y,w:r.width,h:r.height});})()'})
time.sleep(2)

# fish the last eval result from the log
val = None
for line in open("/home/z/my-project/scripts/.camoufox_log.jsonl"):
    try:
        e = json.loads(line)
    except Exception:
        continue
    if e.get("ev") == "ok" and e.get("cmd") == "eval":
        val = e.get("value")
rect = json.loads(val) if isinstance(val, str) else val
print("rect:", rect)
if not rect:
    sys.exit("no rect")

im = Image.open(SHOT).convert("RGB")
print("shot:", im.size)
crop = im.crop((int(rect["x"]), int(rect["y"]),
                int(rect["x"] + rect["w"]), int(rect["y"] + rect["h"])))
W, H = crop.size
a = np.asarray(crop).astype(int)
R, G, B = a[..., 0], a[..., 1], a[..., 2]
mask = (R > 140) & (R - G > 60) & (R - B > 60)
lbl, n = ndimage.label(mask)
cents = []
for i in range(1, n + 1):
    yy, xx = np.nonzero(lbl == i)
    if len(xx) < 120:
        continue
    cents.append([xx.mean(), yy.mean(), len(xx),
                  xx.min(), xx.max(), yy.min(), yy.max()])
# merge parts within 45px
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
for cx, cy, sz, *_ in merged:
    px = rect["x"] + cx * rect["w"] / W
    py = rect["y"] + cy * rect["h"] / H
    pts.append((round(px), round(py)))
    print(f"  icon cluster size={sz} -> page({px:.0f},{py:.0f})")

json.dump({"points": pts},
          open("/home/z/my-project/scripts/.captcha_points.json", "w"))

# instruction bar: below image, ~26px tall strip
bar = im.crop((int(rect["x"]) + 150, int(rect["y"] + rect["h"]) + 18,
               int(rect["x"] + rect["w"]) - 10,
               int(rect["y"] + rect["h"]) + 46))
bw, bh = bar.size
bar.resize((bw * 5, bh * 5), Image.LANCZOS).save(
    "/home/z/my-project/scripts/captcha_inst_5x.png")
# annotated img crop for icon ID
crop.resize((W * 3, H * 3), Image.LANCZOS).save(
    "/home/z/my-project/scripts/captcha_img_3x.png")
print(f"saved {len(pts)} pts -> .captcha_points.json")
