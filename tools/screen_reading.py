#!/usr/bin/env python3
"""画面共有の動画で、①画面の中を読み上げている所（赤枠を出す所）と、②個人のパソコンの中身が見える所（ブラーをかける所）を探す。
07_画面共有とワイプ.yaml の read_frame・blur の道具。2026-09-26 画面解説の案件で作ったもの（work/gamen_kaisetsu_20260926/v006/red_frames.py）を一般にした。

  frames  … 画面を映している字幕ごとに、その時の画面の画像（字幕の頭から 25% と 75% の2枚）を書き出す
  ocr     … 画像を Mac の文字認識（tools/screen_ocr.swift）で読む（1枚 2〜3秒）
  read    … 字幕の言葉と画面の文字を突き合わせて「読み上げている」字幕を探し、赤枠の PNG（1920×1080 透明）と一覧を作る
  private … 文字認識の結果から、Finder・Google ドライブなどが映っている字幕を探す（ブラーの候補。出ている範囲は1秒ごとの画像で確かめる）

使い方（例）:
  python3 tools/screen_reading.py frames --project 案件.prproj --sequence 名前 --captions 字幕一覧.csv --media 画面の素材のフォルダ --out 作業/画面の文字
     字幕一覧.csv … 字幕トラックの順の表（「番号」「字幕」「映すもの」＝カメラ／画面）。--caption-track V3 --video-track V1（既定）
  python3 tools/screen_reading.py ocr --dir 作業/画面の文字
  python3 tools/screen_reading.py read --dir 作業/画面の文字 --captions 字幕一覧.csv --out 作業/赤枠 [--cut-map カット後の字幕の位置.json] [--exclude 147,889]
  python3 tools/screen_reading.py private --dir 作業/画面の文字 --captions 字幕一覧.csv

  画面の録画は高さに合わせて中央に置いている前提（--src-size 1512x982、シーケンス 1920×1080）。
  --cut-map は {"captions": {字幕番号: [開始ticks, 終了ticks]}} の形（cut_v006.py の出力）。無ければ元の時刻のまま。
"""
import argparse
import csv
import difflib
import glob
import json
import os
import re
import subprocess
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
TPS = 254016000000
TOP_CHROME = 0.105            # 画面の上から 10.5% はブラウザの帯（タブ・アドレス・ブックマーク）
MIN_CHARS, MIN_RATIO = 5, 0.6
PAD, STROKE, COLOR = 10, 8, (255, 30, 30, 255)
PRIVATE = {"Finder": ("よく使う項目", "デスクトップ", "アプリケーション", "iCloud Drive", "最近の項目"),
           "Google ドライブ": ("マイドライブ", "共有アイテム", "アイテムを選択", "最近使用したアイテム")}


def load_rows(path):
    return {int(r["番号"]): r for r in csv.DictReader(open(path, encoding="utf-8-sig"))}


def norm(s):
    s = unicodedata.normalize("NFKC", s).lower()
    return re.sub(r"[\s、。・,.!?！？「」『』（）()\[\]【】:：;；\"'`~〜ー\-–—→…]", "", s)


def match_len(a, b):
    """a（字幕）のうち b（画面の1行）と一致する文字数。1文字違いは許す。4文字以上の塊が無ければ 0"""
    blocks = [m for m in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks() if m.size >= 2]
    if not any(m.size >= 4 for m in blocks):
        return 0
    return sum(m.size for m in blocks)


def narrow(o, cap, t):
    """画面の行のうち、読んでいる部分だけに枠を絞る（行の8割以上なら行全体）"""
    blocks = [m for m in difflib.SequenceMatcher(None, cap, t, autojunk=False).get_matching_blocks() if m.size >= 2]
    if not blocks or not t:
        return o
    b0, b1 = min(m.b for m in blocks), max(m.b + m.size for m in blocks)
    f0, f1 = b0 / len(t), b1 / len(t)
    if f1 - f0 >= 0.8:
        return o
    o = dict(o)
    o["x"], o["w"] = o["x"] + f0 * o["w"], (f1 - f0) * o["w"]
    return o


