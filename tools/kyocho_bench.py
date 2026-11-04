#!/usr/bin/env python3
"""強調の答え合わせ：完成版2本の話を AI に読ませて強調する所を選ばせ、お手本の編集者の強調と比べる（音は聴かない。全部未聴取）。

  make  ：タイムラインの範囲から、話の一覧（AI に渡す。強調の印は無い）と答え（AI には見せない）を作る
  score ：AI の選んだ行を答えと比べ、拾えた割合・拾いすぎ・型の合う割合・違う所の一覧を出す

  使い方：
    env/bin/python tools/kyocho_bench.py make --ref 1 --from 300 --to 720 --out <出力のフォルダ>
    env/bin/python tools/kyocho_bench.py score --truth <出力のフォルダ>/truth.json --picks <選んだ行のファイル> --rule <AI に読ませた決まり.md> --out <報告.md>

  選んだ行の形（1行1つ。# はメモ）：番号|種類（意味／感情）|型|文|理由
  型：赤黄・赤・金・青・シュール・ツッコミ・白シャドウ・白テキ

  見る数字は「同じ言葉」：±5秒の中で、お手本の文と AI の文に同じ4字以上の並びがある（1つの選択は1つの強調にだけ当てる）。
  「でたらめ」は同じ数の行をでたらめに選んだ時の同じ言葉。これより十分上でないと意味が無い。
  「位置が近い」は、お手本の強調の頭から ±2.5秒に選んだ行の頭があること。でたらめでも3〜5割になるので、これだけで決めない（2026-11-04）。
  --rule：AI に読ませた決まりの例文と同じお手本は答えが見えているので、お手本からも選択からも外す。
  ネタ＝5秒より近いお手本の強調をまとめた1かたまり。お手本に無い所＝お手本の強調にも札にも近くない選択。
  お手本の札（白背景・青背景・ポイントのボードなど）に当たった選択は、お手本に無い所に数えない。
  お手本は編集者1人の選び方なので、お手本に無い所がそのまま悪いとは言えない。
  話の一覧は完成版の字幕ではなく文字起こしから作る（完成版の字幕は強調の所が抜けているので、答えが透ける）。
"""
import argparse
import csv
import json
import os
import random
import re
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from cut_bench import DATA, REFS, TPS  # noqa: E402

EVENTS = {'1': '実例/みかみCH0726/events.csv', '2': '実例/AI時代に消える仕事残る仕事_冒頭/events.csv'}
SUBS = {'1': '実例/文字組み/字幕_1本目.json', '2': '実例/文字組み/字幕_2本目.json'}
KYOCHO = {'シュールテロップ': 'シュール', '強調赤黄': '赤黄', 'ゴージャス金': '金', 'ゴージャス青': '青', '基本テロップ赤': '赤',
          'ヒラギノ白シャドウ': '白シャドウ', '白テキ': '白テキ', 'ツッコミ': 'ツッコミ'}
WINDOW = 2.5
TEXT_WINDOW = 5.0
GROUP_GAP = 5.0
MAX_CHARS = 20


def clips(ref):
    d = json.load(open(os.path.join(DATA, ref['tl']), encoding='utf-8'))
    out = [(c['start_ticks'] / TPS, c['in_ticks'] / TPS, c['out_ticks'] / TPS) for c in d['tracks']['A1'] if not c.get('muted') and c['name'] == ref['src']]
    return sorted(out)


def spoken_lines(ref, t0, t1):
    """タイムラインの範囲の声を、字幕くらいの長さの行にする：(秒, 終わりの秒, 文字)"""
    asr = json.load(open(os.path.join(DATA, ref['asr']), encoding='utf-8'))
    words = sorted(((w['start'], w['end'], w['word'].strip()) for s in asr for w in s.get('words', []) if w['word'].strip()))
    tl = []
    for start, a, b in clips(ref):
        if start + (b - a) < t0 or start >= t1:
            continue
        for ws, we, w in words:
            if a <= (ws + we) / 2 < b:
                t = start + ws - a
                if t0 <= t < t1:
                    tl.append((t, start + min(we, b) - a, w))
    tl.sort()
    lines, cur = [], []
    for x in tl:
        if cur and (x[0] - cur[-1][1] >= 0.3 or cur[-1][2][-1:] in '。？！?!' or sum(len(y[2]) for y in cur) + len(x[2]) > MAX_CHARS):
            lines.append((cur[0][0], cur[-1][1], ''.join(y[2] for y in cur)))
            cur = []
        cur.append(x)
    if cur:
        lines.append((cur[0][0], cur[-1][1], ''.join(y[2] for y in cur)))
    return lines


