"""（AI動画編集 2026-10-16：話者の目安＝素材と話者の組み・画面の操作＝Loom の画面の動きに変えた）区切り（units）を塊（chunk）に分け、台本係が読む材料の表にする（環境設定 v001 の chunk_units.py と同じ形を作り直した。元は edit/ ごと消えた）。
  ~/Desktop/video_edit_rules/env/bin/python scripts/chunk_units.py [塊の数 N（既定 10）]
  入力：analysis/units.json、analysis/speaker/micratio.json（あれば）、analysis/asr/asr_camera_p.json（2回目の文字起こし。あれば）、analysis/screen/activity.json
  出力：analysis/chunks/chunk_1〜N.txt（1行＝ u|カメラの時刻|話者の目安(dB)|文字起こし〔2回目の文字起こしが違えば〕|画面の操作|前の区切りとの間(秒)）
    話者の目安＝Mac のマイク÷カメラの音の大きさの差（dB）。三上さんは Mac の前にいるので大きい。画面の録画の前（カメラの 16:31 まで）は「?」
    画面の操作＝その区切りの間の Screen Studio の記録（c＝クリック数・k＝キー数）。無ければ空
    塊の切れ目は、塊の長さがそろうように、近くの一番長い間（声の無い所）にする
  analysis/chunks/index.txt に塊ごとの範囲（区切り・カメラの時刻）を書く
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
A = os.path.join(os.path.dirname(HERE), "analysis")
N = int(sys.argv[1]) if len(sys.argv) > 1 else 10
FIXED = [int(x) for x in sys.argv[2:]]   # 1015：塊の頭の区切りを指定する（例 3 461 1100 ＝ 前半の 20:09・後半の頭で分ける）
units = json.load(open(os.path.join(A, "units.json")))
sync = json.load(open(os.path.join(A, "sync", "sync.json")))
try:
    MR = {int(k): v for k, v in json.load(open(os.path.join(A, "speaker", "micratio.json"))).items()}
except FileNotFoundError:
    MR = {}
try:
    act = json.load(open(os.path.join(A, "screen", "motion.json")))
except FileNotFoundError:
    act = None
try:
    P = json.load(open(os.path.join(A, "asr", "asr_camera_p.json")))
except FileNotFoundError:
    P = []
pw = [w for s in P for w in s.get("words", [])]
pw_t = np.array([w["start"] for w in pw]) if pw else np.array([])


def norm(s):
    import re
    import unicodedata
    return re.sub(r"[\s、。・,.!?！？「」『』（）()\[\]【】:：;；\"'`~〜ー\-–—→…／/%＠@〇]", "", unicodedata.normalize("NFKC", s).lower())


def mmss(t):
    return f"{int(t // 60)}:{t % 60:04.1f}"


def second_text(u):
    if not len(pw_t):
        return ""
    i0, i1 = np.searchsorted(pw_t, u["start"] - 0.05), np.searchsorted(pw_t, u["end"] - 0.05)
    t = "".join(w["word"] for w in pw[i0:i1]).strip()
    return t if norm(t) != norm(u["text"]) else ""


def screen_ops(u):
    """AI動画編集：Loom の画面の動き（analysis/screen/motion.json の1秒ごとの変化 0〜100）。区切りの間の最大を「動N」で出す（5未満は空）"""
    if not act:
        return ""
    s0 = u["start"] - sync["offset"]
    s1 = u["end"] - sync["offset"]
    mv = act["motion"]
    if s1 < 0 or s0 > len(mv):
        return ""
    i0, i1 = max(0, int(s0)), min(len(mv), int(s1) + 1)
    m = max(mv[i0:i1]) if i1 > i0 else 0
    return f"動{m:.0f}" if m >= 5 else ""


PARTS = sync["parts"]
WHO = {"1314": "三上/@創太", "1315": "三上/@創太", "1317": "こういち/@創太", "loom": "こういち"}


def part_of(t):
    p = [x for x in PARTS if x["start_sec"] <= t][-1]
    return p["name"]


def line(i, u):
    gap = u["start"] - units[i - 1]["end"] if i else 0.0
    pn = part_of(u["start"])
    sp = f"{pn}:{WHO[pn]}"
    p = second_text(u)
    txt = u["text"] + (f"〔{p}〕" if p else "")
    return f"{u['u']}|{mmss(u['start'])}|{sp}|{txt}|{screen_ops(u)}|{gap:.1f}"


# 塊の切れ目：全体を N 等分した位置の近く（±5%）で、一番長い間（FIXED があればそれ）
n = len(units)
cuts = [0]
for k in range(1, N if not FIXED else 1):
    c = round(n * k / N)
    lo, hi = max(cuts[-1] + 20, c - n // (N * 20)), min(n - 20, c + n // (N * 20))
    best = max(range(lo, hi + 1), key=lambda i: units[i]["start"] - units[i - 1]["end"])
    cuts.append(best)
cuts += FIXED
cuts.append(n)
os.makedirs(os.path.join(A, "chunks"), exist_ok=True)
idx = []
for k in range(N):
    a, b = cuts[k], cuts[k + 1]
    with open(os.path.join(A, "chunks", f"chunk_{k + 1}.txt"), "w", encoding="utf-8") as f:
        f.write("# u|通しの時刻|素材:話者（印なし＝メイン・@＝聞き手）|文字起こし〔2回目〕|画面の動き|前との間(秒)\n")
        for i in range(a, b):
            f.write(line(i, units[i]) + "\n")
    idx.append(f"塊{k + 1}：区切り {units[a]['u']}〜{units[b - 1]['u']}（{b - a}個）カメラの {mmss(units[a]['start'])}〜{mmss(units[b - 1]['end'])}")
open(os.path.join(A, "chunks", "index.txt"), "w", encoding="utf-8").write("\n".join(idx) + "\n")
print("\n".join(idx))
