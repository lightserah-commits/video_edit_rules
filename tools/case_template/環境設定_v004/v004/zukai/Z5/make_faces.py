#!/usr/bin/env python3
"""Z5 の「あなた」の焦り顔と汗（dots の make_zukai.py の face_variant と同じ作り方：パソコン業務.png の眉と口だけ描き替える）。
目の向きを3つ（上の窓・真ん中の窓・下の窓を見る）作り、ページで切り替えて「目が3つの窓を行き来する」にする。
  python3 zukai/Z5/make_faces.py  → zukai/assets/Z5_aseri_1.png・_2.png・_3.png"""
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

SRC = Path(os.path.expanduser("~/Desktop/video_edit_rules/素材/イラスト/パソコン業務.png"))
ASSETS = Path(__file__).resolve().parent.parent / "assets"
SKIN = (255, 205, 163, 255)          # dots の make_zukai.py と同じ
EYE = (40, 30, 28, 255)


def aseri(eye_dx, eye_dy, dst):
    im = Image.open(SRC).convert("RGBA")
    W, H = im.size
    ss = 4
    big = im.resize((W * ss, H * ss), Image.LANCZOS)
    d = ImageDraw.Draw(big)

    def S(*v):
        return [c * ss for c in v]
    d.ellipse(S(103, 175, 140, 194), fill=SKIN)                    # 元の口（にっこり）を消す
    for box in [(81, 88, 109, 103), (136, 88, 165, 103)]:
        d.ellipse(S(*box), fill=SKIN)                              # 元の眉を消す
    bc = (45, 35, 30, 255)
    for (x0, y0, x1, y1) in [(85, 100, 104, 92), (139, 92, 158, 100)]:   # 困り眉（dots の komari と同じ）
        d.line(S(x0, y0, x1, y1), fill=bc, width=5 * ss)
        for x, y in ((x0, y0), (x1, y1)):
            d.ellipse(S(x - 2.5, y - 2.5, x + 2.5, y + 2.5), fill=bc)
    # 目：元の黒い点を消して、窓の方へずらして描き直す
    # 消す所は、まわりの肌の色の平均でぼかして塗る（平らな SKIN だと、ほほの赤みの近くで明るい丸が見えた。2026-10-04）
    src = im.load()
    for (cx, cy) in [(96, 131), (148, 131)]:
        ring = [src[x, y] for x in range(cx - 16, cx + 17) for y in range(cy - 15, cy + 16)
                if 13 <= ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5 <= 16 and sum(src[x, y][:3]) > 500]
        col = tuple(sum(c[k] for c in ring) // len(ring) for k in range(3)) + (255,)
        m = Image.new("L", big.size, 0)
        ImageDraw.Draw(m).ellipse(S(cx - 12, cy - 12, cx + 12, cy + 12), fill=255)
        m = m.filter(ImageFilter.GaussianBlur(2 * ss))
        big.paste(Image.new("RGBA", big.size, col), (0, 0), m)
    d = ImageDraw.Draw(big)
    for (cx, cy) in [(96, 131), (148, 131)]:
        x, y = cx + eye_dx, cy + eye_dy
        d.ellipse(S(x - 6.5, y - 6, x + 6.5, y + 6), fill=EYE)
    # 口：波の線（焦り）
    pts = []
    for i in range(0, 9):
        x = 108 + i * 3.4
        y = 185 + (-3 if i % 2 else 3)
        pts.append((x * ss, y * ss))
    d.line(pts, fill=(150, 20, 50, 255), width=3 * ss, joint="curve")
    out = big.resize((W, H), Image.LANCZOS)
    out.putalpha(im.getchannel("A"))
    # 汗（頭の外にもはみ出すので、別の層に描いて重ねる）
    sw = Image.new("RGBA", (W * ss, H * ss), (0, 0, 0, 0))
    s = ImageDraw.Draw(sw)

    def drop(cx, top, r):
        # しずく：上がとがった形
        s.polygon([(cx * ss, top * ss), ((cx - r) * ss, (top + r * 2.2) * ss), ((cx + r) * ss, (top + r * 2.2) * ss)], fill=(120, 200, 245, 255))
        s.ellipse(S(cx - r, top + r * 1.6, cx + r, top + r * 3.6), fill=(120, 200, 245, 255))
        s.ellipse(S(cx - r * 0.45, top + r * 2.2, cx - r * 0.05, top + r * 2.9), fill=(235, 250, 255, 255))
    drop(196, 70, 9)
    drop(214, 112, 7)
    drop(36, 82, 7)
    sw = sw.resize((W, H), Image.LANCZOS)
    out.alpha_composite(sw)
    out.save(dst)
    print("wrote", dst)


if __name__ == "__main__":
    ASSETS.mkdir(exist_ok=True)
    for i, (dx, dy) in enumerate([(6, -9), (7, 0), (6, 9)], 1):   # 2026-10-04 反証：ずれが数pxで見えない → 上下 ±9 に広げた
        aseri(dx, dy, ASSETS / f"Z5_aseri_{i}.png")
