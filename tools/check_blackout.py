#!/usr/bin/env python3
"""書き出した動画の中で、カメラが「黒へ落ちて、次のコマでパッと戻る」所（暗転）を探す。

2026-10-15 小川さん（1015claude project開設 v005）「ブラーが入ってる所で、三上さんのカメラの映像ごとブラックアウトする」。
原因は、全体挿入の後ろのぼかし E016（調整レイヤー）の終わりに付けたクロスディゾルブ。Premiere は調整レイヤーの
ディゾルブを「ぼかしが外れていく」ではなく「下のカメラごと黒へ溶かす」で描く（v005 の 0:25・0:33・2:20 で明るさ 96 → 16、
ディゾルブの無い同じ E016〈15:07 の図解〉は黒くならない）。02 の P13 の image_exit・tools/native_prproj.py の add_dissolve も見る。

見ること:
  動画を 64×36 の白黒に縮め、16×9 のます目ごとに明るさを測る。ます目の明るさが、少し前（40〜16コマ前の平均）の半分以下まで
  12コマ以内で落ち、そのあと 4コマ以内に 8割まで戻る所を「暗転の形」とし、ます目の 2割以上が同じコマでその形になったら暗転とする。
  画像や札がそのまま残っている所（ます目が暗くならない）は数えない。図解の黒い板（一気に暗くなって戻らない）も数えない。
  --record（vNNN_記録.json）を渡すと、記録のディゾルブ（座布団・※・画像・ぼかし）の終わりごとに、最後の15コマで
  カメラが暗くなっていないかも出す。また、画面を見せている区間（記録の labels＝左上の実演の札）の中で見つかったものは
  「画面の中身が暗くなった所」（暗いダイアログが開いた・暗い所までスクロールした。v005 の 20:42・24:14）として分けて出し、数えない。

使い方:
  python3 tools/check_blackout.py 書き出し.mp4 [--record vNNN_記録.json] [--out 結果.json]
  ~/Desktop/video_edit_rules/env/bin/python を使う（numpy が要る）。暗転（画面の区間の外）が1件でもあれば終了コード1
"""
import argparse
import json
import subprocess
import sys

import numpy as np

W, H, GW, GH = 64, 36, 16, 9


def fps_of(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate",
                        "-of", "csv=p=0", path], capture_output=True, text=True, check=True).stdout.strip()
    a, b = r.split("/")
    return float(a) / float(b)


def cells(path):
    """コマごとの 16×9 のます目の明るさ（コマ数, 9, 16）"""
    cmd = ["ffmpeg", "-v", "error", "-hwaccel", "videotoolbox", "-i", path, "-an",
           "-vf", f"scale={W}:{H}:flags=area,format=gray", "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    fr = np.frombuffer(raw, dtype=np.uint8).reshape(-1, H, W).astype(np.float32)
    return fr.reshape(-1, GH, H // GH, GW, W // GW).mean(axis=(2, 4))


def ts(sec):
    m, s = divmod(sec, 60)
    return f"{int(m)}:{s:05.2f}"


def find_dips(L, share=0.2, low=0.5, back=0.8, fall=12, rec=4, base=(40, 16), min_base=25.0):
    n = len(L)
    flat = L.reshape(n, -1)
    cs = np.concatenate([np.zeros((1, flat.shape[1]), np.float64), np.cumsum(flat, axis=0, dtype=np.float64)])
    a, b = base
    hits = np.zeros(n, dtype=int)
    for i in range(a, n - rec):
        B = (cs[i - b] - cs[i - a]) / (a - b)
        ok = (B >= min_base) & (flat[i] <= low * B) & (flat[i - fall] >= back * B) & (flat[i + 1:i + 1 + rec].max(axis=0) >= back * B)
        hits[i] = int(ok.sum())
    need = share * flat.shape[1]
    ev, i = [], 0
    while i < n:
        if hits[i] >= need:
            j = i
            while j + 1 < n and hits[j + 1] >= need:
                j += 1
            ev.append((i, j, int(hits[i:j + 1].max())))
            i = j + 1
        else:
            i += 1
    return ev


def dissolve_ends(L, fps, record, share=0.2):
    d = json.load(open(record, encoding="utf-8"))
    out = []
    flat = L.reshape(len(L), -1)
    for x in d.get("dissolves", []):
        if not x.get("clip"):
            continue
        e = int(round(x["clip"][1] * fps))
        if e - 17 < 0 or e > len(L):
            continue
        before, last = flat[e - 17], flat[e - 1]
        dark = int(((before >= 25) & (last <= 0.5 * before)).sum())
        out.append({"track": x["track"], "what": x["what"], "end": ts(x["clip"][1]), "dark_cells": dark,
                    "blackout": dark >= share * flat.shape[1]})
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("video")
    ap.add_argument("--record", help="vNNN_記録.json（ディゾルブの終わりごとにも見る）")
    ap.add_argument("--out")
    a = ap.parse_args()
    fps = fps_of(a.video)
    L = cells(a.video)
    ev = find_dips(L)
    screen = []
    if a.record:
        screen = [(x["start"], x["end"]) for x in json.load(open(a.record, encoding="utf-8")).get("labels", [])]
    in_screen = lambda s, e: any(p <= s / fps and (e + 1) / fps <= q for p, q in screen)
    res = {"video": a.video, "frames": len(L), "fps": round(fps, 3),
           "blackouts": [{"from": ts(s / fps), "to": ts((e + 1) / fps), "cells": c} for s, e, c in ev if not in_screen(s, e)],
           "screen_content": [{"from": ts(s / fps), "to": ts((e + 1) / fps), "cells": c} for s, e, c in ev if in_screen(s, e)]}
    print(f"暗転 {len(res['blackouts'])} 件（{len(L)} コマを見た）")
    for x in res["blackouts"]:
        print(f"  {x['from']}〜{x['to']}（暗くなったます目 {x['cells']}/{GW * GH}）")
    if res["screen_content"]:
        print(f"画面を見せている区間の中で暗くなった所 {len(res['screen_content'])} 件（画面録画の中身。数えない）："
              + "・".join(x["from"] for x in res["screen_content"]))
    if a.record:
        res["dissolves"] = dissolve_ends(L, fps, a.record)
        bad = [x for x in res["dissolves"] if x["blackout"]]
        by = {}
        for x in res["dissolves"]:
            by.setdefault(x["track"], [0, 0])[0 if not x["blackout"] else 1] += 1
        print("ディゾルブの終わり：" + "・".join(f"{t} 暗転なし {v[0]}／暗転 {v[1]}" for t, v in sorted(by.items())))
        for x in bad:
            print(f"  暗転：{x['track']} {x['what']}（{x['end']}・ます目 {x['dark_cells']}）")
    if a.out:
        json.dump(res, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    sys.exit(1 if res["blackouts"] else 0)


if __name__ == "__main__":
    main()
