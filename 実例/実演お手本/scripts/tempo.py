"""完成した動画の時刻での語の並びから、テンポ（間・話している割合・1分あたりの文字数）を出す（読むだけ）。"""
import json, sys, statistics as st, re
def load(fn):
    d = json.load(open(fn))
    if isinstance(d, dict): return d['duration'], [tuple(w) for w in d['words']]
    W = [(w['start'], w['end'], w['word']) for s in d for w in s.get('words', [])]
    return W[-1][1], W
def stats(label, fn, skip=0):
    dur, W = load(fn)
    W = [w for w in W if w[0] >= skip and re.sub(r'\s', '', w[2])]
    dur -= skip
    gaps = [b[0] - a[1] for a, b in zip(W, W[1:]) if b[0] - a[1] > 0]
    big = [g for g in gaps if g >= .15]
    cov = 0; last = 0
    for s, e, _ in W:
        s = max(s, last)
        if e > s: cov += e - s; last = e
    chars = sum(len(re.sub(r'\s', '', w[2])) for w in W)
    p = lambda xs, q: sorted(xs)[int(len(xs) * q)] if xs else 0
    print(f"| {label} | {dur/60:.1f}分 | {100*cov/dur:.0f}% | {chars/dur*60:.0f} | {st.median(big):.2f} | {p(big,.9):.2f} | {sum(g>=.5 for g in gaps)/dur*60:.1f} | {sum(g>=1.0 for g in gaps)/dur*60:.2f} |")
print('| 動画 | 長さ | 話している割合 | 1分あたりの文字数 | 間（0.15秒以上）の中央 | 間の90% | 0.5秒以上の間（1分あたり） | 1秒以上の間（1分あたり） |')
print('|---|---|---|---|---|---|---|---|')
for a in sys.argv[1:]:
    lab, fn = a.split('=', 1)
    stats(lab, fn)
