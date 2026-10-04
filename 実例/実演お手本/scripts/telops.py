"""0.5秒ごとの文字認識から、テロップ（同じ位置に同じ文字が続く間）を作り、色の割合を付ける（読むだけ）。
使い方: python telops.py <名前> <動画> → telops_<名前>.json
"""
import json, glob, re, sys, subprocess, difflib, numpy as np
name, video = sys.argv[1], sys.argv[2]
STEP = 0.5; W, H = 480, 270
frames = {}
for f in sorted(glob.glob(f'ocr/{name}_*.json')):
    for k, v in json.load(open(f)).items():
        n = int(re.search(r'(\d+)\.jpg$', k).group(1)); frames[n] = [i for i in v if i['h'] >= 0.045 and i['conf'] >= 0.3]
N = max(frames)
norm = lambda s: re.sub(r'[\s　]', '', s).lower()
# 色を見るための縮めた画像（2fps、480x270）
raw = f'work/{name}_480.rgb'
import os
if not os.path.exists(raw):
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', video, '-vf', f'fps=2,scale={W}:{H}', '-f', 'rawvideo', '-pix_fmt', 'rgb24', raw], check=True)
img = np.memmap(raw, dtype=np.uint8, mode='r').reshape(-1, H, W, 3)
def colors(n, b):
    if n - 1 >= len(img): return {}
    x0, y0 = int(b['x'] * W), int(b['y'] * H); x1, y1 = int((b['x'] + b['w']) * W) + 1, int((b['y'] + b['h']) * H) + 1
    p = img[n - 1, max(0, y0):y1, max(0, x0):x1].reshape(-1, 3).astype(np.float32) / 255
    if len(p) == 0: return {}
    mx, mn = p.max(1), p.min(1); s = (mx - mn) / (mx + 1e-6); v = mx
    r, g, bl = p[:, 0], p[:, 1], p[:, 2]
    hue = np.degrees(np.arctan2(np.sqrt(3) * (g - bl), 2 * r - g - bl)) % 360
    sat = (s > .45) & (v > .35)
    return {'red': float(np.mean(sat & ((hue < 20) | (hue > 340)))), 'yellow': float(np.mean(sat & (hue >= 35) & (hue < 70))),
            'blue': float(np.mean(sat & (hue >= 190) & (hue < 260))), 'white': float(np.mean((s < .15) & (v > .85))),
            'dark': float(np.mean(v < .2))}
open_ = []; done = []
for n in range(1, N + 1):
    cur = frames.get(n, [])
    used = set()
    for ev in open_:
        best = None
        for j, b in enumerate(cur):
            if j in used: continue
            if abs(b['y'] - ev['y']) > .04 or abs(b['x'] - ev['x']) > .15: continue
            r = difflib.SequenceMatcher(None, norm(b['text']), ev['key']).ratio()
            if r >= .7 and (best is None or r > best[0]): best = (r, j)
        if best:
            used.add(best[1]); b = cur[best[1]]; ev['last'] = n; ev['texts'].append(b['text'])
            if len(ev['col']) < 3: ev['col'].append(colors(n, b))
        else:
            ev['gap'] = ev.get('gap', 0) + 1
    # 1コマだけ読めなかった時は続ける
    still = []
    for ev in open_:
        if ev['last'] == n or ev.get('gap', 0) <= 1: still.append(ev)
        else: done.append(ev)
    open_ = still
    for j, b in enumerate(cur):
        if j in used: continue
        open_.append({'first': n, 'last': n, 'x': b['x'], 'y': b['y'], 'w': b['w'], 'h': b['h'], 'key': norm(b['text']), 'texts': [b['text']], 'col': [colors(n, b)]})
done += open_
out = []
for ev in done:
    t = max(set(ev['texts']), key=ev['texts'].count)
    col = {k: round(float(np.mean([c.get(k, 0) for c in ev['col'] if c])), 3) for k in ['red', 'yellow', 'blue', 'white', 'dark']}
    out.append({'start': (ev['first'] - 1) * STEP, 'end': ev['last'] * STEP, 'x': round(ev['x'], 3), 'y': round(ev['y'], 3), 'w': round(ev['w'], 3), 'h': round(ev['h'], 3), 'text': t, 'col': col})
out.sort(key=lambda e: e['start'])
json.dump(out, open(f'telops_{name}.json', 'w'), ensure_ascii=False, indent=0)
print(name, '読めたコマ', len(frames), 'テロップ', len(out))
