"""v002：※の説明を、仕分けの結果（_work/notes_decisions_v004.json）どおりに plan_parts/dNN_NOTES.txt へ反映する。
外すものは行の頭に「# v002：外した（理由）」を付けてコメントにし、残すものは文言を直す（意味は変えない）。
2026-10-04 小川さん「dots で言ったことを元に」＝dots v003「専門用語の解説は丁寧すぎる」（01 の手順3：本当に止まる言葉だけ）。
  python3 v004/_work/apply_notes_v004.py"""
import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
V = os.path.dirname(HERE)
dec = {d["id"]: d for d in json.load(open(os.path.join(HERE, "notes_decisions_v004.json"), encoding="utf-8"))}
seen = set()
for p in sorted(glob.glob(os.path.join(V, "plan_parts", "d*_NOTES.txt"))):
    out = []
    for ln in open(p, encoding="utf-8").read().splitlines():
        if not ln.strip() or ln.startswith("#"):
            out.append(ln)
            continue
        cols = ln.split("|")
        i = cols[0]
        d = dec.get(i)
        if d is None:
            raise SystemExit(f"{os.path.basename(p)} の {i} の判定が無い")
        seen.add(i)
        if d["keep"]:
            if d.get("text") and d["text"].replace("\\r", "\r") != cols[1].replace("\\r", "\r"):
                out.append(f"# v002：文言を縮めた（前は「{cols[1]}」）")
                cols[1] = d["text"].replace("\r", "\\r")
            out.append("|".join(cols))
        else:
            out.append(f"# v002：外した（{d['reason'][:120].replace(chr(10), ' ')}）")
            out.append("# " + ln)
    open(p, "w", encoding="utf-8").write("\n".join(out) + "\n")
missing = set(dec) - seen
print("残す", sum(d["keep"] for d in dec.values()), "外す", sum(not d["keep"] for d in dec.values()), "表に無い判定", sorted(missing))
