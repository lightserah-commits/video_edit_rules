#!/usr/bin/env python3
"""近くで同じ話をくり返している所の候補を出す（読むだけ）。決まりは 08 の cut.remove「同じ話のくり返し（重複）」。

使い方:
  python3 tools/find_repeats.py 版.prproj --seq シーケンス名 --track V6 [--window 180] [--out repeats.tsv]
    --track   通常字幕の段（02 の output_tracks。話者ごとに段が分かれていれば V6,V7 のように並べる）
    --window  何秒以内を「近く」と見るか（既定 180秒）
出力（2つの見方）:
  ① 同じ言葉が続く：動画全体ではあまり出ない言葉（全字幕の5%未満）が、60秒以内に3回以上出る所（例 astra の「パワープレイ」）
  ② 文が似ている：口癖と語尾（じゃないですか・じゃん・です など）を外して8文字以上残る字幕どうしで、7割以上同じか、10文字以上続けて同じもの
  塊ごとに時刻と字幕を並べる。塊の中で一番伝わる1回（一番具体的な1回か、最後の言い切り）を残し、ほかを切る候補にする。
  文字で拾うだけなので、言い方をすっかり変えたくり返しは拾えない。字幕を見る順に読む検査（flow_table.py）とあわせて使う。
"""
import argparse
import difflib
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dump_timeline import dump  # noqa: E402

FILLER = re.compile(r"(なんか|まあ|ちょっと|やっぱり?|とか|みたいな|っていう|って|ほんまに|ほんとに|本当に|マジで|いや|もう|結構|めっちゃ|めちゃくちゃ|ね|よ|な|さ|わ)")
PUNCT = re.compile(r"[\s\r　、。！!？?…「」『』（）()・/／〜~ｗw]")
ENDING = re.compile(r"(じゃないですか|じゃないですかね|ですか|ですね|です|ます|ません|じゃん|やん|って感じ|わけ|よね|のよ|けど|から|だね|だよ|かな|でしょ|っす)+$")
WORD = re.compile(r"[ァ-ヴー]{3,}|[一-龥々]{2,}|[A-Za-z0-9]{3,}")


def key(t):
    return ENDING.sub("", FILLER.sub("", PUNCT.sub("", t)))


def groups_of(link):
    seen = set(); out = []
    for i in range(len(link)):
        if i in seen or not link[i]:
            continue
        st = [i]; g = []
        while st:
            k = st.pop()
            if k in seen:
                continue
            seen.add(k); g.append(k); st += link[k]
        out.append(sorted(g))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("prproj"); ap.add_argument("--seq", required=True); ap.add_argument("--track", required=True)
    ap.add_argument("--window", type=float, default=180); ap.add_argument("--out")
    a = ap.parse_args()
    tl = dump(a.prproj, a.seq); fps = tl["fps"]
    caps = []
    for tr in a.track.split(","):
        for r in tl["tracks"].get(tr, []):
            t = "".join(r.get("texts") or []).replace("\r", "")
            if r["muted"] or not t.strip():
                continue
            caps.append((r["start_f"] / fps, t, key(t)))
    caps.sort()
    n = len(caps)
    fmt = lambda t: f"{int(t // 60):02d}:{t % 60:05.2f}"
    # ① 同じ言葉が続く
    from collections import Counter
    words = [set(WORD.findall(c[1])) for c in caps]
    freq = Counter(w for ws in words for w in ws)
    rare = {w for w, k in freq.items() if k >= 3 and k < .05 * n}
    link1 = [[] for _ in range(n)]
    for w in rare:
        idx = [i for i in range(n) if w in words[i]]
        for x in range(len(idx) - 2):
            if caps[idx[x + 2]][0] - caps[idx[x]][0] <= 60:
                for i in idx[x:x + 3]:
                    for j in idx[x:x + 3]:
                        if i != j and j not in link1[i]:
                            link1[i].append(j)
    # ② 文が似ている
    link2 = [[] for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            if caps[j][0] - caps[i][0] > a.window:
                break
            ki, kj = caps[i][2], caps[j][2]
            if len(ki) < 8 or len(kj) < 8:
                continue
            sm = difflib.SequenceMatcher(None, ki, kj)
            if sm.ratio() >= .7 or sm.find_longest_match(0, len(ki), 0, len(kj)).size >= 10:
                link2[i].append(j); link2[j].append(i)
    lines = []
    for title, link in (("① 同じ言葉が続く", link1), ("② 文が似ている", link2)):
        gs = groups_of(link)
        lines.append(f"# {title}：{len(gs)}か所")
        for g in gs:
            common = set.intersection(*(words[k] for k in g)) if title.startswith("①") else set()
            lines.append(f"## {fmt(caps[g[0]][0])}〜{fmt(caps[g[-1]][0])}（{len(g)}枚）{'「' + '・'.join(sorted(common)) + '」' if common else ''}")
            for k in g:
                lines.append(f"{fmt(caps[k][0])}\t{caps[k][1]}")
    out = "\n".join(lines)
    print(out)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(out + "\n")


if __name__ == "__main__":
    main()
