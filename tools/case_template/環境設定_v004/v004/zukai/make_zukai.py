#!/usr/bin/env python3
"""環境設定 v002 の動く図解を、透明の動画（ProRes 4444）とワイプの動画にする。dots v002 の図解（dots開設/edit/v004_zukai/make_zukai.py）の作り方を、
図解ごとのフォルダ（zukai/<KEY>/：page.html と diagram.json）から作れるようにしたもの。

  python3 zukai/make_zukai.py Z1            … Z1 を作る（描く → overlay.mov・wipe.mp4・確かめの画像・manifest.json）
  python3 zukai/make_zukai.py Z1 --check    … 採寸と重なりの検査だけ（描かない。数秒）
  python3 zukai/make_zukai.py Z1 --previews … 描いたコマはそのままで、確かめの画像と動画だけ作り直す
  python3 zukai/make_zukai.py all           … zukai/Z*/ を全部
  python3 zukai/make_zukai.py I13 --name=auto … overlay を新しい名前（使われていない overlay_rN.mov）で書き、manifest がそれを指す（前の overlay は残す）
  python3 zukai/make_zukai.py I13 --name=overlay_r4.mov … 名前を決めて書く（もうあれば止まる。上書きしない）

zukai/<KEY>/diagram.json（図解を作る人が書く。README.md）：
  key・title・start_f・end_f（タイムラインの絶対のコマ。end は含まない）・anchor {cap, f}（start を決めた字幕と、その時の字幕の開始コマ。
  カットが変わって字幕が動いたら、その分だけずらす）・wipe {show, crop}・se [{f（図解の頭からのコマ）, se（plan_v004.SE の名前）, why}]・
  hide_caption_ids（"auto"＝区間に重なる字幕を全部外す）・removes（図解の間に外す v001 の装飾。plan_parts を直す人へのメモ）・checks（見たいコマ）
出力 zukai/out/<KEY>/：overlay.mov（板と部品。リニア合成の補正済み）・wipe.mp4（576×324）・manifest.json（build・make が読む）・
  previews/（カメラ＋図解＋ワイプを重ねた確かめの画像 *.jpg・まとめ sheet.jpg・動き.mp4＝半分の大きさ・音なし）
作業用（いつ消してもよい）：zukai/out/<KEY>/_work/（frames・base.mp4）
音は鳴らさない。Premiere には触らない。
"""
import json
import math
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent            # edit/v004/zukai
V = HERE.parent
EDIT = V.parent
sys.path.insert(0, str(HERE))
from tl import TL, ts  # noqa: E402

CAM = EDIT / "media" / "camera_CFR2997.mov"
RENDER = HERE / "lib" / "render_frames.mjs"
FACEDET = EDIT / "analysis" / "face" / "facedet"
OUT = HERE / "out"
FPS_N, FPS_D = 30000, 1001
FPS = FPS_N / FPS_D
WIPE_BOX = (1286, 696, 576, 324)                  # dots v002 と同じ（右下。02 の output_tracks とは別の、図解の間だけのワイプ）
ALPHA_GAMMA = 2.46                                # Premiere のシーケンスはリニアカラーで合成（compositeLinearColor=true）。a' = 1-(1-a)^2.46（dots v002 で測った）
JP_FONT = "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"
CHROMES = 2                                       # 7つを同時に作るので 2本まで（2026-10-04 3本×7で重くなった）


def run(cmd, **kw):
    print("$", " ".join(str(c) for c in cmd)[:220], flush=True)
    return subprocess.run([str(c) for c in cmd], check=True, **kw)


def count_frames(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames", "-show_entries", "stream=nb_read_frames",
                        "-of", "csv=p=0", str(p)], capture_output=True, text=True)
    try:
        return int(r.stdout.strip())
    except ValueError:
        return -1


