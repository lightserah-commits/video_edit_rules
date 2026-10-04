#!/usr/bin/env python3
"""Z7 の確かめ：決まったコマを、カメラ＋図解で並べた1枚にする（カードの入り方・「頼む」の入り方を見る）。
  python3 zukai/Z7/strip.py 267-272,309-313,374-378  → zukai/out/Z7/確認_コマ.jpg
"""
import subprocess
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "out" / "Z7"
W = OUT / "_work"
spec = sys.argv[1] if len(sys.argv) > 1 else "267-272,309-313,374-378"
box = tuple(int(v) for v in (sys.argv[2] if len(sys.argv) > 2 else "0,120,1300,720").split(","))
idx = []
for part in spec.split(","):
    a, b = (part.split("-") + [part])[:2]
    idx += list(range(int(a), int(b) + 1))
tmp = W / "strip"
tmp.mkdir(exist_ok=True)
for f in tmp.glob("*.png"):
    f.unlink()
sel = "+".join(f"eq(n,{i})" for i in idx)
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(W / "base.mp4"), "-vf", f"select='{sel}'",
                "-fps_mode", "passthrough", str(tmp / "c_%04d.png")], check=True)
cams = sorted(tmp.glob("c_*.png"))
assert len(cams) == len(idx), (len(cams), len(idx))
fnt = ImageFont.truetype("/System/Library/Fonts/Hiragino Sans GB.ttc", 28)
tw = 640
th = int(tw * (box[3] - box[1]) / (box[2] - box[0]))
cols = 4
rows = (len(idx) + cols - 1) // cols
sh = Image.new("RGB", (cols * tw, rows * th), (40, 40, 40))
for k, (i, c) in enumerate(zip(idx, cams)):
    im = Image.open(c).convert("RGBA")
    im.alpha_composite(Image.open(W / "frames" / f"{i:05d}.png").convert("RGBA"))
    t = im.crop(box).resize((tw, th)).convert("RGB")
    d = ImageDraw.Draw(t)
    d.rectangle([0, 0, 150, 36], fill=(0, 0, 0))
    d.text((8, 2), f"f{i}", font=fnt, fill=(255, 255, 0))
    sh.paste(t, ((k % cols) * tw, (k // cols) * th))
p = OUT / "確認_コマ.jpg"
sh.save(p, quality=86)
print(p)
