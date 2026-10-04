#!/usr/bin/env python3
"""赤枠（07 の read_frame）の材料①：画面を映す字幕ごとに、画面の画像を書き出し、Mac の文字認識で読む（どの案件でも使える道具）。
元：環境設定 v004 の screen_ocr_v004.py（tools/screen_reading.py の frames・ocr を、版の土台の表に合わせたもの）。

  画像：字幕の 25%・75% の2枚（字幕が長く、3秒より後もあれば1秒ごとに足す）。画面録画のコマ＝カメラのコマ − n_screen
  python3 tools/red_frames/screen_frames.py frames --ver <edit/vNNN> --screen <画面録画（CFR）> --out <edit/analysis/screen_ocr_vNNN> \\
      [--seed <前の版の screen_ocr フォルダ>]（同じ画面のコマは前の画像と文字認識を写して使う）[--size 1728x1117]
  python3 tools/red_frames/screen_frames.py ocr --out <同じフォルダ>     … frames/*.png を文字認識（tools/screen_ocr.swift。初回はコンパイル）
  出力：<out>/frames/sNNNNNN.png（NNNNNN＝画面録画のコマ）・jobs.json（[{id, tl, screen_frame, png, text}]）・ocr.json（{png: [{text, x, y, w, h, conf}]}。0〜1）
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.expanduser("~/Desktop/video_edit_rules")
sys.path.insert(0, HERE)
import common as C  # noqa: E402


def probe_size(video):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", video],
                       capture_output=True, text=True, check=True)
    w, h = r.stdout.strip().split(",")[:2]
    return int(w), int(h)


def frames(a):
    C.resolve(a)
    cj, mp, capj = C.load(a.cuts), C.load(a.map), C.load(a.captions)
    caps, nxt = C.caption_order(mp, capj)
    ctl = mp["caption_tl"]
    t2s = C.tl_to_src(cj)
    n_scr = mp["n_screen"]
    spans = mp["screen_spans"]
    if a.size:
        W, H = (int(v) for v in a.size.lower().split("x"))
    else:
        w, h = probe_size(a.screen)
        W, H = w // 2, h // 2                                   # 画面録画の半分の大きさ（環境設定：3456×2234 → 1728×1117）
    fd = os.path.join(a.out, "frames")
    os.makedirs(fd, exist_ok=True)
    seed, seed_ocr = {}, {}
    if a.seed and os.path.isdir(os.path.join(a.seed, "frames")):
        seed = {int(f[1:7]): os.path.join(a.seed, "frames", f) for f in os.listdir(os.path.join(a.seed, "frames"))
                if f.startswith("s") and f.endswith(".png")}
        p = os.path.join(a.seed, "ocr.json")
        seed_ocr = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
    seeded, jobs = {}, []
    for c in caps:
        s, e = ctl[c["id"]], nxt[c["id"]]
        if not any(x <= s < y for x, y in spans):
            continue
        pts = [s + int(0.25 * (e - s)), s + int(0.75 * (e - s))]
        x = s + round(3 * C.FPS)
        while x < e - C.FPS:
            pts.append(x)
            x += round(C.FPS)
        for p in sorted(set(pts)):
            src = t2s(p) - n_scr
            png = os.path.join(fd, f"s{src:06d}.png")
            if not os.path.exists(png) and src in seed and os.path.exists(seed[src]):
                shutil.copyfile(seed[src], png)
                if seed[src] in seed_ocr:
                    seeded[png] = seed_ocr[seed[src]]
            if not os.path.exists(png):
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{src / C.FPS:.4f}", "-i", a.screen, "-frames:v", "1",
                                "-vf", f"scale={W}:{H}", png], check=True)
            jobs.append({"id": c["id"], "tl": p, "screen_frame": src, "png": png, "text": c["text"].replace("\r", "")})
    json.dump(jobs, open(os.path.join(a.out, "jobs.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    path = os.path.join(a.out, "ocr.json")
    out = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    out.update({k: v for k, v in seeded.items() if k not in out})
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"画像 {len(jobs)} 枚（前の画像と文字認識を写した {len(seeded)}）→ {a.out}")


def ocr(a):
    exe = os.path.join(a.out, "screen_ocr")
    if not os.path.exists(exe):
        subprocess.run(["swiftc", "-O", os.path.join(ROOT, "tools", "screen_ocr.swift"), "-o", exe], check=True)
    jobs = json.load(open(os.path.join(a.out, "jobs.json"), encoding="utf-8"))
    pngs = sorted({j["png"] for j in jobs})
    path = os.path.join(a.out, "ocr.json")
    out = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    todo = [p for p in pngs if p not in out]
    for i in range(0, len(todo), 40):
        r = subprocess.run([exe] + todo[i:i + 40], check=True, capture_output=True)
        out.update(json.loads(r.stdout))
        json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False)
        print(f"  {min(i + 40, len(todo))}/{len(todo)}", flush=True)
    print(f"文字認識 {len(out)} 枚 → {path}")


def main():
    ap = argparse.ArgumentParser(description="画面を映す字幕ごとの画面の画像と文字認識（赤枠の材料）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("frames", help="画像を書き出す")
    C.add_case_args(f)
    f.add_argument("--screen", required=True, help="画面録画（29.97fps の CFR にした作業用コピー）")
    f.add_argument("--out", required=True, help="出力のフォルダ（例 edit/analysis/screen_ocr_vNNN）")
    f.add_argument("--seed", help="前の版の screen_ocr フォルダ（同じコマの画像と文字認識を写す）")
    f.add_argument("--size", help="画像の大きさ WxH（省くと画面録画の半分）")
    o = sub.add_parser("ocr", help="文字認識")
    o.add_argument("--out", required=True, help="frames と同じフォルダ")
    a = ap.parse_args()
    {"frames": frames, "ocr": ocr}[a.cmd](a)


if __name__ == "__main__":
    main()
