#!/usr/bin/env python3
"""Z6 の「目を閉じた顔」（寝ると いらんことを 忘れる）。dots v002 の make_zukai.py の face_variant と同じ作り方：
素材/イラスト/パソコン業務.png の目だけを肌の色で消し、閉じた目（下向きの弧）を描く。体・パソコン・形・口は変えない。
出力：zukai/assets/Z6_pc_nemuri.png（元と同じ 241×350）"""
import os
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
SRC = Path(os.path.expanduser("~/Desktop/video_edit_rules/素材/イラスト/パソコン業務.png"))
DST = HERE.parent / "assets" / "Z6_pc_nemuri.png"
SKIN_EYE = (255, 199, 156, 255)        # 目の周りの肌の色（元の画素を測った値。dots の SKIN (255,205,163) より少し濃い所）

im = Image.open(SRC).convert("RGBA")
W, H = im.size
ss = 4
big = im.resize((W * ss, H * ss), Image.LANCZOS)
d = ImageDraw.Draw(big)


def S(*v):
    return [c * ss for c in v]


# 元の目（黒い丸。x89〜100・y126〜135 と x142〜153・y125〜135）を消す
for box in [(86, 122, 104, 139), (139, 121, 157, 139)]:
    d.ellipse(S(*box), fill=SKIN_EYE)
# 閉じた目：下向きの弧（にっこり寝ている目）。眉と同じ濃い色
ec = (40, 30, 28, 255)
for (x0, x1) in [(87, 103), (140, 156)]:
    d.arc(S(x0, 120, x1, 136), 20, 160, fill=ec, width=3 * ss)
out = big.resize((W, H), Image.LANCZOS)
out.putalpha(im.getchannel("A"))
DST.parent.mkdir(parents=True, exist_ok=True)
out.save(DST)
print(DST, out.size)
