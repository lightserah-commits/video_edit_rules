"""赤枠の束（analysis/赤枠_vNNN/batch_NN_in.json）から、赤枠係が読む軽い版 batch_NN_lite.json を作る（1015 の lite と同じ形）。
  python3 scripts/redframe_lite.py analysis/赤枠_v001
  1字幕＝id・tl・who・text・span、frames＝png（名前だけ）・screen_frame・match（字幕の文字と重なる画面の行 上位4）・big（大きい文字 上位2）・n_lines。box は [x, y, w, h]
"""
import glob
import json
import os
import re
import sys
import unicodedata


def norm(s):
    return re.sub(r"[\s、。・,.!?！？「」『』（）()\[\]【】:：;；\"'`~〜ー\-–—→…／/%＠@〇]", "", unicodedata.normalize("NFKC", s).lower())


def score(cap, line):
    c, l = norm(cap), norm(line)
    if len(l) < 2:
        return 0
    grams = {c[i:i + 2] for i in range(len(c) - 1)}
    return sum(1 for i in range(len(l) - 1) if l[i:i + 2] in grams) / max(1, len(l) - 1)


d = sys.argv[1]
for f in sorted(glob.glob(os.path.join(d, "batch_*_in.json"))):
    b = json.load(open(f))
    out = {"context_before": b.get("context_before"), "items": []}
    for it in b["items"]:
        frs = []
        for fr in it["frames"]:
            ocr = fr.get("ocr", [])
            box = lambda o: [round(o["x"], 3), round(o["y"], 3), round(o["w"], 3), round(o["h"], 3)]
            m = sorted(ocr, key=lambda o: -score(it["text"], o["text"]))[:4]
            m = [{"text": o["text"][:40], "box": box(o)} for o in m if score(it["text"], o["text"]) > 0]
            big = sorted(ocr, key=lambda o: -o["h"])[:2]
            frs.append({"png": os.path.basename(fr["png"]), "screen_frame": fr["screen_frame"], "match": m,
                        "big": [{"text": o["text"][:40], "box": box(o)} for o in big], "n_lines": len(ocr)})
        out["items"].append({"id": it["id"], "tl": it["tl"], "who": it["who"], "text": it["text"], "span": it["span"], "frames": frs})
    json.dump(out, open(f.replace("_in.json", "_lite.json"), "w"), ensure_ascii=False)
    print(os.path.basename(f), len(out["items"]))
