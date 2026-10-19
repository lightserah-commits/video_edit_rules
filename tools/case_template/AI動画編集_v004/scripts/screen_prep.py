"""Loom の画面（media/screen_CFR2997.mp4）から、台本係・装飾係・赤枠係が見る材料を作る（AI動画編集 2026-10-16。1015 の screen_frames5.py・screen_activity.py の代わり）。
  ~/Desktop/video_edit_rules/env/bin/python scripts/screen_prep.py
  analysis/screen/f5/sNNNNN.jpg（5秒ごと・1108×720 のまま。NNNNN＝画面コピーの秒）と analysis/screen/f5_index.tsv（通しのカメラの秒 \t 画面コピーの秒 \t ファイル名 \t loom）
  analysis/screen/motion.json（1秒ごとの画面の変化 0〜100。0.5秒ごとの 160×104 の灰色の画像の差の平均×4、上限100）
"""
import json
import os
import subprocess

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
A = os.path.join(os.path.dirname(HERE), "analysis")
M = os.path.join(os.path.dirname(HERE), "media")
S = os.path.join(A, "screen")
F5 = os.path.join(S, "f5")
os.makedirs(F5, exist_ok=True)
sync = json.load(open(os.path.join(A, "sync", "sync.json")))
SCR = os.path.join(M, "screen_CFR2997.mp4")
dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", SCR]).decode())
# 5秒ごとの静止画
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", SCR, "-vf", "fps=1/5", "-q:v", "3", "-start_number", "0", os.path.join(F5, "t%05d.jpg")], check=True)
rows = []
for i in range(int(dur // 5) + 1):
    src = os.path.join(F5, f"t{i:05d}.jpg")
    if not os.path.exists(src):
        continue
    tau = i * 5
    dst = os.path.join(F5, f"s{tau:05d}.jpg")
    os.replace(src, dst)
    rows.append(f"{tau + sync['offset']:.2f}\t{tau}\t{os.path.basename(dst)}\tloom")
open(os.path.join(S, "f5_index.tsv"), "w").write("\n".join(rows) + "\n")
# 画面の動き
W, H = 160, 104
raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i", SCR, "-vf", f"fps=2,scale={W}:{H},format=gray", "-f", "rawvideo", "-"])
fr = np.frombuffer(raw, dtype=np.uint8).reshape(-1, H, W).astype(np.float32)
d = np.abs(np.diff(fr, axis=0)).mean(axis=(1, 2))
per_s = [float(min(100, 4 * max(d[2 * k:2 * k + 2]) if len(d[2 * k:2 * k + 2]) else 0)) for k in range(int(len(d) / 2) + 1)]
json.dump({"motion": [round(x, 1) for x in per_s], "note": "画面コピーの秒ごと（0〜100）"}, open(os.path.join(S, "motion.json"), "w"))
print("f5", len(rows), "motion", len(per_s), "p50/p90", np.percentile(per_s, [50, 90]).round(1))
