"""指示の動画の 1秒ごとの画像から、プログラムモニターだけを切り出して並べる（時刻つき）。
python3 sheet.py <名前> <動画の秒,...>"""
import json, sys, os
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__))
rows = json.load(open(os.path.join(HERE, 'playhead.json')))
name, secs = sys.argv[1], [int(x) for x in sys.argv[2].split(',')]
font = ImageFont.truetype('/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc', 22)
W, H = 624, 351
cols = 3
sheet = Image.new('RGB', (W * cols, (H + 30) * ((len(secs) + cols - 1) // cols)), 'black')
for i, s in enumerate(secs):
    im = Image.open(os.path.join(HERE, 'frames1s', f'f{s + 1:04d}.jpg')).crop((302, 148, 926, 499))
    x, y = (i % cols) * W, (i // cols) * (H + 30)
    sheet.paste(im, (x, y + 30))
    r = rows[min(s * 2, len(rows) - 1)]
    ImageDraw.Draw(sheet).text((x + 6, y + 3), f"指示 {s // 60}:{s % 60:02d} → v002 {r['tc']}", fill='yellow', font=font)
sheet.save(os.path.join(HERE, 'sheets', name + '.jpg'), quality=85)
