#!/usr/bin/env python3
"""カットの答え合わせ：完成版2本の素材を AI に切らせ、お手本の編集者の切り方と文字ごとに比べる。

  make  ：素材の範囲から、区切りの一覧（AI に渡す）と答え（AI には見せない）を作る
  score ：AI のカットの行（x A..B|理由。台本と同じ形）を答えと比べ、合う割合と違う所の一覧を出す

  使い方：
    env/bin/python tools/cut_bench.py make --ref 1 --from 3138.8 --to 3681.6 --out <出力のフォルダ>
    env/bin/python tools/cut_bench.py score --truth <出力のフォルダ>/truth.json --cuts <カットの行のファイル> --out <報告.md>

  切り残し＝お手本は切ったのに AI は残した文字。切りすぎ＝お手本は残したのに AI は切った文字。
  言葉の中身の比べなので、間の詰め方・語尾の端（数コマ）は測らない。時刻は文字起こしの語の時刻なので粗い（2字より短いズレは数えない）。
"""
import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, '実例', 'カット調査', '_data')
TPS = 254016000000
REFS = {
    '1': {'name': '完成版1 AI使いこなす習慣7選', 'tl': 'tl_mikami.json', 'src': 'IMG_1063.MOV', 'asr': 'asr_IMG_1063.json', 'tl_range': (16.3, 2170.5)},
    '2': {'name': '完成版2 AI時代に消える仕事残る仕事', 'tl': 'tl_ai_冒頭.json', 'src': 'IMG_1598.MOV', 'asr': 'asr_IMG_1598.json', 'tl_range': (17.6, 1e9)},
}
CUT_LINE = re.compile(r'^x\s+(\d+)(?:/([^|]*?))?\.\.(\d+)(?:/([^|]*?))?\|(.*)$')


def make_units(asr):
    """scripts/make_units.py と同じ切り方：文字起こしの区切りの中で「。？！」の後と 0.4秒以上の空きで分ける"""
    units = []
    for s in asr:
        ws = [w for w in s.get('words', []) if w['word'].strip()]
        if not ws:
            continue
        cur = [ws[0]]
        for w in ws[1:]:
            p = cur[-1]
            if p['word'].strip()[-1:] in '。？！?!' or w['start'] - p['end'] >= 0.4:
                units.append(cur)
                cur = [w]
            else:
                cur.append(w)
        units.append(cur)
    return units


def keep_intervals(ref):
    d = json.load(open(os.path.join(DATA, ref['tl'])))
    lo, hi = ref['tl_range']
    out = []
    for c in d['tracks']['A1']:
        if c.get('muted') or c['name'] != ref['src']:
            continue
        t = c['start_ticks'] / TPS
        if t < lo or t >= hi:
            continue
        out.append((c['in_ticks'] / TPS, c['out_ticks'] / TPS))
    out.sort()
    merged = []
    for a, b in out:
        if merged and a <= merged[-1][1] + 1e-3:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    return merged


def kept_ratio(st, en, keeps):
    if en <= st:
        en = st + 0.02
    got = 0.0
    for a, b in keeps:
        if b <= st:
            continue
        if a >= en:
            break
        got += min(b, en) - max(a, st)
    return got / (en - st)


def case_units(path):
    """案件の analysis/units.json（words が [頭, 終わり, 語]）を make_units の形にする"""
    return [[{'word': w[2], 'start': w[0], 'end': w[1]} for w in u['words']] for u in json.load(open(path)) if u.get('words')]


