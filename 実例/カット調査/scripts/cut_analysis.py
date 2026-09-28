"""完成版のカットを、切る前の素材と突き合わせて調べる。

  つなぎ目（声のトラックで、となり合うクリップの境目）ごとに：
    - 種類：分割だけ（素材が続いている）／前へ飛ぶ（間を切った）／後ろへ戻る（並べ替え・使い回し）／別の素材
    - 切った長さ（素材の秒）と、切った部分の中身（声のある割合・文字起こし）
    - 残した間：前のクリップの終わりで、声が終わってから何秒残したか（尻）／次のクリップの頭で、声が始まるまで何秒あるか（頭）
  声がある・無いは 10ms ごとの大きさで決める（その素材の声の85パーセンタイルから 12dB 下を境目）。

使い方（numpy の入った環境で）:
  python cut_analysis.py <タイムライン.json> <出力.json> --track A1 --wav 素材名=16k.wav ... [--asr 素材名=asr.json ...]
"""
import argparse
import json
import os
import wave

import numpy as np

TPS = 254016000000
HOP = 0.01
FILLERS = set("えー え えっと えーと あの あのー あー あ まあ まぁ うん うーん ん んー なんか そう その ね で".split())


def envelope(wav):
    cache = wav.replace('.wav', '_env.npy')
    if os.path.exists(cache):
        return np.load(cache)
    with wave.open(wav) as f:
        a = np.frombuffer(f.readframes(f.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    n = len(a) // 160
    x = a[:n * 160].reshape(n, 160)
    db = (10 * np.log10((x ** 2).mean(1) + 1e-12)).astype(np.float32)
    np.save(cache, db)
    return db


class Voice:
    def __init__(self, wav):
        self.db = envelope(wav)
        self.thr = float(np.percentile(self.db, 85)) - 12
        v = self.db > self.thr
        # 30ms より短い途切れはつなぐ（子音の間の小さな谷）
        k = 3
        vv = v.copy()
        for i in range(1, k + 1):
            vv[:-i] |= v[i:]
            vv[i:] |= v[:-i]
        self.v = vv

    def idx(self, t):
        return max(0, min(len(self.v) - 1, int(round(t / HOP))))

    def tail_pause(self, t, limit=3.0):
        """t の手前で、声が最後に鳴っていた所から t までの秒数"""
        i = self.idx(t)
        j0 = max(0, i - int(limit / HOP))
        seg = self.v[j0:i]
        nz = np.nonzero(seg)[0]
        return None if len(nz) == 0 else round((len(seg) - 1 - nz[-1]) * HOP, 2)

    def head_pause(self, t, limit=3.0):
        """t から、次に声が鳴り始めるまでの秒数"""
        i = self.idx(t)
        seg = self.v[i:i + int(limit / HOP)]
        nz = np.nonzero(seg)[0]
        return None if len(nz) == 0 else round(nz[0] * HOP, 2)

    def ratio(self, s, e):
        a, b = self.idx(s), self.idx(e)
        return round(float(self.v[a:b].mean()), 2) if b > a else 0.0


class Asr:
    def __init__(self, path):
        segs = json.load(open(path))
        self.words = sorted(((w['start'], w['end'], w['word'].strip()) for s in segs for w in s.get('words', [])),
                            key=lambda x: x[0])
        self.starts = [w[0] for w in self.words]

    def text(self, s, e):
        """中心が [s, e) に入る語"""
        import bisect
        i = bisect.bisect_left(self.starts, s - 2)
        out = []
        while i < len(self.words) and self.words[i][0] < e + 2:
            a, b, w = self.words[i]
            if s <= (a + b) / 2 < e:
                out.append(w)
            i += 1
        return "".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('timeline')
    ap.add_argument('out')
    ap.add_argument('--track', default='A1')
    ap.add_argument('--wav', nargs='*', default=[])
    ap.add_argument('--asr', nargs='*', default=[])
    a = ap.parse_args()
    voices = {k: Voice(v) for k, v in (x.split('=', 1) for x in a.wav)}
    asrs = {k: Asr(v) for k, v in (x.split('=', 1) for x in a.asr)}
    d = json.load(open(a.timeline))
    fps = d['fps']
    rows = [r for r in d['tracks'][a.track] if not r['muted'] and (r['name'] or '') in voices]
    rows.sort(key=lambda r: r['start_ticks'])
    clips = [{'name': r['name'], 'tl_s': r['start_ticks'] / TPS, 'tl_e': r['end_ticks'] / TPS,
              'src_s': r['in_ticks'] / TPS, 'src_e': r['out_ticks'] / TPS} for r in rows]
    joins = []
    for p, n in zip(clips, clips[1:]):
        j = {'tl': round(n['tl_s'], 3), 'tl_gap': round(n['tl_s'] - p['tl_e'], 3),
             'prev': p['name'], 'next': n['name'], 'prev_out': round(p['src_e'], 3), 'next_in': round(n['src_s'], 3)}
        vp, vn = voices[p['name']], voices[n['name']]
        j['tail_kept'] = vp.tail_pause(p['src_e'])
        j['head_kept'] = vn.head_pause(n['src_s'])
        if p['name'] != n['name']:
            j['kind'] = '別の素材'
        else:
            jump = n['src_s'] - p['src_e']
            j['jump'] = round(jump, 3)
            if abs(jump) <= 1.5 / fps:
                j['kind'] = '分割だけ'
            elif jump > 0:
                j['kind'] = '前へ飛ぶ'
                j['removed_voice'] = vp.ratio(p['src_e'], n['src_s'])
                if p['name'] in asrs:
                    j['removed_text'] = asrs[p['name']].text(p['src_e'], n['src_s'])
            else:
                j['kind'] = '後ろへ戻る'
        if p['name'] in asrs:
            j['before_text'] = asrs[p['name']].text(max(p['src_s'], p['src_e'] - 4), p['src_e'])
        if n['name'] in asrs:
            j['after_text'] = asrs[n['name']].text(n['src_s'], min(n['src_e'], n['src_s'] + 4))
        joins.append(j)
    res = {'timeline': a.timeline, 'sequence': d['sequence'], 'fps': fps, 'track': a.track,
           'thresholds_db': {k: round(v.thr, 1) for k, v in voices.items()},
           'clips': len(clips), 'tl_end': round(clips[-1]['tl_e'], 2) if clips else 0,
           'src_used': round(sum(c['src_e'] - c['src_s'] for c in clips), 1), 'joins': joins}
    json.dump(res, open(a.out, 'w'), ensure_ascii=False, indent=1)
    kinds = {}
    for j in joins:
        kinds[j['kind']] = kinds.get(j['kind'], 0) + 1
    print(a.out, len(clips), 'clips', kinds)


if __name__ == '__main__':
    main()
