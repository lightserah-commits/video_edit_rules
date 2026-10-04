#!/usr/bin/env python3
"""強調テロップの文言が「その1枚で言い切った一文」になっているかを、文字の形で見る。

ルールは 01_判断フロー.md の「強調テロップの文言」（2026-09-27）。意味が通るか・意味が変わっていないかは
このツールでは分からないので、AI が読んで決め、報告の一覧で人に見てもらう。

見ること（どれも言葉の形だけ）:
  文末  … 途中で切れている（〜から・〜けど・〜ので・〜って・〜っていう・〜とか・〜のは・〜を など）→ ×
  文頭  … 前の話につなぐ言葉で始まる（だから・でも・で・そしたら・しかも・って など）→ △
  ぼかし… っていう・みたいな・って感じ・わけ・と思います・んですけど など → △（感情の強調では口調として残してよい）
  指示語… これ・それ・こいつ・ここ・こっち など → ？（画面や直前の字幕で分かるか、目で確かめる）
  倒置・「…」の前振り・「〜のでは」・お願いの「〜て」→ ？
  長さ  … 空白と記号を除いた文字数（参考。意味の強調は字数では削らない＝主語・述語・何の話かをそろえる。感情の強調は9字前後。01 2026-10-02）

使い方:
  python3 tools/kyocho_check.py 文言 [文言 ...]
  python3 tools/kyocho_check.py --csv vNNN/decoration_plan.csv
      P01〜P08 の行の「文字・内容」を見る。「種類」列（意味／感情）と「元の言葉」列があれば使う。
      × が1件でもあれば終了コード1
  組み立てのスクリプトから:
      from kyocho_check import require_texts
      require_texts([{"at": "00:34.30", "pattern": "P08", "kind": "意味", "text": "…", "source": "字幕の文字"}, ...])
      文が空・種類が無い・× がある時は、一覧を出して止める（字幕の文字で埋めない）
"""
import csv
import re
import sys

TAIL_SYMBOLS = r"[\s！!？?…。、,.・w ｗ〜~」』）)\"'”’]+$"
# 文末：途中で切れている（強い）。「て」はお願いの形（教えて・押しといて）もあるので「要確認」に分ける
END_CUT = [
    ("っていう", "引用の途中（〜っていう）"), ("っていうか", "引用の途中"), ("みたいな", "ぼかしで終わる（〜みたいな）"),
    ("みたいなの", "ぼかしで終わる"), ("って感じ", "ぼかしで終わる（〜って感じ）"), ("とかって", "引用の途中"),
    ("ということで", "つなぎで終わる（ということで）"), ("ってことで", "つなぎで終わる"),
    ("から", "理由の途中（〜から）"), ("けど", "逆接の途中（〜けど）"), ("けども", "逆接の途中"), ("ので", "理由の途中（〜ので）"),
    ("んで", "理由の途中（〜んで）"), ("なんで", "理由の途中（〜なんで）"), ("ながら", "途中（〜ながら）"),
    ("のに", "途中（〜のに）"), ("たら", "条件の途中（〜たら）"), ("れば", "条件の途中（〜れば）"), ("ても", "途中（〜ても）"),
    ("わけで", "途中（〜わけで）"), ("くらい", "途中（〜くらい）"), ("ぐらい", "途中（〜ぐらい）"), ("とか", "例示の途中（〜とか）"),
    ("って", "引用の途中（〜って）"), ("のは", "主語だけ（〜のは）"),
    ("を", "助詞で終わる（〜を）"), ("が", "助詞で終わる（〜が）"), ("に", "助詞で終わる（〜に）"), ("へ", "助詞で終わる"),
    ("は", "助詞で終わる（〜は）"), ("で", "途中（〜で）"),
]
END_CHECK = [("のでは", "〜のでは（問いかけなら可）"), ("て", "〜て で終わる（お願いの形なら可）"), ("と", "〜と で終わる（引用の途中？）"), ("し", "〜し で終わる（並べる途中？）"),
             ("じゃないですか", "前振りの言い方（〜じゃないですか）")]
START = ["だから", "でも", "で、", "で ", "それで", "そしたら", "そうしたら", "しかも", "って", "っていうか", "ていうか",
         "まあ", "なんか", "じゃあ", "ほら", "もちろん", "ということで", "それなのに", "結局さ", "あと", "なので", "だって", "けど"]
HEDGE = ["っていう", "みたいな", "って感じ", "わけよ", "わけです", "わけで", "と思います", "と思う", "んですけど", "んですよ",
         "なんですよ", "気がする", "とかが", "とかは"]
HEDGE_END = ["かな", "かなって"]
DEMONST = ["これ", "それ", "あれ", "こいつ", "そいつ", "あいつ", "ここ", "そこ", "こっち", "そっち", "こういう", "そういう",
           "こんな", "そんな", "こうやって", "こうしたら"]


def core(text):
    t = text.replace("\r", " ").replace("/", " ").replace("／", " ")
    t = re.sub(r"\s+", " ", t).strip()
    return t


