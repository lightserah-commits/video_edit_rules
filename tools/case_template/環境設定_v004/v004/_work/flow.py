"""視聴者が受け取る順（字幕・問い・強調・図解・切った所）に並べた表を作る（v001。音を消して分かるか・前後がつながるかを読む検査の材料）。
  python3 v004/_work/flow.py [終わりの秒] → v004/_work/flow_v004.txt"""
import csv, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
V = os.path.dirname(HERE)
FPS = 30000 / 1001
END = float(sys.argv[1]) if len(sys.argv) > 1 else 1e9
tl = json.load(open(os.path.join(HERE, "cuts_v004.json")))["caption_tl"]
caps = json.load(open(os.path.join(HERE, "captions_v004.json")))["captions"]
ev = []
for c in caps:
    if c["id"] in tl:
        ev.append((tl[c["id"]] / FPS, 1, f"  {'聞' if c['who'] == '聞' else '三'}｜{c['text'].replace(chr(13), '／')}  #{c['id']}"))
for r in csv.DictReader(open(os.path.join(V, "decoration_plan.csv"), encoding="utf-8-sig")):
    try:
        t = float(r["開始秒"])
    except ValueError:
        continue
    p = r["パターンID"]
    if p == "SEのみ":
        continue
    tag = {"P11": "【問い】", "図解": "【図解】", "実演の札": "【札】", "P15": "【ハイライト】"}.get(p, f"【強調{p}・{r['種類']}】")
    ev.append((t, 0, tag + r["文字・内容"]))
for r in csv.DictReader(open(os.path.join(V, "カット一覧_v004.csv"), encoding="utf-8-sig")):
    if r["種類"] != "中身" and "中身" not in r["種類"]:
        continue
    m, s = r["v004の時刻"].split(":")
    ev.append((int(m) * 60 + float(s), 2, f"    ✂{r['切った秒']}秒 {r['大きなカット']} 「{r['切った中身（文字起こし）'][:80]}」"))
ev.sort(key=lambda x: (x[0], x[1]))
with open(os.path.join(HERE, "flow_v004.txt"), "w", encoding="utf-8") as f:
    for t, k, s in ev:
        if t <= END:
            f.write(f"{int(t // 60):02d}:{t % 60:05.2f} {s}\n")
print(sum(1 for e in ev if e[0] <= END))
