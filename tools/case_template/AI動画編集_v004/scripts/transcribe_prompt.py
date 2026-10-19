"""2回目の文字起こし（固有名詞のプロンプトつき）。1回目（実例/カット調査/scripts/transcribe_raw.py。ヒント無し）と突き合わせて、聞き取りの怪しい所を直す材料にする。
  ~/Desktop/video_edit_rules/env/bin/python scripts/transcribe_prompt.py
出力 analysis/asr/asr_camera_p.json（時刻は素材の秒）。途中は analysis/asr/_work/p_*.json に残す（止まっても続きから）
  注意：プロンプトに「どうも アドネス株式会社の三上です」のような文を入れない（冒頭の空耳として出て、本物と区別できなくなる。環境設定 v002 の分かったこと）。固有名詞を並べるだけにする
  （1015 の scripts/transcribe_prompt.py を写して、固有名詞をこの案件に変えた。camera.wav は make_media.py が作る通しの声）
"""
import json
import os
import wave

os.environ['HF_HUB_OFFLINE'] = '1'
import mlx_whisper  # noqa: E402
import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
A = os.path.join(HERE, '..', 'analysis', 'asr')
MODEL = os.path.expanduser('~/Desktop/video_edit_rules/models/whisper-large-v3-turbo')
PROMPT = ('Claude、Claude Code、Opus、Opus 5.5、エフォート、Ultracode、Premiere Pro、プレミア、XML、XMLファイル、タイムライン、シーケンス、'
          'コンピュータユース、Addness、アドネス、アドネス株式会社、三上、創太、こういち、アンディ、強調テロップ、SE、スケール縮小、'
          '図解、注釈、テロップ、字幕、判断フロー、演出パターン、ズーム、シュール、ゴージャス、スキル、コンテキスト、プロジェクトマネージャー、'
          'ポン出し、ワンポチ、情報商材、クライアントワーク、公式LINE、概要欄、プレゼント、サムネイル、認定パートナー、ドラム式洗濯機、'
          'みじん切り、ChatGPT、Codex、Dots、Loom、Finder、YouTube。')
with wave.open(os.path.join(A, '_work', 'camera.wav')) as f:
    a = np.frombuffer(f.readframes(f.getnframes()), dtype=np.int16).astype(np.float32) / 32768
CH = 240
segs = []
for st in range(0, len(a) // 16000 + 1, CH):
    cache = os.path.join(A, '_work', f'p_{st:05d}.json')
    if os.path.exists(cache):
        r = json.load(open(cache))
    else:
        r = mlx_whisper.transcribe(a[st * 16000:(st + CH) * 16000], path_or_hf_repo=MODEL, language='ja', word_timestamps=True,
                                   condition_on_previous_text=False, initial_prompt=PROMPT, verbose=None)
        json.dump(r, open(cache, 'w'), ensure_ascii=False)
    for s in r['segments']:
        s = {k: s[k] for k in ('start', 'end', 'text', 'words') if k in s}
        s['start'] += st
        s['end'] += st
        for w in s.get('words', []):
            w['start'] += st
            w['end'] += st
        segs.append(s)
    print(st, flush=True)
json.dump(segs, open(os.path.join(A, 'asr_camera_p.json'), 'w'), ensure_ascii=False)
print('done', len(segs))
