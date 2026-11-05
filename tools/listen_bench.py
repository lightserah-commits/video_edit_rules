#!/usr/bin/env python3
"""音を聞ける AI の聞き分けテスト：完成版の切り口の音と、わざと崩した音を Gemini に聞かせて、当たる割合を数える。

  make ：完成版の切り口から音の組を作る（お手本・語尾を削る・言葉の頭を削る・間を足す）
  run  ：音を Gemini に送って答えを集める（止まっても続きから。キーは Mac のキーチェーンの gemini_api_key）
  score：崩しの種類と大きさごとに当たる割合を出す

  送るのは完成版に残っている部分の音だけ。崩す時は削るだけで、足す間も完成版に残っている静かな所の音を使う。
  編集者が切った所の音は作らない（make の中で確かめて止める）。音は鳴らさない。全部未聴取。

  使い方：
    env/bin/python tools/listen_bench.py make --out <音を置くフォルダ>
    env/bin/python tools/listen_bench.py run --pairs <音を置くフォルダ>/pairs.json --results 結果.jsonl --limit 5
    env/bin/python tools/listen_bench.py score --pairs <音を置くフォルダ>/pairs.json --results 結果.jsonl --out 報告.md
"""
import argparse
import base64
import json
import math
import os
import random
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

import numpy as np
from scipy.io import wavfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cut_bench import DATA, REFS, TPS  # noqa: E402

SR = 48000
FRAME = SR // 100               # 声の大きさを見る幅（10ms）
SOURCES = {
    '1': '/Volumes/Extreme SSD/完成版の素材/1本目_ガチでAI/IMG_1063.MOV.mov',
    '2': '/Volumes/Extreme SSD/完成版の素材/2本目_AI時代/IMG_1598.MOV',
}
CONTEXT = 3.0                   # 切り口の前後に付ける秒
VOICE_DB = 12.0                 # 部屋の音より何 dB 大きければ声と見るか
LEVELS = {'tail': (50, 100, 200), 'head': (50, 100, 200), 'gap': (100, 200, 400)}
KIND_JA = {'tail': '語尾を削る', 'head': '言葉の頭を削る', 'gap': '間を足す', 'same': '同じ音（対照）'}
BASE = 'https://generativelanguage.googleapis.com/v1beta'

PROMPT_PAIR = """これは YouTube のトーク動画の音声です。音声 A と音声 B は、同じ話の同じ箇所をカット編集したもので、長さは約6秒です。
カットのつなぎ目の仕上がりが違う可能性があります。語尾が切れている、言葉の頭が欠けている、間が不自然に長いなどを、音をよく聞いて判断してください。
話の中身ではなく音の聞こえ方で判断し、編集として自然に聞こえる方を A か B で答えてください。reason には聞こえた違いを短く書いてください。"""

SCHEMA_PAIR = {
    'type': 'OBJECT',
    'properties': {'choice': {'type': 'STRING', 'enum': ['A', 'B']}, 'reason': {'type': 'STRING'}},
    'required': ['choice', 'reason'],
}


def load_clips(ref):
    d = json.load(open(os.path.join(DATA, ref['tl'])))
    lo, hi = ref['tl_range']
    clips = []
    for c in d['tracks']['A1']:
        if c.get('muted') or c['name'] != ref['src']:
            continue
        t0, t1 = c['start_ticks'] / TPS, c['end_ticks'] / TPS
        a, b = c['in_ticks'] / TPS, c['out_ticks'] / TPS
        if t0 < lo or t0 >= hi or abs((b - a) - (t1 - t0)) > 0.02:
            continue
        clips.append({'t0': t0, 't1': t1, 'a': a, 'b': b})
    clips.sort(key=lambda c: c['t0'])
    return clips


def extract_wav(ref_id, out):
    path = os.path.join(out, '_src', f'ref{ref_id}.wav')
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', SOURCES[ref_id], '-vn', '-map', '0:a:0', '-ac', '1',
                        '-ar', str(SR), '-c:a', 'pcm_s16le', path], check=True)
    return wavfile.read(path, mmap=True)[1]


