#!/usr/bin/env python3
"""Final precise pendant-centroid alignment with tight search windows."""
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
ys, xs = np.where(alpha > 128)
y0 = int(ys.min())

# ---- piece pendant: dark pixels in strip window x=30..60, y=262..296 ----
strip_gray = cv2.cvtColor(pc[:, :, :3], cv2.COLOR_BGR2GRAY).astype(np.float32)
pw = strip_gray[262:296, 30:60]
pm = (alpha[262:296, 30:60] > 128) & (pw < 110)
pys, pxs = np.where(pm)
p_cx = float(pxs.mean()) + 30
p_cy = float(pys.mean()) + 262
print(f"piece pendant centroid: ({p_cx:.2f}, {p_cy:.2f}) "
      f"[{pm.sum()} px]")

# ---- bg pendant: dark pixels in window x=158..196, y=262..298 ----
bw = bg_gray[262:298, 158:196]
bm = bw < 110
bys, bxs = np.where(bm)
b_cx = float(bxs.mean()) + 158
b_cy = float(bys.mean()) + 262
print(f"bg pendant centroid:    ({b_cx:.2f}, {b_cy:.2f}) [{bm.sum()} px]")

drag_x = b_cx - p_cx
dy = b_cy - p_cy
print(f"\ndelta from centroids: dx={drag_x:.2f} dy={dy:.2f}")
print(f"strip content y0={y0} (bg gap y should match)")
print(f"\n==> DRAG DISTANCE = {round(drag_x)}px")

# sanity render
vis = cv2.cvtColor(bg[:, :, :3], cv2.COLOR_BGR2RGB).copy()
left = int(round(drag_x))
cv2.rectangle(vis, (left, y0), (left + 60, y0 + 56), (255, 0, 0), 2)
cv2.circle(vis, (int(round(b_cx)), int(round(b_cy))), 3, (255, 0, 0), 1)
cv2.imwrite("/home/z/my-project/scripts/dbg_final_pos.png", vis)
print("final overlay: scripts/dbg_final_pos.png")
