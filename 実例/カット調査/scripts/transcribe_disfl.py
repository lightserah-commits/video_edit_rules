"""切る前の素材を、フィラーも書き起こすように促して文字起こしする（語ごとの時刻つき）。08 のフィラーの調査用（2026-10-20）。
transcribe_raw.py（ヒント無し）ではフィラーがほとんど出ないので、AI動画編集 r2 の確かめで使った言葉の並びをプロンプトに渡す。

使い方:
  ~/Desktop/video_edit_rules/env/bin/python 実例/カット調査/scripts/transcribe_disfl.py <素材> <名前> <作業フォルダ> <出力フォルダ>
出力: <出力フォルダ>/disfl_<名前>.json（区切りごと。words に [始め, 終わり, 文字]。時刻は素材の秒）
"""
import json, os, subprocess, sys, wave
os.environ['HF_HUB_OFFLINE'] = '1'
import mlx_whisper
import numpy as np
MODEL = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), 'models', 'whisper-large-v3-turbo')
PROMPT = 'えー、あの、えっと、ど、どこに、その、まあ、なんか、はい。えっとですね、あのー、こ、こういう。'
src, name, work, out = sys.argv[1:5]
os.makedirs(work, exist_ok=True)
os.makedirs(out, exist_ok=True)
wav = os.path.join(work, f'{name}.wav')
if not os.path.exists(wav):
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', src, '-vn', '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', wav], check=True)
with wave.open(wav) as f:
    a = np.frombuffer(f.readframes(f.getnframes()), dtype=np.int16).astype(np.float32) / 32768
segs = []
for st in range(0, len(a) // 16000 + 1, 120):
    r = mlx_whisper.transcribe(a[st * 16000:(st + 120) * 16000], path_or_hf_repo=MODEL, language='ja', word_timestamps=True,
                               condition_on_previous_text=False, initial_prompt=PROMPT, verbose=None)
    for s in r['segments']:
        segs.append({'start': round(s['start'] + st, 2), 'end': round(s['end'] + st, 2), 'text': s['text'],
                     'words': [[round(w['start'] + st, 2), round(w['end'] + st, 2), w['word']] for w in s.get('words', [])]})
    print(name, st, flush=True)
json.dump(segs, open(os.path.join(out, f'disfl_{name}.json'), 'w'), ensure_ascii=False, indent=0)
print('done', name)
