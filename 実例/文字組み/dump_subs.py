import sys, os, json
from collections import Counter
sys.path.insert(0, os.path.expanduser("~/Desktop/video_edit_rules/tools"))
import decoration_report as dr
path, seqname, out = sys.argv[1:4]
_orig = dr.Project.text_of
def _tx(self, pe):
    t, f = _orig(self, pe)
    return [x.replace("\r", "⏎").replace("\n", "⏎") for x in t], f
dr.Project.text_of = _tx
pj = dr.Project(path)
seq = max([s for s in pj.sequences() if s.findtext("Name") == seqname], key=lambda s: sum(len(pj.items(t)) for _, t in pj.tracks(s)))
clips = [c for tn, tr in pj.tracks(seq) for c in (pj.clip(tn, it) for it in pj.items(tr)) if not c["disabled"]]
texts = [c for c in clips if c["track"].startswith("V") and c.get("layers")]
sc = Counter(l["style"] or "(なし:" + ",".join(l["fonts"]) + ")" for c in texts for l in c["layers"])
tot = sum(sc.values()); base = {s for s, n in sc.items() if n >= 0.08 * tot}
def st(c): return [l["style"] or "(なし:" + ",".join(l["fonts"]) + ")" for l in c["layers"]]
subs = sorted([c for c in texts if all(s in base for s in st(c))], key=lambda c: c["start"])
json.dump({"base": sorted(base), "subs": [{"track": c["track"], "start": c["start"], "end": c["end"], "style": st(c), "texts": [l["text"] for l in c["layers"]]} for c in subs]}, open(out, "w"), ensure_ascii=False, indent=0)
print(len(subs))
