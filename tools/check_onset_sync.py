#!/usr/bin/env python3
"""通常字幕・強調の頭が声より早くないかを測る（工程9 の発音同期。2026-11-02 1101 v001「テロップずれてる」から）。音は鳴らさない。全部未聴取。
  物差し1：DTW small の語を字幕の文字に並べ合わせた時刻の近くの、声の谷の後の立ち上がり
  物差し2：mlx の語を字幕の文字に並べ合わせて、その語の幅の中で一番深い谷の後の立ち上がり（DTW を使わない。audible_onset.word_window_onset）
  2つが ±2コマで一致した字幕で「字幕 − 声」を出す。プラス＝字幕が声より早い。字幕の頭を決める道具（audible_onset.word_window_onset）と同じ波形の見方なので、
  カットの切れ目へ寄せた分・手で動かした分・文字が変わった分のずれが主に出る。時刻を使わない確かめは別に要る。
  カットと同じコマに置いた字幕は、決まり（08 の captions.timing の ①）で声より早いので、声の途中の字幕と分けて数える。コマは 29.97fps に直した数。
  合格：声の途中の字幕で声より5コマ以上早い物が 10% 以下（完成版の字幕だけで測ると 15%・4%。段ごと当てると 14.6%・10.7%）。超えると終了コード 1。5コマ以上の物は全部読んで、直すか理由を書く。
  python3 tools/check_onset_sync.py 版.prproj --seq 名前 --media camera_CFR2997.mov --wav camera.wav --mlx asr_camera.json --dtw asr_dtw.json --tracks V6,V7 --cuts vNNN/_work/cuts_vNNN.json --out checks_onset.json
"""
import argparse
import bisect
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audible_onset as AO  # noqa: E402
from check_telop_cut import BASE_FPS, find_cuts, near  # noqa: E402
from dump_timeline import dump  # noqa: E402

TPS = 254016000000
EARLY_LIMIT = 10.0     # 声の途中の字幕で、声より5コマ以上早い物の上限（%）


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("prproj")
    ap.add_argument("--seq", required=True)
    ap.add_argument("--media", required=True)
    ap.add_argument("--wav", required=True)
    ap.add_argument("--mlx", required=True)
    ap.add_argument("--dtw", required=True)
    ap.add_argument("--tracks", default="V6,V7")
    ap.add_argument("--audio", default="A1", help="カットを見る声のトラック（既定 A1）")
    ap.add_argument("--cuts", help="cuts_vNNN.json（highlight_external_frames＝冒頭ハイライトのコマ数を読む）")
    ap.add_argument("--out")
    a = ap.parse_args()
    D = dump(a.prproj, a.seq)
    FPS = D["fps"]
    hl = (json.load(open(a.cuts, encoding="utf-8")).get("highlight_external_frames", 0) or 0) if a.cuts else 0
    cuts = find_cuts(D["tracks"].get(a.audio, []), FPS, hl)
    for name in (a.audio, "V1"):
        v1 = sorted((r for r in D["tracks"].get(name, []) if (r.get("name") or "").startswith(a.media)), key=lambda r: r["start_f"])
        if v1:
            break
    st = [r["start_f"] for r in v1]
    E = AO.BandEnv(a.wav)
    words = AO.load_mlx_words(a.mlx)
    ws = [w[0] for w in words]
    tok = AO.load_whisper_tokens(a.dtw)
    ts = [t["start"] for t in tok]
    mtok = [{"text": w[2], "start": round(w[0], 3)} for w in words]
    mts = [t["start"] for t in mtok]

    def src(f):
        i = bisect.bisect_right(st, f) - 1
        if i < 0 or f >= v1[i]["end_f"]:
            return None, None
        return v1[i]["in_ticks"] / TPS + (f - v1[i]["start_f"]) / FPS, v1[i]

    out, summary, over = {}, {}, False
    print(f"カット {len(cuts)}（{a.audio}。冒頭 {hl}コマを除く）  コマは {BASE_FPS:.2f}fps に直した数。プラス＝字幕が声より早い")
    for tr in a.tracks.split(","):
        rows, prev = [], None
        for r in sorted(D["tracks"].get(tr, []), key=lambda r: r["start_f"]):
            s, clip = src(r["start_f"])
            if s is None or r["start_f"] < hl:
                continue
            text = " ".join(r.get("texts", [])).replace("\r", "")
            if not text:
                continue
            cd = AO.asr_candidate2(tok, ts, text, s, prev_text=prev, window=1.5)
            r1 = AO.onset_from_valley(E, cd) if cd is not None else None
            cm = AO.asr_candidate2(mtok, mts, text, s, prev_text=prev, window=1.5)
            r2 = AO.word_window_onset(E, words, ws, cm)[0] if cm is not None else None
            prev = text
            gap1 = None if r1 is None else round((r1 - s) * BASE_FPS, 1)
            gap2 = None if r2 is None else round((r2 - s) * BASE_FPS, 1)
            both = r1 is not None and r2 is not None and abs(r1 - r2) * BASE_FPS <= 2.01
            d = near(cuts, r["start_f"])
            at_cut = d is not None and abs(d) * BASE_FPS / FPS < 1.5
            rows.append({"tl_f": r["start_f"], "sec": round(r["start_f"] / FPS, 2), "src": round(s, 3), "text": text[:26], "r1": gap1, "r2": gap2, "both": both, "at_cut": at_cut})
        at = [x for x in rows if x["both"] and x["at_cut"]]
        mid = [x for x in rows if x["both"] and not x["at_cut"]]
        b = sorted(x["r1"] for x in mid)
        n = max(1, len(b))
        summary[tr] = {"clips": len(rows), "both": len(at) + len(mid), "at_cut": len(at), "at_cut_over12": sum(x["r1"] > 12.5 for x in at), "mid": len(b), "median": b[len(b) // 2] if b else None,
                       "early5_pct": round(100 * sum(x >= 5 for x in b) / n, 1), "early9_pct": round(100 * sum(x >= 9 for x in b) / n, 1), "late5_pct": round(100 * sum(x <= -5 for x in b) / n, 1)}
        out[tr] = rows
        print(tr, summary[tr])
        for x in mid:
            if x["r1"] >= 5 or x["r1"] <= -5:
                print("  早い" if x["r1"] >= 5 else "  遅い", f"{x['sec']:8.2f}秒", f"{x['r1']:+.1f}コマ", x["text"])
        over = over or summary[tr]["early5_pct"] > EARLY_LIMIT
    if a.out:
        json.dump({"summary": summary, "rows": out}, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    return 1 if over else 0


if __name__ == "__main__":
    sys.exit(main())
