#!/usr/bin/env python3
"""完成版から「テロップ見本集」プロジェクトを作る。

完成版プロジェクトのコピーの中で、本編シーケンスのクリップを外し、その代わりに
部品棚（type_catalog.py の types.json）の代表の実物を、部品ごと複製して並べる。
  A. テロップ型 … 代表のテロップ＋元で同時に置かれていた調整レイヤー・SE＋背景の映像（元の場面から切り出し）
  B. 画面効果   … 調整レイヤー＋背景の映像
  C. SE          … 音
  D. 場面見本   … 完成版の区間を、全トラックごと丸ごと複製（組み合わせ方の実例）
複製は完全な部品コピーなので、見た目・アニメーション・音量は元と同じ。変えるのはフォントの置き換えだけ
（HiraKakuStdN-W8 → HiraginoSans-W8。このMacのPremiereでは前者が使えないため）。

使い方:
  python3 build_library.py --reference 完成.prproj --sequence 本編シーケンス名 --types 見本/分類/types.json --out 見本/テロップ見本集.prproj
"""
import argparse
import json
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from native_prproj import Prproj, TPS  # noqa: E402

FRAME_T = 8475667200          # 29.97fps の1フレーム（ticks）。置く位置と長さはすべてこの整数倍にする
GAP_T = 30 * FRAME_T           # 見本と見本の間（30フレーム）
CAMERA = re.compile(r"^(IMG_|BCVX|LCAU)|\.(mov|mp4)$", re.I)
AUDIO = re.compile(r"\.(wav|mp3|aiff?|m4a)$", re.I)
FONT_SWAP = [("HiraKakuStdN-W8", "HiraginoSans-W8")]

SCENES = [
    ("D01", "オープニング（ダイジェスト→タイトル→挨拶）", 0.0, 18.0),
    ("D02", "決め・皮肉・肯定の連続（BGM停止・寄り・引きを含む）", 111.0, 150.0),
    ("D03", "列挙（1項目ずつ cursor1）", 164.0, 184.0),
    ("D04", "再現シーン（シネスコ帯・左右反転・BGM停止）", 302.0, 352.0),
    ("D05", "章の入り（ポイント→章カード→項目名カード）", 466.0, 490.0),
    ("D06", "画面操作（画面録画＋クリック音）", 813.0, 832.0),
    ("D07", "CTA（概要欄・LINE・1on1）", 1183.0, 1192.0),
]


