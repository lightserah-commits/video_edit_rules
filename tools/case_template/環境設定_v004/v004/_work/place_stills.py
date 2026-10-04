"""Air v001 の土台（最終）を Premiere で作る：見本集（とその Masks フォルダ）を _work/v004_stills.prproj にコピー → 開いて base_v004.xml を読み込み →
オフラインの SE・BGM などをつなぎ直し → 画面の赤枠（red_frames.json）を V4 に置いて保存して閉じる（place_stills_v004.jsx）。
  python3 v004/_work/place_stills.py"""
import json, os, shutil, sys
ROOT = os.path.expanduser("~/Desktop/video_edit_rules")
sys.path.insert(0, os.path.join(ROOT, "tools"))
from premiere_bridge import run, preflight
HERE = os.path.dirname(os.path.abspath(__file__))
base = os.path.join(HERE, "v004_stills.prproj")
xml = os.path.join(HERE, "base_v004.xml")
seq = json.load(open(os.path.join(HERE, "base_v004_map.json"), encoding="utf-8"))["sequence"]
frames = json.load(open(os.path.join(HERE, "red_frames.json"), encoding="utf-8"))["frames"] if os.path.exists(os.path.join(HERE, "red_frames.json")) else []
stills = [[f["png"], 3, f["start"], f["end"]] for f in frames]          # V4（画面に付く演出。02 の output_tracks）
dirs = [os.path.join(ROOT, "素材", "SE"), os.path.join(ROOT, "素材", "BGM"), os.path.expanduser("~/Desktop/video_edit_rules/完成版/コピー_みかみさんCH0726_1"),
        os.path.expanduser("~/Desktop/video_edit_rules/完成版/コピー_AI時代に消える仕事残る仕事")]
if os.path.exists(base):
    raise SystemExit(f"{base} がもうある（作り直す時は、Premiere で開いていないことを確かめてから消す）")
# v002（2026-10-04）：依頼文の工程8（2026-10-03 から）どおり、見本集を直接コピーせず、部品集（見本/テロップ部品集.prproj）を
#   build_parts.py --case-copy でこの版にコピーする（素材をこの Mac の 素材/ に向け直す。部品集が古い・素材が欠けていれば何も書かずに止まる）
import subprocess
subprocess.run([sys.executable, os.path.join(ROOT, "tools", "build_parts.py"), "--case-copy", os.path.abspath(base)], check=True, cwd=ROOT)
masks = os.path.join(ROOT, "見本", "テロップ見本集 Masks")
if os.path.isdir(masks) and not os.path.exists(os.path.join(HERE, "v004_stills Masks")):
    shutil.copytree(masks, os.path.join(HERE, "v004_stills Masks"))          # iMac で分かった：無いと「マスクの復元」の窓で止まる
print(preflight(), len(stills))
js = open(os.path.join(ROOT, "tools", "premiere_helpers.jsx"), encoding="utf-8").read() + "\n" + \
    open(os.path.join(HERE, "place_stills_v004.jsx"), encoding="utf-8").read().replace("__BASE__", base).replace("__XML__", xml) \
    .replace("__SEQ__", seq).replace("__STILLS__", json.dumps(stills, ensure_ascii=False)).replace("__DIRS__", json.dumps(dirs, ensure_ascii=False))
r = run(js, timeout=1800)
r = r if isinstance(r, dict) else json.loads(r)
print(json.dumps(r, ensure_ascii=False, indent=1))
