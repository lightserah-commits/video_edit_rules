"""つなぎ目の一覧（タイムラインの順）：残す区間と次の残す区間のつなぎ目ごとに、前に残した字幕 → 後に残した字幕と、切った中身・理由を並べる。
  並べ替え（A→X→Y→Z）のつなぎ目も入る。08 の no_chop.flow の「切った後のつなぎ目を読んで確かめる」に使う。
  出力 _work/joins_v004.tsv（v001の時刻・素材の切った範囲・秒・前の字幕・後の字幕・切った中身・理由）
  python3 v004/_work/joins.py [--min 0.0]（切った秒がこれ以上のつなぎ目だけ）"""
import bisect, csv, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
V = os.path.dirname(HERE)
E = os.path.dirname(V)
FPS = 30000 / 1001
mn = float(sys.argv[sys.argv.index("--min") + 1]) if "--min" in sys.argv else 0.0
cj = json.load(open(os.path.join(HERE, "cuts_v004.json")))
capj = json.load(open(os.path.join(HERE, "captions_v004.json")))
units = {u["u"]: u for u in json.load(open(os.path.join(E, "analysis", "units.json")))}
caps = sorted([c for c in capj["captions"] if c["mode"] != "drop" and "src" in c], key=lambda c: c["src"])
src = [c["src"] for c in caps]
rows = {}
for r in list(csv.reader(open(os.path.join(V, "カット一覧_v004.csv"), encoding="utf-8-sig")))[1:]:
    rows[r[1]] = r


def mmss(t):
    return f"{int(t // 60)}:{t % 60:05.2f}"


def cap_before(f):
    i = bisect.bisect_right(src, f / FPS - 0.02) - 1
    return caps[i] if i >= 0 else None


def cap_after(f):
    j = bisect.bisect_left(src, f / FPS - 0.02)
    return caps[j] if j < len(caps) else None


def said(a, b):
    """素材の秒 a〜b の文字起こし（語が半分以上入っているもの）"""
    out = []
    for u in units.values():
        if u["end"] < a or u["start"] > b:
            continue
        out.append("".join(w for ws, we, w in u["words"] if (ws + we) / 2 >= a and (ws + we) / 2 < b))
    return "".join(out)


keep = cj["keep_frames"]
tl = sum(b - a for a, b in cj["highlight_frames"]) + cj.get("highlight_external_frames", 0)
out = []
for k in range(len(keep) - 1):
    a0, b0 = keep[k]
    a1, b1 = keep[k + 1]
    tl += b0 - a0
    if b0 == a1:
        continue
    moved = a1 < b0
    L = (a1 - b0) / FPS
    if not moved and L < mn:
        continue
    p, n = cap_before(b0), cap_after(a1)
    r = rows.get(mmss(b0 / FPS))
    why = r[7] if r else ("並べ替え" if moved else "")
    cut_txt = "" if moved else said(b0 / FPS, a1 / FPS)
    out.append([mmss(tl / FPS), f"{mmss(b0 / FPS)}→{mmss(a1 / FPS)}", "並べ替え" if moved else f"{L:.2f}",
                (p["id"] + " " + p["text"].replace("\r", "")) if p else "", (n["id"] + " " + n["text"].replace("\r", "")) if n else "",
                cut_txt[:200], why])
with open(os.path.join(HERE, "joins_v004.tsv"), "w", encoding="utf-8") as f:
    f.write("v004の時刻\t素材\t切った秒\t前の字幕\t後の字幕\t切った中身\t理由\n")
    for r in out:
        f.write("\t".join(r) + "\n")
print(f"つなぎ目 {len(out)}（並べ替え {sum(1 for r in out if r[2] == '並べ替え')}）→ _work/joins_v004.tsv")
