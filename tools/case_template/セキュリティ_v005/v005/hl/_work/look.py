#!/usr/bin/env python3
"""セリフの入り・出を決めるための表示。区切り（units.json）の語の時刻と、10ミリ秒ごとの声の大きさ（camera_env.npy）を並べる。
  asr-env の python で:  look.py 30 31        区切り 30〜31 の語と、前後 0.6秒の大きさ（40ミリ秒ごと）
                         look.py t 81.5 84.2  カメラの秒で指定
"""
import json
import sys
from pathlib import Path

import numpy as np

EDIT = Path(__file__).resolve().parents[3]
A = EDIT / "analysis"
U = json.load(open(A / "units.json", encoding="utf-8"))
E = np.load(A / "camera_env.npy")


def show(t0, t1, step=0.04):
    words = []
    for u in U:
        if u["end"] < t0 or u["start"] > t1:
            continue
        for a, b, w in u["words"]:
            if b >= t0 and a <= t1:
                words.append((a, b, w, u["u"]))
    t = t0
    while t < t1:
        i = int(round(t * 100))
        seg = E[i:i + int(step * 100)]
        db = float(seg.max()) if len(seg) else -99
        ws = [f"{w}({u})" for a, b, w, u in words if a <= t < a + step or (t <= a < t + step)]
        bar = "#" * max(0, int((db + 70) / 2))
        print(f"{t:9.2f} {db:6.1f} {bar:<32s} {' '.join(ws)}")
        t += step


if __name__ == "__main__":
    if sys.argv[1] == "t":
        show(float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4]) if len(sys.argv) > 4 else 0.04)
    else:
        ua, ub = int(sys.argv[1]), int(sys.argv[2])
        show(U[ua]["start"] - 0.6, U[ub]["end"] + 0.6)
