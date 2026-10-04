"""タイムラインのデータ（dump_timeline の JSON）と素材の文字起こしから、完成した動画の時刻での語の並びを作る（読むだけ）。
使い方: python3 words_timeline.py <timeline.json> <出力.json> 素材名=asr.json [素材名=asr.json ...]
"""
import json, sys
tl = json.load(open(sys.argv[1])); out = sys.argv[2]
asr = {}
for a in sys.argv[3:]:
    k, v = a.split('=', 1)
    asr[k] = [(w['start'], w['end'], w['word']) for s in json.load(open(v)) for w in s.get('words', [])]
TPS = 254016000000; ft = tl['frame_ticks']
res = []
for r in tl['tracks']['A1']:
    if r['muted'] or r['name'] not in asr: continue
    s0 = r['in_ticks'] / TPS; s1 = r['out_ticks'] / TPS if r.get('out_ticks') else s0 + (r['end_f'] - r['start_f']) * ft / TPS
    t0 = r['start_f'] * ft / TPS
    for ws, we, w in asr[r['name']]:
        # 語の真ん中がクリップの中にあるものだけ
        m = (ws + we) / 2
        if s0 <= m < s1:
            res.append((t0 + max(ws, s0) - s0, t0 + min(we, s1) - s0, w))
res.sort()
json.dump({'duration': tl['end_f'] * ft / TPS, 'words': res}, open(out, 'w'), ensure_ascii=False)
print(out, len(res))
