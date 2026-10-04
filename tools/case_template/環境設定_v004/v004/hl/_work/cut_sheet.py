"""カットの切り替わりの前後のコマを並べる（二重写し・はみ出しの確認用）と、要所のコマの一覧。hl/ で python3 _work/cut_sheet.py"""
import json, subprocess
p = json.load(open('_work/plan.json'))
F = 30000 / 1001


def sheet(fs, out, cols=6, w=320, h=180):
    ins = []
    for f in fs:
        ins += ['-i', f'_work/frames/{f:05d}.jpg']
    k = len(fs)
    filt = "".join(f"[{i}:v]scale={w}:{h}[s{i}];" for i in range(k)) + "".join(f"[s{i}]" for i in range(k)) + \
        f"xstack=inputs={k}:layout=" + "|".join(f"{(i % cols) * w}_{(i // cols) * h}" for i in range(k))
    subprocess.run(['ffmpeg', '-v', 'error', '-y', *ins, '-filter_complex', filt, out], check=True)


cuts = [round(c['at'] * F) for c in p['clips'][1:]] + [round(p['t_title'] * F)]
fs = []
for n in cuts:
    fs += [n - 1, n, n + 1]
sheet(fs, 'check/cuts_sheet.jpg')
key = list(range(8, p['frames'], 24))
sheet(key, 'check/要所_1秒ごと.jpg', cols=6, w=480, h=270)
print(len(fs), "cut frames,", len(key), "key frames")
