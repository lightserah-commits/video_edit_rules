"""v004 G2（2026-10-04 小川さん「画面共有のところ全体的に、どこの話してるかっていうのは全部赤枠で囲ってください」）：
analysis/赤枠_v004/batch_NN_out.json（字幕ごとに AI が決めて反証した枠。画面の画像の 0〜1）を、今の土台（base_v004_map.json）の時刻の赤枠にする。
  - 続く字幕で group と rect が同じものは1つの枠（出したまま）。話が移ったら次の枠
  - 枠は group の最初の字幕の頭から、最後の字幕の次の字幕の頭まで。画面を映している間だけ（screen_marks と同じ）
  - 字幕の途中で画面が替わる（スクロール・ページが替わる・メニューが開く）時は、item に splits を書く（2026-10-04 最後の直し）：
      "splits": [{"at_screen_frame": 画面録画のコマ, "rect": [x0, y0, x1, y1] か null（そこから枠なし）, "label": …, "group": …}]
    画面録画（screen_CFR2997.mp4）のそのコマが映るタイムラインのコマから、その rect に替える（label・group は省くと item のまま）。
    rect が null の item に splits を書くと「字幕の途中から枠を出す」になる。素材のコマで書くので、カットを変えても場所はずれない
  - 画面の画像 → タイムラインの px：画面録画（3456×2234）は高さ 1080 に合わせて真ん中（幅 1670.7・左 124.7px）
  - 見た目は 07 の read_frame（赤 255,30,30・角丸・線 8px）。出力 _work/red_frames.json（前のものは red_frames_v003.json に残す）と _work/red_frames/g2_*.png
  - 試す時は出力先を環境変数 RED_OUT で変える（RED_OUT/red_frames.json と RED_OUT/red_frames/。_work の物は触らない）
  python3 v004/_work/red_frames_g2.py
  RED_OUT=/tmp/x python3 v004/_work/red_frames_g2.py"""
import bisect
import glob
import json
import os
import shutil

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
E = os.path.dirname(os.path.dirname(HERE))
SRC = os.path.join(E, "analysis", "赤枠_v004")
OUT = os.environ.get("RED_OUT") or HERE
FT = 8475667200
DISP_W = 3456 * 1080 / 2234
OFF_X = (1920 - DISP_W) / 2
STROKE, COLOR = 8, (255, 30, 30, 255)
mp = json.load(open(os.path.join(HERE, "base_v004_map.json"), encoding="utf-8"))
ctl = mp["caption_tl"]
capj = json.load(open(os.path.join(HERE, "captions_v004.json"), encoding="utf-8"))
caps = sorted([c for c in capj["captions"] if c["mode"] != "drop" and "src" in c], key=lambda c: ctl[c["id"]])
nxt = {c["id"]: (ctl[caps[k + 1]["id"]] if k + 1 < len(caps) else mp["total_frames"]) for k, c in enumerate(caps)}
cj = json.load(open(os.path.join(HERE, "cuts_v004.json"), encoding="utf-8"))
_segs, _t = [], cj.get("highlight_external_frames", 0)
for a, b in cj["highlight_frames"] + cj["keep_frames"]:
    _segs.append((_t, a, b - a))
    _t += b - a
_starts = [s[0] for s in _segs]


def screen_frame(f):
    """タイムラインのコマ → 画面録画のコマ（screen_ocr_v004.py と同じ。V2 のクリップの in 点と一致）"""
    i = bisect.bisect_right(_starts, f) - 1
    t0, a, L = _segs[i]
    return a + min(f - t0, L - 1) - mp["n_screen"]


def tl_at_screen(a, b, n):
    """字幕の間（a〜b）で、画面録画のコマ n 以降が初めて映るタイムラインのコマ"""
    for f in range(a, b):
        if screen_frame(f) >= n:
            return f
    return None


def clip_to_screen(a, b):
    for x, y in mp["screen_spans"]:
        if x < b and a < y:
            return max(a, x), min(b, y)
    return None


items = []
for p in sorted(glob.glob(os.path.join(SRC, "batch_*_out.json"))):
    items += json.load(open(p, encoding="utf-8"))["items"]
items = [x for x in items if x["id"] in ctl]
items.sort(key=lambda x: ctl[x["id"]])
# 字幕を、枠が替わる所で区切る（splits が無ければ字幕1つ＝1区切り）
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
    for k, (a, r, g, lab) in enumerate(cut):
        b = cut[k + 1][0] if k + 1 < len(cut) else e
        if b > a:
            parts.append({"id": x["id"], "a": a, "b": b, "rect": r, "group": g, "label": lab, "split": k > 0})
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
        groups.append({"group": x["group"], "rect": r, "label": x["label"], "ids": [x["id"]], "a": x["a"], "b": x["b"],
                       "split": x["split"]})
groups = [g for g in groups if g]
out_dir = os.path.join(OUT, "red_frames")
os.makedirs(out_dir, exist_ok=True)
for f in glob.glob(os.path.join(out_dir, "g2_*.png")):
    os.remove(f)
old = os.path.join(OUT, "red_frames.json")
if OUT == HERE and os.path.exists(old) and not os.path.exists(os.path.join(HERE, "red_frames_v003.json")):
    shutil.copy(old, os.path.join(HERE, "red_frames_v003.json"))
frames = []
for k, g in enumerate(groups):
    sp = clip_to_screen(g["a"], g["b"])
    if not sp or sp[1] - sp[0] < 6:
        continue
    x0, y0, x1, y1 = g["rect"]
    rect = [OFF_X + x0 * DISP_W, y0 * 1080, OFF_X + x1 * DISP_W, y1 * 1080]
    img = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle(rect, 12, outline=COLOR, width=STROKE)
    sfx = "s" if g["split"] else ""
    png = os.path.join(out_dir, f"g2_{k:03d}_{g['ids'][0].replace('+', 'p')}{sfx}.png")
    img.save(png)
    frames.append({"id_from": g["ids"][0], "id_to": g["ids"][-1], "png": png, "rect_px": [round(v) for v in rect],
                   "start": sp[0] * FT, "end": sp[1] * FT, "read": g["label"], "group": g["group"], "ocr": "", "ratio": []})
# 同じ場所の枠が、間を空けずに続く時は1つにまとめる（字幕の切れ目で枠がちらつかないように）
merged = []
for f in frames:
    if merged and merged[-1]["rect_px"] == f["rect_px"] and merged[-1]["end"] == f["start"]:
        merged[-1]["end"] = f["end"]
        merged[-1]["id_to"] = f["id_to"]
        os.remove(f["png"])
    else:
        merged.append(f)
json.dump({"frames": merged, "hits": len(items), "how": "v004 G2：analysis/赤枠_v004/ の AI の判断と反証（splits で字幕の途中の画面の替わり目に合わせる）"},
          open(old, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
tot = sum(f["end"] - f["start"] for f in merged) / FT / 29.97
print(f"字幕 {len(items)}（枠あり {sum(1 for x in items if x.get('rect') or x.get('splits'))}）→ 赤枠 {len(merged)} 個（合わせて {tot / 60:.1f}分）→ {old}")
