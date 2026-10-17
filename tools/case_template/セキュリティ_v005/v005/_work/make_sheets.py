"""確認の画像を12枚ずつ（3列×4行・名前つき）並べる。出力 確認/_sheets/sheet_NN.jpg（確かめ係が全部見る一覧）
  ~/Desktop/video_edit_rules/env/bin/python v005/_work/make_sheets.py"""
import os
from PIL import Image, ImageDraw, ImageFont
V = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(V, "確認")
OUT = os.path.join(D, "_sheets")
os.makedirs(OUT, exist_ok=True)
font = ImageFont.truetype("/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc", 20)
names = sorted(n for n in os.listdir(D) if n.endswith(".png"))
W, H, C, R = 640, 360, 3, 4
for k in range(0, len(names), C * R):
    files = names[k:k + C * R]
    sh = Image.new("RGB", (W * C, (H + 28) * R), "black")
    for i, n in enumerate(files):
        x, y = (i % C) * W, (i // C) * (H + 28)
        sh.paste(Image.open(os.path.join(D, n)).convert("RGB").resize((W, H)), (x, y + 28))
        ImageDraw.Draw(sh).text((x + 4, y + 3), n[:-4], fill="yellow", font=font)
    sh.save(os.path.join(OUT, f"sheet_{k // (C * R):02d}.jpg"), quality=80)
print(f"{len(names)}枚 → {(len(names) + C * R - 1) // (C * R)}枚の一覧 {OUT}")
