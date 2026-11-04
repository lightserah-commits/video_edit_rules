#!/usr/bin/env python3
"""テロップの切り替わりとカットのずれの検査（どの案件でも使える道具。工程9。決まりは ルール/08 の captions.timing）。
完成版2本は、字幕・強調・札の頭と終わりが「カットと同じコマ」か「カットから7コマ以上離れた所」にあり、
カットの2〜6コマ後ろ・前にテロップの切り替わりを置いていない（2026-11-04 測った。字幕 1,293枚で1枚だけ）。
カットの少し後ろで替わると、前のテロップが新しい画の上に数コマ残る。

  ×：テロップの頭か終わりが、カットの前後 2〜6コマにある（0件が合格）
  注意：カットの前後 7〜15コマにある（完成版でも 1〜2% ある。読んで決める）

カット＝声のトラックで素材が飛ぶ所（素材が続いている分け目は数えない）。冒頭ハイライトは --cuts か --hl-frames で外す。
文字のあるトラックを全部見る。--tracks で絞れる。

使い方：
  python3 tools/check_telop_cut.py 版.prproj --seq シーケンス名 [--cuts 版/_work/cuts_vNNN.json] [--out 版/checks_telop_cut.json]
  ×があると終了コード 1。
"""
import argparse
import bisect
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from dump_timeline import dump  # noqa: E402

TPS = 254016000000
BASE_FPS = 30000 / 1001     # コマ数はこの速さに直して数える（完成版の2本目は 59.94fps）


def find_cuts(clips, fps, after=0):
    """声のトラックの切れ目のうち、素材が飛ぶ所（素材が続く分け目は数えない）"""
    clips = sorted(clips, key=lambda r: r["start_f"])
    cuts = []
    for p, q in zip(clips, clips[1:]):
        joined = q["start_f"] == p["end_f"] and q.get("name") == p.get("name") and abs(q["in_ticks"] - p["out_ticks"]) / TPS <= 1.5 / fps
        if not joined and q["start_f"] >= after:
            cuts.append(q["start_f"])
    return sorted(set(cuts))


def near(cuts, f):
    i = bisect.bisect_left(cuts, f)
    c = [cuts[j] for j in (i - 1, i) if 0 <= j < len(cuts)]
    return min((f - x for x in c), key=abs) if c else None


def main():
    ap = argparse.ArgumentParser(description="テロップの頭と終わりが、カットの少し前後にないかを見る")
    ap.add_argument("proj")
    ap.add_argument("--seq", required=True)
    ap.add_argument("--audio", default="A1", help="声のトラック（既定 A1）")
    ap.add_argument("--tracks", help="見るトラック（例 V5,V6,V7）。省くと文字のあるトラックを全部")
    ap.add_argument("--cuts", help="cuts_vNNN.json（highlight_external_frames＝冒頭ハイライトのコマ数を読む）")
    ap.add_argument("--hl-frames", type=int, help="冒頭ハイライトのコマ数（--cuts より優先）")
    ap.add_argument("--out", help="出力の JSON")
    ap.add_argument("--show", type=int, default=30, help="画面に出す × の行数")
    a = ap.parse_args()

    tl = dump(a.proj, a.seq)
    fps = tl["fps"]
    u = BASE_FPS / fps
    hl = a.hl_frames
    if hl is None and a.cuts:
        hl = json.load(open(a.cuts, encoding="utf-8")).get("highlight_external_frames", 0) or 0
    hl = hl or 0
    cuts = find_cuts(tl["tracks"].get(a.audio, []), fps, hl)
    names = a.tracks.split(",") if a.tracks else sorted((k for k, v in tl["tracks"].items() if k[0] == "V" and any(r.get("texts") for r in v)), key=lambda k: int(k[1:]))

    rows, bad, warn = [], [], []
    print(f"カット {len(cuts)}（{a.audio}。冒頭 {hl}コマを除く）  コマは {BASE_FPS:.2f}fps に直した数")
    print("トラック 枚数 | 頭：同じ 2〜6 7〜15 16〜 | 終わり：同じ 2〜6 7〜15 16〜")
    for tr in names:
        items = [r for r in tl["tracks"].get(tr, []) if r.get("texts") and r["start_f"] >= hl]
        if not items:
            continue
        cnt = {"頭": [0, 0, 0, 0], "終わり": [0, 0, 0, 0]}
        for r in items:
            text = " ".join(r["texts"]).replace("\r", " ")[:24]
            for lab, key in (("頭", "start_f"), ("終わり", "end_f")):
                d = near(cuts, r[key])
                if d is None:
                    continue
                x = abs(d) * u
                k = 0 if x < 1.5 else 1 if x <= 6.5 else 2 if x <= 15.5 else 3
                cnt[lab][k] += 1
                if k in (1, 2):
                    row = {"track": tr, "where": lab, "frame": r[key], "sec": round(r[key] / fps, 2), "off": round(d * u, 1), "text": text}
                    (bad if k == 1 else warn).append(row)
        rows.append({"track": tr, "n": len(items), **cnt})
        print(f"{tr:6s} {len(items):5d} | {cnt['頭'][0]:4d} {cnt['頭'][1]:3d} {cnt['頭'][2]:3d} {cnt['頭'][3]:4d} | {cnt['終わり'][0]:4d} {cnt['終わり'][1]:3d} {cnt['終わり'][2]:3d} {cnt['終わり'][3]:4d}")
    print(f"× カットの前後 2〜6コマ {len(bad)}（0件が合格）／注意 7〜15コマ {len(warn)}（読んで決める）")
    for r in bad[:a.show]:
        print(f"  × {r['sec']:8.2f}秒 {r['track']} {r['where']} カットから{r['off']:+.0f}コマ「{r['text']}」")
    if len(bad) > a.show:
        print(f"  …ほか {len(bad) - a.show}件（--out の JSON に全部）")
    out = a.out or os.path.join(os.path.dirname(os.path.abspath(a.proj)), "checks_telop_cut.json")
    json.dump({"cuts": len(cuts), "tracks": rows, "bad": bad, "warn": warn}, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
