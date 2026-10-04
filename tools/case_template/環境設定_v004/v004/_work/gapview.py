"""装飾が空いた区間の字幕を並べる（テンポの見直し用）。python3 _work/gapview.py 6:18 6:41 [8:49 9:33 …]"""
import json, os, sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import plan_v004 as p
FPS = 30000 / 1001
mp = json.load(open(os.path.join(HERE, "_work", "base_v004_map.json"), encoding="utf-8"))
cap = json.load(open(os.path.join(HERE, "_work", "captions_v004.json"), encoding="utf-8"))["captions"]
ctl = mp["caption_tl"]
deco = {e["id"]: "強" + e["pattern"] for e in p.emphasis()}
deco.update({x["id"]: "SE" for x in p.se_only()})
for x in p.plates():
    for k, _ in x["items"]:
        deco[k] = "問い"
def sec(s):
    m, t = s.split(":"); return int(m) * 60 + float(t)
args = sys.argv[1:]
for a, b in zip(args[::2], args[1::2]):
    print("==", a, b)
    for c in cap:
        f = ctl.get(c["id"])
        if f is None: continue
        t = f / FPS
        if sec(a) - 3 <= t <= sec(b) + 1:
            print(f"  {int(t//60)}:{t%60:05.2f} {c['id']:>7} {c['who']} {deco.get(c['id'],''):5} {c['text'].replace(chr(13),'／')}")