def name_of(pj, it):
    sub = pj.ref(it.find("ClipTrackItem/SubClip"))
    return unicodedata.normalize("NFC", sub.findtext("Name") or "") if sub is not None else ""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reference", required=True)
    ap.add_argument("--sequence", required=True)
    ap.add_argument("--types", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--sections", default="ABCD", help="作る区画（例: A, AB, ABCD）")
    ap.add_argument("--no-bg", action="store_true", help="背景の映像を敷かない")
    ap.add_argument("--no-mates", action="store_true", help="同時に置かれた調整レイヤー・SEを付けない")
    ap.add_argument("--limit", type=int, default=0, help="各区画の件数の上限（切り分け用）")
    a = ap.parse_args()
    cat = json.load(open(a.types, encoding="utf-8"))
    pj = Prproj.load(a.reference)
    seq = pj.sequence(a.sequence)

    # 元の配置を覚えてから、本編のクリップを外す
    orig = []
    for tn, tr in pj.tracks(seq):
        for it in pj.items(tr):
            s, e = pj.span(it)
            orig.append({"track": tn, "s": s / TPS, "e": e / TPS, "st": s, "et": e, "el": it, "name": name_of(pj, it),
                         "enabled": it.find("ClipTrackItem/IsMuted") is None})
    pj.detach_all(seq)
    pj.rename_sequence(seq, "テロップ見本集")

    def find(track, start):
        c = [o for o in orig if o["track"] == track and abs(o["s"] - start) < 0.02]
        if not c:
            raise KeyError(f"{track} {start}")
        return c[0]

    def is_adjust(o):
        return o["name"] == "調整レイヤー"

    def is_se(o):
        return o["track"].startswith("A") and o["track"] != "A1" and AUDIO.search(o["name"]) and (o["e"] - o["s"]) < 10 \
            and "メインテーマ" not in o["name"] and "BGM" not in o["name"]

    cloned_texts = []
    placed = []

    def clone(o, at_t, off_t=0, dur_t=None):
        """at_t, off_t, dur_t はすべて ticks（フレームの整数倍）"""
        dur_t = dur_t if dur_t is not None else (o["et"] - o["st"] - off_t)
        new = pj.clone_item(o["el"], seq, o["track"], start_ticks=at_t, duration_ticks=dur_t, src_offset_ticks=off_t)
        if pj.text_components(new):
            cloned_texts.append(new)
        return new

    def background(ws_t, we_t, at_t):
        """元の場面の映像（V1〜V4のカメラ・画面録画）を、同じ長さだけ切り出して敷く（ticks）。"""
        n = 0
        for o in orig:
            if not o["enabled"] or o["track"] not in ("V1", "V2", "V3", "V4") or not CAMERA.search(o["name"]):
                continue
            a0, b0 = max(o["st"], ws_t), min(o["et"], we_t)
            if b0 - a0 < FRAME_T:
                continue
            clone(o, at_t + (a0 - ws_t), off_t=a0 - o["st"], dur_t=b0 - a0)
            n += 1
        return n

    def snap(sec):
        return int(round(sec * 30000 / 1001)) * FRAME_T

    t = 0  # ticks
    record = []
    # A. テロップ型
    lim = (lambda xs: xs[:a.limit] if a.limit else xs)
    for ty in (lim(cat["telop_types"]) if "A" in a.sections else []):
        rep = find(ty["rep"]["track"], ty["rep"]["start"])
        rs, re_ = rep["st"], rep["et"]
        mates = [] if a.no_mates else [o for o in orig if o["enabled"] and o is not rep and abs(o["st"] - rs) <= 2 * FRAME_T and (is_adjust(o) or is_se(o))]
        ws = min([rs] + [m["st"] for m in mates])
        we = max([re_] + [m["et"] for m in mates])
        if not a.no_bg:
            background(ws, we, t)
        clone(rep, t + (rs - ws))
        for m in mates:
            clone(m, t + (m["st"] - ws))
        record.append({"section": "A", "id": ty["id"], "start": round((t + rs - ws) / TPS, 4), "end": round((t + we - ws) / TPS, 4),
                       "source": {"track": rep["track"], "start": round(rs / TPS, 4), "end": round(re_ / TPS, 4)},
                       "text": ty["rep"]["text"], "animation": ty["animation"], "count": ty["count"],
                       "with": [f"{m['track']} {m['name']}" for m in mates]})
        t += (we - ws) + GAP_T
    # B. 画面効果
    for ef in (lim(cat["screen_effects"]) if "B" in a.sections else []):
        rep = find(ef["rep"]["track"], ef["rep"]["start"])
        dur_t = min(rep["et"] - rep["st"], 180 * FRAME_T)
        if not a.no_bg:
            background(rep["st"], rep["st"] + dur_t, t)
        clone(rep, t, dur_t=dur_t)
        record.append({"section": "B", "id": ef["id"], "start": round(t / TPS, 4), "end": round((t + dur_t) / TPS, 4),
                       "source": {"track": rep["track"], "start": round(rep["s"], 4), "end": round(rep["e"], 4)},
                       "summary": ef["summary"], "count": ef["count"]})
        t += dur_t + GAP_T
    # C. SE
    for se in (lim(cat["se"]) if "C" in a.sections else []):
        rep = find(se["rep"]["track"], se["rep"]["start"])
        clone(rep, t)
        d_t = rep["et"] - rep["st"]
        record.append({"section": "C", "id": se["id"], "start": round(t / TPS, 4), "end": round((t + d_t) / TPS, 4),
                       "source": {"track": rep["track"], "start": round(rep["s"], 4)}, "file": se["file"], "gain_db": se["gain_db"],
                       "count": se["count"]})
        t += max(d_t, 30 * FRAME_T) + GAP_T
    # D. 場面見本（全トラック丸ごと）
    for sid, title, ws_s, we_s in (lim(SCENES) if "D" in a.sections else []):
        ws, we = snap(ws_s), snap(we_s)
        n = 0
        for o in orig:
            if not o["enabled"]:
                continue
            a0, b0 = max(o["st"], ws), min(o["et"], we)
            if b0 - a0 < FRAME_T:
                continue
            clone(o, t + (a0 - ws), off_t=a0 - o["st"], dur_t=b0 - a0)
            n += 1
        record.append({"section": "D", "id": sid, "title": title, "start": round(t / TPS, 4), "end": round((t + we - ws) / TPS, 4),
                       "source": {"start": round(ws / TPS, 4), "end": round(we / TPS, 4)}, "clips": n})
        t += (we - ws) + 2 * GAP_T

    swapped = sum(pj.replace_font(it, old, new) for it in cloned_texts for old, new in FONT_SWAP)
    removed = pj.gc()
    pj.save(a.out)
    idx_path = os.path.splitext(a.out)[0] + "_目次.json"
    json.dump({"project": os.path.basename(a.out), "sequence": "テロップ見本集", "duration_sec": round(t / TPS, 1),
               "font_swap": FONT_SWAP, "samples": record}, open(idx_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"見本 {len(record)}件（A {sum(r['section']=='A' for r in record)} / B {sum(r['section']=='B' for r in record)} / "
          f"C {sum(r['section']=='C' for r in record)} / D {sum(r['section']=='D' for r in record)}）、全長 {t / TPS / 60:.1f}分、"
          f"フォント置換 {swapped}、掃除した部品 {removed} → {a.out}")


if __name__ == "__main__":
    main()
