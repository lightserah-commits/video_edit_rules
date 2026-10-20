#!/usr/bin/env python3
"""字幕にも「切る」にも入っていない言葉の声・「切る」と決めた言葉の端の声が、残した区間に残っていないかを探す（読むだけ。どの案件でも使える）。
08 の captions.base.check の ⑥⑦（2026-10-19 小川さん OK。1017 v008 で小川さんが手で切った「今」「だね」「今回」「と」「7」「して」「という風に 押して」から）。

  ⑥ 字幕に無い言葉 … 字幕の頭ではない声（前の字幕を出したまま続く区切り・区切りの中の字幕の頭より前の語）のまとまりが、
     その時に出ている字幕の文字にほとんど無い（合う文字が --match 未満）。字幕の頭からのまとまりは、字幕の言い換えがあるので見ない。
     話し癖のフィラー（あの・まあ・うん など）は数えない。言いよどみ（えー・えっと・あのー・うーん・あー。08 の cut.remove「フィラー（言いよどみ）」）は
     数える（2026-10-20 から。残っていたら切る。区切りの語に出ない言いよどみは tools/find_fillers.py で見る）。台本の行のメモ（「  # …」）にその語を書いてある所・文字を出さない行（u-）は
     「決めてある」として数えない（例「言いかけの『俺が』を出さない（音は切らない）」）
  ⑦ 切ると決めた言葉の端 … 台本の「x A..B」で切ると決めた区切りの語の声が、残した区間に --min 秒以上残っている（切る位置がずれた）

声は 10ms ごとの大きさ（analysis/camera_env.npy。cuts_plan と同じ物）で、AI の版の声のしきい値（cuts の params.voice_thr_db）より --over dB 大きい所。

  ~/Desktop/video_edit_rules/env/bin/python tools/check_stray_words.py --ver "<edit/vNNN>" [--out 出す場所] [--min 0.06] [--over 6]
  （<edit/vNNN>/_work/cuts_vNNN.json・captions_vNNN.json、<edit/vNNN>/script_vNNN.txt、<edit>/analysis/units.json・camera_env.npy を読む。
    名前が違う時は --cuts --captions --script --units --env で指す）
  出す物：<--out>.md と .tsv（既定は <edit/vNNN>/_work/stray_words_vNNN）。⑥⑦が1件でもあれば終了コード1（読んで外した物は台本のメモに書く）
"""
import argparse
import bisect
import difflib
import json
import os
import re
import sys
import unicodedata

import numpy as np

FPS = 30000 / 1001
FILLERS = {"えー", "えーと", "えっと", "えと", "あの", "あのー", "あのう", "まあ", "まぁ", "まー", "うーん", "うん", "んー", "ん",
           "え", "あ", "ま", "ああ", "あー", "えぇ", "ええ", "うー", "おー", "お"}
HESITATION = re.compile(r"^(え+ー+っ?と?|えっと|えと|あのー+|あのう|うー+ん|んー+|あー+)$")   # 言いよどみ（数える。2026-10-20）


def skip_filler(w):
    """数えないフィラー（話し癖・短い反応）か。言いよどみは数える（norm は「ー」を消すので、消す前の形で見る）"""
    raw = unicodedata.normalize("NFKC", w or "").strip(" 、。,.")
    return norm(w) in FILLERS and not HESITATION.match(raw)


def norm(s):
    s = unicodedata.normalize("NFKC", s or "")
    s = re.sub(r"[\s／/\r\n、。,.!！?？「」『』（）()…・ー〜~]", "", s).lower()
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)      # カタカナ → ひらがな


