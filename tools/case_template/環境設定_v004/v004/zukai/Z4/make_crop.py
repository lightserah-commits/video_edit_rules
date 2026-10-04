#!/usr/bin/env python3
"""Z4：Orca の公式の画面（assets/orca_readme_hero.jpg）から、Claude Code の欄の頭（オレンジのキャラと「Claude Code」の字）を切り出す。
元の x372〜556・y88〜142 を 430px 幅（約2.34倍・高さ126px）に。右は「Code」の「e」（元の x549 まで）の直後で切り、
版の番号「v2.1.174」（元の x559 から）は入れない（番号は言っていない。窓の端で字が半分に切れて見えないように）。
キャラの右の2行目・3行目（Fable 5…・~/orca/…）は黒で隠す（黄色の枠が字の上を通らないように。見出しの行だけ残す）。
出力 assets/Z4_orca_cc.png（Orca の窓の中に置く。窓の中の高さは 129px）"""
from pathlib import Path
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
A = HERE.parent / "assets"
im = Image.open(A / "orca_readme_hero.jpg").convert("RGB")
box = (372, 88, 556, 142)
ImageDraw.Draw(im).rectangle([452, 113, 1000, 160], fill=(0, 0, 0))
W = 430
H = round((box[3] - box[1]) * W / (box[2] - box[0]))
im.crop(box).resize((W, H), Image.LANCZOS).save(A / "Z4_orca_cc.png")
print("Z4_orca_cc.png", W, H, "倍率", round(W / (box[2] - box[0]), 3))
