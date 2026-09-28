"""切る前の素材を文字起こしする（語ごとの時刻つき）。完成版のカット調査用。
Codex が使っていた mlx_whisper の環境とモデル（large-v3-turbo）をそのまま使う（新しく入れるものは無い）。

使い方:
  ~/Documents/Codex/2026-09-17/new-chat/work/asr-env/bin/python 実例/カット調査/scripts/transcribe_raw.py <素材> <名前> <作業フォルダ> <出力フォルダ>
出力: <出力フォルダ>/asr_<名前>.json（区切りごと。words に語ごとの start/end。時刻は素材の秒）
"""
import json
import os
import subprocess
import sys
import wave

os.environ['HF_HUB_OFFLINE'] = '1'
import mlx_whisper  # noqa: E402
import numpy as np  # noqa: E402

MODEL = '/Users/yoshizawakouichi/Documents/Codex/2026-09-08/new-chat-3/work/transcription_correct/model'
CHUNK = 300

src, name, work, out = sys.argv[1:5]
os.makedirs(work, exist_ok=True)
os.makedirs(out, exist_ok=True)
wav = os.path.join(work, f'{name}.wav')
if not os.path.exists(wav):
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', src, '-vn', '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', wav], check=True)
with wave.open(wav) as f:
    a = np.frombuffer(f.readframes(f.getnframes()), dtype=np.int16).astype(np.float32) / 32768
segs = []
for start in range(0, len(a) // 16000 + 1, CHUNK):
    cache = os.path.join(work, f'{name}_{start:05d}.json')
    if os.path.exists(cache):
        r = json.load(open(cache))
    else:
        r = mlx_whisper.transcribe(a[start * 16000:(start + CHUNK) * 16000], path_or_hf_repo=MODEL, language='ja',
                                   word_timestamps=True, condition_on_previous_text=False, verbose=None)
        json.dump(r, open(cache, 'w'), ensure_ascii=False)
    for s in r['segments']:
        s = {k: s[k] for k in ('start', 'end', 'text', 'words', 'no_speech_prob', 'avg_logprob') if k in s}
        s['start'] += start
        s['end'] += start
        for w in s.get('words', []):
            w['start'] += start
            w['end'] += start
        segs.append(s)
    print(f'{name}: {min(start + CHUNK, len(a) / 16000):.0f}/{len(a) / 16000:.0f}s', flush=True)
json.dump(segs, open(os.path.join(out, f'asr_{name}.json'), 'w'), ensure_ascii=False, indent=1)
print(f'{name}: done {len(segs)} segments', flush=True)
