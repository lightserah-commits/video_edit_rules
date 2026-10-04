"""波形で「声の間」を測る（読むだけ・音は出さない）。
完成版の音（BGM 入り）：声が、その辺りの声の大きさより 15dB 以上下がった所（BGM だけの所）を間とする。
タイムライン（素材の声をつなぐ）：同じ決まりで、つないだ声の音で測る。
使い方: python voice_gaps.py ラベル=mix:音.wav  /  ラベル=tl:timeline.json:素材名=音.wav[,素材名=音.wav]
"""
import json, sys, wave, numpy as np
import os
K = float(os.environ.get("K", "0.35"))
SR = 16000; HOP = 320  # 20ms
def read(p):
    with wave.open(p) as f: return np.frombuffer(f.readframes(f.getnframes()), dtype=np.int16).astype(np.float32) / 32768
def assemble(tlp, srcs):
    d = json.load(open(tlp)); fps = d['fps']; TPS = 254016000000
    out = np.zeros(int(d['end_f'] / fps * SR) + SR, np.float32)
    for r in d['tracks']['A1']:
        if r['muted'] or r['name'] not in srcs: continue
        a = srcs[r['name']]; s0 = int(r['in_ticks'] / TPS * SR); n = int((r['end_f'] - r['start_f']) / fps * SR); t0 = int(r['start_f'] / fps * SR)
        seg = a[s0:s0 + n]; out[t0:t0 + len(seg)] = seg
    return out
def gaps(x):
    n = len(x) // HOP
    db = 10 * np.log10(np.mean(x[:n * HOP].reshape(n, HOP) ** 2, axis=1) + 1e-10)
    # その辺り（前後7.5秒）の一番静かな大きさ（BGM か部屋の音）と声の大きさから、間のしきい値を決める
    W = 750; idx = np.arange(0, n, 50)
    fl = [np.percentile(db[max(0, i - W // 2):i + W // 2], 10) for i in idx]
    sp = [np.percentile(db[max(0, i - W // 2):i + W // 2], 90) for i in idx]
    fl = np.interp(np.arange(n), idx, fl); sp = np.interp(np.arange(n), idx, sp)
    quiet = db < fl + K * (sp - fl)
    runs = []; i = 0
    while i < n:
        if quiet[i]:
            j = i
            while j < n and quiet[j]: j += 1
            if (j - i) * HOP / SR >= .15: runs.append(((i * HOP) / SR, (j - i) * HOP / SR))
            i = j
        else: i += 1
    return n * HOP / SR, runs
print('| 動画 | 長さ | 間（0.15秒以上）の中央 | 間の90% | 0.5秒以上の間（1分あたり） | 1秒以上の間（1分あたり） | 3秒以上の無言（1分あたり） |')
print('|---|---|---|---|---|---|---|')
for arg in sys.argv[1:]:
    lab, spec = arg.split('=', 1)
    kind, rest = spec.split(':', 1)
    if kind == 'mix': x = read(rest)
    else:
        tlp, ss = rest.split(':', 1)
        x = assemble(tlp, {k: read(v) for k, v in (p.split('=', 1) for p in ss.split(','))})
    dur, R = gaps(x); g = sorted(r[1] for r in R if r[1] < 3)
    m = dur / 60
    print(f"| {lab} | {m:.1f}分 | {np.median(g):.2f} | {g[int(len(g)*.9)]:.2f} | {sum(v>=.5 for v in g)/m:.1f} | {sum(v>=1 for v in g)/m:.2f} | {sum(r[1]>=3 for r in R)/m:.2f} |")
    json.dump(R, open(f'gaps_{lab.split()[0]}.json', 'w'))
