#!/usr/bin/env python3
"""章の帯の項目名カード（T093・T018）の文字が、白い箱からはみ出していないかの検査（どの案件でも使える道具。06 の principle。工程9）。
1021 v002 で、章の帯③「よくあるループと三上さんのループ」・④「ゴールループのテンプレートを作る」（16字）が見本の大きさのままだと
白い箱からはみ出し、③は最後の「プ」の丸が切れて「ルーフ」に見えた（2026-10-22 小川さん「テーマの文字がはみ出てる」）。

  ×：文字の横幅（画面の px）が CARD_MAX_W（1600px。白い箱 x60〜1860 の 1800px から左右 100px ずつ空けた幅）を超える
  見つけ方：ボードの段（--track。既定 V10）で、文字の層が1つ・1行だけのテロップを項目名カードとみなす（ポイントボード・受け取り方のボードは2つ以上の層を持つ）
  横幅：tools/telop_size.measure の値 ÷ 1.67（06 の注意：項目名カードは実際の約1.67倍に数える）

使い方：
  python3 tools/check_card_fit.py <版>.prproj --seq <シーケンス名> [--track V10] [--out <版>/checks_card_fit.json]
  → 1行ずつ「時刻・文字・字数・横幅・○×」。× があると終了コード 1
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # このフォルダ（tools/ の1つ上）
sys.path.insert(0, os.path.join(ROOT, "tools"))
from native_prproj import Prproj, TPS  # noqa: E402
import telop_size  # noqa: E402

CARD_MAX_W = 1600.0
CARD_W_FACTOR = 1.67


def main():
    ap = argparse.ArgumentParser(description="項目名カードの文字のはみ出しの検査", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("proj")
    ap.add_argument("--seq", required=True)
    ap.add_argument("--track", default="V10")
    ap.add_argument("--out")
    a = ap.parse_args()
    pj = Prproj.load(a.proj)
    seq = pj.sequence(a.seq)
    fonts = telop_size.Fonts()
    rows = []
    for it in pj.items(pj.track(seq, a.track)):
        texts = pj.item_texts(it)
        if len(texts) != 1 or len(texts[0]) != 1 or "\r" in texts[0][0] or "\n" in texts[0][0]:
            continue
        m = telop_size.measure(pj, it, fonts)
        if not m["lines"]:
            continue
        w = max(x for x, _ in m["lines"]) / CARD_W_FACTOR
        s, _ = pj.span(it)
        t = s / TPS
        rows.append({"sec": round(t, 2), "time": f"{int(t // 60)}:{t % 60:04.1f}", "text": texts[0][0], "chars": len(texts[0][0]),
                     "width_px": round(w), "ok": w <= CARD_MAX_W + 1})   # 縮めた値の丸めの誤差を1px許す
    for r in rows:
        print(f"{r['time']:>8}  {'○' if r['ok'] else '×'}  {r['width_px']:5}px  {r['chars']:2}字  {r['text']}")
    ng = [r for r in rows if not r["ok"]]
    print(f"項目名カード {len(rows)}、× {len(ng)}（横幅の上限 {CARD_MAX_W:.0f}px）")
    if a.out:
        json.dump({"max_w": CARD_MAX_W, "cards": rows}, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    sys.exit(1 if ng else 0)


if __name__ == "__main__":
    main()