def src_ranges(tl, S, E):
    """タイムラインのコマ [S, E) を作る素材（カメラ）のコマの範囲"""
    out = []
    for s, e, a in tl.segs:
        lo, hi = max(S, s), min(E, e)
        if lo < hi:
            out.append((a + lo - s, a + hi - s))
    assert sum(b - a for a, b in out) == E - S, "カットの表とタイムラインが合わない"
    return out


def make_base(work, S, E, src):
    """図解の区間のカメラ（v002 と同じカットで素材からつなぎ直したもの）。ワイプと確かめの画像の元"""
    base = work / "base.mp4"
    n = E - S
    if base.exists() and count_frames(base) == n:
        return base
    # 区間の頭の少し前へ飛んでから読む（-ss で飛ばずに頭から読むと、12GB のカメラを毎回全部読むことになる。2026-10-04 に7つ同時で重くなった）
    sel = "+".join(f"between(t,{(a - 0.5) / FPS:.6f},{(b - 0.5) / FPS:.6f})" for a, b in src)
    t0 = max(0.0, (src[0][0] - 60) / FPS)
    run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t0:.4f}", "-copyts", "-i", CAM, "-an",
         "-vf", f"select='{sel}',setpts=N/({FPS_N}/{FPS_D})/TB", "-r", f"{FPS_N}/{FPS_D}", "-frames:v", n,
         "-c:v", "libx264", "-crf", "12", "-preset", "fast", "-threads", "2", "-pix_fmt", "yuv420p", base])
    got = count_frames(base)
    assert got == n, f"カメラのコマ数が合わない {got}/{n}"
    return base


def grab(video, idxs, outdir):
    outdir.mkdir(parents=True, exist_ok=True)
    for f in outdir.glob("g_*.png"):
        f.unlink()
    idxs = sorted(set(idxs))
    sel = "+".join(f"eq(n,{i})" for i in idxs)
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", video, "-vf", f"select='{sel}'", "-fps_mode", "passthrough", outdir / "g_%04d.png"])
    got = sorted(outdir.glob("g_*.png"))
    assert len(got) == len(idxs), f"{video.name} から取れたコマが足りない {len(got)}/{len(idxs)}"
    return dict(zip(idxs, got))


