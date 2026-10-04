"""強調が出た瞬間（30fps のコマ）と、強調に書いた最初の言葉が聞こえ始める瞬間（文字起こし＋波形）の差を測る（読むだけ・音は出さない）。
使い方: python emph_timing.py <名前> <動画> <asr.json> <16k.wav>
"""
import json, sys, re, subprocess, wave, numpy as np, statistics as st
name, video, asrp, wavp = sys.argv[1:5]
FPS = 30000 / 1001
T = json.load(open(f'telops_{name}_kind.json'))
KINDS = ['赤黄', '金', '赤い字幕（要点の一文）', 'ツッコミ・強い一言（大）', '白黒（シュール・明朝ほか）', '赤い帯', '青い帯・青い札', '字幕（青）']
W = [(w['start'], re.sub(r'\s', '', w['word'])) for s in json.load(open(asrp)) for w in s.get('words', []) if re.sub(r'\s', '', w['word'])]
with wave.open(wavp) as f: x = np.frombuffer(f.readframes(f.getnframes()), dtype=np.int16).astype(np.float32) / 32768
HOP = 160; n = len(x) // HOP
db = 10 * np.log10(np.mean(x[:n * HOP].reshape(n, HOP) ** 2, axis=1) + 1e-10)
hp = np.diff(x, prepend=0); dbh = 10 * np.log10(np.mean(hp[:n * HOP].reshape(n, HOP) ** 2, axis=1) + 1e-10)
norm = lambda s: re.sub(r'[\s\r　、。！!？?…「」『』｢｣（）()・/／〜~ｗw↑←→⬆︎※〈〉＜＞<>【】]', '', s).lower()
def appear(e):
    s = e['start']; t0 = max(0, s - .7)
    X, Y, Wd, Hd = [int(v) for v in (e['x'] * 1280, e['y'] * 720, e['w'] * 1280, e['h'] * 720)]
    Wd = max(16, min(Wd, 1280 - X)); Hd = max(16, min(Hd, 720 - Y))
    r = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{t0:.3f}', '-i', video, '-t', '1.0', '-vf', f'crop={Wd}:{Hd}:{X}:{Y},scale=96:24,format=gray', '-f', 'rawvideo', '-'], capture_output=True)
    a = np.frombuffer(r.stdout, np.uint8).reshape(-1, 24, 96).astype(np.float32)
    if len(a) < 10: return None
    ref = a[min(len(a) - 1, int((s + .2 - t0) * FPS))]
    d = np.abs(a - ref).mean(axis=(1, 2))
    k0 = int(max(0, (s - .6 - t0)) * FPS); k1 = int((s + .05 - t0) * FPS)
    seg = d[k0:k1 + 1]
    if len(seg) == 0 or seg.max() < 8: return None
    th = seg.max() * .4
    for k in range(len(seg)):
        if seg[k] < th: return t0 + (k0 + k) / FPS
    return None
def first_word(t, text):
    key = norm(text)[:2]
    if len(key) < 2: return None
    best = None
    for i, (ws, w) in enumerate(W):
        if abs(ws - t) > 3: continue
        if ''.join(v for _, v in W[i:i + 4]).lower().startswith(key):
            if best is None or abs(ws - t) < abs(best - t): best = ws
    return best
def wave_onset(w):
    i0, i1 = int((w - .25) * 100), int((w + .25) * 100)
    e = db[max(0, i0):i1]
    if len(e) < 10: return w
    m = int(np.argmin(e[:len(e) // 2 + 5])); lo, hi = e[m], e[m:].max()
    for k in range(m, len(e)):
        if e[k] > lo + .6 * (hi - lo): return (max(0, i0) + k) / 100
    return w
def se_rise(t):
    i = int(t * 100); a = dbh[max(0, i - 15):i - 2].mean(); b = dbh[i:i + 10].max()
    return b - a
res = {}
def is_second_line(e):
    # 同じ種類のテロップが、すぐ上に同じ時刻（0.5秒以内）から出ていれば2行目
    return any(o is not e and o['kind'] == e['kind'] and abs(o['start'] - e['start']) <= .5 and 0 < e['y'] - o['y'] < .2 for o in T)
for e in T:
    if e['kind'] not in KINDS or e['h'] < .06 or len(norm(e['text'])) < 2 or is_second_line(e): continue
    ap = appear(e)
    if ap is None: continue
    fw = first_word(ap, e['text'])
    if fw is None: continue
    on = wave_onset(fw)
    res.setdefault(e['kind'], []).append({'t': ap, 'text': e['text'], 'asr': ap - fw, 'wave': ap - on, 'se': se_rise(ap)})
json.dump(res, open(f'timing_{name}.json', 'w'), ensure_ascii=False, indent=0)
print('| 種類 | 測れた数 | 書いた最初の言葉より0.2秒以上早く出る | ±0.2秒以内 | 0.3秒以上遅く出る | 差の中央（＋は言葉より後） |')
print('|---|---|---|---|---|---|')
for k in KINDS:
    v = [r['wave'] for r in res.get(k, [])]
    if not v: continue
    print(f"| {k} | {len(v)} | {sum(a < -.2 for a in v)}（{100*sum(a < -.2 for a in v)/len(v):.0f}%） | {sum(abs(a) <= .2 for a in v)}（{100*sum(abs(a) <= .2 for a in v)/len(v):.0f}%） | {sum(a > .3 for a in v)} | {st.median(v):+.2f}秒 |")
