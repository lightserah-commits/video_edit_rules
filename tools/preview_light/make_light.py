#!/usr/bin/env python3
"""timeline.json から、カット・画面・ワイプ・赤枠・図解だけを重ねた軽い映像（テロップなし）を ffmpeg で作る。Premiere は使わない。
  python3 make_light.py timeline.json <出力フォルダ> [--from 秒 --to 秒] [--jobs 6]
- 切れ目ごとに小さな mp4 を作ってつなぐ。作ってある切れ端は使い回す（直した所だけ作り直せる）
- 図解（透明の .mov）の下にあるテロップは、ブラウザで重ねられないので sprites/ の透明 PNG を焼き込む（--sprites）"""
import argparse, concurrent.futures as cf, hashlib, json, os, subprocess, time
FPS = 30000 / 1001
W, H = 1280, 720
K = H / 1080
SIZES = {}
NEAR = 0  # --shift の値

def probe(p):
    if p not in SIZES:
        o = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", p], capture_output=True, text=True).stdout.strip().split("\n")[0]
        a = o.split(",")
        SIZES[p] = (int(a[0]), int(a[1]))
    return SIZES[p]

def fr(t):
    return int(round(t * FPS))

def norm(p):
    return "/" + p.lstrip("/") if p else p

def nums(v):
    return [float(x) for x in str(v).rstrip(".").split(":")]

def motion_of(row):
    for c in row["comps"]:
        if c["match"] == "AE.ADBE Motion":
            return c["params"]
    return None

def adj_of(row):
    d = {}
    for c in row["comps"]:
        p = c["params"]
        if c["match"] == "AE.ADBE Gaussian Blur 2":
            d["blur"] = float(p["ブラー"]["v"].rstrip("."))
        if c["match"] == "AE.ADBE Lumetri" and p.get("露光量"):
            d["ev"] = float(p["露光量"]["v"].rstrip("."))
        if c["match"] == "AE.ADBE Geometry2" and p.get("スケール (高さ)"):
            d["scale"] = float(p["スケール (高さ)"]["v"].rstrip("."))
        if c["match"] == "AE.ADBE AECrop":
            d["crop"] = [float(p[n]["v"].rstrip(".")) for n in ("左", "上", "右", "下")]
    return d

def layers_at(rows, a):
    """コマ a に出ている映像の段（下から順）"""
    return [r for r in rows if fr(r["start"]) <= a < fr(r["end"])]

def expr(kf, idx, clip_t, base_mul):
    """キーフレーム（クリップの頭からの秒）を、この切れ端の t の式にする"""
    s = ""
    k = [(t, v[idx] * base_mul) for t, v in kf]
    tail = f"{k[-1][1]:.5f}"
    for i in range(len(k) - 1, 0, -1):
        t0, v0 = k[i - 1]; t1, v1 = k[i]
        if t1 <= t0:
            continue
        tail = f"if(lt(t+{clip_t:.4f}\\,{t1:.4f})\\,{v0:.5f}+({v1 - v0:.5f})*(t+{clip_t:.4f}-{t0:.4f})/{t1 - t0:.4f}\\,{tail})"
    return f"if(lt(t+{clip_t:.4f}\\,{k[0][0]:.4f})\\,{k[0][1]:.5f}\\,{tail})"

