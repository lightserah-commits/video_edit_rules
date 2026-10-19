"""台本の1つの塊（script_parts/pNN.txt）の書き方を確かめる（台本係・検査係が書いた後に自分で流す）。
  ~/Desktop/video_edit_rules/env/bin/python v004/_work/check_part.py v004/script_parts/p02.txt 700 1400
  見ること：書き方が読める・区切りが全部どこかに入っている（字幕・カット・「u-」）・「u+語」「u/語」の語が区切りの文字起こしに入っている・
            1行17字・3行なし・句読点なし・番号順・カットの中の区切りに字幕が無い・頭を切った区切りを「u|」で書いていない
  エラー（E）が0になるまで直す。注意（W）は読んで決める。
"""
import os
import re
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE)))
from common import Script, load_units, norm, width  # noqa: E402

path, a, b = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
units = load_units()
ids = [u for u in sorted(units) if a <= u <= b]
try:
    sc = Script(path)
except Exception as e:  # noqa: BLE001
    print("E 台本が読めない：", repr(e))
    sys.exit(1)
errors, warns = [], []

# カットで丸ごと消える区切り・頭が切られる・後ろが切られる
full, head_cut, tail_cut = set(), {}, {}
for c in sc.cuts:
    (ua, wa), (ub, wb) = c["a"], c["b"]
    if ua not in units or ub not in units:
        errors.append(f"行{c['line']}：カットの区切り {ua}〜{ub} が units に無い")
        continue
    for u, w in ((ua, wa), (ub, wb)):
        if w is not None and norm(w) not in norm(units[u]["text"]):
            errors.append(f"行{c['line']}：カットの語「{w}」が区切り{u}「{units[u]['text']}」に含まれない")
    if wa is not None:
        tail_cut[ua] = wa
    if wb is not None:
        head_cut[ub] = wb
    lo = ua + (1 if wa is not None else 0)
    hi = ub - (1 if wb is not None else 0)
    for u in ids:
        if lo <= u <= hi:
            full.add(u)
starts = {c["u"]: c for c in sc.captions if c["mode"] == "start"}
drops = {c["u"] for c in sc.captions if c["mode"] == "drop"}
mids = defaultdict(list)
for c in sc.captions:
    if c["mode"] == "mid":
        mids[c["u"]].append(c)
last_u = -1
for c in sc.captions:
    u = c["u"]
    if not (a <= u <= b):
        errors.append(f"行{c['line']}：区切り{u}は担当（{a}〜{b}）の外")
        continue
    if u < last_u:
        errors.append(f"行{c['line']}：番号順になっていない（{u} の前に {last_u}）")
    last_u = max(last_u, u)
    if u in full:
        errors.append(f"行{c['line']}：字幕 {c['id']} の区切り{u}はカットの中")
    if c["mode"] == "start" and u in head_cut:
        errors.append(f"行{c['line']}：区切り{u}は頭が切られているので「{u}+|」で書く")
    if c["mode"] == "mid" and c["anchor"]:
        if norm(c["anchor"]) not in norm(units[u]["text"]):
            errors.append(f"行{c['line']}：「{u}+{c['anchor']}」の語が区切り{u}「{units[u]['text']}」に含まれない")
    if c["mode"] != "drop":
        lines = c["text"].split("\r")
        if len(lines) > 2:
            errors.append(f"行{c['line']}：3行以上「{c['text']}」")
        for ln in lines:
            if width(ln) > 17:
                errors.append(f"行{c['line']}：1行が17字を超える（{width(ln):.1f}字）「{ln}」")
        if re.search(r"[、。，．]", c["text"]):
            errors.append(f"行{c['line']}：句読点「{c['text']}」")
        if re.search(r"(^|[\s\r])(えー|えっと|あのー|まあ|うーん)", c["text"]):
            warns.append(f"行{c['line']}：フィラーが残っている？「{c['text']}」")
# どの字幕にも入っていない区切り
cur = None
for u in ids:
    if u in full:
        cur = None if (u + 1 in starts or u + 1 in full) else cur
        continue
    if u in starts:
        cur = starts[u]
    elif u in head_cut and mids.get(u):
        cur = mids[u][0]
    elif cur is None and u not in drops:
        errors.append(f"区切り{u}「{units[u]['text']}」がどの字幕にも入っていない（カットの後の頭に字幕が無い）")
    if mids.get(u):
        cur = mids[u][-1]
n_cap = sum(1 for c in sc.captions if c["mode"] != "drop")
print(f"字幕 {n_cap}枚／カット {len(sc.cuts)}か所（丸ごと消える区切り {len(full)}／{len(ids)}）")
print(f"エラー {len(errors)}")
for e in errors[:80]:
    print("  E", e)
print(f"注意 {len(warns)}")
for w in warns[:40]:
    print("  W", w)
sys.exit(1 if errors else 0)
