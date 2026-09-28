#!/usr/bin/env python3
"""映像・声の「切れ端」（0.2秒より短く出る所）を探す。08 の cut.no_slivers（2026-09-27 ユーザー指示）。

1フレームだけ別の映像が出る・ワイプが一瞬だけ出る／消える・声が一瞬だけ鳴ると、カクッとして気持ち悪い。
お手本2本は映像のかたまりの最短が 0.18〜0.23秒で、2フレーム以下は0件。

見ること:
  映像と声の入ったクリップ（.mov .mp4 など）のあるトラックごとに、素材がそのまま続いている所をひとかたまりにして、
  長さが --min 秒より短いかたまりを出す。前後に何があるか（別の素材・同じ素材の別の所・空き）も出す。
  素材がそのまま続いている分け目（同じ素材で時刻も続いている）は切れ端に数えない。無効化したクリップは除く。

使い方:
  python3 tools/check_slivers.py 版.prproj --seq シーケンス名 [--min 0.2] [--out 結果.json]
  python3 tools/check_slivers.py timeline.json          （tools/dump_timeline.py の出力でもよい）
  切れ端が1件でもあれば終了コード1
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
TPS = 254016000000
MEDIA = ('.mov', '.mp4', '.m4v', '.mxf', '.avi')


def load(path, seq):
    if path.endswith('.json'):
        return json.load(open(path))
    from dump_timeline import dump
    return dump(path, seq)


def runs(rows, ft):
    cl = sorted([r for r in rows if not r['muted'] and r['name'] and r['name'].lower().endswith(MEDIA) and r['in_ticks'] is not None],
                key=lambda r: r['start_ticks'])
    out = []
    for r in cl:
        s, e = round(r['start_ticks'] / ft), round(r['end_ticks'] / ft)
        src = round(r['in_ticks'] / ft)
        if out and out[-1]['e'] == s and out[-1]['name'] == r['name'] and out[-1]['src_end'] == src:
            out[-1]['e'] = e
            out[-1]['src_end'] = src + (e - s)
        else:
            out.append({'s': s, 'e': e, 'name': r['name'], 'src_end': src + (e - s)})
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('path')
    ap.add_argument('--seq')
    ap.add_argument('--min', type=float, default=0.2, help='これより短いかたまりを切れ端とする（秒）')
    ap.add_argument('--out')
    a = ap.parse_args()
    d = load(a.path, a.seq)
    ft = d['frame_ticks']
    fps = TPS / ft
    minf = a.min * fps

    def tc(f):
        s = f / fps
        return f"{int(s // 60):02d}:{s % 60:05.2f}"

    found = []
    for tr, rows in d['tracks'].items():
        R = runs(rows, ft)
        for i, r in enumerate(R):
            n = r['e'] - r['s']
            if n >= minf:
                continue
            p = R[i - 1] if i else None
            q = R[i + 1] if i + 1 < len(R) else None
            before = (p['name'] if p['e'] == r['s'] else '空き') if p else '空き'
            after = (q['name'] if q['s'] == r['e'] else '空き') if q else '空き'
            found.append({'track': tr, 'time': tc(r['s']), 'frame': r['s'], 'frames': n, 'name': r['name'],
                          'before': before, 'after': after})
    found.sort(key=lambda x: (x['frame'], x['track']))
    by = {}
    for x in found:
        by[x['track']] = by.get(x['track'], 0) + 1
    print(f"{d.get('sequence', '')}：{a.min}秒（{minf:.1f}フレーム）より短い切れ端 {len(found)}件 " + ' '.join(f'{k}:{v}' for k, v in by.items()))
    for x in found:
        print(f"  {x['time']} {x['track']} {x['frames']}フレーム {x['name']}（前 {x['before']}／後 {x['after']}）")
    if a.out:
        json.dump({'min_seconds': a.min, 'fps': fps, 'slivers': found}, open(a.out, 'w'), ensure_ascii=False, indent=1)
    sys.exit(1 if found else 0)


if __name__ == '__main__':
    main()
