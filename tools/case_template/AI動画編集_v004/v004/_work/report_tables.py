"""確認_v004.md の表（言い直した強調・足した説明・問いの札・図解・ボード）を v004_記録.json から作る（工程11）。
  python3 v004/_work/report_tables.py > _work/report_tables.md"""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
V = os.path.dirname(HERE)
r = json.load(open(os.path.join(V, "v004_記録.json"), encoding="utf-8"))


def mmss(s):
    return f"{int(s // 60)}:{s % 60:04.1f}"


def one(t):
    return t.replace("\r", "／").replace("|", "｜")


print("### 言い直した強調テロップ（時刻・種類・型・話した言葉 → 出した文）\n")
print("| 時刻 | 種類 | 型 | 話した言葉 | 出した文 |\n|---|---|---|---|---|")
for t in sorted(r["telops"], key=lambda x: x["start"]):
    src = one(t.get("source", ""))
    if src.replace("／", "").replace(" ", "") == one(t["text"]).replace("／", "").replace(" ", ""):
        continue
    print(f"| {mmss(t['start'])} | {t['kind']} | {t['pattern']} {t['type']} | {src} | {one(t['text'])} |")
print("\n### 足した説明（※の補足・↑の一言。話していない言葉）\n")
print("| 時刻 | 足した言葉 | なぜ |\n|---|---|---|")
for n in sorted(r.get("notes_added", []), key=lambda x: x["start"]):
    print(f"| {mmss(n['start'])} | {one(n['text'])} | {one(n['reason'])[:120]} |")
print("\n### 問いの札（Q:）と並べる座布団\n")
print("| 時刻 | 種類 | 文字 |\n|---|---|---|")
for g in r.get("plates", []):
    print(f"| {mmss(g['items'][0][2])} | {g['kind']} | {' ／ '.join(one(x[1]) for x in g['items'])} |")
print("\n### 図解\n")
print("| 時刻 | 見出し | 札 |\n|---|---|---|")
for d in r.get("diagrams", []):
    print(f"| {mmss(d['start'])}〜{mmss(d['end'])} | {d['head']} | {' ／ '.join(one(x[1]) for x in d['items'])} |")
print("\n### ボード（ポイント・CTA の受け取り方）\n")
print("| 時刻 | 型 | 文字 |\n|---|---|---|")
for b in r.get("boards", []):
    print(f"| {mmss(b['start'])}〜{mmss(b['end'])} | {b['type']} | {one(b['text'])} |")
print("\n### BGM を止めた所\n")
print(", ".join(f"{mmss(a)}〜{mmss(b)}" for a, b in r["bgm"]["stops"]))
