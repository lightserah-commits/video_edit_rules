"""テロップを位置・大きさ・色で種類に分け、種類ごとの切り抜きを並べた画像を作る（読むだけ）。
使い方: python classify.py <名前> → telops_<名前>_kind.json と sheets/<名前>_<種類>.jpg
"""
import json, sys, re, subprocess, os, random
name = sys.argv[1]
T = json.load(open(f'telops_{name}.json'))
def kind(e):
    c = e['col']; t = e['text']; x, y, w, h = e['x'], e['y'], e['w'], e['h']
    sat = c['red'] + c['yellow'] + c['blue']
    if re.match(r'^\s*[QＱ][:：]', t): return '問い（Q:）'
    if t.strip().startswith(('※', '＊')): return '※注釈'
    if re.search(r'[↑←⬆]', t): return '↑←の一言'
    if y < .16 and (x + w) > .55 and sat < .1: return '右上の現在地'
    if c['red'] >= .5 and c['white'] >= .15: return '赤い帯'
    if c['blue'] >= .45 and c['white'] >= .15 and c['dark'] < .1: return '青い帯・青い札'
    if c['red'] >= .25 and c['yellow'] >= .06: return '赤黄'
    if c['yellow'] >= .2 and c['red'] < .15: return '金'
    if c['red'] >= .15 and c['yellow'] < .06: return 'ツッコミ・強い一言（大）' if h >= .14 else '赤い字幕（要点の一文）'
    if c['blue'] >= .15 and y >= .7: return '字幕（青）'
    if c['dark'] >= .35 and c['white'] >= .1 and sat < .08: return '白黒（シュール・明朝ほか）'
    if c['white'] >= .4 and c['dark'] < .1 and sat < .05: return '画面の文字'
    return 'その他'
for e in T: e['kind'] = kind(e)
json.dump(T, open(f'telops_{name}_kind.json', 'w'), ensure_ascii=False, indent=0)
from collections import Counter
c = Counter(e['kind'] for e in T); print(name, c.most_common())
os.makedirs('sheets', exist_ok=True)
random.seed(0)
for k in c:
    xs = [e for e in T if e['kind'] == k]
    xs = random.sample(xs, min(12, len(xs)))
    ins = []; fl = []
    for i, e in enumerate(xs):
        n = int(e['start'] / .5) + 2
        f = f'frames/{name}/{n:05d}.jpg'
        if not os.path.exists(f): continue
        X, Y, Wd, Hd = [int(v) for v in (e['x'] * 1280 - 10, e['y'] * 720 - 6, e['w'] * 1280 + 20, e['h'] * 720 + 12)]
        X, Y = max(0, X), max(0, Y); Wd = min(Wd, 1280 - X); Hd = min(Hd, 720 - Y)
        ins += ['-i', f]; fl.append(f'[{len(fl)}:v]crop={Wd}:{Hd}:{X}:{Y},scale=640:80:force_original_aspect_ratio=decrease,pad=640:80:(ow-iw)/2:(oh-ih)/2:color=gray[v{len(fl)}]')
    if not fl: continue
    lay = '|'.join(f'0_{80*i}' for i in range(len(fl)))
    graph = ';'.join(fl) + ';' + ''.join(f'[v{i}]' for i in range(len(fl))) + (f'xstack=inputs={len(fl)}:layout={lay}' if len(fl) > 1 else 'null')
    subprocess.run(['ffmpeg', '-v', 'error', '-y'] + ins + ['-filter_complex', graph, '-frames:v', '1', f'sheets/{name}_{k}.jpg'])
