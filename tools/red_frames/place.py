#!/usr/bin/env python3
"""赤枠（07 の read_frame）を時刻へ：AI が字幕ごとに決めて反証した枠（batch_NN_out.json。画面の画像の 0〜1）を、今の版の土台の時刻の
赤枠（透明の PNG と red_frames.json）にする（どの案件でも使える道具）。組み立て（make_vNNN.py）が red_frames.json を読んで V4 に置く。
元：環境設定 v004 の _work/red_frames_g2.py（splits 入り）。

  python3 tools/red_frames/place.py --src <edit/analysis/赤枠_vNNN> --ver <edit/vNNN> --screen-size 3456x2234 [--out <版>/_work]
  - 続く字幕で group と rect が同じものは1つの枠（出したまま）。話が移ったら次の枠
  - 枠は group の最初の字幕の頭から、最後の字幕の次の字幕の頭まで。画面を映している間だけ（6コマ未満は捨てる）
  - 字幕の途中で画面が替わる（スクロール・ページが替わる・メニューが開く）時は、item に splits を書く：
      "splits": [{"at_screen_frame": 画面録画のコマ, "rect": [x0, y0, x1, y1] か null（そこから枠なし）, "label": …, "group": …}]
    画面録画のそのコマが映るタイムラインのコマから、その rect に替える（label・group は省くと item のまま）。
    rect が null の item に splits を書くと「字幕の途中から枠を出す」になる。素材のコマで書くので、カットを変えても場所はずれない
  - 画面の画像 → タイムラインの px：画面録画（--screen-size。例 3456×2234）を高さ 1080 に合わせて真ん中に置いた時の位置
    （02 の画面の置き方と違う案件は --disp "幅,左" で渡す）
  - 見た目は 07 の read_frame（赤 255,30,30・角丸・線 8px）
  出力：<out>/red_frames.json と <out>/red_frames/<prefix>_NNN_<字幕ID>.png（前の red_frames.json は red_frames_前.json に1つだけ残す。
  <prefix>_*.png は作り直す）。試す時は --out を別の所に
"""
import argparse
import bisect
import glob
import json
import os
import shutil
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

STROKE, COLOR = 8, (255, 30, 30, 255)


