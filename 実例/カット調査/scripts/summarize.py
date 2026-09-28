"""cut_analysis.py の結果を集計する（切った長さの分布・残した間・中の間）。
使い方: python summarize.py <cut_*.json> <タイムライン.json> 素材名=16k.wav ...
"""
import json
import sys

import numpy as np

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from cut_analysis import TPS, Voice  # noqa: E402


def inner_pauses(tl, voices, track='A1'):
    d = json.load(open(tl))
    rows = [r for r in d['tracks'][track] if not r['muted'] and (r['name'] or '') in voices]
    out = []
    by = {}
    for r in rows:
        by.setdefault(r['name'], []).append((r['in_ticks'] / TPS, r['out_ticks'] / TPS))
    for name, rs in by.items():
        v = voices[name]
        kept = []
        for s, e in sorted(rs):
            if kept and abs(s - kept[-1][1]) < 0.05:
                kept[-1][1] = max(kept[-1][1], e)
            else:
                kept.append([s, e])
        for s, e in kept:
            seg = v.v[v.idx(s):v.idx(e)]
            nz = np.nonzero(seg)[0]
            if len(nz) < 2:
                continue
            run = 0
            for x in seg[nz[0]:nz[-1] + 1]:
                if not x:
                    run += 1
                elif run:
                    out.append((run * 0.01, name, s))
                    run = 0
    return out


def main():
    cut, tl = sys.argv[1], sys.argv[2]
    voices = {k: Voice(v) for k, v in (x.split('=', 1) for x in sys.argv[3:])}
    d = json.load(open(cut))
    J = d['joins']
    fw = [j for j in J if j['kind'] == '前へ飛ぶ']
    L = np.array([j['jump'] for j in fw]) if fw else np.array([0.0])
    res = {'sequence': d['sequence'], 'clips': d['clips'], 'tl_end': d['tl_end'],
           'kinds': {k: sum(j['kind'] == k for j in J) for k in ('前へ飛ぶ', '後ろへ戻る', '分割だけ', '別の素材')},
           'removed_by_length': {}}
    for lo, hi in [(0, 0.3), (0.3, 1), (1, 3), (3, 10), (10, 60), (60, 1e9)]:
        m = (L > lo) & (L <= hi)
        res['removed_by_length'][f'{lo}-{hi if hi < 1e9 else ""}s'] = {
            'n': int(m.sum()), 'sec': round(float(L[m].sum()), 1),
            'voice_ratio_median': round(float(np.median([j['removed_voice'] for j, x in zip(fw, m) if x])), 2) if m.any() else None}
    tk = [j['tail_kept'] for j in fw if j['tail_kept'] is not None]
    hk = [j['head_kept'] for j in fw if j['head_kept'] is not None]
    both = [j['tail_kept'] + j['head_kept'] for j in fw if j['tail_kept'] is not None and j['head_kept'] is not None]
    q = lambda xs: {p: round(float(np.percentile(xs, p)), 2) for p in (25, 50, 75, 90)} if xs else None
    res['kept_at_join'] = {'tail': q(tk), 'head': q(hk), 'heard_total': q(both)}
    P = inner_pauses(tl, voices)
    arr = np.array([p for p, _, _ in P])
    res['inner_pauses'] = {'n_over_0.3': int((arr >= 0.3).sum()), 'n_over_0.5': int((arr >= 0.5).sum()),
                           'n_over_0.8': int((arr >= 0.8).sum()),
                           'p90_of_over_0.1': round(float(np.percentile(arr[arr >= 0.1], 90)), 2),
                           'long_ones': sorted([(round(p, 2), n, round(s, 1)) for p, n, s in P if p >= 0.5], reverse=True)[:30]}
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