def cmd_make(a):
    if a.tl:  # 案件の手のカットを答えにする（--tl 手で切ったタイムライン.json --src 素材の名前 --units units.json）
        ref = {'name': a.name or os.path.basename(a.tl), 'tl': os.path.abspath(a.tl), 'src': a.src, 'tl_range': (0, 1e12)}
        keeps = keep_intervals(ref)
        all_units = case_units(a.units)
    else:
        ref = REFS[a.ref]
        keeps = keep_intervals(ref)
        all_units = make_units(json.load(open(os.path.join(DATA, ref['asr']))))
    units = [u for u in all_units if u[0]['start'] >= a.src_from and u[-1]['end'] <= a.src_to]
    os.makedirs(a.out, exist_ok=True)
    lines, truth = [], []
    for i, ws in enumerate(units):
        text = ''.join(w['word'] for w in ws).strip()
        gap = units[i + 1][0]['start'] - ws[-1]['end'] if i + 1 < len(units) else 0
        lines.append(f"{i}|{ws[0]['start']:.2f}|{ws[-1]['end'] - ws[0]['start']:.2f}|{text}|{gap:.2f}")
        chars, cut, sec = [], [], []
        for w in ws:
            t = w['word'].strip()
            if not t:
                continue
            k = kept_ratio(w['start'], w['end'], keeps) >= 0.5
            d = max(w['end'] - w['start'], 0.02) / len(t)
            chars += list(t)
            cut += [not k] * len(t)
            sec += [d] * len(t)
        truth.append({'u': i, 'start': ws[0]['start'], 'end': ws[-1]['end'], 'chars': chars, 'cut': cut, 'sec': sec})
    with open(os.path.join(a.out, 'units.txt'), 'w') as f:
        f.write('# 区切り|素材の秒|長さ|文字起こし|次の区切りまでの空き（秒）\n')
        f.write('\n'.join(lines) + '\n')
    json.dump({'ref': ref['name'], 'from': a.src_from, 'to': a.src_to, 'units': truth}, open(os.path.join(a.out, 'truth.json'), 'w'), ensure_ascii=False)
    n = sum(len(u['chars']) for u in truth)
    c = sum(sum(u['cut']) for u in truth)
    print(f"{ref['name']} 素材 {a.src_from}〜{a.src_to}：区切り {len(truth)}・{n}字・お手本が切った字 {c}（{c / max(n, 1) * 100:.0f}%）")


