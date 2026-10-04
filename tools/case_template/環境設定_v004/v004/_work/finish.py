"""Air v001 を Premiere で開き、右上タイトルの最初にディゾルブ（0.5秒）を付けて保存し、確認の画像を書き出す（finish_v004.jsx）。
  python3 v004/_work/finish.py [--no-dissolve]"""
import json, os, sys
ROOT = os.path.expanduser("~/Desktop/video_edit_rules")
sys.path.insert(0, os.path.join(ROOT, "tools"))
from premiere_bridge import run, preflight
HERE = os.path.dirname(os.path.abspath(__file__))
V = os.path.dirname(HERE)
proj = os.path.join(V, "kankyo_v004.prproj")
seq = json.load(open(os.path.join(HERE, "base_v004_map.json"), encoding="utf-8"))["sequence"]
os.makedirs(os.path.join(V, "確認"), exist_ok=True)
JOBS = sys.argv[sys.argv.index("--jobs") + 1] if "--jobs" in sys.argv else os.path.join(HERE, "review_jobs.json")   # v003：一部だけ書き出し直す時
jobs = [[tc, os.path.join(V, "確認", name)] for tc, name, _ in json.load(open(JOBS, encoding="utf-8"))]
print(preflight())
js = open(os.path.join(ROOT, "tools", "premiere_helpers.jsx"), encoding="utf-8").read() + "\n" + \
    open(os.path.join(HERE, "finish_v004.jsx"), encoding="utf-8").read().replace("__PROJ__", proj).replace("__SEQ__", seq) \
    .replace("__JOBS__", json.dumps(jobs, ensure_ascii=False)).replace("__WAIT__", "20000") \
    .replace("__DISSOLVE__", "0" if "--no-dissolve" in sys.argv else "15")
r = run(js, timeout=1500)
print(r)
