"""確認の画像を書き出す時刻（review_jobs.json）を、v004_記録.json から選ぶ（編集の依頼文.md の工程10）。
  v001（素材からの最初の版）から。v002 は動く図解・ディゾルブも足した。、強調・問い・説明・図解・ボード・代弁・赤枠は全部、ほかは代表を選ぶ。各演出の途中（開始から 0.6 秒後か、真ん中）
  python3 v004/_work/review_jobs.py"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
V = os.path.dirname(HERE)
FPS = 30000 / 1001
rec = json.load(open(os.path.join(V, "v004_記録.json"), encoding="utf-8"))
mp = json.load(open(os.path.join(HERE, "base_v004_map.json"), encoding="utf-8"))
cj = json.load(open(os.path.join(HERE, "cuts_v004.json"), encoding="utf-8"))
jobs = []


def tc(sec):
    f = int(round(sec * FPS))
    return f"{f // 108000:02d}:{f // 1800 % 60:02d}:{f // 30 % 60:02d}:{f % 30:02d}"


def add(sec, name):
    m, s = int(sec // 60), sec % 60
    jobs.append([tc(sec), f"{m:02d}{int(s):02d}_{name}", round(sec, 2)])


def mid(a, b, lead=0.6):
    return min(a + lead, (a + b) / 2)


hl = cj.get("highlight_external_frames", 0) / FPS
# v003：冒頭ハイライトを作り直した（H4・H5・H7 を外した。18.9秒）ので、1秒ごとに見る
for t in [0.6, 2.0, 3.5, 5.0, 5.8, 6.4, 7.0, 7.6, 8.5, 9.5, 10.5, 11.5, 12.5, 13.5, 14.5, 15.5, 16.5, 17.5, hl - 0.3]:
    add(t, f"ハイライト_{t:.1f}")
add(hl + 0.1, "挨拶_白から戻る途中")
add(hl + 1.0, "挨拶_後")
for t in rec["telops"]:
    add(mid(t["start"], t["end"]), f"強調_{t['kind']}_{t['pattern']}_{t['id'].replace('+', 'p')}")
for k, g in enumerate(rec.get("plates", [])):
    add(g["items"][-1][2] + 0.9, f"{g['kind']}{k + 1:02d}_{g['items'][0][0].replace('+', 'p')}")
for n in rec.get("notes_added", []):
    add(mid(n["start"], n["end"], 0.8), f"説明_{n['id'].replace('+', 'p')}")
for k, d in enumerate(rec.get("diagrams", [])):
    add(d["start"] + 0.8, f"図解{k + 1}_見出し")
    for j, it in enumerate(d["items"]):
        add(it[2] + 0.9, f"図解{k + 1}_札{j + 1}")
    add(d["end"] - 0.5, f"図解{k + 1}_全部")
# v002：動く図解（zukai/out/<KEY>/manifest.json の確かめの画像と同じコマ＋頭と終わり）・ディゾルブの途中
for d in rec.get("anim_diagrams", []):
    k = d["key"]
    add(d["start"] + 0.05, f"動く図解{k}_出だし")
    mpath = os.path.join(V, "zukai", "out", k, "manifest.json")
    if os.path.exists(mpath):
        zm = json.load(open(mpath, encoding="utf-8"))
        for p in zm.get("previews", []):
            f = int(os.path.basename(p).rsplit("_f", 1)[1].split(".")[0])
            add((zm["tl_start_f"] + f) / FPS, f"動く図解{k}_f{f:04d}")
    add(d["end"] - 0.1, f"動く図解{k}_最後")
    add(d["end"] + 0.1, f"動く図解{k}_後")
for x in rec.get("dissolves", []):
    if len(x.get("clip") or []) != 2:              # v004：※AI指示中 のディゾルブはまとめて1行（時刻なし）。G5 の画像で見る
        continue
    a, b = x["clip"]
    if "終わり" in x["what"]:
        add(b - 0.25, f"ディゾルブ途中_{x['track']}")
    else:
        add(a + 0.25, f"ディゾルブ途中_{x['track']}_タイトル")
for k, b in enumerate(rec["boards"]):
    add(mid(b["start"], b["end"], 1.0), f"ボード{k + 1}_{b['type']}")
for k, r in enumerate(rec.get("roleplay", [])):
    add(mid(r["start"], r["end"], 1.0), f"代弁{k + 1}")
for k, lb in enumerate(rec["labels"][::3]):
    add(lb["start"] + 1.5, f"画面と札{k + 1}")
for k, z in enumerate(rec["zooms"][::10]):
    add(mid(z["start"], z["end"], 0.4), f"ズーム{k + 1}_{int(z['scale'])}")
for k, (a, b) in enumerate(mp["screen_spans"][::6]):
    add((a - 1) / FPS, f"切り替え{k + 1}_前")
    add((a + 2) / FPS, f"切り替え{k + 1}_後")
ti = rec.get("titles", [])
cap = mp["caption_tl"]
first = min(cap[i] for i in cap) / FPS
for t in rec.get("titles", [])[:1]:
    pass
add(cap["3"] / FPS + 0.3 if "3" in cap else first + 5, "右上タイトル_最初の頃")
for k, (i, t) in enumerate(json.load(open(os.path.join(V, "v004_記録.json"), encoding="utf-8")).get("topics_placed", [])[:0]):
    pass
# v004：直した所の前後（v003 から：ロゴの札・サッカー・G1 はそのまま。v004 の新しいもの）
F1 = 1 / FPS
cap = mp["caption_tl"]
for i, nm in [("94", "強調まず一回"), ("124", "3:03切った後_シンプルに"), ("142+1", "3:10_よくスキル"), ("413", "7:04いい動画"), ("132", "サッカー_頭")]:
    if i in cap:
        add(cap[i] / FPS + 0.15, f"v004_{nm}_頭")
        add(cap[i] / FPS - 0.1, f"v004_{nm}_前")
for x in cj.get("g4_caption_at_cut", []):
    add(x["to_tl"] / FPS + 0.5 * F1, f"G4_{x['id'].replace('+', 'p')}_カット後")
    add(x["to_tl"] / FPS + (x["frames"] + 0.5) * F1, f"G4_{x['id'].replace('+', 'p')}_もとの頭")
for k, x in enumerate(rec.get("ai_talk", [])):
    add(x["start"] + 1.0, f"G5_{x['from'].replace('+', 'p')}_出ている")
    add(x["start"] + 1.5, f"G5_{x['from'].replace('+', 'p')}_消える途中")
for k, f in enumerate(rec.get("frames", [])):
    add(f["start"] + min(0.6, (f["end"] - f["start"]) / 2), f"赤枠G2_{k + 1:03d}_{f['from'].replace('+', 'p')}")
for x in rec.get("images", []):                    # v004 G3：画像（zukai/I*・L1）の出だし・途中・終わり
    a, b = x["start"], x["end"]
    add(a + 0.35, f"画像{x['key']}_出だし")
    add((a + b) / 2, f"画像{x['key']}_途中")
    add(b - 0.25, f"画像{x['key']}_終わり")
    add(b + 0.15, f"画像{x['key']}_後")
for k, x in enumerate(rec.get("jump_aligned", [])[::8]):
    add(x["to"][0] + 0.5 * F1 if x["to"][0] != x["from"][0] else x["to"][1] - 0.5 * F1, f"つなぎ寄せ{k + 1}_{x['track']}")

def add_f(f, name):                                   # コマで指定（秒から丸めると、前と後が同じコマになることがある）
    s_ = f / FPS
    jobs.append([f"{f // 108000:02d}:{f // 1800 % 60:02d}:{f // 30 % 60:02d}:{f % 30:02d}", f"{int(s_ // 60):02d}{int(s_ % 60):02d}_{name}", round(s_, 3)])


g1 = []
for x in rec.get("g1_pieces", []):
    f = int(round(x["at"] * FPS))
    g1.append(f)
    add_f(f - 1, f"G1_f{f}_カット前")
    add_f(f, f"G1_f{f}_カット後")
for t in rec.get("telops", []):
    if t["id"] in ("1253", "1299", "51"):
        f = int(round(t["start"] * FPS))
        if f not in g1:
            add_f(f - 1, f"G1_f{f}_強調の前_{t['id']}")
            add_f(f, f"G1_f{f}_強調の頭_{t['id']}")
jobs.sort(key=lambda j: j[2])
json.dump(jobs, open(os.path.join(HERE, "review_jobs.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
json.dump([j for j in jobs if "_G1_" in j[1]], open(os.path.join(HERE, "review_jobs_g1.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print(len(jobs), "jobs")
