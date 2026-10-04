"""plan_parts の表を読んで、書き方の誤りを探す（字幕ID が実在するか・まとめる最後の字幕が後ろにあるか・SE の名前・パターン・項目の数・区間の重なり）。
  python3 v004/_work/check_plan.py"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
V = os.path.dirname(HERE)
sys.path.insert(0, V)
import plan_v004 as plan
cj = json.load(open(os.path.join(HERE, "cuts_v004.json")))
capj = json.load(open(os.path.join(HERE, "captions_v004.json")))
caps = [c for c in capj["captions"] if c["mode"] != "drop" and "src" in c]
ctl = cj["caption_tl"]
order = [c["id"] for c in sorted(caps, key=lambda c: ctl[c["id"]])]
pos = {k: i for i, k in enumerate(order)}
err, warn = [], []


def chk(i, where):
    if i not in pos:
        err.append(f"{where}：字幕ID {i!r} が無い")
        return False
    return True


def rng(a, b, where):
    if chk(a, where) and chk(b, where) and pos[b] < pos[a]:
        err.append(f"{where}：{a}〜{b} が逆（タイムラインの順で {b} が前）")


for a, b, lab, why in plan.SCREEN:
    rng(a, b, f"SCREEN {a}")
for t in plan.TAME:
    chk(t, "TAME")
used = {}
try:
    emp = plan.emphasis()
except Exception as e:
    err.append(f"EMPHASIS の読み込み：{e!r}")
    emp = []
for e in emp:
    rng(e["id"], e["until"], f"EMPHASIS {e['id']}")
    if e["kind"] not in ("意味", "感情"):
        err.append(f"EMPHASIS {e['id']}：種類 {e['kind']!r}")
    if not e["text_fix"]:
        err.append(f"EMPHASIS {e['id']}：文が無い")
    if e["text_fix"].replace("Claude Code", "ClaudeCode").replace("Sonnet 5.5", "x").replace("6.1 Sol", "x").count(" ") > 1:
        warn.append(f"EMPHASIS {e['id']}：半角の空白が2つ以上（改行は1か所）「{e['text_fix']}」")
    if e["id"] in pos:
        for k in order[pos[e["id"]]:pos.get(e["until"], pos[e["id"]]) + 1]:
            if k in used:
                err.append(f"字幕{k} が2つの演出に使われている（{used[k]} と EMPHASIS {e['id']}）")
            used[k] = f"EMPHASIS {e['id']}"
for f, n in (("se_only", "SE_ONLY"), ("chapters", "CHAPTERS"), ("boards", "BOARDS"), ("plates", "PLATES"), ("diagrams", "DIAGRAMS"),
             ("roleplay", "ROLEPLAY"), ("notes", "NOTES")):
    try:
        items = getattr(plan, f)()
    except Exception as e:
        err.append(f"{n} の読み込み：{e!r}")
        continue
    for x in items:
        if n == "SE_ONLY":
            chk(x["id"], n)
        elif n == "NOTES":
            chk(x["id"], n)
        elif n == "CHAPTERS":
            rng(x["num_id"], x["end"], n); chk(x["item_id"], n)
            for k in order[pos.get(x["num_id"], 0):pos.get(x["end"], -1) + 1]:
                if k in used: err.append(f"字幕{k} が2つの演出（{used[k]} と 章 {x['num_id']}）")
                used[k] = f"章 {x['num_id']}"
        elif n == "BOARDS":
            rng(x["from"], x["to"], f"{n} {x['from']}")
            for k in order[pos.get(x["from"], 0):pos.get(x["to"], -1) + 1]:
                if k in used: err.append(f"字幕{k} が2つの演出（{used[k]} と ボード {x['from']}）")
                used[k] = f"ボード {x['from']}"
        elif n == "PLATES":
            if x["kind"] not in ("問い", "並列", "並列画像"):   # v003：並列画像＝公式のロゴの札（zukai/L1）
                err.append(f"PLATES：種類 {x['kind']!r}")
            for key, text in x["items"]:
                chk(key, f"PLATES {key}")
            if x["items"]:
                rng(x["items"][0][0], x["end"], f"PLATES {x['items'][0][0]}")
            if x["kind"] == "問い":
                if len(x["items"]) != 1: err.append(f"問い {x['items'][0][0]}：項目は1つ")
                t = x["items"][0][1]
                if not t.startswith("Q:"): warn.append(f"問い {x['items'][0][0]}：Q: で始まっていない")
                if t.count("／") > 1: err.append(f"問い {x['items'][0][0]}：3行")
                for k in order[pos.get(x["items"][0][0], 0):pos.get(x["end"], -1) + 1]:
                    if k in used: err.append(f"字幕{k} が2つの演出（{used[k]} と 問い {x['items'][0][0]}）")
                    used[k] = f"問い {x['items'][0][0]}"
            elif len(x["items"]) > 3:
                err.append(f"並列 {x['items'][0][0]}：項目が4つ以上")
        elif n == "DIAGRAMS":
            chk(x["head_id"], n); chk(x["end"], n)
            if len(x["items"]) > 3: err.append(f"図解 {x['head_id']}：項目が4つ以上")
            for key, text in x["items"]:
                chk(key, f"図解 {x['head_id']}")
        elif n == "ROLEPLAY":
            for key, text, band in x["lines"]:
                chk(key, "ROLEPLAY")
                if key in used: err.append(f"字幕{key} が2つの演出（{used[key]} と 代弁）")
                used[key] = "代弁"
for i, t in plan.topics():
    chk(i, "TOPICS")
    if len(t) > 13: warn.append(f"話題タイトル {i}「{t}」が長い（{len(t)}字）")
print(f"エラー {len(err)}")
for x in err: print("  E", x)
print(f"注意 {len(warn)}")
for x in warn: print("  W", x)
print({"SCREEN": len(plan.SCREEN), "TAME": len(plan.TAME), "EMPHASIS": len(emp), "SE_ONLY": len(plan.se_only()), "NOTES": len(plan.notes()),
       "PLATES": len(plan.plates()), "BOARDS": len(plan.boards()), "DIAGRAMS": len(plan.diagrams()), "TOPICS": len(plan.topics()),
       "CHAPTERS": len(plan.chapters()), "ROLEPLAY": len(plan.roleplay())})
