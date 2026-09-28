"""切った部分（前へ飛ぶつなぎ目）の中身を、文字起こしから大まかに分ける。最後は人（AI）が読んで確かめる前提の下ごしらえ。

  無音        ：声のある割合が 0.15 未満で、語が無い
  つなぎ言葉  ：語が全部フィラー（えー・あの・まあ・なんか など）
  言い直し    ：切った部分の頭が、切った後に続く言葉と同じ言い出し（3文字以上一致）／切った部分が切った後の言葉を含む
  構成        ：10秒以上
  その他      ：上のどれでもない（中身を読んで判断する）

使い方: python classify.py <cut_*.json（--asr つきで作ったもの）> <出力.json>
"""
import json
import re
import sys

FILLERS = {"えー", "え", "えっと", "えーと", "えーっと", "あの", "あのー", "あー", "あ", "まあ", "まぁ", "うん", "うーん", "ん", "んー",
           "なんか", "その", "ね", "で", "そう", "うーんと", "はい", "ま", "こう"}


def norm(s):
    return re.sub(r"[、。？！\?\!\s・…「」]", "", s or "")


def is_filler(text):
    t = norm(text)
    if not t:
        return True
    rest = t
    for f in sorted(FILLERS, key=len, reverse=True):
        rest = rest.replace(f, "")
    return len(rest) == 0


def common_prefix(a, b):
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def kind(j):
    L = j['jump']
    rt = norm(j.get('removed_text'))
    at = norm(j.get('after_text'))
    if L >= 10:
        return '構成'
    if j.get('removed_voice', 0) < 0.15 and not rt:
        return '無音'
    if is_filler(rt):
        return 'つなぎ言葉'
    if rt and at and (common_prefix(rt, at) >= 3 or (len(rt) >= 3 and rt[:3] in at[:12]) or (len(at) >= 4 and at[:4] in rt)):
        return '言い直し'
    return 'その他'


def main():
    d = json.load(open(sys.argv[1]))
    fw = [j for j in d['joins'] if j['kind'] == '前へ飛ぶ']
    out = {'sequence': d['sequence'], 'counts': {}, 'sec': {}, 'items': []}
    for j in fw:
        k = kind(j)
        j['cut_kind'] = k
        out['counts'][k] = out['counts'].get(k, 0) + 1
        out['sec'][k] = round(out['sec'].get(k, 0) + j['jump'], 1)
        out['items'].append({k2: j.get(k2) for k2 in ('tl', 'jump', 'cut_kind', 'removed_voice', 'before_text',
                                                    'removed_text', 'after_text', 'tail_kept', 'head_kept')})
    json.dump(out, open(sys.argv[2], 'w'), ensure_ascii=False, indent=1)
    print(d['sequence'], out['counts'], out['sec'])


if __name__ == '__main__':
    main()
