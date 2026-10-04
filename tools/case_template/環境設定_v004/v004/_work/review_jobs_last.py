"""v004 最後の直し（急ぎ）：確認の画像を、直した所だけに絞る（review_jobs.py の 869枚の代わり）→ _work/review_jobs_last.json
  python3 v004/_work/review_jobs_last.py && python3 v004/_work/finish.py --no-dissolve --jobs v004/_work/review_jobs_last.json"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
V = os.path.dirname(HERE)
FPS = 30000 / 1001
rec = json.load(open(os.path.join(V, "v004_記録.json"), encoding="utf-8"))
jobs = []


def add(sec, name):
    f = int(round(sec * FPS))
    m, s = int(sec // 60), sec % 60
    jobs.append([f"{f // 108000:02d}:{f // 1800 % 60:02d}:{f // 30 % 60:02d}:{f % 30:02d}", f"{m:02d}{int(s):02d}_{name}", round(sec, 2)])


for im in rec["images"]:                                   # 画像（I*・L1）：出だし・真ん中・終わり
    a, b = im["start"], im["end"]
    for t, w in ((a + 0.4, "出だし"), ((a + b) / 2, "途中"), (b - 0.2, "終わり")):
        add(t, f"画像{im['key']}_{w}")
for d in rec.get("anim_diagrams", []):                     # 動く図解：頭と終わり（Z3 は 9:48 のつなぎ、Z7 は前倒し）
    add(d["start"] - 0.15, f"図解{d['key']}_直前")
    add(d["start"] + 0.1, f"図解{d['key']}_頭")
    add(d["end"] + 0.1, f"図解{d['key']}_直後")
for z in rec["zooms"]:                                     # 小川さんの顔まね
    if "顔まね" in z["why"]:
        add(z["start"] - 0.3, "小川さん顔まね_前")
        add(z["start"] + 0.3, "小川さん顔まね_寄り")
        add(z["end"] - 0.1, "小川さん顔まね_終わり")
        add(z["end"] + 0.3, "小川さん顔まね_後")
for x in rec.get("screen_lead", []):                       # [35] 画面をカットから出した所
    add(x["at"] + 0.05, "画面の頭を前へ_頭")
    add(x["was"] + 0.1, "画面の頭を前へ_元の頭")
for t in rec.get("titles_dropped", []):                    # [37] 置かなかった右上タイトル
    add((t["start"] + t["end"]) / 2, "右上タイトルを置かない")
for fr in rec.get("frames", [])[::3]:                      # 赤枠：3つに1つ
    add(fr["start"] + 0.3, f"赤枠_{str(fr['from']).replace('+', 'p')}")
seen, out = set(), []
for j in sorted(jobs, key=lambda x: x[2]):
    if j[0] not in seen:
        seen.add(j[0])
        out.append(j)
json.dump(out, open(os.path.join(HERE, "review_jobs_last.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print("確認の画像", len(out))
