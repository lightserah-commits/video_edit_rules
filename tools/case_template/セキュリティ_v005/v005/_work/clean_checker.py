# AI の絵に焼き込まれた格子模様（透明の印）を白にする。2026-10-17 メインの AI
# 格子＝彩度がほぼ無い 252 前後と 224〜232 前後のマス。縁につながる所と、2つの明るさが混ざった塊を白にする
import sys
import numpy as np
from PIL import Image
from scipy import ndimage
for src in sys.argv[1:]:
    a = np.asarray(Image.open(src).convert("RGB")).astype(int)
    mx, mn = a.max(2), a.min(2)
    m = ((mx - mn) <= 12) & (mn >= 210)
    lab, n = ndimage.label(m)
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    fill = np.zeros_like(m)
    sizes = ndimage.sum(np.ones_like(lab), lab, range(1, n + 1))
    darkish = ndimage.sum((mn >= 214) & (mn <= 240), lab, range(1, n + 1))
    for i in range(1, n + 1):
        if i in border:
            fill |= lab == i
        elif sizes[i - 1] > 300 and 0.2 < darkish[i - 1] / sizes[i - 1] < 0.8:
            fill |= lab == i
    fill = ndimage.binary_dilation(fill, iterations=1) & (mn >= 190) & ((mx - mn) <= 16)
    out = a.copy()
    out[fill] = 255
    dst = src.replace(".png", "_w.png")
    Image.fromarray(out.astype(np.uint8)).save(dst)
    left = (m & ~fill & (mn <= 238)).sum()
    print(dst, "filled", int(fill.sum()), "left_grayish", int(left))