def frames_db(x):
    n = len(x) // FRAME
    if n == 0:
        return np.zeros(0)
    f = np.asarray(x[:n * FRAME], dtype=np.float64).reshape(n, FRAME)
    return 10 * np.log10((f ** 2).mean(axis=1) + 1.0)


def contiguous(p, n):
    return abs(p['t1'] - n['t0']) < 0.002


def find_seams(clips, x):
    """両側が声で、語尾と言葉の頭を削ると声にかかる切り口だけを選ぶ"""
    seams = []
    for i in range(len(clips) - 1):
        p, n = clips[i], clips[i + 1]
        if not contiguous(p, n) or n['a'] - p['b'] < 0.2:
            continue
        if p['b'] - p['a'] < 1.5 or n['b'] - n['a'] < 1.5:
            continue
        s0 = int(max(0.0, p['b'] - 10) * SR)
        room = float(np.percentile(frames_db(x[s0:int((p['b'] + 10) * SR)]), 10))
        tail = frames_db(x[int((p['b'] - 0.5) * SR):int(p['b'] * SR)])
        head = frames_db(x[int(n['a'] * SR):int((n['a'] + 0.5) * SR)])
        if len(tail) < 50 or len(head) < 50:
            continue
        on_t = np.nonzero(tail > room + VOICE_DB)[0]
        on_h = np.nonzero(head > room + VOICE_DB)[0]
        if len(on_t) == 0 or len(on_h) == 0:
            continue
        end_i, start_i = int(on_t[-1]) + 1, int(on_h[0])
        gap_t, gap_h = (50 - end_i) * 0.01, start_i * 0.01
        if gap_t > 0.20 or gap_h > 0.20:
            continue
        # 削る 0.2秒の中が声であること
        if (tail[max(0, end_i - 20):end_i] > room + VOICE_DB).mean() < 0.7:
            continue
        if (head[start_i:start_i + 20] > room + VOICE_DB).mean() < 0.7:
            continue
        seams.append({'i': i, 'voice_end': p['b'] - gap_t, 'voice_start': n['a'] + gap_h,
                      'gap_tail': gap_t, 'gap_head': gap_h, 'tl': n['t0'], 'removed': n['a'] - p['b']})
    return seams


def side_segments(clips, i, step, seconds):
    """切り口から片側へ、続いているクリップをたどって素材の範囲を集める。step=-1 は前、+1 は後ろ"""
    segs, left, j = [], seconds, i
    while left > 0.001 and 0 <= j < len(clips):
        c = clips[j]
        take = min(left, c['b'] - c['a'])
        segs.append((c['b'] - take, c['b']) if step < 0 else (c['a'], c['a'] + take))
        left -= take
        k = j + step
        if not (0 <= k < len(clips)) or not contiguous(*((clips[k], c) if step < 0 else (c, clips[k]))):
            break
        j = k
    return segs[::-1] if step < 0 else segs


def room_tone(clips, i, x, ms):
    """切り口の近くで完成版に残っている一番静かな 0.3秒を、つなぎ目が目立たないようにつないで長さを作る"""
    best, best_db = None, 1e9
    for c in clips[max(0, i - 25):i + 26]:
        a, b = int(c['a'] * SR), int(c['b'] * SR)
        db = frames_db(x[a:b])
        if len(db) < 30:
            continue
        s = np.convolve(db, np.ones(30) / 30, mode='valid')
        k = int(np.argmin(s))
        if s[k] < best_db:
            best_db, best = float(s[k]), (a + k * FRAME, a + k * FRAME + 30 * FRAME)
    piece = np.asarray(x[best[0]:best[1]], dtype=np.float64)
    need = int(ms / 1000 * SR)
    fade = int(0.01 * SR)
    ramp = np.linspace(0, 1, fade)
    out = piece.copy()
    while len(out) < need + fade:
        joined = out[:-fade].tolist()
        mix = out[-fade:] * (1 - ramp) + piece[:fade] * ramp
        out = np.concatenate([np.array(joined), mix, piece[fade:]])
    return out[:need], (best[0] / SR, best[1] / SR)


