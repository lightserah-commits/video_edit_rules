"""完成版で、編集者がどのフィラーを残し、どれを切ったかを数える（08 の cut.remove「フィラー（言いよどみ）」の根拠。2026-10-20）。
  python3 実例/カット調査/scripts/filler_analysis.py
読む物：_data/tl_*.json（完成版のタイムライン）・_data/disfl_IMG_*.json（transcribe_disfl.py の文字起こし）
出す物：_data/fillers.json（1つずつ：形・残した／抜いた／端で切った／塊ごと・前後の言葉が残っているか・完成版の時刻）と、形ごとの表（標準出力）
  残した＝フィラーを残した／抜いた＝前後を残してフィラーだけ切った／端で切った＝残した所の頭か終わりで切った（つなぎ目）／塊ごと＝まわりごと切った（数えない）
  完成版の声には聞き手の声も入っている。文字起こしが拾えなかったフィラーは数に入らない"""
import json, os, re, sys, collections
TPS = 254016000000
D = os.path.expanduser('~/Desktop/video_edit_rules/実例/カット調査/_data')
H = D
SETS = {  # 完成版 → (タイムライン, 素材)
    'v2': (['tl_ai_冒頭.json', 'tl_ai_後半.json'], ['IMG_1598', 'IMG_1599']),
    'v1': (['tl_mikami.json'], ['IMG_1063']),
}
# フィラーの形（文字起こしの文字列で探す）。後ろの条件で「その場合」「あの人」などを外す
B = r'(?<![ぁ-んァ-ヶ一-龥ー])'   # 前が語の途中でない（「たとえ」「伝えと」「じゃあ」を外す）
PATS = [
    ('えー・えっと', B + r'(えー+っと|えーと|えっと|えと(?=[、 ])|えー+|え(?=[、 ]))'),
    ('あのー（伸ばす）', B + r'(あのー+|あのう)'),
    ('あの', B + r'あの(?=[、 。]|$)'),
    ('うーん・あー', B + r'(うー+ん|んー+|あー+(?=[、 ]))'),
    ('まあ', r'(?<!じゃ)(まあ|まぁ|まー)'),
    ('なんか', r'なんか'),
    ('その', B + r'その(?=[、 ]|$)'),
    ('やっぱ', r'やっぱり?'),
    ('ですね（文の中）', r'(?<=[^ 、。])ですね(?=[、 ])'),
    ('ちなみに', r'ちなみに'),
    ('はい（区切り）', B + r'はい(?=[、。 ]|$)'),
    ('なんだろう', r'なんだろう(な|ね)?'),
]

CLIPS = collections.defaultdict(list)   # 素材 → (素材の始め, 終わり, シーケンス, シーケンスの始め)
def kept_ranges(tls, names):
    rng = collections.defaultdict(list)
    for f in tls:
        d = json.load(open(os.path.join(D, f)))
        for c in d['tracks'].get('A1', []):
            n = c['name'].split('.')[0]
            if n in names and not c.get('muted'):
                rng[n].append((c['in_ticks'] / TPS, c['out_ticks'] / TPS))
                CLIPS[n].append((c['in_ticks'] / TPS, c['out_ticks'] / TPS, d['sequence'], c['start_ticks'] / TPS))
    for n in rng:
        rng[n].sort()
    return rng

def overlap(rs, a, b):
    if b <= a: return 0.0
    t = 0.0
    for s, e in rs:
        if e <= a: continue
        if s >= b: break
        t += min(e, b) - max(a, s)
    return t / (b - a)

def chars(segs):
    """文字ごとの時刻。区切りの間には空白を入れる"""
    out = []
    for s in segs:
        for (a, b, w) in s['words']:
            w = w.strip()
            if not w: continue
            n = len(w)
            for i, ch in enumerate(w):
                out.append((a + (b - a) * i / n, a + (b - a) * (i + 1) / n, ch))
        out.append((s['end'], s['end'], ' '))
    return out

rows = []
for vid, (tls, names) in SETS.items():
    rng = kept_ranges(tls, names)
    for n in names:
        p = os.path.join(H, f'disfl_{n}.json')
        if not os.path.exists(p): continue
        cs = chars(json.load(open(p)))
        text = ''.join(c[2] for c in cs)
        for kind, pat in PATS:
            for m in re.finditer(pat, text):
                i, j = m.start(), m.end()
                a, b = cs[i][0], cs[j - 1][1]
                if b - a < 0.03: b = a + 0.1
                k = overlap(rng[n], a, b)
                # となりの言葉（前後 0.5秒・空白と句読点を除く）
                pi = i - 1
                while pi >= 0 and cs[pi][2] in ' 、。': pi -= 1
                ni = j
                while ni < len(cs) and cs[ni][2] in ' 、。': ni += 1
                pk = overlap(rng[n], cs[pi][0], cs[pi][1] + 0.02) if pi >= 0 else 0
                nk = overlap(rng[n], cs[ni][0] - 0.02, cs[ni][1]) if ni < len(cs) else 0
                gap_before = a - cs[pi][1] if pi >= 0 else 9
                head = gap_before > 0.3 or (pi >= 0 and text[pi + 1:i].strip(' ') in ('。',)) 
                if k >= 0.5: cls = '残した'
                elif pk >= 0.5 and nk >= 0.5: cls = '抜いた'      # 前後を残してフィラーだけ切った
                elif pk >= 0.5 or nk >= 0.5: cls = '端で切った'   # 残した所の頭・終わりで切った
                else: cls = '塊ごと'                              # まわりごと切った（判断に使わない）
                tl = ''
                for (s0, s1, sq, t0) in CLIPS[n]:
                    if s0 - 0.3 <= a <= s1 + 0.3:
                        x = t0 + max(0, a - s0); tl = f'{sq} {int(x // 60)}:{x % 60:04.1f}'; break
                rows.append({'tl': tl, 'vid': vid, 'src': n, 't': round(a, 2), 'dur': round(b - a, 2), 'kind': kind, 'word': m.group(0),
                             'cls': cls, 'pk': round(pk,2), 'nk': round(nk,2), 'head': head, 'before': text[max(0, i - 18):i].replace(' ', '／'),
                             'after': text[j:j + 18].replace(' ', '／')})
json.dump(rows, open(os.path.join(H, 'fillers.json'), 'w'), ensure_ascii=False, indent=0)
tab = collections.defaultdict(collections.Counter)
for r in rows:
    tab[r['kind']][r['cls']] += 1
print('形 | 残した | 抜いた | 端で切った | 塊ごと | 残した率（塊ごと除く）')
for kind, _ in PATS:
    c = tab[kind]
    
    inf = c['残した'] + c['抜いた'] + c['端で切った']
    print(f"{kind} | {c['残した']} | {c['抜いた']} | {c['端で切った']} | {c['塊ごと']} | {c['残した'] / inf * 100 if inf else 0:.0f}%")
