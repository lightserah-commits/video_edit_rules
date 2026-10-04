"""赤枠の道具（tools/red_frames/）が共通に読むもの：版の土台の表（base_vNNN_map.json）・字幕（captions_vNNN.json）・カット（cuts_vNNN.json）。
元：環境設定 v004 の _work/red_frames_g2.py・retime_red_frames.py・screen_ocr_v004.py の読み込みの所。

版のフォルダ（edit/vNNN）を --ver で渡すと、ふつうの置き場所を使う：
  <版>/_work/base_vNNN_map.json・<版>/_work/captions_vNNN.json・<版>/_work/cuts_vNNN.json
置き場所が違う時は --map・--captions・--cuts で1つずつ渡す。
map に要るもの：caption_tl {字幕ID: タイムラインのコマ}・screen_spans [[開始, 終わり], …]（画面を映すコマ）・total_frames・n_screen（画面録画のずれ。
  画面録画のコマ＝カメラのコマ − n_screen）
"""
import bisect
import json
import os
import re

FPS = 30000 / 1001
FT = 8475667200                      # 29.97fps の1コマの ticks


def add_case_args(ap, cuts=True):
    ap.add_argument("--ver", help="版のフォルダ（edit/vNNN）。_work/ の base_vNNN_map.json・captions_vNNN.json・cuts_vNNN.json を使う")
    ap.add_argument("--map", help="base_vNNN_map.json（--ver より優先）")
    ap.add_argument("--captions", help="captions_vNNN.json（--ver より優先）")
    if cuts:
        ap.add_argument("--cuts", help="cuts_vNNN.json（--ver より優先）")


def resolve(a, need=("map", "captions", "cuts")):
    """--ver から置き場所を決める（--map などが渡されていればそちら）。見つからなければ止める"""
    tag = None
    if getattr(a, "ver", None):
        m = re.search(r"v(\d{3})$", os.path.basename(os.path.normpath(a.ver)))
        tag = m.group(1) if m else None
    names = {"map": "base_v{}_map.json", "captions": "captions_v{}.json", "cuts": "cuts_v{}.json"}
    for k in need:
        if getattr(a, k, None):
            continue
        if not tag:
            raise SystemExit(f"--{k} か --ver（vNNN のフォルダ）を渡してください")
        p = os.path.join(a.ver, "_work", names[k].format(tag))
        if not os.path.exists(p):
            raise SystemExit(f"{p} が無い（--{k} で場所を渡す）")
        setattr(a, k, p)
    return a


def load(path):
    return json.load(open(path, encoding="utf-8"))


def caption_order(mp, capj):
    """タイムラインの順の字幕（drop を除く）と、字幕ID → 次の字幕の頭のコマ"""
    ctl = mp["caption_tl"]
    caps = sorted([c for c in capj["captions"] if c.get("mode") != "drop" and "src" in c and c["id"] in ctl], key=lambda c: ctl[c["id"]])
    nxt = {c["id"]: (ctl[caps[k + 1]["id"]] if k + 1 < len(caps) else mp["total_frames"]) for k, c in enumerate(caps)}
    return caps, nxt


def tl_to_src(cj):
    """タイムラインのコマ → 素材（カメラ）のコマ。冒頭ハイライト（highlight_external_frames）の後から本編"""
    segs, t = [], cj.get("highlight_external_frames", 0)
    for a, b in cj.get("highlight_frames", []) + cj["keep_frames"]:
        segs.append((t, a, b - a))
        t += b - a
    starts = [s[0] for s in segs]

    def f(x):
        i = max(0, bisect.bisect_right(starts, x) - 1)
        t0, a, L = segs[i]
        return a + min(x - t0, L - 1)
    return f


def clip_to_screen(mp, a, b, keep=False):
    """a〜b を、画面を映している区間に切る（重ならなければ None。keep=True なら a, b のまま）"""
    for x, y in mp["screen_spans"]:
        if x < b and a < y:
            return max(a, x), min(b, y)
    return (a, b) if keep else None


def ts(f):
    s = f / FPS
    return f"{int(s // 60)}:{s % 60:05.2f}"