def render(seam, clips, x, kind, ms):
    """音の配列と、使った素材の範囲を返す"""
    i = seam['i']
    before = side_segments(clips, i, -1, CONTEXT)
    after = side_segments(clips, i + 1, +1, CONTEXT)
    if kind == 'tail':
        before[-1] = (before[-1][0], seam['voice_end'] - ms / 1000)
    if kind == 'head':
        after[0] = (seam['voice_start'] + ms / 1000, after[0][1])
    arrs = [np.asarray(x[int(a * SR):int(b * SR)], dtype=np.float64) for a, b in before]
    used = list(before) + list(after)
    if kind == 'gap':
        tone, rng = room_tone(clips, i, x, ms)
        used.append(rng)
        fade = int(0.003 * SR)
        ramp = np.linspace(0, 1, fade)
        tone = tone.copy()
        tone[:fade] *= ramp
        tone[-fade:] *= ramp[::-1]
        arrs.append(tone)
    arrs += [np.asarray(x[int(a * SR):int(b * SR)], dtype=np.float64) for a, b in after]
    return np.clip(np.concatenate(arrs), -32768, 32767).astype(np.int16), used


def check_kept(used, clips):
    """編集者が切った所の音を使っていたら止める"""
    for a, b in used:
        if not any(c['a'] - 0.002 <= a and b <= c['b'] + 0.002 for c in clips):
            raise SystemExit(f'完成版に残っていない所の音を使おうとした：{a:.3f}〜{b:.3f}秒')


def write_flac(path, audio):
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 's16le', '-ar', str(SR), '-ac', '1', '-i', 'pipe:0',
                    '-c:a', 'flac', path], input=audio.tobytes(), check=True)


