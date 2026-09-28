#!/usr/bin/env python3
"""型一覧（人が読む記録）を作る。types.json と見本集の目次から、見本/型一覧.md を生成する。

  python3 make_type_list.py   （既定の場所を使う）
"""
import json
import os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
TYPES = os.path.join(ROOT, "見本", "分類", "types.json")
INDEX = os.path.join(ROOT, "見本", "テロップ見本集_目次.json")
OUT = os.path.join(ROOT, "見本", "型一覧.md")

# 保存スタイル → 系統名・演出パターン（02_演出パターン.yaml）
FAMILY = {
    "みかみテロップ": ("通常字幕（メイン話者）", "NONE"),
    "質問者テロップ": ("通常字幕（聞き手）", "NONE"),
    "強調赤黄": ("強調赤黄（決め・断言）", "P01"),
    "ゴージャス金": ("ゴージャス金（成果・ポジティブ）", "P02"),
    "ゴージャス青": ("ゴージャス青（名言・肯定）", "P03"),
    "シュールテロップ": ("シュール明朝（本音・皮肉）", "P04"),
    "ヒラギノ白シャドウ": ("ヒラギノ白シャドウ（笑い・呆れ・注釈）", "P05"),
    "ツッコミ": ("ツッコミ（強いツッコミ）", "P06"),
    "白テキ": ("白テキ（短い反応）", "P07"),
    "基本テロップ赤": ("基本テロップ赤（要点の一文）", "P08"),
    "テキストスタイル": ("ポイントボード", "P09"),
    "対談用_質問者テロップ": ("項目名カード（章）", "P10"),
    "青背景": ("青背景ラベル（列挙・図解）", "P11"),
    "黄色見出し": ("黄色見出し", "P14"),
    "白ベース": ("白ベース（人物・用語の補足）", "P13"),
    "ブラック風_通常テロップ": ("注記ボックス", "P13"),
}


def family_of(t):
    if t.get("family"):                      # 2本目など、別の完成版から足した型（区画F）は系統を持っている
        return (t["family"], t.get("pattern", "―"))
    text = t["rep"]["text"]
    if text.startswith("ポイント"):
        return ("ポイントボード", "P09")
    if "PA1GothicStd-Bold" in t["fonts"]:
        return ("章見出し（番号カード）", "P10")
    if "SourceHanSans-Heavy" in t["fonts"] and ("⬆" in text or "LINE" in text or "こちら" in text):
        return ("CTA（概要欄・LINE）", "P14")
    for s in t["styles"]:
        if s in FAMILY:
            return FAMILY[s]
    tr = next(iter(t["tracks"]), "")
    if tr == "V6":
        return ("右上：シリーズ名", "構造")
    if tr == "V5":
        return ("右上：話題タイトル", "構造")
    if "PA1GothicStd-Bold" in t["fonts"]:
        return ("章見出し（番号カード）", "P10")
    if "SourceHanSans-Heavy" in t["fonts"]:
        return ("CTA（概要欄・LINE）", "P14")
    return ("その他（スタイルなし・個別デザイン）", "―")