def build_job(a, b, active, out, sprites):
    dur = (b - a) / FPS
    args = ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"color=c=black:s={W}x{H}:r=30000/1001:d={dur + 0.2:.4f}"]
    f, last, n = [], "0:v", 1
    for r in active:
        m = norm(r["media"]) if r["media"] else None
        tn = r["track"]
        lab = f"l{n}"
        if tn == "V3":
            ad = adj_of(r)
            if "crop" in ad:
                # 調整レイヤーのクロップは上下の黒い帯になる（r3 の 1033秒・1497秒で確かめた。1713_代弁1.png だけ r3 と違う古い画像）
                l_, t_, r_, b_ = ad["crop"]
                f.append(f"[{last}]drawbox=x=0:y=0:w={W}:h={int(H * t_ / 100)}:c=black:t=fill,drawbox=x=0:y={H - int(H * b_ / 100)}:w={W}:h={int(H * b_ / 100) + 1}:c=black:t=fill[{lab}]")
            else:
                sc = ad.get("scale", 100) / 100
                ev = ad.get("ev", 0)
                sw, sh = int(W * sc) // 2 * 2, int(H * sc) // 2 * 2
                f.append(f"[{last}]scale={sw}:{sh},crop={W}:{H},gblur=sigma={ad.get('blur', 0) * K * 0.7:.1f},eq=brightness={ev * 0.15:.3f}[{lab}]")
            last = lab
            continue
        if not m or not os.path.exists(m):
            continue
        ext = os.path.splitext(m)[1].lower()
        src_t = r["in"] + (a - fr(r["start"])) / FPS
        if ext in (".png", ".jpg", ".jpeg"):
            args += ["-loop", "1", "-framerate", "30000/1001", "-t", f"{dur + 0.1:.4f}", "-i", m]
        else:
            # -ss はその時刻以降の最初のコマを取る。--shift で手前から取る
            args += ["-ss", f"{max(0, src_t - NEAR / FPS):.5f}", "-t", f"{dur + 0.1:.4f}", "-i", m]
        sw, sh = probe(m)
        mp = motion_of(r)
        clip_t = (a - fr(r["start"])) / FPS
        scale, pos, anchor, kf_s, kf_p = 100.0, [0.5, 0.5], [0.5, 0.5], None, None
        if mp:
            if mp.get("スケール"):
                scale = nums(mp["スケール"]["v"])[0]
                if mp["スケール"].get("k"):
                    kf_s = [[t - r["in"], nums(v)] for t, v in mp["スケール"]["k"]]
            if mp.get("位置"):
                pos = nums(mp["位置"]["v"])
                if mp["位置"].get("k"):
                    kf_p = [[t - r["in"], nums(v)] for t, v in mp["位置"]["k"]]
            if mp.get("アンカーポイント"):
                anchor = nums(mp["アンカーポイント"]["v"])
        fmt = "format=rgba," if ext in (".png", ".mov") else ""
        if tn == "V15":
            # 図解の overlay.mov の透明度は、Premiere のリニア合成に合わせて a'=1-(1-a)^2.46 にしてある（manifest.json の overlay.alpha）。ffmpeg は普通に重ねるので元に戻す
            fmt = "format=rgba,lutrgb=a='255*(1-exp(log(abs(1-val/255)+0.000000001)/2.46))',"
        if kf_s or kf_p:
            s_e = expr(kf_s, 0, clip_t, 1) if kf_s else f"{scale}"
            px = expr(kf_p, 0, clip_t, 1) if kf_p else f"{pos[0]}"
            py = expr(kf_p, 1, clip_t, 1) if kf_p else f"{pos[1]}"
            we = f"trunc(({s_e})/100*{sw}*{K}/2)*2"
            he = f"trunc(({s_e})/100*{sh}*{K}/2)*2"
            f.append(f"[{n}:v]{fmt}scale=w='{we}':h='{he}':eval=frame:flags=fast_bilinear[s{n}]")
            f.append(f"[{last}][s{n}]overlay=x='({px})*{W}-{anchor[0]}*overlay_w':y='({py})*{H}-{anchor[1]}*overlay_h':eval=frame:eof_action=pass[{lab}]")
        else:
            tw, th = max(2, int(round(sw * scale / 100 * K / 2)) * 2), max(2, int(round(sh * scale / 100 * K / 2)) * 2)
            x, y = pos[0] * W - anchor[0] * tw, pos[1] * H - anchor[1] * th
            f.append(f"[{n}:v]{fmt}scale={tw}:{th}:flags=fast_bilinear[s{n}]")
            f.append(f"[{last}][s{n}]overlay=x={x:.1f}:y={y:.1f}:eof_action=pass[{lab}]")
        last = lab
        n += 1
    f.append(f"[{last}]format=yuv420p,setsar=1[out]" if f else "[0:v]format=yuv420p,setsar=1[out]")
    args += ["-filter_complex", ";".join(f), "-map", "[out]", "-frames:v", str(b - a), "-r", "30000/1001", "-c:v", "libx264", "-preset", "veryfast", "-crf", "25", "-pix_fmt", "yuv420p",
             "-threads", "2", "-g", "60", "-bf", "0", "-video_track_timescale", "30000", "-an", out]
    return args

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("timeline"); ap.add_argument("out")
    ap.add_argument("--from", dest="a", type=float, default=0); ap.add_argument("--to", dest="b", type=float, default=None); ap.add_argument("--jobs", type=int, default=6); ap.add_argument("--shift", type=float, default=0, help="素材を何コマ手前から取るか（さらささん v002 では 1 で Premiere に近づいた）")
    o = ap.parse_args()
    global NEAR
    NEAR = o.shift
    rows = json.load(open(o.timeline, encoding="utf-8"))["rows"]
    tracks = ["V1", "V2", "V11", "V3", "V4", "V14", "V15", "V16"]
    vis = []
    for r in rows:
        if r["track"] in tracks and not r["muted"]:
            is_text = any(c["match"] == "AE.ADBE Text" for c in r["comps"])
            if is_text:
                continue
            vis.append(r)
    order = {t: i for i, t in enumerate(tracks)}
    vis.sort(key=lambda r: (order[r["track"]], r["start"]))
    end = max(fr(r["end"]) for r in vis)
    A, B = fr(o.a), min(fr(o.b), end) if o.b else end
    cuts = sorted({A, B} | {fr(r["start"]) for r in vis if A < fr(r["start"]) < B} | {fr(r["end"]) for r in vis if A < fr(r["end"]) < B})
    seg_dir = os.path.join(o.out, "_seg"); os.makedirs(seg_dir, exist_ok=True)
    jobs, listing = [], []
    for a, b in zip(cuts, cuts[1:]):
        act = sorted(layers_at(vis, a), key=lambda r: order[r["track"]])
        key = json.dumps([[r["media"], r["track"], r["in"] + (a - fr(r["start"])) / FPS, r["comps"] if r["track"] != "V1" else [c for c in r["comps"] if c["match"] == "AE.ADBE Motion"]] for r in act], sort_keys=True, ensure_ascii=False) + f"|{b - a}|{a - min([fr(r['start']) for r in act] or [a])}" + ("|r2" if any(r["track"] == "V15" for r in act) else "") + ("|r3" if any(r["track"] == "V3" for r in act) else "")
        h = hashlib.md5(key.encode()).hexdigest()[:16]
        p = os.path.join(seg_dir, f"{h}.mp4")
        listing.append(p)
        if not os.path.exists(p):
            jobs.append((a, b, act, p))
    print(f"切れ目 {len(cuts) - 1}・作る {len(jobs)}", flush=True)
    t0 = time.time()
    errs = []
    def run(j):
        a, b, act, p = j
        tmp = p + ".tmp.mp4"
        args = build_job(a, b, act, tmp, None)
        r = subprocess.run(args, capture_output=True, text=True)
        if r.returncode:
            errs.append((a, r.stderr[-400:]))
            return
        os.replace(tmp, p)
    with cf.ThreadPoolExecutor(o.jobs) as ex:
        for i, _ in enumerate(ex.map(run, jobs)):
            if (i + 1) % 100 == 0:
                print(i + 1, f"{time.time() - t0:.0f}秒", flush=True)
    print("作り終わり", f"{time.time() - t0:.0f}秒", "失敗", len(errs), errs[:2], flush=True)
    cl = os.path.join(o.out, "_list.txt")
    with open(cl, "w") as f:
        for p in listing:
            f.write(f"file '{p}'\n")
    final = os.path.join(o.out, "base.mp4")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", cl, "-c", "copy", "-movflags", "+faststart", final], check=True)
    print("つないだ", final, f"{time.time() - t0:.0f}秒")

if __name__ == "__main__":
    main()