def cmd_make(a):
    rng = random.Random(a.seed)
    os.makedirs(os.path.join(a.out, 'clips'), exist_ok=True)
    pairs, summary = [], {}
    for ref_id in ('1', '2'):
        ref = REFS[ref_id]
        clips = load_clips(ref)
        x = extract_wav(ref_id, a.out)
        seams = find_seams(clips, x)
        summary[ref_id] = {'name': ref['name'], 'clips': len(clips), 'seams': len(seams),
                           'gap_head_median': float(np.median([s['gap_head'] for s in seams])),
                           'gap_tail_median': float(np.median([s['gap_tail'] for s in seams]))}
        chosen = [seams[int(k * len(seams) / a.seams)] for k in range(a.seams)]

        def make(tag, seam, kind, ms):
            audio, used = render(seam, clips, x, kind, ms)
            check_kept(used, clips)
            path = os.path.join(a.out, 'clips', f'{tag}.flac')
            write_flac(path, audio)
            return os.path.relpath(path, a.out), round(len(audio) / SR, 3)

        for n, seam in enumerate(chosen):
            sid = f'r{ref_id}s{n:02d}'
            orig, sec = make(f'{sid}_orig', seam, 'orig', 0)
            base = {'seam': sid, 'ref': ref_id, 'tl': round(seam['tl'], 3), 'removed': round(seam['removed'], 3)}
            trials = [('tail', LEVELS['tail'][n % 3]), ('head', LEVELS['head'][(n + 1) % 3]),
                      ('gap', LEVELS['gap'][(n + 2) % 3])]
            if n % 6 == 0:
                trials.append(('tail', 400))
            if n % 6 == 3:
                trials.append(('gap', 1000))
            for kind, ms in trials:
                bad, _ = make(f'{sid}_{kind}{ms}', seam, kind, ms)
                pairs.append({**base, 'id': f'{sid}_{kind}{ms}', 'kind': kind, 'ms': ms, 'orig': orig, 'bad': bad,
                              'orig_is': rng.choice('AB'), 'sec': sec})
            if n % 2 == 0:
                pairs.append({**base, 'id': f'{sid}_same', 'kind': 'same', 'ms': 0, 'orig': orig, 'bad': orig,
                              'orig_is': rng.choice('AB'), 'sec': sec})
    rng.shuffle(pairs)
    json.dump({'summary': summary, 'pairs': pairs}, open(os.path.join(a.out, 'pairs.json'), 'w'), ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print('組の数', len(pairs))


def api_key():
    r = subprocess.run(['security', 'find-generic-password', '-s', 'gemini_api_key', '-w'], capture_output=True, text=True)
    key = r.stdout.strip()
    if not key:
        raise SystemExit('キーチェーンに gemini_api_key が無い。ユーザーに入れてもらう：\n'
                         '  security add-generic-password -U -a "$USER" -s gemini_api_key -w "$(pbpaste)"（キーをコピーしてから）')
    return key


def audio_part(root, rel):
    data = open(os.path.join(root, rel), 'rb').read()
    return {'inlineData': {'mimeType': 'audio/flac', 'data': base64.b64encode(data).decode()}}


def call_gemini(key, model, parts, schema):
    body = {'contents': [{'role': 'user', 'parts': parts}],
            'generationConfig': {'responseMimeType': 'application/json', 'responseSchema': schema, 'temperature': 0}}
    req = urllib.request.Request(f'{BASE}/models/{model}:generateContent', data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json', 'x-goog-api-key': key})
    for attempt in range(60):       # 無料枠は混むと 503 が続くので、長く待つ（最大で1回5分）
        try:
            with urllib.request.urlopen(req, timeout=180) as f:
                return json.load(f)
        except urllib.error.HTTPError as e:
            text = e.read().decode(errors='replace')
            if e.code == 429 and re.search(r'PerDay|per day', text, re.I):
                raise SystemExit(f'今日の無料枠の上限に当たった。明日続きから動かす：{text[:300]}')
            if e.code in (429, 500, 503):
                m = re.search(r'"retryDelay":\s*"(\d+)', text)
                wait = int(m.group(1)) + 1 if m else min(300, 15 * (attempt + 1))
                print(f'  {e.code} で {wait}秒待つ', flush=True)
                time.sleep(wait)
                continue
            raise SystemExit(f'Gemini のエラー {e.code}：{text[:500]}')
        except (urllib.error.URLError, TimeoutError) as e:
            print(f'  通信のエラー {e}、待ってやり直す', flush=True)
            time.sleep(min(300, 15 * (attempt + 1)))
    raise SystemExit('60回やり直しても通らなかった')


def cmd_run(a):
    root = os.path.dirname(os.path.abspath(a.pairs))
    pairs = json.load(open(a.pairs))['pairs']
    done = set()
    if os.path.exists(a.results):
        done = {json.loads(line)['id'] for line in open(a.results) if line.strip()}
    todo = [p for p in pairs if p['id'] not in done]
    if a.only:      # 例 tail400,gap1000（無料枠は1モデル1日20回なので、確かめる組を絞る時に使う）
        only = set(a.only.split(','))
        todo = [p for p in todo if f"{p['kind']}{p['ms']}" in only or p['kind'] in only]
    if a.limit:
        todo = todo[:a.limit]
    print(f'全部 {len(pairs)} 組、済み {len(done)}、今回 {len(todo)}', flush=True)
    if a.dry:
        print(PROMPT_PAIR)
        return
    key = api_key()
    wait = 60.0 / a.rpm
    for n, p in enumerate(todo):
        t0 = time.time()
        first, second = (p['orig'], p['bad']) if p['orig_is'] == 'A' else (p['bad'], p['orig'])
        parts = [{'text': PROMPT_PAIR}, {'text': '音声 A：'}, audio_part(root, first), {'text': '音声 B：'}, audio_part(root, second)]
        r = call_gemini(key, a.model, parts, SCHEMA_PAIR)
        cand = (r.get('candidates') or [{}])[0]
        text = ''.join(q.get('text', '') for q in cand.get('content', {}).get('parts', []))
        try:
            ans = json.loads(text)
        except ValueError:
            ans = {'choice': None, 'reason': text[:300]}
        if ans.get('choice') not in ('A', 'B'):     # 答えが無い時は×に数えず、次に動かした時にやり直す
            print(f"{n + 1}/{len(todo)} {p['id']} 答えが無い（{cand.get('finishReason')}）：{str(ans.get('reason'))[:100]}", flush=True)
            continue
        rec = {'id': p['id'], 'kind': p['kind'], 'ms': p['ms'], 'ref': p['ref'], 'orig_is': p['orig_is'], 'choice': ans.get('choice'),
               'correct': ans.get('choice') == p['orig_is'], 'reason': ans.get('reason'), 'model': r.get('modelVersion', a.model),
               'usage': r.get('usageMetadata'), 'finish': cand.get('finishReason')}
        with open(a.results, 'a') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
        print(f"{n + 1}/{len(todo)} {p['id']} 答え{rec['choice']} お手本{p['orig_is']} {'○' if rec['correct'] else '×'}", flush=True)
        left = wait - (time.time() - t0)
        if left > 0 and n + 1 < len(todo):
            time.sleep(left)


def wilson(k, n):
    if n == 0:
        return (0.0, 0.0)
    z = 1.96
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def cmd_score(a):
    recs = [json.loads(line) for line in open(a.results) if line.strip()]
    lines = ['| 崩し | 大きさ | 組 | お手本を選んだ | 割合 | 95% の幅 |', '|---|---|---|---|---|---|']
    groups = {}
    for r in recs:
        if r['kind'] != 'same':
            groups.setdefault((r['kind'], r['ms']), []).append(r)
    for (kind, ms), rs in sorted(groups.items(), key=lambda kv: (list(KIND_JA).index(kv[0][0]), kv[0][1])):
        k = sum(r['correct'] for r in rs)
        lo, hi = wilson(k, len(rs))
        lines.append(f'| {KIND_JA[kind]} | {ms}ms | {len(rs)} | {k} | {k / len(rs):.0%} | {lo:.0%}〜{hi:.0%} |')
    normal = [r for r in recs if r['kind'] != 'same' and r['ms'] <= 400 and not (r['kind'] == 'tail' and r['ms'] == 400)]
    for ref_id in ('1', '2'):
        rs = [r for r in normal if r['ref'] == ref_id]
        if rs:
            k = sum(r['correct'] for r in rs)
            lo, hi = wilson(k, len(rs))
            lines.append(f'| 完成版{ref_id} の全部 | | {len(rs)} | {k} | {k / len(rs):.0%} | {lo:.0%}〜{hi:.0%} |')
    same = [r for r in recs if r['kind'] == 'same']
    if same:
        na = sum(r['choice'] == 'A' for r in same)
        lines += ['', f'同じ音を2つ渡した対照 {len(same)} 組：A を選んだ {na}、B を選んだ {len(same) - na}（片方に寄ると、順番で答えている）']
    tok = [r['usage'].get('totalTokenCount', 0) for r in recs if r.get('usage')]
    if tok:
        lines += ['', f'1組あたりのトークン 中央 {int(np.median(tok))}・合計 {sum(tok)}']
    models = sorted({r['model'] for r in recs})
    lines += ['', f'モデル：{", ".join(models)}']
    text = '\n'.join(lines)
    print(text)
    if a.out:
        open(a.out, 'w').write(text + '\n')


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    m = sub.add_parser('make')
    m.add_argument('--out', required=True)
    m.add_argument('--seams', type=int, default=30, help='1本あたりの切り口の数')
    m.add_argument('--seed', type=int, default=20261104)
    r = sub.add_parser('run')
    r.add_argument('--pairs', required=True)
    r.add_argument('--results', required=True)
    r.add_argument('--model', default='gemini-3.8-flash')
    r.add_argument('--limit', type=int, default=0)
    r.add_argument('--only', help='送る崩しを絞る。例 tail400,gap1000,same')
    r.add_argument('--rpm', type=float, default=8.0, help='1分に送る数の上限')
    r.add_argument('--dry', action='store_true')
    s = sub.add_parser('score')
    s.add_argument('--pairs')
    s.add_argument('--results', required=True)
    s.add_argument('--out')
    a = ap.parse_args()
    {'make': cmd_make, 'run': cmd_run, 'score': cmd_score}[a.cmd](a)


if __name__ == '__main__':
    main()
