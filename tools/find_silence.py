#!/usr/bin/env python3
"""残している区間の「声の無い所」を、声の大きさだけで探す（08 の cut.pauses の rule・screen・laugh_gaps の取りこぼしを拾う検査。どの案件でも使える道具）。
元：1018 アプリ開発 v007（2026-10-21）。画面の実演で Claude Code の処理を黙って待つ 14.7秒（v007 31:06）が v001 から残り、小川さんが公開の直前に見つけた
（「なんでこんなミスするの」「２度と起きない様にしろ」）。find_laugh_gaps.py は文字起こしに語が無い所を探すので、無音に文字起こしが語を書いた所
（ささやき・機械の音・書き起こしの誤り）を拾えなかった。ここでは文字起こしを使わず、声の大きさ（analysis/camera_env.npy＝10ms ごとの dB）だけで見る。

  ~/Desktop/video_edit_rules/env/bin/python tools/find_silence.py --ver "<edit/vNNN>" [--min 1.5] [--out 一覧.md]

  - 残している区間（_work/cuts_vNNN.json の keep_frames）の中で、声の大きさが「声のしきい値（cuts の params.voice_thr_db）＋6dB」より小さい所が
    --min 秒（既定 1.5）以上続く所を、版の時刻・素材の秒・その時の画面（図解・全体挿入の画像・画面を映す区間・最後の30秒）つきで出す
  - 「残してよい見込み」：図解の中（声に合わせて組んだ動き）・最後の30秒（挨拶・手を振る）。それ以外は「切る候補」
  - 切る候補が1つでもあれば終了コード 1（検査の合格にしない）。残すなら、理由を台本の行のメモか cuts_plan の注記に書いてから --allow 素材の秒 で外す
  決めるのは人（AI）：画面で黙って待つ所は、結果が出る所（話し出す直前）だけ 0.5〜1秒残して詰める（08 の pauses.screen）。
  顔や手で演じている所（keep_face）・溜め（keep_as_tame）は、コマを見て残す長さを決める
"""
import argparse
import json
import os
import sys

import numpy as np

FPS = 30000 / 1001


def fm(t):
    return f"{int(t // 60)}:{t % 60:05.2f}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ver", required=True, help="版のフォルダ edit/vNNN")
    ap.add_argument("--env", help="10ms ごとの声の大きさ（省略で <edit>/analysis/camera_env.npy）")
    ap.add_argument("--min", type=float, default=1.5, help="この秒以上声の無い所を出す（既定 1.5）")
    ap.add_argument("--margin", type=float, default=6.0, help="声のしきい値に足す dB（既定 6）")
    ap.add_argument("--allow", nargs="*", type=float, default=[], help="残すと決めた所の素材の秒（±0.5秒）")
    ap.add_argument("--out", help="一覧（.md）の書き先（省略で <版>/_work/silence_vNNN.md）")
    a = ap.parse_args()
    V = os.path.abspath(os.path.expanduser(a.ver))
    tag = os.path.basename(V)
    A = os.path.join(os.path.dirname(V), "analysis")
    cuts = json.load(open(os.path.join(V, "_work", f"cuts_{tag}.json"), encoding="utf-8"))
    env = np.load(a.env or os.path.join(A, "camera_env.npy"))
    thr = float(cuts.get("params", {}).get("voice_thr_db", -52.9)) + a.margin
    rec_p = os.path.join(V, f"{tag}_記録.json")
    rec = json.load(open(rec_p, encoding="utf-8")) if os.path.exists(rec_p) else {}
    diag = [(d["start"], d["end"], d.get("key", "")) for d in rec.get("anim_diagrams", [])]
    full = [(d["start"], d["end"], d["key"]) for d in rec.get("images", []) if d.get("insert") == "full"]
    total = cuts.get("total_frames")
    hl = cuts.get("highlight_external_frames", 0)
    keep = cuts["keep_frames"]
    end_tl = (hl + sum(b - c for c, b in keep)) / FPS
    rows, t = [], hl
    for c, b in keep:
        i0, i1 = int(round(c / FPS * 100)), int(round(b / FPS * 100))
        q = env[i0:i1] < thr
        k = 0
        while k < len(q):
            if not q[k]:
                k += 1
                continue
            j = k
            while j < len(q) and q[j]:
                j += 1
            dur = (j - k) / 100
            if dur >= a.min:
                tl = (t + k / 100 * FPS) / FPS
                src = (i0 + k) / 100
                why = ""
                for s, e, key in diag:
                    if s <= tl < e:
                        why = f"図解 {key} の中（残してよい見込み）"
                for s, e, key in full:
                    if s <= tl < e and not why:
                        why = f"全体挿入の画像 {key} の間"
                if tl > end_tl - 30 and not why:
                    why = "最後の30秒（挨拶・手を振る。残してよい見込み）"
                ok = "残してよい見込み" in why or any(abs(src - x) <= 0.5 for x in a.allow)
                rows.append(dict(tl=tl, dur=dur, src=src, why=why or "切る候補", ok=ok))
            k = j
        t += b - c
    out = a.out or os.path.join(V, "_work", f"silence_{tag}.md")
    bad = [r for r in rows if not r["ok"]]
    with open(out, "w", encoding="utf-8") as f:
        f.write(f"# 声の無い所 {a.min}秒以上（{tag}）\n\n声の大きさ：analysis/camera_env.npy が {thr:.1f}dB（声のしきい値＋{a.margin:g}dB）より小さい。文字起こしは使っていない。**全部未聴取**\n\n")
        f.write(f"- 切る候補 {len(bad)}（合わせて {sum(r['dur'] for r in bad):.1f}秒）・残してよい見込み {len(rows) - len(bad)}\n\n| 版の時刻 | 秒 | 素材の秒 | 見立て |\n|---|---|---|---|\n")
        for r in rows:
            f.write(f"| {fm(r['tl'])} | {r['dur']:.1f} | {r['src']:.1f} | {r['why']}{'（allow）' if r['ok'] and '見込み' not in r['why'] else ''} |\n")
    print(f"声の無い所 {a.min}秒以上：{len(rows)}（切る候補 {len(bad)}・{sum(r['dur'] for r in bad):.1f}秒）→ {out}")
    for r in bad:
        print(f"  {fm(r['tl'])}  {r['dur']:.1f}秒  素材 {r['src']:.1f}  {r['why']}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