def tc(sec):
    """見本集での位置（29.97fps ドロップフレーム表記）"""
    frame = int(round(sec * 30000 / 1001))
    d, m = divmod(frame, 17982)
    adj = 18 * d + (2 * ((m - 2) // 1798) if m >= 2 else 0)
    f = frame + adj
    return f"{f // 108000:02d};{(f // 1800) % 60:02d};{(f // 30) % 60:02d};{f % 30:02d}"


def src(sec):
    return f"{int(sec // 60):02d}:{sec % 60:05.2f}"


def main():
    types = json.load(open(TYPES, encoding="utf-8"))
    idx = {s["id"]: s for s in json.load(open(INDEX, encoding="utf-8"))["samples"]}
    eff = {e["id"]: e for e in types["screen_effects"]}
    L = ["# 型一覧（テロップ型・画面効果・SE）", "",
         "完成版（みかみさんCH0726_最終 / AI使いこなす習慣7選）で使われた演出を、実物ごとに分類した一覧。",
         "「見本集の位置」は `見本/テロップ見本集.prproj` の「テロップ見本集」シーケンスでのタイムコード（そこに実物がある）。",
         "「元の位置」は完成版の本編での時刻。新しい動画では `tools/reproduce.py` で型IDを指定して複製する。", "",
         "件数が1の型は、完成版で1回だけ使われた一点物（サイズや位置を個別に調整したもの）。",
         "区画F（T199〜）は2本目（AI時代に消える仕事残る仕事）から足した型。「元の位置」は2本目のシーケンス名と時刻。",
         "区画G（E020〜）は図解の土台の黒い板（2本目から。09_図解.md）。もう1つの土台のぼかしは E016。", ""]
    groups = defaultdict(list)
    for t in types["telop_types"]:
        groups[family_of(t)].append(t)
    order = sorted(groups.items(), key=lambda kv: -sum(t["count"] for t in kv[1]))
    L += ["## テロップ型（T）", "", "| 系統 | パターン | 型の数 | 使用回数 |", "|---|---|---|---|"]
    for (fam, pat), ts in order:
        L.append(f"| {fam} | {pat} | {len(ts)} | {sum(t['count'] for t in ts)} |")
    for (fam, pat), ts in order:
        L += ["", f"### {fam}（{pat}）", "",
              "| 型 | 回数 | 見本集の位置 | 元の位置 | アニメーション | 一緒の画面効果 | 一緒のSE | 代表の文字 |",
              "|---|---|---|---|---|---|---|---|"]
        for t in sorted(ts, key=lambda x: (-x["count"], x["id"])):
            s = idx.get(t["id"])
            where = tc(s["start"]) if s else "―"
            effs = "、".join(f"{k}（{eff[k]['summary'][:14]}）×{v}" if k in eff else f"{k}×{v}" for k, v in t["adjust_with"].items()) or "―"
            ses = "、".join(f"{k.replace('.wav', '').replace('.mp3', '')}×{v}" for k, v in list(t["se_with"].items())[:3]) or "―"
            text = t["rep"]["text"].replace("|", "｜")[:30]
            origin = ("2本目 " + t.get("source_sequence", "") + " ") if t.get("source_project") else ""
            L.append(f"| {t['id']} | {t['count']} | {where} | {origin}{t['rep']['track']} {src(t['rep']['start'])} | {t['animation']} | {effs} | {ses} | {text} |")
    L += ["", "## 画面効果（E）", "", "調整レイヤー。置いたトラックより下（映像）に効く。E020〜 は図解の土台の黒い板（シェイプ。上に図の部品を重ねる）。", "",
          "| 型 | 回数 | 見本集の位置 | 元の位置 | 中身 |", "|---|---|---|---|---|"]
    for e in types["screen_effects"]:
        s = idx.get(e["id"])
        origin = ("2本目 " + e.get("source_sequence", "") + " ") if e.get("source_project") else ""
        L.append(f"| {e['id']} | {e['count']} | {tc(s['start']) if s else '―'} | {origin}{e['rep']['track']} {src(e['rep']['start'])} | {e['summary']} |")
    L += ["", "## SE（S）", "", "同じ音でも、完成版で設定されていた音量（クリップゲイン）ごとに分けている。", "",
          "| 型 | 回数 | 見本集の位置 | 音源 | ゲイン(dB) |", "|---|---|---|---|---|"]
    for se in types["se"]:
        s = idx.get(se["id"])
        L.append(f"| {se['id']} | {se['count']} | {tc(s['start']) if s else '―'} | {se['file']} | {se['gain_db']} |")
    L += ["", "## 場面見本（D）", "", "完成版の区間を、全トラック（映像・声・BGM・SE・テロップ・調整レイヤー）ごと複製したもの。組み合わせ方の実例。", "",
          "| 場面 | 見本集の位置 | 元の区間 | 内容 |", "|---|---|---|---|"]
    for sid, s in idx.items():
        if s["section"] == "D":
            L.append(f"| {sid} | {tc(s['start'])} | {src(s['source']['start'])}〜{src(s['source']['end'])} | {s['title']} |")
    open(OUT, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("→", OUT)


if __name__ == "__main__":
    main()
