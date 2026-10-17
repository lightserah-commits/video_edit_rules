"""v005 G1・G3 の続き（2:35 より後。Q1「残りにも当てはめてよいか」の答えが来たら EXTRA_CUTS に足す案）。2026-10-17 メインの AI
_work/laugh_gaps_v005.tsv の候補から、決まりで切る区間を決めて _work/g1_after_235_draft.tsv に書く（cuts_plan には入れない）。
  決まり：08 cut.pauses（0.5秒以上の間は詰める）・keep_as_tame（オチ・言い切りの強調の前は 0.5秒まで残す）・after_punchline（オチの後は 0.4秒残す）
          keep_face（顔や手で演じている所は一番出ている所を 1.5秒ほど残す。コマは analysis/レビュー_v003_20261017/gap_frames/sheet.jpg）
  ~/Desktop/video_edit_rules/env/bin/python v005/_work/g1_after_235_draft.py
"""
import csv, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
V = os.path.dirname(HERE)
FROM_TL = 2 * 60 + 30.0          # v005 の 2:30 より後（v003 の 2:35 あたり。前は当てはめ済み）
PUNCH = {"P03", "P04", "P06", "P07"}   # オチ・ツッコミ・格言（前は溜め、後は 0.4秒）
MANUAL = {   # コマを見て決めた長い間（素材の秒）
    263.01: ((263.02, 264.62), "三上さんが体を折って大笑い（コマ）。次の「連絡めっちゃ来る」の前に 0.4秒だけ残す"),
    565.97: ((566.00, 567.30), "手で形を見せて説明している（keep_face）。後ろの 1.55秒（567.30〜568.85）を残す"),
    992.87: ((993.27, 995.41), "オチ「創太くんがもう払ってんだから」の後は 0.4秒残す（after_punchline）"),
    225.59: (None, "問いの札（v005 2:26 ごろ「サイバー攻撃が普通に不安すぎるので…」）を読む間＝残す"),
    1379.83: (None, "最後の挨拶「それでは」と手を振る所（08 の keep。KEEP_WHOLE）＝残す"),
}


def tsec(s):
    m, x = s.split(":")
    return int(m) * 60 + float(x)


def main():
    caps = {c["id"]: c for c in json.load(open(os.path.join(HERE, "captions_v005.json")))["captions"] if "src" in c}
    emph = []   # (素材の秒, パターン, 文)
    for fn in sorted(os.listdir(os.path.join(V, "plan_parts"))):
        if not fn.endswith("_EMPHASIS.txt"):
            continue
        for ln in open(os.path.join(V, "plan_parts", fn), encoding="utf-8"):
            if ln.startswith("#") or "|" not in ln:
                continue
            p = ln.rstrip("\n").split("|")
            if p[0] in caps:
                emph.append((caps[p[0]]["src"], p[1], p[6]))
    rows = list(csv.reader(open(os.path.join(HERE, "laugh_gaps_v005.tsv"), encoding="utf-8"), delimiter="\t"))[1:]
    out = []
    for r in rows:
        tl = tsec(r[0])
        if tl < FROM_TL:
            continue
        g0, g1 = map(float, r[2].split("-"))
        c0, c1 = map(float, re.findall(r"[\d.]+", r[3]))
        why = ""
        if g0 in MANUAL:
            cut, why = MANUAL[g0]
        else:
            nxt = [e for e in emph if 0 <= e[0] - g1 <= 0.4 and e[1] in PUNCH]
            prv = [e for e in emph if 0 <= g0 - e[0] <= 4.0 and e[1] in PUNCH]
            cut = (c0, c1)
            if nxt:
                cut = (c0, max(c0, c1 - 0.5)) if c1 - c0 > 0.8 else None
                why = f"次がオチ・言い切りの強調「{nxt[0][2]}」（{nxt[0][1]}）→ 溜め 0.5秒を残す"
            elif prv:
                cut = (c0 + 0.4, c1) if c1 - c0 > 0.6 else None
                why = f"オチ「{prv[0][2]}」（{prv[0][1]}）の後 → 0.4秒残す"
            else:
                why = "言葉の無い間（笑い・息）→ 詰める" if int(r[4].rstrip("%")) >= 50 else "言葉の無い間（小さい音）→ 詰める（08 の 0.5秒）"
            if cut and cut[1] - cut[0] < 0.2:
                cut, why = None, why + "（切る長さが 0.2秒未満なので残す）"
        out.append((r[0], r[1], r[2], f"({cut[0]:.2f}, {cut[1]:.2f})" if cut else "残す", r[4], r[6], r[7], why))
    path = os.path.join(HERE, "g1_after_235_draft.tsv")
    with open(path, "w", encoding="utf-8") as f:
        f.write("v005の時刻\t長さ\t素材の秒\t切る(素材)\t音\t字幕\t字幕の文字\t理由\n")
        for o in out:
            f.write("\t".join(o) + "\n")
    cuts = [o for o in out if o[3] != "残す"]
    tot = sum(float(o[3].strip("()").split(",")[1]) - float(o[3].strip("()").split(",")[0]) for o in cuts)
    print(f"2:30 より後の候補 {len(out)}・切る案 {len(cuts)}（計 {tot:.1f}秒）・残す {len(out) - len(cuts)} → {path}")


if __name__ == "__main__":
    main()
