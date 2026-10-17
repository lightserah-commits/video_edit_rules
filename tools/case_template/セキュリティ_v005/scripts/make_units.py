"""文字起こし（asr_camera.json）を「元の字幕」にあたる区切り（unit）に分ける。カット・テロップの番号の土台。
  区切り：文字起こしの区切り（segment）ごと。その中で「。？！」の後と、語と語の間が 0.4秒以上空いた所でも分ける。
  開始・終了は語の時刻（素材＝カメラの秒）。声の大きさ（10ms ごと）も作って analysis/camera_env.npy に置く。
  出力 analysis/units.json・analysis/units.txt（番号|開始|長さ|文字）
  ~/Desktop/video_edit_rules/env/bin/python scripts/make_units.py（セキュリティについて：asr_camera.json は asr_img1320.json に part を付けた写し。素材1本なので素材の秒＝通しの秒）
"""
import json, os, wave
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
A = os.path.join(HERE, '..', 'analysis')
asr = json.load(open(os.path.join(A, 'asr', 'asr_camera.json')))
envp = os.path.join(A, 'camera_env.npy')
if not os.path.exists(envp):
    with wave.open(os.path.join(A, 'asr', '_work', 'camera.wav')) as f:
        a = np.frombuffer(f.readframes(f.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    n = len(a) // 160
    db = (10 * np.log10((a[:n * 160].reshape(n, 160) ** 2).mean(1) + 1e-12)).astype(np.float32)
    np.save(envp, db)
db = np.load(envp)
units = []
for si, s in enumerate(asr):
    ws = [w for w in s.get('words', []) if w['word'].strip()]
    if not ws:
        continue
    cur = [ws[0]]
    for w in ws[1:]:
        p = cur[-1]
        if p['word'].strip()[-1:] in '。？！?!' or w['start'] - p['end'] >= 0.4:
            units.append(cur); cur = [w]
        else:
            cur.append(w)
    units.append(cur)
out = []
for i, ws in enumerate(units):
    text = ''.join(w['word'] for w in ws).strip()
    st, en = ws[0]['start'], ws[-1]['end']
    seg = db[int(st * 100):int(en * 100) + 1]
    lv = float(np.percentile(seg, 90)) if len(seg) else -99
    out.append({'u': i, 'start': round(st, 3), 'end': round(en, 3), 'text': text, 'lv90': round(lv, 1),
                'prob': round(float(np.mean([w.get('probability', 1) for w in ws])), 2),
                'words': [[round(w['start'], 3), round(w['end'], 3), w['word']] for w in ws]})
json.dump(out, open(os.path.join(A, 'units.json'), 'w'), ensure_ascii=False)
with open(os.path.join(A, 'units.txt'), 'w') as f:
    for u in out:
        f.write(f"{u['u']}|{u['start']:.2f}|{u['end'] - u['start']:.1f}|{u['lv90']:.0f}|{u['text']}\n")
print(len(out), 'units; env thr85-12 =', round(float(np.percentile(db, 85)) - 12, 1))
