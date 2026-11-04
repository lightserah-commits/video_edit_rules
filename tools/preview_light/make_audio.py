#!/usr/bin/env python3
"""プロジェクトの音の段（声・BGM・SE）を、レベルの値のとおり重ねて audio.m4a を作る。再生はしない。
  env/bin/python make_audio.py <prproj> <シーケンス名> <出力フォルダ>"""
import hashlib, json, os, subprocess, sys, time
import numpy as np
sys.path.insert(0, os.path.expanduser("~/Desktop/video_edit_rules/tools"))
from native_prproj import Prproj, TPS
from prproj_motion import is_muted
SR = 48000
UNITY = 10 ** (-15 / 20)  # Premiere の「レベル」の値：0.1778 が 0dB

def level_of(pj, it):
    ow = it.find("ClipTrackItem/ComponentOwner")
    ch = pj.ref(ow.find("Components")) if ow is not None else None
    if ch is None:
        return 1.0, None
    for c in ch.iter("Component"):
        e = pj.ref(c)
        if e is None:
            continue
        for p in e.iter("Param"):
            pe = pj.ref(p)
            if pe is not None and (pe.findtext("Name") or "").strip() == "レベル":
                v = pe.findtext("StartKeyframe") or ""
                g = float(v.split(",")[1]) / UNITY if "," in v else 1.0
                kf = [k for k in (pe.findtext("Keyframes") or "").strip().split(";") if k]
                if kf:
                    return g, [(int(k.split(",")[0]) / TPS, float(k.split(",")[1]) / UNITY) for k in kf]
                return g, None
    return 1.0, None

def media(pj, it):
    sub = pj.ref(it.find("ClipTrackItem/SubClip"))
    clip = pj.ref(sub.find("Clip"))
    c = clip.find("Clip")
    inp = int(c.findtext("InPoint") or 0) / TPS
    src = pj.ref(c.find("Source"))
    m = pj.ref(src.find("MediaSource/Media"))
    p = m.findtext("FilePath") or m.findtext("ActualMediaFilePath")
    # 効果音と大きすぎる声は、クリップの Gain（倍率）で下げてある（prj_helpers.add_gain_db）
    g = clip.find("Gain")
    return "/" + p.lstrip("/"), inp, float(g.text) if g is not None and g.text else 1.0

def decode(path, cache):
    os.makedirs(cache, exist_ok=True)
    raw = os.path.join(cache, hashlib.md5(path.encode()).hexdigest()[:12] + ".f32")
    if not os.path.exists(raw):
        tmp = raw + ".tmp"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", path, "-vn", "-ac", "2", "-ar", str(SR), "-f", "f32le", tmp], check=True)
        os.replace(tmp, raw)
    return np.memmap(raw, dtype=np.float32, mode="r").reshape(-1, 2)

def main(proj, seqname, out):
    pj = Prproj.load(proj)
    seq = pj.sequence(seqname)
    t0 = time.time()
    end = 0.0
    rows = []
    for tn, tr in pj.tracks(seq):
        if not tn.startswith("A"):
            continue
        for it in pj.items(tr):
            if is_muted(it):
                continue
            s, e = pj.span(it)
            p, inp, cg = media(pj, it)
            g, kf = level_of(pj, it)
            rows.append((tn, s / TPS, e / TPS, p, inp, g * cg, [(t, v * cg) for t, v in kf] if kf else None))
            end = max(end, e / TPS)
    mix = {t: np.zeros((int(end * SR) + 1, 2), dtype=np.float32) for t in ("A1", "A2", "A3", "A4", "A5")}
    cache = os.path.join(out, "_audio")
    for tn, s, e, p, inp, g, kf in rows:
        if not os.path.exists(p):
            print("無い", p); continue
        d = decode(p, cache)
        a = int(round(s * SR)); n = int(round((e - s) * SR)); si = int(round(inp * SR))
        chunk = np.asarray(d[si:si + n], dtype=np.float32)
        chunk = chunk[:max(0, len(mix[tn]) - a)]
        if len(chunk) == 0:
            continue
        if kf:
            ts = (np.arange(len(chunk)) / SR + inp)
            gain = np.interp(ts, [k[0] for k in kf], [k[1] for k in kf])[:, None]
            chunk = chunk * gain
        else:
            chunk = chunk * g
        mix[tn][a:a + len(chunk)] += chunk
    print("重ねた", len(rows), f"{time.time() - t0:.0f}秒", flush=True)
    # A1 と A2 は同じ声を左右に振っている。-3dB で足すと Premiere の書き出しとピークがそろう（1101 v002 r5：ピーク -1.5dB）
    all_ = (mix["A1"] + mix["A2"]) * (10 ** (-3 / 20)) + mix["A3"] + mix["A4"] + mix["A5"]
    raw = os.path.join(cache, "mix.f32")
    all_.tofile(raw)
    r = subprocess.run(["ffmpeg", "-hide_banner", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", raw, "-af", "ebur128=peak=true:framelog=quiet", "-f", "null", "-"], capture_output=True, text=True).stderr
    print("音の大きさ", [l.strip() for l in r.splitlines() if l.strip().startswith(("I:", "Peak:"))], flush=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", raw, "-c:a", "aac", "-b:a", "160k", os.path.join(out, "audio.m4a")], check=True)
    os.remove(raw)
    print("音のファイル", f"{time.time() - t0:.0f}秒")

if __name__ == "__main__":
    main(*sys.argv[1:4])
