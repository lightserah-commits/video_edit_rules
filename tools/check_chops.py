#!/usr/bin/env python3
"""声の途中で切れているつなぎ目（音のブツッ）を探す。08 の cut.no_chop.sound（2026-09-28 ユーザー指示
「音声の途中なのに切るのは NG。ちゃんと終わってから切るっていうのを徹底」）。

見ること（声のトラックの、素材が続いていないつなぎ目ごと）:
  前が切れている … つなぎ目の前の2フレームが声（-38dB 以上）で、素材でその後ろの0.1秒も声 ＝ 言い終わる前に切った
  後ろが途中から … つなぎ目の後の2フレームが声で、素材でその前の0.1秒も声 ＝ 言い始めた後から入った
  （無音・息・部屋の音は -45dB より小さい。声は -35〜-20dB くらい）

使い方:
  python3 tools/audible_onset.py extract 素材.MOV 声.wav        … 声を 16kHz・モノラルの WAV にする（1回だけ）
  python3 tools/check_chops.py 版.prproj --seq シーケンス名 --track A1 --media 素材の名前=声.wav [--after 424] [--out 結果.json]
  python3 tools/check_chops.py timeline.json --track A1 --media …   （tools/dump_timeline.py の出力でもよい）
  --media は、タイムラインのクリップの素材名（例 camera_CFR2997.mov）と、その声の WAV の組。素材の時刻＝クリップの in。
  1件でもあれば終了コード1
"""
import argparse
import audioop
import json
import math
import os
import sys
import wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
LOUD = -38.0          # これ以上を声とみなす（dB）
EDGE_FRAMES = 2       # つなぎ目の前後で見るフレーム数
BEYOND = 0.10         # 素材で、つなぎ目の向こう側を見る秒


class Wav:
    def __init__(self, path):
        self.w = wave.open(path, "rb")
        assert self.w.getnchannels() == 1 and self.w.getsampwidth() == 2, "16bit・モノラルの WAV（audible_onset.py extract）"
        self.rate = self.w.getframerate()
        self.n = self.w.getnframes()

    def db(self, t0, t1):
        """t0〜t1 秒の中の、10ミリ秒ごとの大きさの最大（dBFS）"""
        a, b = max(0, int(t0 * self.rate)), min(self.n, int(t1 * self.rate))
        if b <= a:
            return -99.0
        self.w.setpos(a)
        raw = self.w.readframes(b - a)
        hop = self.rate // 100 * 2
        best = 0
        for k in range(0, len(raw) - hop + 1, hop):
            best = max(best, audioop.rms(raw[k:k + hop], 2))
        return 20 * math.log10(best / 32768) if best else -99.0


def load(path, seq):
    if path.endswith(".json"):
        return json.load(open(path))
    from dump_timeline import dump
    return dump(path, seq)


def check(d, track, media, after=0):
    ft = d["frame_ticks"]
    fps = 254016000000 / ft
    rows = sorted([r for r in d["tracks"][track] if not r["muted"] and r["in_ticks"] is not None], key=lambda r: r["start_f"])
    out = []
    for x, y in zip(rows, rows[1:]):
        if y["start_f"] < after or x["name"] not in media or y["name"] not in media:
            continue
        xe = (x["in_ticks"] + (x["end_ticks"] - x["start_ticks"])) / 254016000000
        ys = y["in_ticks"] / 254016000000
        if x["name"] == y["name"] and abs(ys - xe) < 0.5 / fps:
            continue                                   # 素材がそのまま続いている
        wx, wy = media[x["name"]], media[y["name"]]
        tail_in = wx.db(xe - EDGE_FRAMES / fps, xe)
        tail_beyond = wx.db(xe, xe + BEYOND)
        head_in = wy.db(ys, ys + EDGE_FRAMES / fps)
        head_beyond = wy.db(ys - BEYOND, ys)
        tail = tail_in >= LOUD and tail_beyond >= LOUD
        head = head_in >= LOUD and head_beyond >= LOUD
        if tail or head:
            f = y["start_f"]
            out.append({"frame": f, "time": f"{int(f / fps // 60):02d}:{f / fps % 60:05.2f}",
                        "tail_cut": tail, "head_cut": head,
                        "db": {"tail_in": round(tail_in, 1), "tail_beyond": round(tail_beyond, 1),
                               "head_beyond": round(head_beyond, 1), "head_in": round(head_in, 1)}})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--seq")
    ap.add_argument("--track", default="A1")
    ap.add_argument("--media", action="append", required=True, help="素材の名前=声.wav")
    ap.add_argument("--after", type=int, default=0, help="検査しない頭のフレーム数（冒頭のハイライトなど）")
    ap.add_argument("--out")
    a = ap.parse_args()
    media = {}
    for m in a.media:
        k, v = m.split("=", 1)
        media[k] = Wav(v)
    d = load(a.src, a.seq)
    rows = check(d, a.track, media, a.after)
    res = {"loud_db": LOUD, "rows": rows, "tail_cut": sum(r["tail_cut"] for r in rows), "head_cut": sum(r["head_cut"] for r in rows)}
    if a.out:
        json.dump(res, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"声の途中で切れているつなぎ目 {len(rows)}（前が切れている {res['tail_cut']}・後ろが途中から {res['head_cut']}）")
    for r in rows:
        print(f"  {r['time']} {'前が切れている ' if r['tail_cut'] else ''}{'後ろが途中から' if r['head_cut'] else ''} {r['db']}")
    sys.exit(1 if rows else 0)


if __name__ == "__main__":
    main()
