"""Air v005 のシーケンスを Media Encoder で MP4（YouTube 1080p HD）に書き出す（Premiere は固まらない。前面のプロジェクトは戻す）。
画面解説 v009 の export_v009.py と同じ書き方。出力 edit/v005/sec_v005.mp4
  python3 v005/_work/export.py"""
import json, os, sys
ROOT = os.path.expanduser("~/Desktop/video_edit_rules")
sys.path.insert(0, os.path.join(ROOT, "tools"))
from premiere_bridge import run, preflight
HERE = os.path.dirname(os.path.abspath(__file__))
V = os.path.dirname(HERE)
PROJ = os.path.join(V, "sec_v005.prproj")
OUT = os.path.join(V, sys.argv[1] if len(sys.argv) > 1 else "sec_v005.mp4")   # v005：締めの Pan を付けた書き出しは別の名前（python3 _work/export.py sec_v005_pan.mp4）。前の書き出しは残す
SEQ = json.load(open(os.path.join(HERE, "base_v005_map.json"), encoding="utf-8"))["sequence"]
PRESET = "/Applications/Adobe Premiere Pro 2026/Adobe Premiere Pro 2026.app/Contents/MediaIO/systempresets/4E49434B_48323634/YouTube 1080p HD.epr"
if os.path.exists(OUT):
    raise SystemExit(f"{OUT} がもうある")
print(preflight())
js = open(os.path.join(ROOT, "tools", "premiere_helpers.jsx"), encoding="utf-8").read() + "\n" + \
    open(os.path.join(HERE, "export_ame_v005.jsx"), encoding="utf-8").read().replace("__PROJ__", PROJ) \
    .replace("__SEQ__", SEQ).replace("__OUT__", OUT).replace("__PRESET__", PRESET)
print(run(js, timeout=600))
