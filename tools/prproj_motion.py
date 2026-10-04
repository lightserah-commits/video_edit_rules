#!/usr/bin/env python3
"""Premiere のプロジェクト（.prproj）のクリップから、モーション（スケール・位置）と無効（IsMuted）を読む小さな道具（読むだけ）。
tools/check_gakaku.py・tools/diff_user_edits.py が使う。どの案件でも使える。
元：環境設定 v004 の prj_helpers.py の component_param・get_static（読む所だけを抜き出した）。

  from prproj_motion import motion_of, is_muted
  sc, pos, keyed = motion_of(pj, item)     # スケール（%。部品が無ければ 100）・位置 [x, y]（0〜1。無ければ [0.5, 0.5]）・キーフレームがあるか
  python3 tools/prproj_motion.py <プロジェクト.prproj> <シーケンス名> V1 [件数]   … V1 のクリップのスケール・位置を並べる（確かめ用）
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from native_prproj import Prproj, TPS  # noqa: E402

# モーションの部品（AE.ADBE Motion）の ParameterID。名前（スケール・位置）は Premiere の言語で変わるので番号で探し、名前は控え
MOTION_IDS = {"位置": "1", "スケール": "2"}


def component_param(pj, item, match_name, names):
    """item に付いた部品 match_name の中の、名前が names のパラメーター要素 {名前: 要素}（最初に見つかった部品だけ）"""
    chain = pj.ref(item.find("ClipTrackItem/ComponentOwner/Components"))
    out = {}
    if chain is None:
        return out
    want_ids = {MOTION_IDS[n]: n for n in names if n in MOTION_IDS} if match_name == "AE.ADBE Motion" else {}
    for c in chain.findall("ComponentChain/Components/Component"):
        ce = pj.ref(c)
        if ce is None or ce.findtext("MatchName") != match_name:
            continue
        for p in ce.findall("Component/Params/Param"):
            pe = pj.ref(p)
            if pe is None:
                continue
            nm = (pe.findtext("Name") or "").strip()
            pid = (pe.findtext("ParameterID") or "").strip()
            key = nm if nm in names else want_ids.get(pid)
            if key and key not in out:
                out[key] = pe
        if out:
            return out
    return out


def get_static(pe):
    """キーフレームの無い値（StartKeyframe の2つ目）。文字のまま返す（例 '125.'・'0.4525:0.5962'）"""
    return pe.find("StartKeyframe").text.split(",")[1]


def has_keys(pe):
    return bool((pe.findtext("Keyframes") or "").strip())


def motion_of(pj, item):
    """(スケール, [x, y], キーフレームがあるか)。モーションの部品が無いクリップ（初期値のまま）は (100.0, [0.5, 0.5], False)"""
    mp = component_param(pj, item, "AE.ADBE Motion", {"スケール", "位置"})
    sc, pos, keyed = 100.0, [0.5, 0.5], False
    if "スケール" in mp:
        sc = float(get_static(mp["スケール"]).rstrip("."))
        keyed = keyed or has_keys(mp["スケール"])
    if "位置" in mp:
        pos = [float(v) for v in get_static(mp["位置"]).split(":")]
        keyed = keyed or has_keys(mp["位置"])
    return sc, pos, keyed


def is_muted(item):
    """クリップが無効（Premiere の「有効」のチェックが外れている＝ClipTrackItem/IsMuted が true）か"""
    return (item.findtext("ClipTrackItem/IsMuted") or "").strip() == "true"


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        return
    pj = Prproj.load(sys.argv[1])
    seq = pj.sequence(sys.argv[2])
    n = int(sys.argv[4]) if len(sys.argv) > 4 else 20
    ft = pj.frame_ticks(seq)
    for it in sorted(pj.items(pj.track(seq, sys.argv[3])), key=lambda i: pj.span(i)[0])[:n]:
        a, b = pj.span(it)
        sc, pos, keyed = motion_of(pj, it)
        print(f"{a / TPS:9.2f}〜{b / TPS:9.2f}秒（{(b - a) // ft}コマ） スケール {sc:g} 位置 {pos[0]:.4f}:{pos[1]:.4f}"
              f"{' キーフレームあり' if keyed else ''}{' 無効' if is_muted(it) else ''}")


if __name__ == "__main__":
    main()
