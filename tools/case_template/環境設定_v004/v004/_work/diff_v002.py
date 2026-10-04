"""v003 の確認の画像を、v002 の同じ名前（時刻を除いた所：強調_意味_P01_25・動く図解Z1_f0008 など）の画像と比べる（工程10 の下見）。
同じ演出なのに絵が違う所だけを、目で見る一覧にする。出力 _work/diff_v002.tsv（違いの大きい順）と 確認/まとめ/違い_*.jpg（左 v002・右 v003）
  python3 v004/_work/diff_v002.py"""
import os

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageStat

HERE = os.path.dirname(os.path.abspath(__file__))
V = os.path.dirname(HERE)
OLD = os.path.join(os.path.dirname(V), "v003", "確認")   # v004：前の版（v003）と比べる
NEW = os.path.join(V, "確認")
OUT = os.path.join(NEW, "まとめ")
os.makedirs(OUT, exist_ok=True)


def label(n):
    return n.split("_", 1)[1] if "_" in n else n


old = {}
for n in os.listdir(OLD):
    if n.endswith(".png"):
        old.setdefault(label(n), n)
rows = []
for n in sorted(os.listdir(NEW)):
    if not n.endswith(".png"):
        continue
    lb = label(n)
    if lb not in old:
        rows.append((-1.0, n, "", "v002 に同じ名前なし"))
        continue
    a = Image.open(os.path.join(OLD, old[lb])).convert("L").resize((480, 270))
    b = Image.open(os.path.join(NEW, n)).convert("L").resize((480, 270))
    d = ImageStat.Stat(ImageChops.difference(a, b)).mean[0]
    rows.append((round(d, 2), n, old[lb], ""))
rows.sort(key=lambda r: -r[0])
with open(os.path.join(HERE, "diff_v002.tsv"), "w", encoding="utf-8") as f:
    f.write("違い（0〜255の平均）\tv003\tv002\tメモ\n")
    for r in rows:
        f.write("\t".join(str(x) for x in r) + "\n")
font = ImageFont.truetype("/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc", 18)
big = [r for r in rows if r[0] >= 6.0]
for k in range(0, len(big), 8):
    sh = Image.new("RGB", (960 * 2, 300 * min(8, len(big) - k)), "black")
    for i, (d, n, o, _) in enumerate(big[k:k + 8]):
        sh.paste(Image.open(os.path.join(OLD, o)).convert("RGB").resize((480, 270)), (0, i * 300 + 30))
        sh.paste(Image.open(os.path.join(NEW, n)).convert("RGB").resize((480, 270)), (490, i * 300 + 30))
        ImageDraw.Draw(sh).text((4, i * 300 + 4), f"違い {d}  v002 {o}  →  v003 {n}", fill="yellow", font=font)
    sh = sh.crop((0, 0, 980, sh.height))
    sh.save(os.path.join(OUT, f"違い_{k // 8 + 1:02d}.jpg"), quality=80)
print(f"比べた {sum(1 for r in rows if r[0] >= 0)}、v002 に無い {sum(1 for r in rows if r[0] < 0)}、違いが 6 以上 {len(big)}")
