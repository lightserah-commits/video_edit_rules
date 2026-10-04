#!/usr/bin/env python3
"""強調テロップが出る瞬間と、強調に書いた最初の言葉が聞こえ始める瞬間の差を出す（読むだけ・音は出さない）。
決まりは 01_判断フロー.md の「出す時刻」（2026-10-02）：出る瞬間＝書いた最初の言葉の聞こえ始め。それより前には出さない。

使い方:
  python3 tools/check_kyocho_timing.py 版.prproj --seq シーケンス名 --track V7 \
      --asr 素材名=文字起こし.json [--wav 素材名=声16k.wav] [--out checks_kyocho_timing.json]
    --track  強調テロップの段（02 の output_tracks。複数は V7,V8）
    --asr    素材の文字起こし（語ごとの時刻 words つき。実例/カット調査/scripts/transcribe_raw.py の形）。素材名は A1 のクリップ名
    --wav    素材の声（16kHz・1ch。tools/audible_onset.py extract）。あれば語の頭を波形で合わせ直す
合格: 書いた最初の言葉より 0.1秒以上早く出るもの 0件（文字起こしの誤りで出たものは、波形・画像で確かめて理由を書く）。
     0.3秒以上遅いものは読んで決める（お手本は聞こえ始めと同時か 0.1〜0.3秒あと）。
2行のテロップの2行目は、1行目と同時に出るので測らない。書いた言葉が文字起こしに見つからないものは「測れない」。
"""
import argparse
import json
import os
import re
import sys
import wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dump_timeline import dump  # noqa: E402

TPS = 254016000000
NORM = re.compile(r"[\s\r　、。！!？?…「」『』｢｣（）()・/／〜~ｗw↑←→※〈〉＜＞<>【】:：]")


def words(p):
    out = []
    for s in json.load(open(p, encoding="utf-8")):
        for w in s.get("words", []):
            t = NORM.sub("", w["word"]).lower()
            if t:
                out.append((w["start"], t))
    return out


def env_db(p):
    import numpy as np  # 波形を使う時だけ
    with wave.open(p) as f:
        x = np.frombuffer(f.readframes(f.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    n = len(x) // 160
    return 10 * np.log10(np.mean(x[:n * 160].reshape(n, 160) ** 2, axis=1) + 1e-10)


def wave_onset(db, w):
    """語の頭（文字起こしの時刻 w の前後 0.25秒）で、声が立ち上がる所。"""
    i0 = max(0, int((w - .25) * 100)); e = db[i0:int((w + .25) * 100)]
    if len(e) < 10:
        return w
    half = e[:len(e) // 2 + 5]; m = int(half.argmin()); lo, hi = e[m], e[m:].max()
    for k in range(m, len(e)):
        if e[k] > lo + .6 * (hi - lo):
            return (i0 + k) / 100
    return w


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("prproj"); ap.add_argument("--seq", required=True); ap.add_argument("--track", required=True)
    ap.add_argument("--asr", action="append", required=True); ap.add_argument("--wav", action="append", default=[])
    ap.add_argument("--out")
    a = ap.parse_args()
    asr = {k: words(v) for k, v in (x.split("=", 1) for x in a.asr)}
    dbs = {k: env_db(v) for k, v in (x.split("=", 1) for x in a.wav)}
    tl = dump(a.prproj, a.seq); fps = tl["fps"]
    # タイムラインのコマ → (素材名, 素材の秒)
    srcmap = {}
    for r in tl["tracks"].get("A1", []):
        if r["muted"] or r["name"] not in asr or r["in_ticks"] is None:
            continue
        for f in range(r["start_f"], r["end_f"]):
            srcmap[f] = (r["name"], r["in_ticks"] / TPS + (f - r["start_f"]) / fps)
    tel = []
    for tr in a.track.split(","):
        for r in tl["tracks"].get(tr, []):
            t = "".join(r.get("texts") or [])
            if r["muted"] or len(NORM.sub("", t)) < 2:
                continue
            tel.append(r)
    res = []
    for r in tel:
        text = "／".join(x.replace("\r", "／") for x in r["texts"])
        first = NORM.sub("", r["texts"][0].split("\r")[0]).lower()
        at = r["start_f"] / fps
        row = {"時刻": f"{int(at // 60):02d}:{at % 60:05.2f}", "文字": text}
        if r["start_f"] not in srcmap:
            row["結果"] = "測れない（声の素材が無い所）"; res.append(row); continue
        nm, sec = srcmap[r["start_f"]]
        W = asr[nm]; key = first[:2]; best = None
        for i, (ws, w) in enumerate(W):
            if abs(ws - sec) > 3:
                continue
            if "".join(v for _, v in W[i:i + 4]).startswith(key) and (best is None or abs(ws - sec) < abs(best - sec)):
                best = ws
        if best is None:
            row["結果"] = "測れない（書いた最初の言葉が文字起こしに無い）"; res.append(row); continue
        on = wave_onset(dbs[nm], best) if nm in dbs else best
        d = round(sec - on, 2)
        row["差"] = d
        row["結果"] = "早い" if d <= -.1 else ("遅い" if d > .3 else "○")
        res.append(row)
    early = [x for x in res if x.get("結果") == "早い"]; late = [x for x in res if x.get("結果") == "遅い"]
    ok = [x for x in res if x.get("結果") == "○"]; nm_ = [x for x in res if "差" not in x]
    for x in early + late:
        print(f"{x['時刻']}\t{x['結果']}\t{x['差']:+.2f}秒\t{x['文字']}")
    print(f"# 強調 {len(res)}件：○ {len(ok)}・早い（0.1秒以上前）{len(early)}・遅い（0.3秒より後）{len(late)}・測れない {len(nm_)}", file=sys.stderr)
    if a.out:
        json.dump(res, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    sys.exit(1 if early else 0)


if __name__ == "__main__":
    main()
