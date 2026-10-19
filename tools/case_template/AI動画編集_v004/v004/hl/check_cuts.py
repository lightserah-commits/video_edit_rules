#!/usr/bin/env python3
"""ハイライトのつなぎ目の検査。08 の no_chop（tools/check_chops.py と同じ見方：つなぎ目の手前2コマと素材の向こう0.1秒が
両方 -38dB 以上なら「声の途中で切った」）と no_slivers（0.2秒未満の切れ端）を、clips.tsv の入り・出で確かめる。
  python3 check_cuts.py   （声の WAV は analysis/asr/_work/camera.wav。カメラの秒と同じ）
"""
import audioop
import math
import os
import sys
import wave
from pathlib import Path

HERE = Path(__file__).resolve().parent
WAV = HERE.parent.parent / "analysis" / "asr" / "_work" / "camera.wav"
sys.path.insert(0, os.path.expanduser("~/Desktop/video_edit_rules/tools"))
LOUD, EDGE, BEYOND, FPS = -38.0, 2, 0.10, 30000 / 1001


class Wav:
    def __init__(self, p):
        self.w = wave.open(str(p), "rb")
        self.rate, self.n = self.w.getframerate(), self.w.getnframes()

    def db(self, t0, t1):
        a, b = max(0, int(t0 * self.rate)), min(self.n, int(t1 * self.rate))
        self.w.setpos(a)
        raw = self.w.readframes(b - a)
        hop = self.rate // 100 * 2
        best = max([audioop.rms(raw[k:k + hop], 2) for k in range(0, len(raw) - hop + 1, hop)] or [0])
        return 20 * math.log10(best / 32768) if best else -99.0


w = Wav(WAV)
bad, short = [], []
for ln in (HERE / "clips.tsv").read_text(encoding="utf-8").splitlines():
    if not ln.strip() or ln.startswith("#"):
        continue
    cid, a, b, txt = ln.split("\t")
    a, b = float(a), float(b)
    head = w.db(a, a + EDGE / FPS) >= LOUD and w.db(a - BEYOND, a) >= LOUD
    tail = w.db(b - EDGE / FPS, b) >= LOUD and w.db(b, b + BEYOND) >= LOUD
    if head or tail:
        bad.append((cid, "頭" if head else "", "終わり" if tail else "", txt))
    if b - a < 0.2:
        short.append((cid, round(b - a, 3), txt))
print("声の途中で切ったつなぎ目:", len(bad), bad)
print("0.2秒未満の切れ端:", len(short), short)
sys.exit(1 if bad or short else 0)