def main():
    ap = argparse.ArgumentParser(description="決めた赤枠を今の版の時刻の赤枠（PNG と red_frames.json）にする")
    ap.add_argument("--src", required=True, help="batch_NN_out.json のあるフォルダ（例 edit/analysis/赤枠_vNNN）")
    C.add_case_args(ap)
    ap.add_argument("--screen-size", required=True, help="画面録画の大きさ WxH（例 3456x2234）")
    ap.add_argument("--disp", help="タイムラインでの画面の「幅,左」px（省くと高さ 1080 に合わせて真ん中）")
    ap.add_argument("--out", help="出力のフォルダ（省くと <版>/_work）")
    ap.add_argument("--prefix", default="rf", help="PNG の名前の頭（既定 rf。環境設定 v004 は g2）")
    ap.add_argument("--min-frames", type=int, default=6, help="これより短い枠は捨てる（既定 6コマ）")
    a = ap.parse_args()
    C.resolve(a)
    out_root = a.out or (os.path.join(a.ver, "_work") if a.ver else None)
    if not out_root:
        raise SystemExit("--out か --ver を渡す")
    sw, sh = (int(v) for v in a.screen_size.lower().split("x"))
    if a.disp:
        disp_w, off_x = (float(v) for v in a.disp.split(","))
    else:
        disp_w = sw * 1080 / sh
        off_x = (1920 - disp_w) / 2
    mp, capj, cj = C.load(a.map), C.load(a.captions), C.load(a.cuts)
    ctl = mp["caption_tl"]
    _, nxt = C.caption_order(mp, capj)
    t2s = C.tl_to_src(cj)

    def screen_frame(f):
        """タイムラインのコマ → 画面録画のコマ（V2 のクリップの in 点と同じ決め方）"""
        return t2s(f) - mp["n_screen"]

    def tl_at_screen(s, e, n):
        """字幕の間（s〜e）で、画面録画のコマ n 以降が初めて映るタイムラインのコマ"""
        for f in range(s, e):
            if screen_frame(f) >= n:
                return f
        return None

    items = []
    for p in sorted(glob.glob(os.path.join(a.src, "batch_*_out.json"))):
        items += C.load(p)["items"]
    if not items:
        raise SystemExit(f"{a.src} に batch_*_out.json が無い")
    lost = [x["id"] for x in items if x["id"] not in ctl or x["id"] not in nxt]
    if lost:
        print(f"！ 今の版に無い字幕（枠を捨てた）{len(lost)}：{lost[:10]}")
    items = [x for x in items if x["id"] in ctl and x["id"] in nxt]
    items.sort(key=lambda x: ctl[x["id"]])
    parts = []
    for x in items:
        s, e = ctl[x["id"]], nxt[x["id"]]
        cut = [(s, x.get("rect"), x.get("group", ""), x.get("label", ""))]
        for sp in x.get("splits", []):
            f = tl_at_screen(s, e, sp["at_screen_frame"])
            if f is None:
                print(f"！ 字幕 {x['id']}：画面のコマ {sp['at_screen_frame']} が字幕の間に映らない（split を飛ばした）")
                continue
            cut.append((f, sp.get("rect"), sp.get("group", x.get("group", "")), sp.get("label", x.get("label", ""))))
        cut.sort(key=lambda c: c[0])
        for k, (f0, r, g, lab) in enumerate(cut):
            f1 = cut[k + 1][0] if k + 1 < len(cut) else e
            if f1 > f0:
                parts.append({"id": x["id"], "a": f0, "b": f1, "rect": r, "group": g, "label": lab, "split": k > 0})
    groups = []
    for x in parts:
        if not x["rect"]:
            groups.append(None)
            continue
        r = [round(v, 3) for v in x["rect"]]
        g = groups[-1] if groups else None                 # 前の区切りが枠なし（None）なら新しい枠
        if g and g["group"] == x["group"] and g["rect"] == r:
            g["ids"].append(x["id"])
            g["b"] = x["b"]
        else:
            groups.append({"group": x["group"], "rect": r, "label": x["label"], "ids": [x["id"]], "a": x["a"], "b": x["b"], "split": x["split"]})
    groups = [g for g in groups if g]
    out_dir = os.path.join(out_root, "red_frames")
    os.makedirs(out_dir, exist_ok=True)
    for f in glob.glob(os.path.join(out_dir, f"{a.prefix}_*.png")):
        os.remove(f)
    dst = os.path.join(out_root, "red_frames.json")
    if os.path.exists(dst):
        shutil.copy(dst, os.path.join(out_root, "red_frames_前.json"))
    frames = []
    for k, g in enumerate(groups):
        sp = C.clip_to_screen(mp, g["a"], g["b"])
        if not sp or sp[1] - sp[0] < a.min_frames:
            continue
        x0, y0, x1, y1 = g["rect"]
        rect = [off_x + x0 * disp_w, y0 * 1080, off_x + x1 * disp_w, y1 * 1080]
        img = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
        ImageDraw.Draw(img).rounded_rectangle(rect, 12, outline=COLOR, width=STROKE)
        png = os.path.join(out_dir, f"{a.prefix}_{k:03d}_{g['ids'][0].replace('+', 'p')}{'s' if g['split'] else ''}.png")
        img.save(png)
        frames.append({"id_from": g["ids"][0], "id_to": g["ids"][-1], "png": png, "rect_px": [round(v) for v in rect],
                       "start": sp[0] * C.FT, "end": sp[1] * C.FT, "read": g["label"], "group": g["group"], "ocr": "", "ratio": []})
    # 同じ場所の枠が、間を空けずに続く時は1つにまとめる（字幕の切れ目で枠がちらつかないように）
    merged = []
    for f in frames:
        if merged and merged[-1]["rect_px"] == f["rect_px"] and merged[-1]["end"] == f["start"]:
            merged[-1]["end"] = f["end"]
            merged[-1]["id_to"] = f["id_to"]
            os.remove(f["png"])
        else:
            merged.append(f)
    json.dump({"frames": merged, "hits": len(items), "how": f"tools/red_frames/place.py：{a.src} の AI の判断と反証（splits で字幕の途中の画面の替わり目に合わせる）"},
              open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    tot = sum(f["end"] - f["start"] for f in merged) / C.FT / C.FPS
    print(f"字幕 {len(items)}（枠あり {sum(1 for x in items if x.get('rect') or x.get('splits'))}）→ 赤枠 {len(merged)} 個（合わせて {tot / 60:.1f}分）→ {dst}")


if __name__ == "__main__":
    main()
