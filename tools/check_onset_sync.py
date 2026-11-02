#!/usr/bin/env python3
"""通常字幕・強調の頭が声より早くないかを測る（工程9 の発音同期。2026-11-02 1101 v001「テロップずれてる」から）。音は鳴らさない。全部未聴取。
  物差し1：DTW small の語を字幕の文字に並べ合わせた時刻の近くの、声の谷の後の立ち上がり
  物差し2：mlx の語の幅の中で一番深い谷の後の立ち上がり（DTW を使わない）
  2つが ±2コマで一致した字幕で「字幕 − 声」を出す。プラス＝字幕が声より早い。字幕の頭を決める道具（audible_onset.word_window_onset）と同じ波形の見方なので、
  カットの切れ目へ寄せた分・手で動かした分・文字が変わった分のずれが主に出る。時刻を使わない確かめは別に要る。
  python3 tools/check_onset_sync.py 版.prproj --seq 名前 --media camera_CFR2997.mov --wav camera.wav --mlx asr_camera.json --dtw asr_dtw.json --tracks V6,V7 --out checks_onset.json
"""
import argparse
import bisect
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audible_onset as AO  # noqa: E402

FPS = 30000 / 1001
TPS = 254016000000


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("prproj")
    ap.add_argument("--seq", required=True)
    ap.add_argument("--media", required=True)
    ap.add_argument("--wav", required=True)
    ap.add_argument("--mlx", required=True)
    ap.add_argument("--dtw", required=True)
    ap.add_argument("--tracks", default="V6,V7")
    ap.add_argument("--out")
    a = ap.parse_args()
    tmp = tempfile.mktemp(suffix=".json")
    subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "dump_timeline.py"), a.prproj, a.seq, tmp], check=True, stdout=subprocess.DEVNULL)
    D = json.load(open(tmp, encoding="utf-8"))
    v1 = sorted((r for r in D["tracks"]["V1"] if r["name"] == a.media), key=lambda r: r["start_f"])
    st = [r["start_f"] for r in v1]
    E = AO.BandEnv(a.wav)
    words = AO.load_mlx_words(a.mlx)
    ws = [w[0] for w in words]
    tok = AO.load_whisper_tokens(a.dtw)
    ts = [t["start"] for t in tok]

    def src(f):
        i = bisect.bisect_right(st, f) - 1
        if i < 0 or f >= v1[i]["end_f"]:
            return None, None
        return v1[i]["in_ticks"] / TPS + (f - v1[i]["start_f"]) / FPS, v1[i]

    out, summary = {}, {}
    for tr in a.tracks.split(","):
        rows = []
        for r in D["tracks"].get(tr, []):
            s, clip = src(r["start_f"])
            if s is None:
                continue
            text = " ".join(r.get("texts", [])).replace("\r", "")
            if not text:
                continue
            cd = AO.asr_candidate2(tok, ts, text, s, window=1.5)
            r1 = AO.onset_from_valley(E, cd) if cd is not None else None
            i = bisect.bisect_left(ws, s - 0.45)
            cands = [w for w in words[max(0, i - 1):i + 6] if w[0] <= s + 0.45 and w[1] >= s - 0.05]
            r2s = [AO.onset_in_span(E, w[0], w[1]) for w in cands]
            r2s = [x for x in r2s if x is not None and abs(x - s) <= 0.8]
            r2 = min(r2s, key=lambda x: abs(x - (r1 if r1 is not None else s))) if r2s else None
            gap1 = None if r1 is None else round((r1 - s) * FPS, 1)
            gap2 = None if r2 is None else round((r2 - s) * FPS, 1)
            both = r1 is not None and r2 is not None and abs(r1 - r2) * FPS <= 2.01
            rows.append({"tl_f": r["start_f"], "src": round(s, 3), "text": text[:26], "r1": gap1, "r2": gap2, "both": both})
        b = [x["r1"] for x in rows if x["both"]]
        n = max(1, len(b))
        summary[tr] = {"clips": len(rows), "both": len(b), "median": sorted(b)[len(b) // 2] if b else None, "early5_pct": round(100 * sum(x >= 5 for x in b) / n, 1),
                       "early9_pct": round(100 * sum(x >= 9 for x in b) / n, 1), "late5_pct": round(100 * sum(x <= -5 for x in b) / n, 1)}
        out[tr] = rows
        print(tr, summary[tr])
        for x in rows:
            if x["both"] and x["r1"] <= -5:
                print("  遅い", x["tl_f"], x["src"], x["r1"], x["text"])
    if a.out:
        json.dump({"summary": summary, "rows": out}, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=0)


if __name__ == "__main__":
    main()