def auto_crop(base, work, n):
    """ワイプの切り出し：区間の 1/4・1/2・3/4 のコマで顔を探し、顔の中心が切り出しの真ん中より少し上になる 16:9（幅 1000px）"""
    g = grab(base, [n // 4, n // 2, (3 * n) // 4], work / "face")
    xs, ys, ws = [], [], []
    for p in g.values():
        r = subprocess.run([str(FACEDET), str(p)], capture_output=True, text=True).stdout.strip()
        for ln in r.splitlines():
            parts = ln.split()[-1].split(",")
            if len(parts) == 4:
                x, y, w, h = map(int, parts)
                xs.append(x + w / 2)
                ys.append(y + h / 2)
                ws.append(w)
                break
    if not xs:
        return [460, 120, 1000, 563], "顔が見つからない（決まった切り出し）"
    cx, cy, fw = sorted(xs)[len(xs) // 2], sorted(ys)[len(ys) // 2], sorted(ws)[len(ws) // 2]
    W = int(min(1400, max(900, fw * 5.2)))
    W -= W % 16
    H = int(W * 9 / 16)
    x = int(min(max(0, cx - W / 2), 1920 - W))
    y = int(min(max(0, cy - H * 0.5), 1080 - H))      # 顔の中心を真ん中に（0.42 だと髪の上が切れた。2026-10-04 Z1〜Z7 の反証。dots v002 は頭の上に余白がある）
    return [x, y, W, H], f"顔の中心 ({cx:.0f},{cy:.0f})・顔の幅 {fw}px から"


def make_wipe(base, out, crop, n):
    cx, cy, cw, ch = crop
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", base, "-an",
         "-vf", f"crop={cw}:{ch}:{cx}:{cy},scale={WIPE_BOX[2]}:{WIPE_BOX[3]}:flags=lanczos,setsar=1", "-r", f"{FPS_N}/{FPS_D}", "-frames:v", n,
         "-c:v", "libx264", "-crf", "14", "-preset", "slow", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out])


def render(page, frames, n):
    if frames.exists():
        shutil.rmtree(frames)
    frames.mkdir(parents=True)
    k = CHROMES if n > 120 else 1
    cuts = [round(n * i / k) for i in range(k + 1)]

    def one(i):
        return subprocess.run(["node", str(RENDER), str(page), str(frames), str(n), str(cuts[i]), str(cuts[i + 1])],
                              capture_output=True, text=True)
    with ThreadPoolExecutor(k) as ex:
        rs = list(ex.map(one, range(k)))
    for r in rs:
        if r.returncode != 0:
            raise SystemExit("描けない：" + (r.stderr or r.stdout)[-1500:])
        print("  ", r.stdout.strip())
    got = len(list(frames.glob("*.png")))
    assert got == n, f"描いたコマが足りない {got}/{n}"


def measure_only(page, work, n):
    """1コマだけ描いて採寸（measure.json）を得る"""
    tmp = work / "measure_frames"
    if tmp.exists():
        shutil.rmtree(tmp)
    r = subprocess.run(["node", str(RENDER), str(page), str(tmp), str(n), "0", "1"], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("ページが読めない：" + (r.stderr or r.stdout)[-1500:])
    shutil.rmtree(tmp, ignore_errors=True)


def check_measure(work, wipe_show):
    """部品が画面の外に出ていないか・ワイプの所に重なっていないか"""
    p = work / "measure.json"
    if not p.exists():
        return ["measure.json が無い（ページの __measure が動かない）"]
    M = json.load(open(p, encoding="utf-8"))
    out = []
    wx, wy, ww, wh = WIPE_BOX
    for pid, v in M.items():
        x, y, w, h = v["box"]
        if w == 0 or h == 0:
            continue
        if x < 20 or y < 20 or x + w > 1900 or y + h > 1060:
            out.append(f"{pid}：画面の端から出る・端に近すぎる {v['box']}")
        if wipe_show and x < wx + ww and wx < x + w and y < wy + wh and wy < y + h:
            out.append(f"{pid}：右下のワイプ（{WIPE_BOX}）に重なる {v['box']}（f{v['f0']}〜f{v['f1']}）")
    return out


def encode_overlay(frames, out):
    lut = f"lutrgb=a=clip(maxval*(1-pow(max(0\\,1-val/maxval)\\,{ALPHA_GAMMA}))\\,0\\,maxval)"
    run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", f"{FPS_N}/{FPS_D}", "-i", frames / "%05d.png",
         "-vf", f"format=rgba,{lut}", "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le", "-vendor", "apl0", out])


def font(size):
    return ImageFont.truetype(JP_FONT, size)


