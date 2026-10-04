"""v003：画面の赤枠（_work/red_frames.json）の時刻を、今の土台（base_v004_map.json）に合わせて直す（文字認識 screen_ocr は重いので流さない）。
screen_marks_v004.py と同じ決め方：枠は id_from の字幕の頭から id_to の次の字幕の頭まで、画面を映している間だけ。PNG の場所も v003 に。
  python3 v004/_work/retime_red_frames.py"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
FT = 8475667200
mp = json.load(open(os.path.join(HERE, "base_v004_map.json"), encoding="utf-8"))
ctl = mp["caption_tl"]
capj = json.load(open(os.path.join(HERE, "captions_v004.json"), encoding="utf-8"))
caps = sorted([c for c in capj["captions"] if c["mode"] != "drop" and "src" in c], key=lambda c: ctl[c["id"]])
nxt = {c["id"]: (ctl[caps[k + 1]["id"]] if k + 1 < len(caps) else mp["total_frames"]) for k, c in enumerate(caps)}


def clip_to_screen(a, b):
    for x, y in mp["screen_spans"]:
        if x < b and a < y:
            return max(a, x), min(b, y)
    return a, b


p = os.path.join(HERE, "red_frames.json")
d = json.load(open(p, encoding="utf-8"))
for f in d["frames"]:
    a, b = clip_to_screen(ctl[f["id_from"]], nxt[f["id_to"]])
    old = (f["start"] / FT, f["end"] / FT)
    f["start"], f["end"] = a * FT, b * FT
    f["png"] = os.path.join(HERE, "red_frames", os.path.basename(f["png"]))
    assert os.path.exists(f["png"]), f["png"]
    print(f"{f['id_from']}-{f['id_to']}: {old[0]/29.97:.2f}〜{old[1]/29.97:.2f} → {a/29.97:.2f}〜{b/29.97:.2f}  {f['read'][:24]}")
json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