def ff(t):
    if t is None:
        return "-"
    m = int(t // 60)
    return f"{m}:{t - 60 * m:05.2f}"


def parse_pos(s):
    s = s.strip()
    if "/" in s:
        u, w = s.split("/", 1)
        return int(u), w
    return int(s), None


def load_script(path):
    cuts, notes = [], {}
    for ln, raw in enumerate(open(path, encoding="utf-8"), 1):
        line = raw.rstrip("\n")
        if not line.strip() or line.startswith("#"):
            continue
        note = ""
        if "  #" in line:
            line, note = line.split("  #", 1)
        notes[ln] = note
        if line.startswith("x "):
            rng, why = line[2:].split("|", 1)
            a, b = rng.split("..")
            cuts.append(dict(a=parse_pos(a), b=parse_pos(b), why=why.strip(), line=ln))
    return cuts, notes


def word_index(words, marker):
    """区切りの語の並びの中で、marker（文字）が始まる語の番号"""
    if marker is None:
        return None
    cat, starts = "", []
    for w in words:
        starts.append(len(cat))
        cat += norm(w[2])
    k = cat.find(norm(marker))
    if k < 0:
        return None
    return max(i for i, s in enumerate(starts) if s <= k)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ver", required=True)
    ap.add_argument("--cuts")
    ap.add_argument("--captions")
    ap.add_argument("--script")
    ap.add_argument("--units")
    ap.add_argument("--env")
    ap.add_argument("--min", type=float, default=0.06, help="声として数える長さ（秒。既定 0.06＝2フレーム）")
    ap.add_argument("--over", type=float, default=6.0, help="声のしきい値より何 dB 大きい所を声とするか（既定 6）")
    ap.add_argument("--match", type=float, default=0.34, help="⑥：まとまりの文字のうち、字幕の文字に合う割合がこれ未満なら出す（既定 0.34）")
    ap.add_argument("--out")
    a = ap.parse_args()
    V = os.path.abspath(os.path.expanduser(a.ver))
    tag = os.path.basename(V)
    E = os.path.dirname(V)
    cuts = json.load(open(a.cuts or os.path.join(V, "_work", f"cuts_{tag}.json"), encoding="utf-8"))
    caps = json.load(open(a.captions or os.path.join(V, "_work", f"captions_{tag}.json"), encoding="utf-8"))["captions"]
    script_cuts, notes = load_script(a.script or os.path.join(V, f"script_{tag}.txt"))
    units = {u["u"]: u for u in json.load(open(a.units or os.path.join(E, "analysis", "units.json"), encoding="utf-8"))}
    env = np.load(a.env or os.path.join(E, "analysis", "camera_env.npy"))
    thr = cuts["params"]["voice_thr_db"] + a.over
    out = a.out or os.path.join(V, "_work", f"stray_words_{tag}")

    # 残した区間（素材の秒）と、タイムラインの秒への対応
    keep, tl0 = [], cuts.get("highlight_external_frames", 0)
    for f0, f1 in cuts["keep_frames"]:
        keep.append((f0 / FPS, f1 / FPS, tl0 / FPS))
        tl0 += f1 - f0
    ks = sorted(keep)
    kstart = [k[0] for k in ks]

    def kept_voice(s, e):
        """素材の [s, e) のうち、残していて声のある秒と、その頭のタイムラインの秒"""
        i = max(0, bisect.bisect_right(kstart, s) - 1)
        tot, first = 0.0, None
        for k0, k1, t in ks[i:]:
            if k0 >= e:
                break
            lo, hi = max(s, k0), min(e, k1)
            if hi <= lo:
                continue
            seg = env[int(lo * 100):int(hi * 100)]
            n = float((seg > thr).sum()) * 0.01
            if n > 0 and first is None:
                first = t + (lo - k0)
            tot += n
        return tot, first

    # ⑦ 切ると決めた区切りの語
    cut_words = set()
    seven = []
    for c in script_cuts:
        (ua, wa), (ub, wb) = c["a"], c["b"]
        for u in range(ua, ub + 1):
            if u not in units:
                continue
            ws = units[u]["words"]
            i0 = word_index(ws, wa) if (u == ua and wa) else 0
            i1 = word_index(ws, wb) if (u == ub and wb) else len(ws)
            if i0 is None:
                i0 = 0
            if i1 is None:
                i1 = len(ws)
            for k in range(i0, i1):
                s, e, w = ws[k]
                cut_words.add((u, k))
                if e - s < 0.04 or skip_filler(w):
                    continue
                v, t = kept_voice(s + 0.02, e - 0.02)
                if v >= a.min:
                    seven.append(dict(tl=t, src=s, u=u, w=w, sec=round(v, 2), why=c["why"][:60], line=c["line"]))

    # ⑥ 字幕に無い言葉：字幕の頭ではない所（前の字幕を出したまま続く声）の語のまとまりが、その字幕の文字にほとんど無い
    #   区切りを「字幕の頭（start・mid の語）」で分け、頭で始まらないまとまり＝前の字幕に乗っている声だけを見る（字幕の頭の言い換えは見ない）
    shown = sorted([c for c in caps if c.get("src") is not None], key=lambda c: c["src"])
    cap_src = [c["src"] for c in shown]
    heads = {}                                         # 区切り u → 字幕が始まる語の番号の集まり
    for c in caps:
        u = c.get("u")
        if u not in units or c.get("mode") == "drop":
            continue
        ws = units[u]["words"]
        k = word_index(ws, c.get("anchor")) if c.get("mode") == "mid" else 0
        heads.setdefault(u, set()).add(k or 0)
    drops = {c["u"] for c in caps if c.get("mode") == "drop"}
    six = []
    for u, U in units.items():
        ws = U["words"]
        if not ws:
            continue
        hs = sorted(heads.get(u, set()))
        bounds = sorted(set([0] + hs + [len(ws)]))
        for p, q in zip(bounds, bounds[1:]):
            if p in hs:
                continue                               # 字幕の頭から始まるまとまり（字幕の文字そのもの）
            piece = [(k, ws[k]) for k in range(p, q) if (u, k) not in cut_words and not skip_filler(ws[k][2])]
            if not piece:
                continue
            s, e = piece[0][1][0], piece[-1][1][1]
            v, tt = kept_voice(s + 0.02, e - 0.02)
            if v < a.min:
                continue
            i = bisect.bisect_right(cap_src, (s + e) / 2) - 1
            if i < 0:
                continue
            c = shown[i]
            pt = "".join(norm(w[2]) for _, w in piece)
            ct = norm(c["text"])
            m = sum(blk.size for blk in difflib.SequenceMatcher(None, pt, ct, autojunk=False).get_matching_blocks())
            ratio = m / max(1, len(pt))
            if ratio >= a.match:
                continue
            # 決めてある：文字を出さない行（u-）か、その字幕・同じ区切りの字幕の行のメモにこの語を書いてある
            note = " ".join(notes.get(x.get("line"), "") for x in caps if x is c or x.get("u") == u)
            words = "".join(w[2] for _, w in piece)
            decided = (u in drops) or (bool(note) and pt and pt in norm(note))
            six.append(dict(tl=tt, src=s, u=u, w=words, sec=round(v, 2), cap=c["id"], text=c["text"].replace("\r", "／"),
                            decided=decided, ratio=round(ratio, 2)))

    six_n = [x for x in six if not x["decided"]]
    L = [f"# 字幕に無い言葉・切ると決めた言葉の端（{tag}）", "",
         f"声：camera_env の {thr:.1f}dB（AI の版の声のしきい値 {cuts['params']['voice_thr_db']:.1f}dB ＋{a.over:.0f}dB）を超える所が {a.min:.2f}秒以上。"
         "**全部未聴取**（大きさと文字起こしで見ただけ）", "",
         f"- ⑦ 切ると決めた言葉の端が残っている：{len(seven)}件", f"- ⑥ 字幕に無い言葉の声：{len(six_n)}件（台本のメモで決めてある物 {len(six) - len(six_n)}件は数えない）", "",
         "## ⑦ 切ると決めた言葉の端", "", "| 版の時刻 | 素材の秒 | 区切り | 語 | 残っている声 | 台本の切る行 |", "|---|---|---|---|---|---|"]
    L += [f"| {ff(x['tl'])} | {x['src']:.2f} | {x['u']} | {x['w']} | {x['sec']:.2f}秒 | {x['line']}行：{x['why']} |"
          for x in sorted(seven, key=lambda x: x["tl"] or 0)]
    L += ["", "## ⑥ 字幕に無い言葉", "", "| 版の時刻 | 素材の秒 | 区切り | 語 | 声 | その時の字幕 |", "|---|---|---|---|---|---|"]
    L += [f"| {ff(x['tl'])} | {x['src']:.2f} | {x['u']} | {x['w']} | {x['sec']:.2f}秒 | {x['cap']}「{x['text'][:30]}」{'（決めてある）' if x['decided'] else ''} |"
          for x in sorted(six, key=lambda x: x["tl"] or 0)]
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    open(out + ".md", "w", encoding="utf-8").write("\n".join(L) + "\n")
    with open(out + ".tsv", "w", encoding="utf-8") as f:
        f.write("種類\t版の時刻\t素材の秒\t区切り\t語\t声の秒\t字幕か切る行\n")
        for x in seven:
            f.write(f"⑦\t{ff(x['tl'])}\t{x['src']:.2f}\t{x['u']}\t{x['w']}\t{x['sec']}\t{x['line']}行 {x['why']}\n")
        for x in six:
            f.write(f"⑥{'（決めてある）' if x['decided'] else ''}\t{ff(x['tl'])}\t{x['src']:.2f}\t{x['u']}\t{x['w']}\t{x['sec']}\t{x['cap']} {x['text']}\n")
    print(f"⑦ 切ると決めた言葉の端 {len(seven)}件・⑥ 字幕に無い言葉 {len(six_n)}件（決めてある {len(six) - len(six_n)}件）→ {out}.md")
    sys.exit(1 if (seven or six_n) else 0)


if __name__ == "__main__":
    main()
