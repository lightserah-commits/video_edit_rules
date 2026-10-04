"""カットの一覧に「前の一文 → 後の一文」を足す（08 の no_chop.flow。ユーザーも読んで確かめられるように）。
  中身のカット（台本の x）ごとに、切った所の直前に残した字幕と直後に残した字幕を並べる → カット一覧_v004.csv を作り直す
  python3 v004/_work/cut_flow.py"""
import csv, json, os, sys, bisect
HERE = os.path.dirname(os.path.abspath(__file__))
V = os.path.dirname(HERE)
sys.path.insert(0, V)
FPS = 30000 / 1001
cj = json.load(open(os.path.join(HERE, "cuts_v004.json")))
capj = json.load(open(os.path.join(HERE, "captions_v004.json")))
caps = sorted([c for c in capj["captions"] if c["mode"] != "drop" and "src" in c], key=lambda c: c["src"])
src = [c["src"] for c in caps]
rows = list(csv.reader(open(os.path.join(V, "カット一覧_v004.csv"), encoding="utf-8-sig")))
head, body = rows[0], rows[1:]
out = [head + ["前に残した字幕", "後に残した字幕"]]
def sec(t):
    m, s = t.split(":"); return int(m) * 60 + float(s)
for r in body:
    a, b = sec(r[1]), sec(r[2])
    i = bisect.bisect_left(src, a) - 1
    j = bisect.bisect_left(src, b - 0.05)
    prev = caps[i]["text"].replace("\r", "") if i >= 0 else ""
    nxt = caps[j]["text"].replace("\r", "") if j < len(caps) else ""
    out.append(r + [prev, nxt])
with open(os.path.join(V, "カット一覧_v004.csv"), "w", encoding="utf-8-sig", newline="") as f:
    csv.writer(f).writerows(out)
for r in out[1:]:
    if "中身" in r[4]:
        print(f"{r[0]} {r[3]}秒 | {r[-2]} → {r[-1]} | {r[7][:50]}")
