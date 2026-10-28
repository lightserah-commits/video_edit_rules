#!/usr/bin/env python3
"""映像・声の「切れ端」（0.2秒より短く出る所）を探す。08 の cut.no_slivers（2026-09-27 ユーザー指示）。

1フレームだけ別の映像が出る・ワイプが一瞬だけ出る／消える・声が一瞬だけ鳴ると、カクッとして気持ち悪い。
お手本2本は映像のかたまりの最短が 0.18〜0.23秒で、2フレーム以下は0件。

見ること（3種類。どれも1件でもあれば終了コード1）:
  かたまり … 映像と声の入ったクリップのあるトラックごとに、素材がそのまま続いている所をひとかたまりにして、
             長さが --min 秒より短いかたまり（一瞬だけ別の絵・別の声が出る）。前後に何があるかも出す。
  分け目   … 素材はそのまま続いているが、クリップとして --min 秒より短く分かれている所（2026-10-28 から）。
             見た目は続いて見えるが、タイムラインに2〜3コマのクリップが残り、手で直す時に切れ端に見える・
             その分け目で別のトラックの絵が変わると一瞬だけ前の絵が残る。前後のどちらのクリップと続いているかも出す。
             （1026 v004：字幕の区切りで分けた後に字幕だけ切れ目へ寄せて、2〜3コマのクリップが3つ残っていた。
               小川さん「1フレームとか数フレームある謎の…」「検査が本当に働いてるのかな」。前の版はここを数えていなかった）
  重ねのずれ … 一番下の映像トラック（カメラ・画面）の切れ目と、上に重ねた絵（調整レイヤー・画像・動画の札。
             文字だけのテロップは除く）の頭・終わりが、1〜（--min 秒未満）コマだけずれている所（2026-10-28 から）。
             切れ目の後に前の重ねが数コマ残る・重ねが消えた後に前の絵が数コマ見える。同じトラックで重ねが
             消えてから次の重ねが出るまでの数コマの隙間も数える。
  無効化したクリップは除く。声のトラック（.wav などで、タイムラインの半分以上を覆うトラック。声・BGM）も
  「かたまり」と「分け目」で見る（前の版は .wav を見ていなかった）。効果音のように短い物が並ぶトラックは見ない。

使い方:
  python3 tools/check_slivers.py 版.prproj --seq シーケンス名 [--min 0.2] [--out 結果.json] [--base V1]
  python3 tools/check_slivers.py timeline.json          （tools/dump_timeline.py の出力でもよい）
  --no-splits・--no-overlay で「分け目」「重ねのずれ」を数えない（前の版と同じ数え方）
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
TPS = 254016000000
MEDIA = ('.mov', '.mp4', '.m4v', '.mxf', '.avi')
AUDIO = ('.wav', '.aif', '.aiff', '.m4a', '.mp3', '.aac')
PICTURE = MEDIA + ('.png', '.jpg', '.jpeg', '.psd', '.tif', '.tiff', '.gif', '.webp')
ADJUST = ('調整レイヤー', 'adjustment layer')


def load(path, seq):
    if path.endswith('.json'):
        return json.load(open(path))
    from dump_timeline import dump
    return dump(path, seq)


def is_audio_track(name):
    return name.upper().startswith('A')


def clips_of(rows, exts):
    return sorted([r for r in rows if not r['muted'] and r['name'] and r['name'].lower().endswith(exts) and r['in_ticks'] is not None],
                  key=lambda r: r['start_ticks'])


def runs(cl, ft):
    """素材がそのまま続く所をひとかたまりに。各かたまりに、中のクリップ（分け目）も持たせる"""
    out = []
    for r in cl:
        s, e = round(r['start_ticks'] / ft), round(r['end_ticks'] / ft)
        src = round(r['in_ticks'] / ft)
        piece = {'s': s, 'e': e, 'src': src}
        if out and out[-1]['e'] == s and out[-1]['name'] == r['name'] and out[-1]['src_end'] == src:
            out[-1]['e'] = e
            out[-1]['src_end'] = src + (e - s)
            out[-1]['pieces'].append(piece)
        else:
            out.append({'s': s, 'e': e, 'name': r['name'], 'src_end': src + (e - s), 'pieces': [piece]})
    return out


def voice_like(cl, end_f, ft):
    """声・BGM のように、同じ素材でタイムラインの半分以上を覆うトラックか（効果音のトラックは除く）"""
    if not cl or not end_f:
        return False
    cover = {}
    for r in cl:
        cover[r['name']] = cover.get(r['name'], 0) + (r['end_ticks'] - r['start_ticks']) / ft
    return max(cover.values()) >= 0.5 * end_f


def is_overlay(r):
    """絵を変える重ね（調整レイヤー・画像・動画）。文字だけのテロップ（texts を持つ）は除く"""
    if r['muted'] or not r['name'] or r.get('texts'):
        return False
    n = r['name'].lower()
    return n.endswith(PICTURE) or any(n.startswith(a) for a in ADJUST)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('path')
    ap.add_argument('--seq')
    ap.add_argument('--min', type=float, default=0.2, help='これより短いかたまりを切れ端とする（秒）')
    ap.add_argument('--out')
    ap.add_argument('--base', default='V1', help='一番下の映像トラック（重ねのずれを測る切れ目の元）')
    ap.add_argument('--no-splits', action='store_true', help='「分け目」を数えない')
    ap.add_argument('--no-overlay', action='store_true', help='「重ねのずれ」を数えない')
    a = ap.parse_args()
    d = load(a.path, a.seq)
    ft = d['frame_ticks']
    fps = TPS / ft
    minf = a.min * fps
    end_f = d.get('end_f') or 0

    def tc(f):
        s = f / fps
        return f"{int(s // 60):02d}:{s % 60:05.2f}"

    found = []
    base_cuts = set()
    for tr, rows in d['tracks'].items():
        exts = MEDIA + AUDIO if is_audio_track(tr) else MEDIA
        cl = clips_of(rows, exts)
        if is_audio_track(tr) and not voice_like(cl, end_f, ft):
            continue
        R = runs(cl, ft)
        if tr == a.base:
            for r in R:
                base_cuts.update((r['s'], r['e']))
        for i, r in enumerate(R):
            p = R[i - 1] if i else None
            q = R[i + 1] if i + 1 < len(R) else None
            n = r['e'] - r['s']
            if n < minf:
                before = (p['name'] if p['e'] == r['s'] else '空き') if p else '空き'
                after = (q['name'] if q['s'] == r['e'] else '空き') if q else '空き'
                found.append({'kind': 'かたまり', 'track': tr, 'time': tc(r['s']), 'frame': r['s'], 'frames': n, 'name': r['name'],
                              'before': before, 'after': after})
                continue
            if a.no_splits or len(r['pieces']) < 2:
                continue
            P = r['pieces']
            for j, pc in enumerate(P):
                m = pc['e'] - pc['s']
                if m >= minf:
                    continue
                # どちらと続いているか（かたまりの頭なら前は切れ目、終わりなら後ろが切れ目）
                if j == 0:
                    where = 'かたまりの頭（前は切れ目・後ろと続く）'
                elif j == len(P) - 1:
                    where = 'かたまりの終わり（前と続く・後ろは切れ目）'
                else:
                    where = 'かたまりの途中（前後と続く）'
                found.append({'kind': '分け目', 'track': tr, 'time': tc(pc['s']), 'frame': pc['s'], 'frames': m, 'name': r['name'],
                              'src_frame': pc['src'], 'before': where, 'after': f"かたまり {tc(r['s'])}〜{tc(r['e'])}"})
    if not a.no_overlay and base_cuts:
        cuts = sorted(base_cuts)
        import bisect
        for tr, rows in d['tracks'].items():
            if is_audio_track(tr) or tr == a.base:
                continue
            ov = sorted([r for r in rows if is_overlay(r)], key=lambda r: r['start_f'])
            edges = []
            for r in ov:
                edges += [(r['start_f'], '頭', r), (r['end_f'], '終わり', r)]
            for f, edge, r in edges:
                i = bisect.bisect_left(cuts, f)
                near = [c for c in cuts[max(0, i - 1):i + 1] if 0 < abs(c - f) < minf]
                if not near or f in base_cuts:
                    continue
                c = min(near, key=lambda x: abs(x - f))
                found.append({'kind': '重ねのずれ', 'track': tr, 'time': tc(min(c, f)), 'frame': min(c, f), 'frames': abs(c - f),
                              'name': r['name'], 'before': f"{a.base} の切れ目 {tc(c)}",
                              'after': f"重ねの{edge} {tc(f)}（{'切れ目の後' if f > c else '切れ目の前'}）"})
            for r0, r1 in zip(ov, ov[1:]):
                g = r1['start_f'] - r0['end_f']
                if 0 < g < minf:
                    found.append({'kind': '重ねのずれ', 'track': tr, 'time': tc(r0['end_f']), 'frame': r0['end_f'], 'frames': g,
                                  'name': f"{r0['name']} → {r1['name']}", 'before': '重ねの隙間（下の絵が見える）', 'after': ''})
    found.sort(key=lambda x: (x['frame'], x['track']))
    # 同じ所・同じ種類の物（V1 と A1・A2 の同じ分け目など）は1件にまとめ、トラックを並べる
    grouped = []
    for x in found:
        g = grouped[-1] if grouped else None
        if g and g['kind'] == x['kind'] and g['frame'] == x['frame'] and g['frames'] == x['frames'] and x['kind'] != '重ねのずれ':
            g['tracks'].append(x['track'])
            continue
        grouped.append(dict(x, tracks=[x['track']]))
    by, kinds = {}, {}
    for x in found:
        by[x['track']] = by.get(x['track'], 0) + 1
    for x in grouped:
        kinds[x['kind']] = kinds.get(x['kind'], 0) + 1
    print(f"{d.get('sequence', '')}：{a.min}秒（{minf:.1f}フレーム）より短い切れ端 {len(grouped)}か所 "
          + ' '.join(f'{k}:{v}' for k, v in kinds.items()) + ' ／ トラックごと ' + ' '.join(f'{k}:{v}' for k, v in by.items()))
    for x in grouped:
        print(f"  {x['time']} [{x['kind']}] {'・'.join(x['tracks'])} {x['frames']}フレーム {x['name']}（{x['before']}／{x['after']}）")
    if a.out:
        json.dump({'min_seconds': a.min, 'fps': fps, 'counts': kinds, 'slivers': grouped}, open(a.out, 'w'), ensure_ascii=False, indent=1)
    sys.exit(1 if found else 0)


if __name__ == '__main__':
    main()
