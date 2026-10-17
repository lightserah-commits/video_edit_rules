"""確認の画像を、Premiere ではなく書き出した mp4 から切り出す（review_jobs.json の時刻。セキュリティについて v005 2026-10-17：
Premiere を長く使わずに済むように。Premiere の書き出しと同じ名前で 確認/ に PNG を書く。make_sheets.py で一覧にする）
  ~/Desktop/video_edit_rules/env/bin/python v005/_work/frames_from_jobs.py [mp4]"""
import json
import os
import subprocess
import sys
HERE = os.path.dirname(os.path.abspath(__file__))
V = os.path.dirname(HERE)
MP4 = sys.argv[1] if len(sys.argv) > 1 else os.path.join(V, "sec_v005.mp4")
jobs = json.load(open(os.path.join(HERE, "review_jobs.json"), encoding="utf-8"))
D = os.path.join(V, "確認")
os.makedirs(D, exist_ok=True)
seen = set()
for tc, name, sec in jobs:
    if name in seen:
        continue
    seen.add(name)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{sec + 0.5 / 29.97:.3f}", "-i", MP4, "-frames:v", "1", "-vf", "scale=960:-2",
                    os.path.join(D, name + ".png")], check=True)
print(len(seen), "枚 →", D)
