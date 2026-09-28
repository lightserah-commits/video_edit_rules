#!/usr/bin/env python3
"""シーケンスの全クリップ（トラック・開始/終了・素材名・in/out・無効化・文字）をJSONに書き出す。
途中の版から始める案件で「変えてはいけない基準」を残すのに使う（編集の依頼文.md の工程1）。
元は work/gamen_kyoyu_20260926/analysis/dump_timeline.py。

使い方: python3 tools/dump_timeline.py <prproj> <シーケンス名> <出力.json>
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from native_prproj import Prproj, TPS  # noqa: E402


def dump(path, seq_name):
    pj = Prproj.load(path)
    seq = pj.sequence(seq_name)
    ft = pj.frame_ticks(seq)
    out = {"project": path, "sequence": seq_name, "frame_ticks": ft, "fps": TPS / ft, "tracks": {}}
    end_all = 0
    for name, tr in pj.tracks(seq):
        rows = []
        for it in pj.items(tr):
            s, e = pj.span(it)
            end_all = max(end_all, e)
            sc = pj.ref(it.find('ClipTrackItem/SubClip'))
            clip = pj.ref(sc.find('Clip')) if sc is not None and sc.find('Clip') is not None else None
            h = pj.range_holder(clip)
            mu = it.find('ClipTrackItem/IsMuted')
            r = {"start_f": s // ft, "end_f": e // ft, "start_ticks": s, "end_ticks": e,
                 "name": sc.findtext('Name') if sc is not None else None,
                 "in_ticks": int(h.findtext('InPoint')) if h is not None else None,
                 "out_ticks": int(h.findtext('OutPoint')) if h is not None else None,
                 "muted": (mu is not None and mu.text == 'true'), "object_id": it.attrib.get('ObjectID')}
            try:
                t = pj.item_texts(it)
                if t:
                    r["texts"] = ["".join(x) for x in t]
            except Exception as ex:
                r["texts_err"] = str(ex)
            rows.append(r)
        out["tracks"][name] = rows
    out["end_ticks"] = end_all
    out["end_f"] = end_all // ft
    return out


if __name__ == '__main__':
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    d = dump(sys.argv[1], sys.argv[2])
    json.dump(d, open(sys.argv[3], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"{sys.argv[3]}：{sum(len(v) for v in d['tracks'].values())}クリップ・{d['end_f']}フレーム")
