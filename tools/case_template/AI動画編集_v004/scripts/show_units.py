"""区切りを、2回目の文字起こし・マイクの差の話者の目安と並べて出す。 python3 scripts/show_units.py 開始 終了 [開始 終了 …]"""
import json, bisect, os, sys
A = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'analysis')
U = json.load(open(os.path.join(A, 'units.json')))
P = json.load(open(os.path.join(A, 'asr', 'asr_camera_p.json')))
W = sorted((w['start'], w['end'], w['word']) for s in P for w in s.get('words', []))
ws = [w[0] for w in W]
R = {int(k): v for k, v in json.load(open(os.path.join(A, 'speaker', 'micratio.json'))).items()}
args = list(map(int, sys.argv[1:]))
for a, b in zip(args[::2], args[1::2]):
    for u in U[a:b + 1]:
        s, e = u['start'], u['end']; i = bisect.bisect_left(ws, s - 0.15)
        t = ''.join(w[2] for w in W[i:] if w[0] < e - 0.05 and w[1] > s).strip()
        r = R.get(u['u']); tag = '?' if r is None else ('み' if r >= 3.5 else ('聞' if r < 1.5 else '?'))
        alt = '' if t.replace(' ', '') == u['text'].replace(' ', '') else f'  〔{t}〕'
        print(f"{u['u']}|{int(s // 60)}:{s % 60:04.1f}|{tag}|{u['text']}{alt}")
    print('----')
