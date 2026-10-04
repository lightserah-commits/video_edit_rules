#!/usr/bin/env python3
"""赤枠（07 の read_frame）の材料②：画面を映す字幕ごとに、その時の画面の画像と文字認識の結果を、区間ごとにまとめて
batch_NN_in.json にする（AI が字幕ごとに枠を決めるための束。どの案件でも使える道具）。
元：環境設定 v004 の analysis/赤枠_v004/prep.py。

  python3 tools/red_frames/prep.py --ver <edit/vNNN> --ocr-dir <edit/analysis/screen_ocr_vNNN> [--ocr-dir <前の版の screen_ocr> …] \\
      --out <edit/analysis/赤枠_vNNN> [--size 25]
  - 画像の一覧（jobs.json）は最後の --ocr-dir のもの（--jobs で別に渡せる）。文字認識（ocr.json）は全部の --ocr-dir から画像の名前で引く
  - 文字認識の確かさ（conf）0.3 未満の行は落とす
  - 25枚ぐらいずつの束にする（最後の束が 10枚未満なら前の束に足す）。束の頭に、前の束の最後の2つの字幕を「前の流れ」（context_before）として付ける
出力 <out>/batch_NN_in.json：{"context_before": [{id, text, span}], "items": [{span, span_tl, id, tl, who, text, frames: [{png, screen_frame, ocr}]}]}
  （span＝何番目の画面の区間か。tl・span_tl はタイムラインの秒）
次は README.md の「2. 決める」（AI が batch_NN_out.json を書く）
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="赤枠を決める束（batch_NN_in.json）を作る")
    C.add_case_args(ap, cuts=False)
    ap.add_argument("--ocr-dir", action="append", required=True, help="screen_frames.py の出力フォルダ（何回でも）")
    ap.add_argument("--jobs", help="画像の一覧 jobs.json（省くと最後の --ocr-dir の jobs.json）")
    ap.add_argument("--out", required=True, help="束を書くフォルダ（例 edit/analysis/赤枠_vNNN）")
    ap.add_argument("--size", type=int, default=25, help="1つの束の字幕の数（既定 25）")
    ap.add_argument("--min-conf", type=float, default=0.3)
    a = ap.parse_args()
    C.resolve(a, need=("map", "captions"))
    jobs = C.load(a.jobs or os.path.join(a.ocr_dir[-1], "jobs.json"))
    ocr = {}
    for d in a.ocr_dir:
        p = os.path.join(d, "ocr.json")
        if os.path.exists(p):
            for k, v in C.load(p).items():
                ocr[os.path.basename(k)] = v
    mp, capj = C.load(a.map), C.load(a.captions)
    ctl = mp["caption_tl"]
    caps = {c["id"]: c for c in capj["captions"] if c.get("mode") != "drop" and "src" in c}
    by = {}
    for j in jobs:
        by.setdefault(j["id"], []).append(j)
    spans = []
    for x, y in mp["screen_spans"]:
        ids = sorted([i for i in by if i in ctl and i in caps and x <= ctl[i] < y], key=lambda i: ctl[i])
        if ids:
            spans.append({"tl": [round(x / C.FPS, 2), round(y / C.FPS, 2)], "ids": ids})
    items, no_ocr = [], 0
    for k, sp in enumerate(spans):
        for i in sp["ids"]:
            fr = []
            for j in sorted(by[i], key=lambda z: z["screen_frame"]):
                name = os.path.basename(j["png"])
                no_ocr += name not in ocr
                lines = [{"text": o["text"], "x": round(o["x"], 4), "y": round(o["y"], 4), "w": round(o["w"], 4), "h": round(o["h"], 4)}
                         for o in ocr.get(name, []) if o.get("conf", 1) >= a.min_conf]
                fr.append({"png": j["png"], "screen_frame": j["screen_frame"], "ocr": lines})
            items.append({"span": k, "span_tl": sp["tl"], "id": i, "tl": round(ctl[i] / C.FPS, 2), "who": caps[i].get("who", ""),
                          "text": caps[i]["text"].replace("\r", "／"), "frames": fr})
    if not items:
        raise SystemExit("画面を映す字幕が無い（map の screen_spans と jobs.json を確かめる）")
    batches = [items[k:k + a.size] for k in range(0, len(items), a.size)]
    if len(batches) > 1 and len(batches[-1]) < 10:
        batches[-2] += batches.pop()
    os.makedirs(a.out, exist_ok=True)
    for n, b in enumerate(batches):
        i0 = items.index(b[0])
        ctx = items[max(0, i0 - 2):i0]
        json.dump({"context_before": [{"id": x["id"], "text": x["text"], "span": x["span"]} for x in ctx], "items": b},
                  open(os.path.join(a.out, f"batch_{n + 1:02d}_in.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(n + 1, len(b), "字幕", b[0]["tl"], "〜", b[-1]["tl"], "区間", sorted(set(x["span"] for x in b)))
    print("区間", len(spans), "字幕", len(items), f"（文字認識の無い画像 {no_ocr}）→ {a.out}")


if __name__ == "__main__":
    main()
