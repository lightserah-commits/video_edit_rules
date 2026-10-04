#!/usr/bin/env python3
"""セリフの入り・出の候補を見る。語（units.json）の頭・終わりの前後を 20ミリ秒ごとの大きさ（-dB）で1行に並べ、
一番静かな所（谷）を出す。asr-env の python で:  edges.py 81.78 83.80 [幅=0.5]
"""
import json
import sys
from pathlib import Path

import numpy as np

EDIT = Path(__file__).resolve().parents[3]
A = EDIT / "analysis"
U = json.load(open(A / "units.json", encoding="utf-8"))
E = np.load(A / "camera_env.npy")


def words_near(t0, t1):
    out = []
    for u in U:
        if u["end"] < t0 - 1 or u["start"] > t1 + 1:
            continue
        for a, b, w in u["words"]:
            if b >= t0 and a <= t1:
                out.append((a, b, w))
    return out


def row(t0, t1):
    vals = []
    t = t0
    while t < t1 - 1e-6:
        i = int(round(t * 100))
        vals.append((t, float(E[i:i + 2].max())))
        t += 0.02
    s = " ".join(f"{-v:2.0f}" for _, v in vals)
    lo = min(vals, key=lambda x: x[1])
    return s, lo


def show(ws, we, w=0.5):
    for name, a, b in (("頭", ws - w, ws + 0.3), ("尾", we - 0.3, we + w)):
        s, lo = row(a, b)
        wd = " ".join(f"{x:.2f}-{y:.2f}{z}" for x, y, z in words_near(a, b))
        print(f"{name} {a:.2f}〜 [{s}]  谷 {lo[0]:.2f}({lo[1]:.0f})  語: {wd}")


if __name__ == "__main__":
    show(float(sys.argv[1]), float(sys.argv[2]), float(sys.argv[3]) if len(sys.argv) > 3 else 0.5)