def previews(key, d, tl, S, E, base, frames, wipe, odir):
    """カメラ＋図解（補正前のアルファで sRGB に重ねる＝Premiere のリニア合成に近い見え方）＋ワイプ。部品が出たコマの 8コマ後と最後"""
    pv = odir / "previews"
    if pv.exists():
        shutil.rmtree(pv)
    pv.mkdir(parents=True)
    n = E - S
    M = json.load(open(odir / "_work" / "measure.json", encoding="utf-8")) if (odir / "_work" / "measure.json").exists() else {}
    pts = set(d.get("checks", []))
    for v in M.values():
        pts.add(min(n - 1, v["f0"] + 8))
    pts.add(n - 2)
    pts = sorted(p for p in pts if 0 <= p < n)
    cam = grab(base, pts, odir / "_work" / "grab_cam")
    wp = grab(wipe, pts, odir / "_work" / "grab_wipe") if wipe and wipe.exists() else {}
    made = []
    for f in pts:
        im = Image.open(cam[f]).convert("RGBA")
        ov = Image.open(frames / f"{f:05d}.png").convert("RGBA")
        im.alpha_composite(ov)
        if f in wp:
            w = Image.open(wp[f]).convert("RGBA")
            im.alpha_composite(w, (WIPE_BOX[0], WIPE_BOX[1]))
        dr = ImageDraw.Draw(im)
        c = tl.caps[tl.at(S + f)]
        lab = f"{key} {ts(S + f)}（図解の {f}コマ）字幕[{c['id']}] {c['text'][:28]}"
        dr.rectangle([0, 0, 1920, 46], fill=(0, 0, 0, 200))
        dr.text((12, 6), lab, font=font(30), fill=(255, 255, 0, 255))
        p = pv / f"{key}_{ts(S + f).replace(':', '')}_f{f:04d}.jpg"
        im.convert("RGB").save(p, quality=88)
        made.append(p)
    # まとめ
    cols, tw, th = 4, 480, 270
    rows = math.ceil(len(made) / cols)
    sh = Image.new("RGB", (cols * tw, rows * th), (30, 30, 30))
    for i, p in enumerate(made):
        sh.paste(Image.open(p).resize((tw, th)), ((i % cols) * tw, (i // cols) * th))
    sh.save(pv / f"sheet_{key}.jpg", quality=85)
    # 動き（半分の大きさ・音なし）
    inputs = ["-i", base, "-framerate", f"{FPS_N}/{FPS_D}", "-i", frames / "%05d.png"]
    fc = "[0:v][1:v]overlay=0:0[a]"
    if wipe and wipe.exists():
        inputs += ["-i", wipe]
        fc += f";[a][2:v]overlay={WIPE_BOX[0]}:{WIPE_BOX[1]}[b];[b]scale=960:540[o]"
    else:
        fc += ";[a]scale=960:540[o]"
    run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", fc, "-map", "[o]", "-r", f"{FPS_N}/{FPS_D}",
         "-c:v", "libx264", "-crf", "24", "-preset", "fast", "-pix_fmt", "yuv420p", pv / f"動き_{key}.mp4"])
    return made


def build(key, mode=""):
    ddir = HERE / key
    d = json.load(open(ddir / "diagram.json", encoding="utf-8"))
    page = ddir / "page.html"
    tl = TL()
    S, E = d["start_f"], d["end_f"]
    shift = 0
    if d.get("anchor"):
        now = tl.caps[d["anchor"]["cap"]]["s"]
        shift = now - d["anchor"]["f"]
        if shift:
            print(f"!! 字幕 {d['anchor']['cap']} が {shift}コマ動いた → 図解もずらす")
            S, E = S + shift, E + shift
    n = E - S
    import re
    mm = re.search(r"frames\s*:\s*(\d+)", page.read_text(encoding="utf-8"))
    if not mm or int(mm.group(1)) != n:
        raise SystemExit(f"page.html の window.ZUKAI.frames（{mm.group(1) if mm else '無い'}）が end_f − start_f＝{n} と違う")
    odir = OUT / key
    work = odir / "_work"
    work.mkdir(parents=True, exist_ok=True)
    wipe_show = d.get("wipe", {}).get("show", True)
    measure_only(page, work, n)                     # work/measure.json（render_frames.mjs が書く）
    issues = check_measure(work, wipe_show)
    for s in issues:
        print("!!", s)
    # 画面を映している所に重ねない（07・09）
    scr = [f for f in range(S, E, 15) if tl.on_screen(f)]
    if scr:
        issues.append(f"画面を映している所に重なる（{ts(scr[0])}〜{ts(scr[-1])}）")
        print("!!", issues[-1])
    if mode == "check":
        return {"key": key, "issues": issues}
    src = src_ranges(tl, S, E)
    base = make_base(work, S, E, src)
    frames = work / "frames"
    overlay = odir / "overlay.mov"
    if NAME:
        # v004 最後の直し：作り直した overlay は新しい名前で書く（前の overlay*.mov は Premiere・ほかの組み立てが指しているかもしれないので、
        # 消さない・上書きしない）。--name=auto は使われていない overlay_rN.mov（N≥2）を選ぶ。--previews では今の manifest の overlay を使う
        if mode == "previews":
            mp = odir / "manifest.json"
            overlay = Path(json.load(open(mp, encoding="utf-8"))["overlay"]["file"]) if mp.exists() else overlay
        elif NAME == "auto":
            k_ = 2
            while (odir / f"overlay_r{k_}.mov").exists():
                k_ += 1
            overlay = odir / f"overlay_r{k_}.mov"
        else:
            overlay = odir / NAME
            if overlay.exists():
                raise SystemExit(f"{overlay.name} はもうある（上書きしない。別の名前か --name=auto）")
        print(f"  overlay の名前：{overlay.name}")
    wipe = odir / "wipe.mp4"
    crop = d.get("wipe", {}).get("crop")
    how = "diagram.json の crop"
    if wipe_show and not crop:
        crop, how = auto_crop(base, work, n)
    if mode != "previews":
        fresh = frames.exists() and len(list(frames.glob("*.png"))) == n and \
            min(f.stat().st_mtime for f in frames.glob("*.png")) > max(page.stat().st_mtime, (HERE / "lib" / "zukai.js").stat().st_mtime)
        if fresh:
            print("  描いたコマは page.html より新しいので描き直さない")
        else:
            render(page, frames, n)
        if overlay.exists() and count_frames(overlay) == n and overlay.stat().st_mtime > max(f.stat().st_mtime for f in frames.glob("*.png")):
            print("  overlay.mov は描いたコマより新しいので作り直さない")
        else:
            encode_overlay(frames, overlay)
        if wipe_show:
            make_wipe(base, wipe, crop, n)
    assert count_frames(overlay) == n, "overlay のコマ数が合わない"
    made = previews(key, d, tl, S, E, base, frames, wipe if wipe_show else None, odir)
    # 区間に重なる字幕
    hide = d.get("hide_caption_ids", "auto")
    if hide == "auto":
        hide = [i for i in tl.ids if tl.caps[i]["s"] < E and S < tl.caps[i]["e"]]
    se = []
    for ev in d.get("se", []):
        se.append({"tl_f": S + ev["f"], "tl": ts(S + ev["f"]), "se": ev["se"], "why": ev.get("why", "")})
    m = {"key": key, "title": d.get("title", ""), "fps": "30000/1001", "tl_start_f": S, "tl_end_f": E, "frames": n,
         "tl_start": ts(S), "tl_end": ts(E), "shift": shift,
         "overlay": {"file": str(overlay), "frames": n, "codec": "ProRes 4444（ストレートのアルファ）",
                     "alpha": f"リニア合成の補正 a'=1-(1-a)^{ALPHA_GAMMA}（板 80%→98%）", "track": "V15"},
         "wipe": ({"file": str(wipe), "box": list(WIPE_BOX), "crop_from_camera": crop, "crop_how": how, "track": "V16"} if wipe_show else None),
         "se_events": se, "hide_caption_ids": hide, "removes": d.get("removes", ""),
         "issues": issues, "previews": [str(p) for p in made], "src_ranges": src, "story": d.get("story", "")}
    json.dump(m, open(odir / "manifest.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"== {key}: {ts(S)}〜{ts(E)}（{n}コマ・{n / FPS:.1f}秒）overlay・{'wipe・' if wipe_show else ''}画像 {len(made)}枚・"
          f"字幕を外す {len(hide)}・SE {len(se)}・注意 {len(issues)}")
    return m


NAME = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--name=")), "")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    mode = "check" if "--check" in sys.argv else ("previews" if "--previews" in sys.argv else "")
    keys = sorted(p.name for p in HERE.iterdir() if p.is_dir() and p.name.startswith("Z")) if args == ["all"] else args
    for k in keys:
        build(k, mode)


if __name__ == "__main__":
    main()
