"""画面を映す字幕ごとに、画面の画像（字幕の 25%・75% の2枚。画面の間が3秒以上空く所は1秒ごとに足す）を書き出し、Mac の文字認識で読む。
07 の read_frame（赤枠）と blur（個人・社内の情報）の材料。tools/screen_reading.py の frames・ocr を、この案件の土台（XML）に合わせたもの。
  出力 analysis/screen_ocr_v004/frames/*.png（1512×982）・jobs.json・ocr.json（v001：v001 の analysis/screen_ocr は上書きしない。
  同じ画面のフレームは v001 の画像と文字認識の結果を写して使う）
  python3 v004/screen_ocr_v004.py frames ／ python3 v004/screen_ocr_v004.py ocr
"""
import bisect
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CASE = os.path.dirname(HERE)
ROOT = os.path.expanduser("~/Desktop/video_edit_rules")   # ルールと道具の場所（案件フォルダはどこにあってもよい。2026-09-28）
OUT = os.path.join(CASE, "analysis", "screen_ocr_v004")
FPS = 30000 / 1001
SCREEN = os.path.join(CASE, "media", "screen_CFR2997.mp4")


def tl_to_src(cj):
    """タイムラインのフレーム → 素材（カメラ）のフレーム"""
    segs, t = [], cj.get("highlight_external_frames", 0)   # 冒頭ハイライト（hl/）の後から本編
    for a, b in cj["highlight_frames"]:
        segs.append((t, a, b - a))
        t += b - a
    for a, b in cj["keep_frames"]:
        segs.append((t, a, b - a))
        t += b - a
    starts = [s[0] for s in segs]

    def f(x):
        i = bisect.bisect_right(starts, x) - 1
        t0, a, L = segs[i]
        return a + min(x - t0, L - 1)
    return f


def frames():
    cj = json.load(open(os.path.join(HERE, "_work", "cuts_v004.json"), encoding="utf-8"))
    mp = json.load(open(os.path.join(HERE, "_work", "base_v004_map.json"), encoding="utf-8"))
    capj = json.load(open(os.path.join(HERE, "_work", "captions_v004.json"), encoding="utf-8"))
    caps = [c for c in capj["captions"] if c["mode"] != "drop" and "src" in c]
    ctl = mp["caption_tl"]
    order = sorted(caps, key=lambda c: ctl[c["id"]])
    t2s = tl_to_src(cj)
    n_scr = mp["n_screen"]
    spans = mp["screen_spans"]
    os.makedirs(os.path.join(OUT, "frames"), exist_ok=True)
    prev = os.path.join(CASE, "analysis", "screen_ocr_v004")          # v002 の画像と文字認識（素材のフレームが同じなら写して使う）
    v1 = {int(f[1:7]): os.path.join(prev, "frames", f) for f in os.listdir(os.path.join(prev, "frames")) if f.endswith(".png")} \
        if os.path.isdir(os.path.join(prev, "frames")) else {}
    v1ocr = json.load(open(os.path.join(prev, "ocr.json"))) if os.path.exists(os.path.join(prev, "ocr.json")) else {}
    seeded = {}
    jobs = []
    for k, c in enumerate(order):
        s = ctl[c["id"]]
        e = ctl[order[k + 1]["id"]] if k + 1 < len(order) else mp["total_frames"]
        if not any(a <= s < b for a, b in spans):
            continue
        pts = [s + int(0.25 * (e - s)), s + int(0.75 * (e - s))]
        x = s + round(3 * FPS)
        while x < e - FPS:
            pts.append(x)
            x += round(1 * FPS)
        for p in sorted(set(pts)):
            src = t2s(p) - n_scr
            png = os.path.join(OUT, "frames", f"s{src:06d}.png")
            if not os.path.exists(png) and src in v1 and os.path.exists(v1[src]):
                shutil.copyfile(v1[src], png)
                if v1[src] in v1ocr:
                    seeded[png] = v1ocr[v1[src]]
            if not os.path.exists(png):
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{src / FPS:.4f}", "-i", SCREEN, "-frames:v", "1",
                                "-vf", "scale=1728:1117", png], check=True)
            jobs.append({"id": c["id"], "tl": p, "screen_frame": src, "png": png, "text": c["text"].replace("\r", "")})
    json.dump(jobs, open(os.path.join(OUT, "jobs.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    path = os.path.join(OUT, "ocr.json")
    out = json.load(open(path)) if os.path.exists(path) else {}
    out.update({k: v for k, v in seeded.items() if k not in out})
    json.dump(out, open(path, "w"), ensure_ascii=False)
    print(f"画像 {len(jobs)} 枚（v001 の画像と文字認識を写した {len(seeded)}）")


def ocr():
    exe = os.path.join(OUT, "screen_ocr")
    if not os.path.exists(exe):
        subprocess.run(["swiftc", "-O", os.path.join(ROOT, "tools", "screen_ocr.swift"), "-o", exe], check=True)
    jobs = json.load(open(os.path.join(OUT, "jobs.json"), encoding="utf-8"))
    pngs = sorted({j["png"] for j in jobs})
    path = os.path.join(OUT, "ocr.json")
    out = json.load(open(path)) if os.path.exists(path) else {}
    todo = [p for p in pngs if p not in out]
    for i in range(0, len(todo), 40):
        chunk = todo[i:i + 40]
        r = subprocess.run([exe] + chunk, check=True, capture_output=True)
        out.update(json.loads(r.stdout))
        json.dump(out, open(path, "w"), ensure_ascii=False)
        print(f"  {min(i + 40, len(todo))}/{len(todo)}", flush=True)


if __name__ == "__main__":
    {"frames": frames, "ocr": ocr}[sys.argv[1]]()
