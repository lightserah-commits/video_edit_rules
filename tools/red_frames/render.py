#!/usr/bin/env python3
"""赤枠（07 の read_frame）の確かめ：AI が決めた枠（batch_NN_out.json）を画面の画像の上に描いて、見直し・反証に使う絵にする（どの案件でも使える道具）。
元：環境設定 v004 の analysis/赤枠_v004/render.py。

  python3 tools/red_frames/render.py --dir <edit/analysis/赤枠_vNNN> [NN …]   （NN を省くと batch_*_out.json の全部）
  → <dir>/previews/NN/<字幕ID>_<k>.jpg（上の帯：字幕ID・話者・字幕の文字／枠の名前と group）と <dir>/previews/sheet_NN.jpg（3列に並べた一覧）
batch_NN_out.json：{"items": [{"id", "rect": [x0, y0, x1, y1]（画面の画像の 0〜1）か null, "label", "group", "reason", "splits"?}]}
  splits がある字幕は、その画面のコマ（at_screen_frame）以降の画像に splits の rect を描く
"""
import argparse
import glob
import json
import os
import re

from PIL import Image, ImageDraw, ImageFont

FONT = "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"


def rect_at(d, screen_frame):
    """字幕の決め（d）の、画面のコマ screen_frame の時の枠と名前"""
    r, lab, g = d.get("rect"), d.get("label"), d.get("group", "")
    for sp in sorted(d.get("splits", []), key=lambda s: s["at_screen_frame"]):
        if screen_frame >= sp["at_screen_frame"]:
            r, lab, g = sp.get("rect"), sp.get("label", lab), sp.get("group", g)
    return r, lab, g


def render(d_dir, n):
    inp = json.load(open(os.path.join(d_dir, f"batch_{n}_in.json"), encoding="utf-8"))
    out = json.load(open(os.path.join(d_dir, f"batch_{n}_out.json"), encoding="utf-8"))
    dec = {x["id"]: x for x in out["items"]}
    font = ImageFont.truetype(FONT, 22)
    pd = os.path.join(d_dir, "previews", n)
    os.makedirs(pd, exist_ok=True)
    tiles = []
    for it in inp["items"]:
        d = dec.get(it["id"], {})
        for k, fr in enumerate(it["frames"]):
            if not os.path.exists(fr["png"]):
                print(f"！ 画像が無い {fr['png']}")
                continue
            im = Image.open(fr["png"]).convert("RGB")
            W, H = im.size
            dr = ImageDraw.Draw(im)
            r, lab, g = rect_at(d, fr["screen_frame"])
            if r:
                x0, y0, x1, y1 = r
                dr.rounded_rectangle([x0 * W, y0 * H, x1 * W, y1 * H], 8, outline=(255, 30, 30), width=6)
            bar = Image.new("RGB", (W, 64), (0, 0, 0))
            ImageDraw.Draw(bar).text((8, 4), f"{it['id']}（{it.get('who', '')}）{it['text'][:44]}", fill="white", font=font)
            ImageDraw.Draw(bar).text((8, 34), f"枠：{lab or 'なし'}  [{g}]  画面のコマ {fr['screen_frame']}", fill="yellow", font=font)
            im2 = Image.new("RGB", (W, H + 64))
            im2.paste(bar, (0, 0))
            im2.paste(im, (0, 64))
            p = os.path.join(pd, f"{it['id'].replace('+', 'p')}_{k}.jpg")
            im2.save(p, quality=80)
            tiles.append(p)
    if not tiles:
        print(n, "描く画像が無い")
        return
    cols = 3
    w0, h0 = Image.open(tiles[0]).size
    tw, th = 640, int(640 * h0 / w0)
    rows = (len(tiles) + cols - 1) // cols
    sh = Image.new("RGB", (tw * cols, th * rows), "black")
    for i, p in enumerate(tiles):
        sh.paste(Image.open(p).resize((tw, th)), ((i % cols) * tw, (i // cols) * th))
    sh.save(os.path.join(d_dir, "previews", f"sheet_{n}.jpg"), quality=75)
    print(n, len(tiles), "枚 →", pd)


def main():
    ap = argparse.ArgumentParser(description="決めた赤枠を画面の画像に描いて確かめる絵にする")
    ap.add_argument("--dir", required=True, help="batch_NN_in.json・batch_NN_out.json のあるフォルダ")
    ap.add_argument("nums", nargs="*", help="束の番号（01 など。省くと全部）")
    a = ap.parse_args()
    nums = a.nums or sorted(re.search(r"batch_(\d+)_out", p).group(1) for p in glob.glob(os.path.join(a.dir, "batch_*_out.json")))
    if not nums:
        raise SystemExit("batch_NN_out.json が無い（README.md の「2. 決める」）")
    for n in nums:
        render(a.dir, n)


if __name__ == "__main__":
    main()
