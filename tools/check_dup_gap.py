#!/usr/bin/env python3
"""強調と字幕の同じ言葉・テロップの無い所の検査（どの案件でも使える道具。工程9。読むだけ）。
元は雛形の _work/check_dup_gap.py（2026-10-22 小川さん「強調の直前に同じ言葉が通常テロップで入ってる」「テロップないところあるところ」）。

  1. 強調の直前（2.5秒）・同時に、同じ言葉が通常字幕に出ていないか（01 の「出す時刻」：同じ文を2回読ませない）。共通 6字以上か同時＝落第、4〜5字＝一覧
  2. 声があるのに、字幕・強調・札・ボード・図解のどれも出ていない所（0.3秒以上＝落第。--env が無ければ測らない）
  3. 表示が何も無い 1.0秒以上の切れ目（落第。声が小さい聞き手を取りこぼさないため）
  落第が1つでもあれば終了コード 1。読んで残すと決めた同じ言葉は --allow の JSON に書く：[{"強調": "文の頭", "字幕": "文の頭", "why": "理由"}]

使い方：
  ~/Desktop/video_edit_rules/env/bin/python tools/check_dup_gap.py 版.prproj --seq シーケンス名 --cuts vNNN/_work/cuts_vNNN.json --env analysis/camera_env.npy --out vNNN/checks_dup_gap.json
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from dump_timeline import dump  # noqa: E402

FPS = 30000 / 1001
DROP = set(" 　\r\n、。・？！…「」『』（）()／/：:→↑←※‼！?")


def norm(t):
    return "".join(c for c in t if c not in DROP)


def lcs(a, b):
    best, bs = 0, ""
    for i in range(len(a)):
        for j in range(len(b)):
            k = 0
            while i + k < len(a) and j + k < len(b) and a[i + k] == b[j + k]:
                k += 1
            if k > best:
                best, bs = k, a[i:i + k]
    return best, bs


def fm(t):
    return f"{int(t // 60)}:{t % 60:05.2f}"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("proj")
    ap.add_argument("--seq", required=True)
    ap.add_argument("--caption", default="V6", help="通常字幕の段")
    ap.add_argument("--emphasis", default="V7", help="強調の段")
    ap.add_argument("--shown", default="V6,V7,V10,V12,V13,V14", help="文字が出ている段（空のクリップは数えない）")
    ap.add_argument("--images", default="V15,V16", help="図解・画像の段（文字が無くても出ていると数える）")
    ap.add_argument("--cuts", help="cuts_vNNN.json（冒頭ハイライトのコマ数・残す区間・声の境目）")
    ap.add_argument("--env", help="camera_env.npy（10ms ごとの声の大きさ）。無ければ 2 を測らない")
    ap.add_argument("--allow", help="読んで残すと決めた同じ言葉の JSON（省略時は cuts と同じ場所の dup_allow.json）")
    ap.add_argument("--out")
    a = ap.parse_args()
    tl = dump(a.proj, a.seq)
    fps = tl["fps"]

    def rows(tr):
        out = []
        for r in tl["tracks"].get(tr, []):
            if r["muted"]:
                continue
            out.append({"s": r["start_f"] / fps, "e": r["end_f"] / fps, "text": "".join(r.get("texts") or []), "track": tr})
        return sorted(out, key=lambda x: x["s"])

    caps = [r for r in rows(a.caption) if r["text"].strip()]
    emps = [r for r in rows(a.emphasis) if r["text"].strip()]
    images = a.images.split(",")
    subs = []
    for tr in a.shown.split(",") + images:
        for r in rows(tr):
            if tr in images or r["text"].strip():
                subs.append(r)

    cuts = json.load(open(a.cuts, encoding="utf-8")) if a.cuts else {}
    hl = cuts.get("highlight_external_frames", 0) or 0
    allow_p = a.allow or (os.path.join(os.path.dirname(a.cuts), "dup_allow.json") if a.cuts else None)
    allow = json.load(open(allow_p, encoding="utf-8")) if allow_p and os.path.exists(allow_p) else []

    def allowed(e, c):
        return any(norm(e["text"]).startswith(norm(x["強調"])) and norm(c["text"]).startswith(norm(x["字幕"])) for x in allow)

    fails, warns = [], []
    # 1. 強調の直前（2.5秒）・同時の同じ言葉
    for e in emps:
        en = norm(e["text"])
        for c in caps:
            before = (c["e"] <= e["s"] + 0.02 and c["e"] > e["s"] - 2.5) or (c["s"] < e["s"] < c["e"])
            during = c["s"] < e["e"] and e["s"] < c["e"] and not before
            if not (before or during):
                continue
            k, s_ = lcs(norm(c["text"]), en)
            if k < 4:
                continue
            row = {"what": "強調の直前の同じ言葉" if before else "強調と同時の同じ言葉",
                   "強調": f"{fm(e['s'])} {e['text'][:24]}", "字幕": f"{fm(c['s'])}〜{fm(c['e'])} {c['text'][:24]}", "共通": s_, "字数": k}
            if allowed(e, c):
                row["allow"] = True
                warns.append(row)
            else:
                (fails if k >= 6 or during else warns).append(row)

    # 2. 声があるのにテロップが無い所
    if a.env and cuts:
        import numpy as np
        env = np.load(a.env)
        thr = float(cuts.get("params", {}).get("voice_thr_db", -52.9)) + 6.0
        keep = cuts["keep_frames"]
        total_f = hl + sum(y - x for x, y in keep)
        n10 = int(total_f / FPS * 100) + 1
        voice = np.zeros(n10, dtype=bool)
        tf = hl
        for x, y in keep:
            i0 = int(round(tf / FPS * 100))
            seg = env[int(round(x / FPS * 100)):int(round(x / FPS * 100)) + int(round((y - x) / FPS * 100))]
            voice[i0:i0 + len(seg)] = seg[:max(0, n10 - i0)] >= thr
            tf += y - x
        covered = np.zeros(n10, dtype=bool)
        for r in subs:
            covered[max(0, int(r["s"] * 100)):min(n10, int(r["e"] * 100) + 1)] = True
        bad = voice & ~covered
        bad[:int(hl / FPS * 100)] = False       # 冒頭ハイライトは焼き込みの別作り
        i = 0
        while i < n10:
            if bad[i]:
                j = i
                while j < n10 and bad[j]:
                    j += 1
                if j - i >= 30:
                    prev = max((c for c in caps if c["e"] <= i / 100 + 0.05), key=lambda c: c["e"], default=None)
                    fails.append({"what": "声があるのにテロップが無い", "時刻": f"{fm(i / 100)}〜{fm(j / 100)}", "秒": round((j - i) / 100, 2), "前の字幕": (prev or {}).get("text", "")[:24]})
                i = j
            else:
                i += 1

    # 3. 表示の切れ目（1.0秒以上なにも出ていない）
    merged = []
    for r in sorted(subs, key=lambda x: x["s"]):
        if merged and r["s"] <= merged[-1][1] + 0.01:
            merged[-1][1] = max(merged[-1][1], r["e"])
        else:
            merged.append([r["s"], r["e"]])
    prev_end = hl / fps
    for s0, e0 in merged:
        if e0 <= prev_end:
            continue
        if s0 - prev_end >= 1.0:
            fails.append({"what": "表示が何も無い切れ目", "時刻": f"{fm(prev_end)}〜{fm(s0)}", "秒": round(s0 - prev_end, 2)})
        prev_end = max(prev_end, e0)

    if a.out:
        json.dump({"fails": fails, "warns": warns, "fail_count": len(fails), "warn_count": len(warns)}, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for f_ in fails:
        print("落第", json.dumps(f_, ensure_ascii=False))
    for w_ in warns:
        print("一覧", json.dumps(w_, ensure_ascii=False))
    print(f"落第 {len(fails)}・一覧（4〜5字の弱い一致） {len(warns)}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
