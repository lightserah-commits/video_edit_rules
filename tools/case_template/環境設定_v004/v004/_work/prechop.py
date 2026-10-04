"""組み立て前に、cuts_v004.json の残す区間のつなぎ目を tools/check_chops.py と同じ見方で確かめる（Premiere を通す前に0件にするため）。
  python3 v004/_work/prechop.py"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.expanduser("~/Desktop/video_edit_rules/tools"))
import check_chops
FT = 8475667200
cj = json.load(open(os.path.join(HERE, "cuts_v004.json")))
rows, t = [], cj.get("highlight_external_frames", 0)
for a, b in cj["highlight_frames"] + cj["keep_frames"]:
    rows.append({"start_f": t, "end_f": t + b - a, "start_ticks": t * FT, "end_ticks": (t + b - a) * FT, "in_ticks": a * FT, "muted": False, "name": "cam"})
    t += b - a
d = {"frame_ticks": FT, "tracks": {"A1": rows}}
wav = check_chops.Wav(os.path.join(os.path.dirname(os.path.dirname(HERE)), "analysis", "asr", "_work", "camera.wav"))
out = check_chops.check(d, "A1", {"cam": wav})
print(f"組み立て前の声のブツッ {len(out)}")
for r in out:
    print(" ", r["time"], "前" if r["tail_cut"] else "", "後" if r["head_cut"] else "", r["db"])
