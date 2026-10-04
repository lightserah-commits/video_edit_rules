#!/usr/bin/env python3
"""v004 最後の直し（点検 [32]）：動く図解 Z7 の始まりを、カット（字幕1563 の頭＝G4 でカットのコマ）へ前倒しする。
Z7 は今カットの 8コマ後から始まり、その間に字幕のない素のカメラ（右上タイトルだけ）が 0.27秒出る。
描き直さず（page.html の部品のコマはそのまま）、overlay の頭に1コマ目（板と見出しの出だし。板はもう 80%）を足し、
ワイプはカメラから新しい区間で作り直す。どちらも新しい名前（overlay_r2.mov・wipe_r2.mp4）で書く（前のファイルは消さない）。
出だしの SE（f=0 のピピ）も新しい頭へ。manifest だけ直す（diagram.json・page.html は変えない。make_zukai.py Z7 を流し直すと元に戻る）
  python3 v004/_work/z7_head_pad.py
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
Z = HERE.parent / "zukai"
sys.path.insert(0, str(Z))
from tl import TL, ts  # noqa: E402
import make_zukai as mz  # noqa: E402

KEY = "Z7"
tl = TL()
mp = Z / "out" / KEY / "manifest.json"
m = json.load(open(mp, encoding="utf-8"))
d = json.load(open(Z / KEY / "diagram.json", encoding="utf-8"))
S0, E = m["tl_start_f"], m["tl_end_f"]
S = tl.caps[d["anchor"]["cap"]]["s"]                 # 字幕1563 の頭＝カットのコマ
pad = S0 - S
if m.get("head_pad_v004"):
    raise SystemExit(f"もう前倒ししてある（{m['head_pad_v004']}）")
assert 0 < pad <= 15, (S0, S, pad)
print(f"{KEY}: {ts(S0)} → {ts(S)}（{pad}コマ前倒し）")
odir = Z / "out" / KEY
work = odir / "_work_pad"
work.mkdir(exist_ok=True)
n = E - S
src = mz.src_ranges(tl, S, E)
base = mz.make_base(work, S, E, src)
old_ov = Path(m["overlay"]["file"])
ov = odir / "overlay_r2.mov"
wipe = odir / "wipe_r2.mp4"
assert not ov.exists() and not wipe.exists()
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(old_ov), "-vf", f"tpad=start={pad}:start_mode=clone",
                "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le", "-vendor", "apl0", str(ov)], check=True)
assert mz.count_frames(ov) == n, (mz.count_frames(ov), n)
crop = m["wipe"]["crop_from_camera"]
mz.make_wipe(base, wipe, crop, n)
assert mz.count_frames(wipe) == n
for ev in m["se_events"]:
    if ev["tl_f"] == S0:
        ev["tl_f"], ev["tl"] = S, ts(S)
hide = [i for i in tl.ids if tl.caps[i]["s"] < E and S < tl.caps[i]["e"]]
m.update({"tl_start_f": S, "tl_start": ts(S), "frames": n, "src_ranges": [list(x) for x in src], "hide_caption_ids": hide,
          "head_pad_v004": {"frames": pad, "from": ts(S0), "how": "_work/z7_head_pad.py（overlay の1コマ目を頭に足し、ワイプはカメラから作り直し）"}})
m["overlay"].update({"file": str(ov), "frames": n})
m["wipe"]["file"] = str(wipe)
json.dump(m, open(mp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("字幕を外す", hide)