def check(text):
    t = core(text)
    body = re.sub(TAIL_SYMBOLS, "", t)
    res = {"text": t, "chars": len(re.sub(r"[\s!-/:-@\[-`{-~！？…、。「」『』（）・〜ｗw]", "", t)), "end": "", "end_check": "",
           "start": "", "hedge": [], "demonst": []}
    if re.search(r"(…|\.\.\.)[\s?？]*$", t):
        res["end_check"] = "「…」で終わる（次のオチへつなぐ前振りなら可）"
    for suf, why in ([] if res["end_check"] else sorted(END_CUT, key=lambda x: -len(x[0]))):
        if body.endswith(suf):
            if suf == "って" and re.search(r"[いだよるた]って$", body):
                res["end_check"] = "〜って で終わる（強めの言い切り？引用の途中？）"
                break
            # 倒置：前の区切りが言い切りで終わり、後ろに言葉が付いているだけ（「100倍賢いやん こっちの方が」）
            segs = t.split(" ")
            if len(segs) > 1 and any(re.search(r"(る|た|い|だ|よ|ね|やん|じゃん|です|ます|な|ぞ|ぜ|わ)$", s) for s in segs[:-1]):
                res["end_check"] = "倒置？（言い切りの後ろに言葉が付いている）"
                break
            res["end"] = why
            break
    if not res["end"] and not res["end_check"]:
        for suf, why in END_CHECK:
            if body.endswith(suf) and not (suf == "と" and body.endswith("こと")):
                res["end_check"] = why
                break
    for w in START:
        if t.startswith(w):
            res["start"] = w.strip("、 ")
            break
    res["hedge"] = [w for w in HEDGE if w in t] + [w for w in HEDGE_END if body.endswith(w)]
    if re.match(r"^で(僕|俺|私|これ|それ|この|その|今|実は)", t) and not res["start"]:
        res["start"] = "で"
    res["demonst"] = [w for w in DEMONST if w in t]
    return res


def verdict(r, kind=""):
    if r["end"]:
        return "×途中で切れている"
    if r["start"] or (r["hedge"] and kind != "感情"):
        return "△削れる言葉がある"
    if r["end_check"]:
        return "？文末を確認"
    if r["demonst"]:
        return "？指示語を確認"
    return "○"


def notes(r):
    return [x for x in [r["end"], r["end_check"], ("文頭「%s」" % r["start"]) if r["start"] else "",
                        ("ぼかし「%s」" % "・".join(r["hedge"])) if r["hedge"] else "",
                        ("指示語「%s」" % "・".join(r["demonst"])) if r["demonst"] else ""] if x]


def norm(s):
    return re.sub(r"[\s/／\r、。！？!?…]", "", s or "")


def require_texts(items):
    """組み立ての前に呼ぶ。問題があれば一覧を出して SystemExit。"""
    bad = []
    for it in items:
        at = it.get("at", "")
        text, kind = (it.get("text") or "").strip(), it.get("kind", "")
        if not text:
            bad.append(f"{at} 強調の文が書かれていない（字幕の文字で埋めない。01「強調テロップの文言」で作る）")
            continue
        if kind not in ("意味", "感情"):
            bad.append(f"{at}「{text}」種類（意味／感情）が書かれていない")
        r = check(text)
        if r["end"]:
            bad.append(f"{at}「{text}」{r['end']}")
    if bad:
        raise SystemExit("強調テロップの文言を直してから組み立てる:\n  " + "\n  ".join(bad))
    same = [it for it in items if it.get("kind") == "意味" and it.get("source") and norm(it["text"]) == norm(it["source"])]
    if same:
        print(f"（参考）意味の強調で字幕と同じ文字のもの {len(same)}件。話した言葉がもともと一文なら問題ない")


def type_ratio(pats):
    """強調の型の割合を知らせる（01 の手順2「見直しのきっかけ」。止めない）。"""
    n = len(pats)
    red = sum(p in ("P01", "P08", "P06") for p, _ in pats)      # 赤黄・基本テロップ赤・ツッコミ
    gor = sum(p in ("P02", "P03") for p, _ in pats)             # ゴージャス金・青
    sur = sum(p == "P04" for p, _ in pats)
    emo = [p for p, k in pats if k == "感情"]
    emo_gold = sum(p == "P02" for p in emo)
    print(f"# 型の割合（強調 {n}件）：赤い系（赤黄・基本テロップ赤・ツッコミ）{red}・ゴージャス（金・青）{gor}・シュール {sur}", file=sys.stderr)
    warn = []
    if gor * 3 > red:
        warn.append(f"ゴージャスが赤い系の3分の1を超えている（{gor}／{red}。実演のお手本は約10分の1）")
    if emo and emo_gold / len(emo) > .1:
        warn.append(f"感情の強調の {100 * emo_gold / len(emo):.0f}% が金（お手本は3%。喜び・興奮の一言は赤黄か白シャドウ）")
    if n >= 20 and sur / n < .1:
        warn.append(f"シュールが {100 * sur / n:.0f}%（お手本は29%。冷めた言い方の結論・本音を見落としていないか）")
    for w in warn:
        print("# 見直す：" + w, file=sys.stderr)


def main():
    args = sys.argv[1:]
    items = []
    pats = []
    if args and args[0] == "--csv":
        for row in csv.DictReader(open(args[1], encoding="utf-8-sig")):
            if re.match(r"P0[1-8]$", row.get("パターンID", "")):
                items.append((row.get("時刻", ""), row.get("文字・内容", ""), row.get("種類", ""), row.get("元の言葉", "")))
                pats.append((row.get("パターンID", ""), row.get("種類", "")))
    else:
        items = [("", a, "", "") for a in args]
    count = {}
    for tm, text, kind, src in items:
        r = check(text)
        v = verdict(r, kind)
        count[v] = count.get(v, 0) + 1
        extra = f"\t元:{src}" if src else ""
        print(f"{tm}\t{v}\t{kind}\t{r['chars']}字\t{r['text']}\t{' / '.join(notes(r))}{extra}")
    if len(items) > 1:
        print("# " + "  ".join(f"{k} {n}" for k, n in sorted(count.items())), file=sys.stderr)
    if pats:
        type_ratio(pats)
    sys.exit(1 if any(k.startswith("×") for k in count) else 0)


if __name__ == "__main__":
    main()