def speakers(key):
    subs = json.load(open(os.path.join(ROOT, SUBS[key]), encoding='utf-8'))['subs']
    return sorted((s['start'], s['end'], '聞' if '質問者テロップ' in s['style'] else 'み') for s in subs if any(x in ('みかみテロップ', '質問者テロップ') for x in s['style']))


def cmd_make(a):
    ref = REFS[a.ref]
    lines = spoken_lines(ref, a.t0, a.t1)
    spk = speakers(a.ref)
    os.makedirs(a.out, exist_ok=True)
    rows, who = [], 'み'
    for i, (s, e, text) in enumerate(lines):
        for ss, se, w in spk:     # 字幕が無い所（強調で隠れた所）は1つ前の話者のまま
            if ss <= s + 0.1 < se:
                who = w
                break
        rows.append(f"{i}|{s:.2f}|{who}|{text}")
    with open(os.path.join(a.out, 'list.txt'), 'w', encoding='utf-8') as f:
        f.write(f"# {ref['name']} の {a.t0:.0f}〜{a.t1:.0f}秒。番号|秒|話者（み＝三上さん・聞＝聞き手）|言葉（文字起こし。誤りがある）\n")
        f.write('\n'.join(rows) + '\n')
    truth, other = [], []
    for e in csv.DictReader(open(os.path.join(ROOT, EVENTS[a.ref]), encoding='utf-8-sig')):
        s = float(e['秒'])
        text = e['装飾テロップ'].strip()
        if not text or not (a.t0 <= s < a.t1):
            continue
        item = {'sec': s, 'text': text, 'style': e['装飾スタイル'], 'se': e['SE']}
        if e['装飾スタイル'] in KYOCHO:
            item['kata'] = KYOCHO[e['装飾スタイル']]
            truth.append(item)
        else:
            other.append(item)
    json.dump({'ref': a.ref, 'name': ref['name'], 'from': a.t0, 'to': a.t1, 'lines': [{'i': i, 'sec': round(s, 2), 'end': round(e, 2), 'text': t} for i, (s, e, t) in enumerate(lines)],
               'truth': truth, 'other': other}, open(os.path.join(a.out, 'truth.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    m = (a.t1 - a.t0) / 60
    print(f"{ref['name']} {a.t0:.0f}〜{a.t1:.0f}秒：行 {len(rows)}・お手本の強調 {len(truth)}（1分あたり {len(truth) / m:.1f}）・札など {len(other)}")


def read_picks(path, lines):
    out = []
    for raw in open(path, encoding='utf-8'):
        raw = raw.strip()
        if not raw or raw.startswith('#'):
            continue
        c = raw.split('|')
        m = re.match(r'\d+', c[0].strip())
        if not m or int(m.group()) >= len(lines):
            print('読めない行：', raw[:60])
            continue
        ln = lines[int(m.group())]
        out.append({'i': ln['i'], 'sec': ln['sec'], 'line': ln['text'], 'shurui': c[1].strip() if len(c) > 1 else '', 'kata': c[2].strip() if len(c) > 2 else '',
                    'text': c[3].strip() if len(c) > 3 else '', 'why': c[4].strip() if len(c) > 4 else ''})
    return out


def plain(s):
    return re.sub(r'[\s/　、。！!？?…「」『』（）()・〜~ｗw↑←→]', '', s).lower()


def shares(a, b, n=3):
    a, b = plain(a), plain(b)
    return any(a[i:i + n] in b for i in range(max(0, len(a) - n + 1)))


def same_words(t, p):
    return shares(t['text'], p['text'] or p['line'])


def match(truth, picks):
    pairs = []
    for it, t in enumerate(truth):
        for ip, p in enumerate(picks):
            d = abs(p['sec'] - t['sec'])
            same = same_words(t, p)
            if d <= WINDOW or (same and d <= TEXT_WINDOW):
                pairs.append((0 if same else 1, d, it, ip))     # 言葉も同じ物を先に当てる
    tm, pm = {}, {}
    for _, _, it, ip in sorted(pairs):
        if it not in tm and ip not in pm:
            tm[it], pm[ip] = ip, it
    return tm, pm


def strict(truth, picks, win=5.0, n=4):
    pairs = sorted((abs(p['sec'] - t['sec']), it, ip) for it, t in enumerate(truth) for ip, p in enumerate(picks)
                   if abs(p['sec'] - t['sec']) <= win and shares(t['text'], p['text'] or p['line'], n))
    a, b = {}, {}
    for _, it, ip in pairs:
        if it not in a and ip not in b:
            a[it], b[ip] = ip, it
    return a, b


def chance(truth, picks, lines, times=200):
    rng = random.Random(1)
    got = []
    for _ in range(times):
        q = [{'sec': l['sec'], 'text': plain(l['text'])[:len(plain(x['text'] or x['line']))], 'line': l['text']}
             for x, l in zip(picks, rng.sample(lines, min(len(picks), len(lines))))]
        got.append(len(strict(truth, q)[0]))
    return statistics.mean(got)


def drop_seen(tj, picks, rule_path):
    """決まりの例文と同じお手本（6字以上同じ）を、答えが見えている物としてお手本と選択から外す"""
    rule = plain(open(rule_path, encoding='utf-8').read())
    def seen(t):
        x = plain(t['text'])
        return len(x) >= 4 and any(x[i:i + 6] in rule for i in range(max(1, len(x) - 5)))
    gone = [t for t in tj['truth'] if seen(t)]
    _, b = strict(gone, picks) if gone else ({}, {})
    return dict(tj, truth=[t for t in tj['truth'] if not seen(t)]), [p for i, p in enumerate(picks) if i not in b], gone


def groups(truth):
    g, out = [], []
    for it, t in enumerate(truth):
        if g and t['sec'] - truth[g[-1]]['sec'] >= GROUP_GAP:
            out.append(g)
            g = []
        g.append(it)
    if g:
        out.append(g)
    return out


def score(tj, picks):
    truth = sorted(tj['truth'], key=lambda t: t['sec'])
    other = tj['other']
    tm, pm = match(truth, picks)
    gs = groups(truth)
    hit_g = sum(1 for g in gs if any(i in tm for i in g))
    extra, on_other = [], 0
    for ip, p in enumerate(picks):
        if ip in pm:
            continue
        if any(abs(o['sec'] - p['sec']) <= WINDOW or shares(o['text'], p['text'] or p['line']) and abs(o['sec'] - p['sec']) <= TEXT_WINDOW for o in other):
            on_other += 1
        elif any(abs(t['sec'] - p['sec']) <= GROUP_GAP for t in truth):
            p['near'] = True      # お手本の強調のすぐ隣（同じネタの2枚目）。拾いすぎに数えない
            on_other += 1
        else:
            extra.append(p)
    same = sum(1 for it, ip in tm.items() if picks[ip]['kata'] == truth[it]['kata'])
    words = sum(1 for it, ip in tm.items() if same_words(truth[it], picks[ip]))
    by = {}
    for it, t in enumerate(truth):
        k = by.setdefault(t['kata'], [0, 0])
        k[0] += 1
        k[1] += it in tm
    return {'truth': truth, 'tm': tm, 'pm': pm, 'groups': gs, 'hit_groups': hit_g, 'extra': extra, 'on_other': on_other, 'same_kata': same, 'same_words': words, 'by_kata': by, 'minutes': (tj['to'] - tj['from']) / 60}


def nearest_line(lines, sec):
    return min(lines, key=lambda x: abs(x['sec'] - sec))['text'] if lines else ''


def cmd_score(a):
    tj = json.load(open(a.truth, encoding='utf-8'))
    picks = read_picks(a.picks, tj['lines'])
    gone = []
    if a.rule:
        tj, picks, gone = drop_seen(tj, picks, a.rule)
    r = score(tj, picks)
    sa, _ = strict(r['truth'], picks)
    ch = chance(r['truth'], picks, tj['lines'])
    t, m = r['truth'], r['minutes']
    n, h = len(t), len(r['tm'])
    w = [f"# 強調の答え合わせ：{tj['name']} {tj['from']:.0f}〜{tj['to']:.0f}秒", '',
         '| 数 | 値 |', '|---|---|',
         f"| お手本の強調 | {n}（1分あたり {n / m:.1f}。ネタ {len(r['groups'])}） |",
         f"| AI の選んだ数 | {len(picks)}（1分あたり {len(picks) / m:.1f}） |",
         f"| 同じ言葉 | {len(sa)}（お手本の {100 * len(sa) // max(1, n)}%・選んだ物の {100 * len(sa) // max(1, len(picks))}%） |",
         f"| でたらめに選んだ時の同じ言葉 | {ch:.1f} |",
         f"| 位置が近い（甘い） | {h}（{100 * h // max(1, n)}%） |",
         f"| 位置が近いネタ | {r['hit_groups']}（{100 * r['hit_groups'] // max(1, len(r['groups']))}%） |",
         f"| お手本に無い所 | {len(r['extra'])}（{100 * len(r['extra']) // max(1, len(picks))}%） |",
         f"| 札か同じネタに当たった選択 | {r['on_other']} |",
         f"| 型が同じ | {r['same_kata']}／{h} |",
         f"| 決まりの例文と同じなので外したお手本 | {'・'.join(t['text'] for t in gone) or 'なし'} |", '',
         '## 型ごとの拾えた数', '', '| お手本の型 | 数 | 拾えた |', '|---|---|---|']
    for k, (c, x) in sorted(r['by_kata'].items(), key=lambda kv: -kv[1][0]):
        w.append(f"| {k} | {c} | {x}（{100 * x // c}%） |")
    w += ['', '## 拾えなかった強調', '', '| 秒 | 型 | お手本の文 | その時の声 |', '|---|---|---|---|']
    for it, x in enumerate(t):
        if it not in r['tm']:
            w.append(f"| {x['sec']:.1f} | {x['kata']} | {x['text']} | {nearest_line(tj['lines'], x['sec'])} |")
    w += ['', '## お手本に無い所', '', '| 秒 | 型 | AI の文 | 理由 |', '|---|---|---|---|']
    for p in r['extra']:
        w.append(f"| {p['sec']:.1f} | {p['kata']} | {p['text'] or p['line']} | {p['why']} |")
    w += ['', '## 拾えた強調', '', '| 秒 | お手本の型 | AI の型 | お手本の文 | AI の文 |', '|---|---|---|---|---|']
    for it, ip in sorted(r['tm'].items()):
        w.append(f"| {t[it]['sec']:.1f} | {t[it]['kata']} | {picks[ip]['kata']} | {t[it]['text']} | {picks[ip]['text'] or picks[ip]['line']}{'' if same_words(t[it], picks[ip]) else '（位置だけ）'} |")
    text = '\n'.join(w) + '\n'
    if a.out:
        open(a.out, 'w', encoding='utf-8').write(text)
    print('\n'.join(w[:15]))
    for k, (c, x) in sorted(r['by_kata'].items(), key=lambda kv: -kv[1][0]):
        print(f"  {k}: {x}/{c}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('make')
    p.add_argument('--ref', choices=list(REFS), required=True)
    p.add_argument('--from', dest='t0', type=float, required=True, help='タイムラインの秒')
    p.add_argument('--to', dest='t1', type=float, required=True)
    p.add_argument('--out', required=True)
    p.set_defaults(fn=cmd_make)
    p = sub.add_parser('score')
    p.add_argument('--truth', required=True)
    p.add_argument('--picks', required=True)
    p.add_argument('--rule', help='AI に読ませた決まり（例文と同じお手本を外す）')
    p.add_argument('--out')
    p.set_defaults(fn=cmd_score)
    a = ap.parse_args()
    a.fn(a)


if __name__ == '__main__':
    main()