def iou(a, b):
    ix = max(0, min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"]))
    iy = max(0, min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"]))
    inter = ix * iy
    return inter / (a["w"] * a["h"] + b["w"] * b["h"] - inter + 1e-9)


def cmd_frames(a):
    from native_prproj import Prproj
    pj = Prproj.load(a.project)
    seq = pj.sequence(a.sequence)
    caps = sorted(pj.items(pj.track(seq, a.caption_track)), key=lambda i: pj.span(i)[0])
    vids = sorted(pj.items(pj.track(seq, a.video_track)), key=lambda i: pj.span(i)[0])
    rows = list(csv.DictReader(open(a.captions, encoding="utf-8-sig")))
    assert len(caps) == len(rows), (len(caps), len(rows))
    os.makedirs(os.path.join(a.out, "frames"), exist_ok=True)
    jobs = []
    for it, r in zip(caps, rows):
        if r.get("映すもの") != "画面":
            continue
        s, e = pj.span(it)
        for off in (0.25, 0.75):
            t = s + int(off * (e - s))
            for c in vids:
                x0, x1 = pj.span(c)
                if x0 <= t < x1:
                    name = pj.ref(c.find("ClipTrackItem/SubClip")).findtext("Name") or ""
                    h = pj.range_holder(pj.ref(pj.ref(c.find("ClipTrackItem/SubClip")).find("Clip")))
                    src = (int(h.findtext("InPoint")) + t - x0) / TPS
                    png = os.path.join(a.out, "frames", f"{int(r['番号']):04d}_{int(off * 100):02d}.png")
                    if not os.path.exists(png):
                        subprocess.run(["ffmpeg", "-nostats", "-hide_banner", "-loglevel", "error", "-y", "-ss", str(src),
                                        "-i", os.path.join(a.media, name), "-frames:v", "1", png], check=True)
                    jobs.append({"idx": int(r["番号"]), "at": off, "file": name, "src": round(src, 3), "png": png})
                    break
    json.dump(jobs, open(os.path.join(a.out, "jobs.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"画像 {len(jobs)} 枚 → {a.out}")


def cmd_ocr(a):
    exe = os.path.join(a.dir, "screen_ocr")
    if not os.path.exists(exe):
        subprocess.run(["swiftc", "-O", os.path.join(HERE, "screen_ocr.swift"), "-o", exe], check=True)
    pngs = sorted(glob.glob(os.path.join(a.dir, "frames", "*.png")))
    out = {}
    for i in range(0, len(pngs), 50):          # 50枚ずつ（途中で止まっても続きからやり直せるように）
        chunk = pngs[i:i + 50]
        r = subprocess.run([exe] + chunk, check=True, capture_output=True)
        out.update(json.loads(r.stdout))
        print(f"  {min(i + 50, len(pngs))}/{len(pngs)}", flush=True)
    json.dump(out, open(os.path.join(a.dir, "ocr.json"), "w"), ensure_ascii=False)


def by_caption(a):
    ocr = json.load(open(os.path.join(a.dir, "ocr.json")))
    jobs = json.load(open(os.path.join(a.dir, "jobs.json"), encoding="utf-8"))
    base = {os.path.basename(k): v for k, v in ocr.items()}
    out = {}
    for j in jobs:
        out.setdefault(j["idx"], []).append((j, base.get(os.path.basename(j["png"]), [])))
    return out


def cmd_read(a):
    from PIL import Image, ImageDraw
    rows = load_rows(a.captions)
    groups_src = by_caption(a)
    cmap = json.load(open(a.cut_map))["captions"] if a.cut_map else None
    exclude = {int(x) for x in a.exclude.split(",") if x} if a.exclude else set()
    sw, sh = (int(v) for v in a.src_size.split("x"))
    disp_w = sw * 1080 / sh
    off_x = (1920 - disp_w) / 2
    hits = []
    for idx in sorted(groups_src):
        if idx in exclude or (cmap is not None and str(idx) not in cmap):
            continue
        cap = norm(rows[idx]["字幕"])
        if len(cap) < MIN_CHARS:
            continue
        best = None
        for j, items in groups_src[idx]:
            for o in items:
                if o["y"] < TOP_CHROME or o.get("conf", 1) < 0.3:
                    continue
                t = norm(o["text"])
                L = match_len(cap, t)
                if L >= MIN_CHARS and L / len(cap) >= MIN_RATIO:
                    score = (L / len(cap), L)
                    if best is None or score > best[0]:
                        best = (score, narrow(o, cap, t), j)
        if best:
            hits.append({"idx": idx, "text": rows[idx]["字幕"], "ocr": best[1]["text"], "box": best[1], "file": best[2]["file"],
                         "ratio": round(best[0][0], 2)})
    groups = []
    for h in hits:
        if groups and h["idx"] - groups[-1][-1]["idx"] <= 2 and iou(h["box"], groups[-1][-1]["box"]) > 0.2 and h["file"] == groups[-1][-1]["file"]:
            groups[-1].append(h)
        else:
            groups.append([h])
    os.makedirs(os.path.join(a.out, "frames"), exist_ok=True)
    frames = []
    for k, g in enumerate(groups):
        x0 = min(h["box"]["x"] for h in g)
        y0 = min(h["box"]["y"] for h in g)
        x1 = max(h["box"]["x"] + h["box"]["w"] for h in g)
        y1 = max(h["box"]["y"] + h["box"]["h"] for h in g)
        rect = [off_x + x0 * disp_w - PAD, y0 * 1080 - PAD, off_x + x1 * disp_w + PAD, y1 * 1080 + PAD]
        img = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
        ImageDraw.Draw(img).rounded_rectangle(rect, 12, outline=COLOR, width=STROKE)
        png = os.path.join(a.out, "frames", f"frame_{k:03d}_{g[0]['idx']:04d}.png")
        img.save(png)
        fr = {"idx_from": g[0]["idx"], "idx_to": g[-1]["idx"], "png": os.path.abspath(png), "rect_px": [round(v) for v in rect],
              "read": " / ".join(h["text"] for h in g), "ocr": " / ".join(h["ocr"] for h in g), "ratio": [h["ratio"] for h in g]}
        if cmap is not None:
            fr["start"], fr["end"] = cmap[str(g[0]["idx"])][0], cmap[str(g[-1]["idx"])][1]
        frames.append(fr)
    json.dump({"frames": frames, "hits": len(hits)}, open(os.path.join(a.out, "red_frames.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"読んでいる字幕 {len(hits)} 本 → 赤枠 {len(frames)} 個（一覧を見て、ボタンの文字などに当たっただけのものを --exclude で外す）")
    for f in frames:
        print(f"{f['idx_from']:4d}-{f['idx_to']:4d}  話：{f['read'][:36]}  画面：{f['ocr'][:36]}")


def cmd_private(a):
    rows = load_rows(a.captions)
    for idx, lst in sorted(by_caption(a).items()):
        found = set()
        for j, items in lst:
            txt = " ".join(o["text"] for o in items)
            for kind, keys in PRIVATE.items():
                if sum(k in txt for k in keys) >= 2:
                    found.add(kind)
        if found:
            print(idx, rows[idx].get("開始", ""), "・".join(sorted(found)), rows[idx]["字幕"][:30])


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("frames")
    for k in ("--project", "--sequence", "--captions", "--media", "--out"):
        p.add_argument(k, required=True)
    p.add_argument("--caption-track", default="V3")
    p.add_argument("--video-track", default="V1")
    p = sp.add_parser("ocr")
    p.add_argument("--dir", required=True)
    p = sp.add_parser("read")
    for k in ("--dir", "--captions", "--out"):
        p.add_argument(k, required=True)
    p.add_argument("--cut-map")
    p.add_argument("--exclude")
    p.add_argument("--src-size", default="1512x982")
    p = sp.add_parser("private")
    p.add_argument("--dir", required=True)
    p.add_argument("--captions", required=True)
    a = ap.parse_args()
    {"frames": cmd_frames, "ocr": cmd_ocr, "read": cmd_read, "private": cmd_private}[a.cmd](a)


if __name__ == "__main__":
    main()