def parse_cuts(path, truth):
    units = {u['u']: ''.join(u['chars']) for u in truth['units']}
    marks = {u['u']: [False] * len(u['chars']) for u in truth['units']}
    why = {u['u']: [''] * len(u['chars']) for u in truth['units']}
    errs = []
    for ln, line in enumerate(open(path), 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        m = CUT_LINE.match(line)
        if not m:
            if line.startswith('x'):
                errs.append(f'{ln}行目が読めない：{line[:60]}')
            continue
        ua, wa, ub, wb, reason = int(m[1]), m[2], int(m[3]), m[4], m[5]
        if ua not in units or ub not in units or ua > ub:
            errs.append(f'{ln}行目の区切りの番号が範囲の外：{line[:60]}')
            continue
        sa = 0
        if wa:
            sa = units[ua].find(wa)
            if sa < 0:
                errs.append(f'{ln}行目の語が見つからない：{wa}（区切り {ua}）')
                continue
        eb = len(units[ub])
        if wb:
            eb = units[ub].find(wb)
            if eb < 0:
                errs.append(f'{ln}行目の語が見つからない：{wb}（区切り {ub}）')
                continue
        for u in range(ua, ub + 1):
            lo = sa if u == ua else 0
            hi = eb if u == ub else len(units[u])
            for i in range(lo, hi):
                marks[u][i] = True
                why[u][i] = reason
    return marks, why, errs


def spans(truth, marks, why, kind):
    """切り残し（お手本 cut・AI 残す）か切りすぎ（お手本 残す・AI cut）の続いた所を集める"""
    out, cur = [], None
    for u in truth['units']:
        for i, ch in enumerate(u['chars']):
            t, a = u['cut'][i], marks[u['u']][i]
            hit = (t and not a) if kind == 'miss' else (a and not t)
            if hit:
                if cur is None:
                    cur = {'u': u['u'], 'start': u['start'], 'text': '', 'sec': 0.0, 'why': why[u['u']][i]}
                cur['text'] += ch
                cur['sec'] += u['sec'][i]
                cur['end_u'] = u['u']
            elif cur is not None:
                out.append(cur)
                cur = None
    if cur is not None:
        out.append(cur)
    return [s for s in out if len(s['text']) >= 2]


def context(truth, u, before=True):
    us = truth['units']
    for x in us:
        if x['u'] == u:
            return ''.join(x['chars'])
    return ''


def drop_fragments(flags):
    """区切りの中の3字以下の切れ端を外す（区切りを丸ごと切る物は残す）。語の時刻の粗さで出る端のズレを数えないため"""
    out = list(flags)
    n, i = len(out), 0
    while i < n:
        if not out[i]:
            i += 1
            continue
        j = i
        while j < n and out[j]:
            j += 1
        if j - i <= 3 and j - i < n:
            out[i:j] = [False] * (j - i)
        i = j
    return out


def count(truth, marks, key_truth=None):
    tp = fp = fn = tn = 0
    fps = fns = 0.0
    for u in truth['units']:
        tt = key_truth(u['cut']) if key_truth else u['cut']
        mm = key_truth(marks[u['u']]) if key_truth else marks[u['u']]
        for i in range(len(u['chars'])):
            t, m, s = tt[i], mm[i], u['sec'][i]
            if t and m:
                tp += 1
            elif m:
                fp += 1; fps += s
            elif t:
                fn += 1; fns += s
            else:
                tn += 1
    rec = tp / max(tp + fn, 1)
    pre = tp / max(tp + fp, 1)
    return {'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn, 'fps': fps, 'fns': fns, 'rec': rec, 'pre': pre, 'f1': 2 * rec * pre / max(rec + pre, 1e-9)}


def cmd_score(a):
    truth = json.load(open(a.truth))
    marks, why, errs = parse_cuts(a.cuts, truth)
    r = count(truth, marks)
    tp, fp, fn, tn, fps, fns, rec, pre, f1 = r['tp'], r['fp'], r['fn'], r['tn'], r['fps'], r['fns'], r['rec'], r['pre'], r['f1']
    b = count(truth, marks, drop_fragments)
    res = {'ref': truth['ref'], 'chars': tp + fp + fn + tn, 'お手本が切った字': tp + fn, 'AI が切った字': tp + fp,
           '同じに切った字': tp, '切り残し字': fn, '切りすぎ字': fp, '切り残し秒': round(fns, 1), '切りすぎ秒': round(fps, 1),
           '切り当て率': round(rec, 3), '切った所の正しさ': round(pre, 3), 'F1': round(f1, 3),
           '端を除く': {'お手本が切った字': b['tp'] + b['fn'], 'AI が切った字': b['tp'] + b['fp'], '切り当て率': round(b['rec'], 3), '切った所の正しさ': round(b['pre'], 3), 'F1': round(b['f1'], 3)},
           '読めなかった行': errs}
    miss = spans(truth, marks, why, 'miss')
    over = spans(truth, marks, why, 'over')
    L = [f"# カットの答え合わせ：{truth['ref']}（素材 {truth['from']}〜{truth['to']}）", '']
    L += [f"- 全部 {res['chars']}字／お手本が切った字 {res['お手本が切った字']}／AI が切った字 {res['AI が切った字']}／同じに切った字 {tp}",
          f"- 切り当て率 {rec * 100:.0f}%（お手本が切った字のうち AI も切った割合）／切った所の正しさ {pre * 100:.0f}%（AI が切った字のうちお手本も切った割合）／F1 {f1:.2f}",
          f"- 切り残し {fn}字・{fns:.1f}秒／切りすぎ {fp}字・{fps:.1f}秒", '']
    if errs:
        L += ['## 読めなかった行'] + [f'- {e}' for e in errs] + ['']
    for title, ss in (('切り残し（お手本は切った・AI は残した）', miss), ('切りすぎ（お手本は残した・AI は切った）', over)):
        L += [f'## {title}：{len(ss)}か所', '', '| 区切り | 素材の秒 | 秒 | 文字 | AI の理由 |', '|---|---|---|---|---|']
        for s in ss:
            L.append(f"| {s['u']}〜{s['end_u']} | {s['start']:.1f} | {s['sec']:.1f} | {s['text']} | {s['why']} |")
        L.append('')
    if a.out:
        open(a.out, 'w').write('\n'.join(L))
        json.dump({**res, 'miss': miss, 'over': over}, open(os.path.splitext(a.out)[0] + '.json', 'w'), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest='cmd', required=True)
    m = sp.add_parser('make')
    m.add_argument('--ref', choices=REFS)
    m.add_argument('--tl', help='案件の手のカットのタイムライン（--ref の代わり）')
    m.add_argument('--src', help='--tl の声のトラックの素材の名前')
    m.add_argument('--units', help='--tl の時の案件の analysis/units.json')
    m.add_argument('--name', help='--tl の時の報告の名前')
    m.add_argument('--from', dest='src_from', type=float, required=True)
    m.add_argument('--to', dest='src_to', type=float, required=True)
    m.add_argument('--out', required=True)
    m.set_defaults(func=cmd_make)
    s = sp.add_parser('score')
    s.add_argument('--truth', required=True)
    s.add_argument('--cuts', required=True)
    s.add_argument('--out')
    s.set_defaults(func=cmd_score)
    a = p.parse_args()
    a.func(a)


if __name__ == '__main__':
    sys.exit(main())
