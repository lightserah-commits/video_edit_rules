#!/usr/bin/env python3
"""話者不明の字幕を、声の高さと声色で「どちらの話者か」判別する（08_カットと字幕の追加ルール.yaml の captions）。

  1. プロジェクトの字幕トラックと声のトラックから、字幕ごとの素材の時刻の範囲を出す
  2. 声の素材を 16kHz モノラルに書き出し、tools/voice_features.swift で字幕ごとの特徴（声の高さ・声色）を測る
  3. 話者の分かっている字幕を手本にして、話者不明の字幕を近いもの（k近傍、話者の数の偏りは割り引く）で判別する
     手本どうしで試した正解率も出す（画面解説の案件では 92〜96%、自信 0.8 以上なら 98%）

  自信が低いもの（0.8 未満）は、前後のやりとり（丁寧語か、相手への返事か、呼びかけか）で決め、それでも決めきれないものは一覧で確認をもらう。
  結果は判別の材料。字幕のスタイルを直すのは案件の組み立て側（例 work/gamen_kaisetsu_20260926/v006/cut_v006.py）。

使い方:
  python3 tools/speaker_id.py --project 案件.prproj --sequence シーケンス名 --captions 字幕一覧.csv --audio 声の素材.mov --out 結果.json
    字幕一覧.csv … 字幕トラックの順（開始の早い順）に並んだ表。「番号」「話者」「字幕」の列。話者不明は「?」
    --caption-track V3 --voice-track A1（既定）、--work 作業フォルダ（既定は結果と同じ場所の _speaker_work）
"""
import argparse
import csv
import json
import math
import os
import subprocess
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from native_prproj import Prproj, TPS  # noqa: E402


def caption_ranges(pj, seq, caption_track, voice_track, rows):
    caps = sorted(pj.items(pj.track(seq, caption_track)), key=lambda i: pj.span(i)[0])
    voice = sorted(pj.items(pj.track(seq, voice_track)), key=lambda i: pj.span(i)[0])
    if len(caps) != len(rows):
        raise ValueError(f"字幕の数が表と合いません（トラック {len(caps)}、表 {len(rows)}）")
    out = []
    for it, r in zip(caps, rows):
        s, e = pj.span(it)
        rr = []
        for c in voice:
            a, b = pj.span(c)
            if a < e and s < b:
                h = pj.range_holder(pj.ref(pj.ref(c.find("ClipTrackItem/SubClip")).find("Clip")))
                inp = int(h.findtext("InPoint"))
                lo, hi = max(a, s), min(b, e)
                rr.append([round((inp + lo - a) / TPS, 4), round((inp + hi - a) / TPS, 4)])
        out.append({"idx": int(r["番号"]), "spk": r["話者"], "ranges": rr})
    return out


def vec(x):
    m = x["mel"]
    mu = sum(m) / len(m)
    return [a - mu for a in m] + [math.log(x["f0_med"]) * 3 if x.get("f0_med") else 0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--sequence", required=True)
    ap.add_argument("--captions", required=True)
    ap.add_argument("--audio", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--caption-track", default="V3")
    ap.add_argument("--voice-track", default="A1")
    ap.add_argument("--unknown", default="?")
    ap.add_argument("--work")
    ap.add_argument("-k", type=int, default=15)
    a = ap.parse_args()
    work = a.work or os.path.join(os.path.dirname(os.path.abspath(a.out)), "_speaker_work")
    os.makedirs(work, exist_ok=True)
    rows = list(csv.DictReader(open(a.captions, encoding="utf-8-sig")))
    pj = Prproj.load(a.project)
    seq = pj.sequence(a.sequence)
    json.dump(caption_ranges(pj, seq, a.caption_track, a.voice_track, rows), open(os.path.join(work, "cap_ranges.json"), "w"), ensure_ascii=False)
    pcm = os.path.join(work, "camera_16k.f32")
    if not os.path.exists(pcm):
        subprocess.run(["ffmpeg", "-nostats", "-hide_banner", "-loglevel", "error", "-y", "-i", a.audio, "-vn", "-ac", "1", "-ar", "16000",
                        "-f", "f32le", pcm], check=True)
    exe = os.path.join(work, "voice_features")
    if not os.path.exists(exe):
        subprocess.run(["swiftc", "-O", os.path.join(HERE, "voice_features.swift"), "-o", exe], check=True)
    subprocess.run([exe, work], check=True)
    F = json.load(open(os.path.join(work, "voicefeat.json")))
    lab = [x for x in F if x["spk"] != a.unknown and "mel" in x and x.get("f0_n", 0) >= 3]
    V = [vec(x) for x in lab]
    prior = Counter(x["spk"] for x in lab)

    def dist(p, q):
        return math.sqrt(sum((x - y) ** 2 for x, y in zip(p, q)))

    def knn(v, excl=None):
        ds = sorted((dist(v, V[j]), lab[j]["spk"]) for j in range(len(lab)) if j != excl)[:a.k]
        c = defaultdict(float)
        for d, s in ds:
            c[s] += 1 / (d + 1e-3) / prior[s] * 500
        tot = sum(c.values())
        best = max(c, key=c.get)
        return best, round(c[best] / tot, 2)

    ok = sum(knn(V[i], i)[0] == lab[i]["spk"] for i in range(len(lab)))
    f0 = defaultdict(list)
    for x in lab:
        f0[x["spk"]].append(x["f0_med"])
    by = {int(r["番号"]): r for r in rows}
    preds = []
    for x in F:
        if x["spk"] != a.unknown:
            continue
        if "mel" in x and x.get("f0_n", 0) >= 3:
            p, cf = knn(vec(x))
        else:
            p, cf = None, 0.0
        preds.append({"idx": x["idx"], "text": by[x["idx"]]["字幕"], "pred": p, "conf": cf,
                      "f0": round(x["f0_med"]) if x.get("f0_med") else None,
                      "prev": by.get(x["idx"] - 1, {}).get("話者"), "next": by.get(x["idx"] + 1, {}).get("話者")})
    res = {"accuracy_leave_one_out": round(ok / len(lab), 3), "labeled": dict(prior),
           "f0_median": {k: round(sorted(v)[len(v) // 2]) for k, v in f0.items()}, "predictions": preds}
    json.dump(res, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"手本 {len(lab)} 本で試した正解率 {res['accuracy_leave_one_out']}、声の高さの中央値 {res['f0_median']}")
    print(f"話者不明 {len(preds)} 本：自信 0.8 以上 {sum(p['conf'] >= 0.8 for p in preds)} 本 → {a.out}")


if __name__ == "__main__":
    main()
