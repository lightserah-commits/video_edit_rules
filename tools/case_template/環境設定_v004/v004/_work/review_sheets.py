"""確認の画像を、見る人用に並べる（v003 の直した所・G1 のカットの前後・ハイライト）。出力 確認/まとめ/見る_*.jpg
  python3 v004/_work/review_sheets.py"""
import os
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__))
V = os.path.dirname(HERE)
D = os.path.join(V, "確認")
OUT = os.path.join(D, "まとめ")
font = ImageFont.truetype("/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc", 20)
names = sorted(n for n in os.listdir(D) if n.endswith(".png"))
W, H = 640, 360


def sheet(files, path, cols):
    rows = (len(files) + cols - 1) // cols
    sh = Image.new("RGB", (W * cols, (H + 28) * rows), "black")
    for i, n in enumerate(files):
        x, y = (i % cols) * W, (i // cols) * (H + 28)
        sh.paste(Image.open(os.path.join(D, n)).convert("RGB").resize((W, H)), (x, y + 28))
        ImageDraw.Draw(sh).text((x + 4, y + 3), n[:-4], fill="yellow", font=font)
    sh.save(path, quality=82)


hl = [n for n in names if "_ハイライト_" in n or "_挨拶_" in n]
sheet(hl, os.path.join(OUT, "見る_ハイライト.jpg"), 4)
# v004：直した所・G4・G5・画像・赤枠（G2）
for tag, nm, per, cols in [("_v004_", "直した所", 12, 3), ("_G4_", "G4", 12, 4), ("_G5_", "G5", 12, 4), ("_画像", "画像", 16, 4), ("_赤枠G2_", "赤枠", 16, 4)]:
    lst = [n for n in names if tag in n]
    for k in range(0, len(lst), per):
        sheet(lst[k:k + per], os.path.join(OUT, f"見る_{nm}_{k // per + 1:02d}.jpg"), cols)
g1 = [n for n in names if "_G1_" in n]
for k in range(0, len(g1), 16):
    sheet(g1[k:k + 16], os.path.join(OUT, f"見る_G1_{k // 16 + 1:02d}.jpg"), 4)
print(len(hl), len(g1))
