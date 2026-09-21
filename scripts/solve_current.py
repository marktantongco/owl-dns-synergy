#!/usr/bin/env python3
"""Definitive solve with the REAL captcha assets:
- piece = bitwise_and_result.png (RGBA strip, 42x300 for this puzzle)
- bg = inpainted_with_mask.png (the gap is inpainted + a dark shadow hint
  baked at the target position)
Method: the shadow = piece alpha shape darkened. Match piece alpha columns
against bg darkness columns (full 300x300 search, exact y from piece alpha)."""
import cv2
import numpy as np

p = cv2.imread("/home/z/my-project/scripts/cur_piece.png",
               cv2.IMREAD_UNCHANGED)
b = cv2.imread("/home/z/my-project/scripts/cur_bg.png")
bg_gray = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY).astype(np.float32)
alpha = p[:, :, 3]

ys, xs = np.where(alpha > 128)
py0, py1 = int(ys.min()), int(ys.max()) + 1
px0, px1 = int(xs.min()), int(xs.max()) + 1
print(f"piece opaque bbox: x[{px0},{px1}) y[{py0},{py1}) "
      f"size {px1-px0}x{py1-py0}")
am = (alpha[py0:py1, px0:px1] > 128).astype(np.float32)
H, W = am.shape

# darkness map: pixel vs 15px median
med = cv2.medianBlur(bg_gray.astype(np.uint8), 15).astype(np.float32)
dark = np.clip(med - bg_gray, 0, None)

# model: dark(y,x) ≈ k * am(y-py0, x-D) at the target; scan D and y
print("scanning D x dy:")
res = []
for dy in range(-12, 13):
    gy = py0 + dy
    if gy < 0 or gy + H > 300:
        continue
    band = dark[gy:gy + H]
    for D in range(0, 301 - W):
        win = band[:, D:D + W]
        k = float((win * am).sum() / max((am * am).sum(), 1))
        if not (0.1 < k < 1.2):
            continue
        resid = win - k * am
        res.append((float((resid * resid).sum()), D, gy, k))
res.sort()
print("top 8 (resid, D, gy, k):")
for r, D, gy, k in res[:8]:
    print(f"  resid={r:9.1f} D={D:3d} gy={gy} k={k:.3f}")
if res:
    r, D, gy, k = res[0]
    print(f"\n==> PIECE LEFT EDGE TARGET D={D}  "
          f"(drag = D - {px0} = {D - px0}px, gy={gy} vs py0={py0}, k={k:.2f})")
    vis = b.copy()
    cv2.rectangle(vis, (D, gy), (D + W, gy + H), (0, 0, 255), 2)
    cv2.imwrite("/home/z/my-project/scripts/dbg_cur_solve.png", vis)
    print("overlay: scripts/dbg_cur_solve.png")
