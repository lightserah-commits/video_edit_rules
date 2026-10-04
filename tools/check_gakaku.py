#!/usr/bin/env python3
"""画角の変わり目の検査（どの案件でも使える道具。04 の zoom.gakaku_check。工程9）。
元：環境設定 v004 の _work/check_gakaku.py（V2 の無効のクリップ＝IsMuted を画面に数えない直し入り）。

画角が変わるコマ（カメラ＝V1 の大きさが変わる所＝寄り・引きの入りと出、画面＝V2 の出入り）で、テロップの出入りがそのコマにそろっているかを見る。
  ×：テロップの頭か終わりが、画角の変わるコマの前後 15コマ以内にあって、そのコマとずれている（数コマだけ前の絵・後の絵に残る・先に出る）
  ×：字幕（V6）・強調（V7）・説明（V5）が、画角の変わるコマをまたいでいる
  注意：右上タイトル（V8・V9）・ボード（V10）・札（V12〜V14）がまたいでいる（並べる座布団は寄りの上に重ねる作り。一覧だけ）
  数えないもの：V2 の無効のクリップ（映さない所）。画面の下（V1 が前後とも無効）でのカメラの大きさの切れ目。冒頭ハイライト（--hl-frames か --cuts）
  意図してまたがせた強調は --intended の JSON（{"テロップの文言の頭": "理由", …}）に書くと × に数えず「意図」に出す

使い方：
  python3 tools/check_gakaku.py --proj <版のフォルダ>/<案件>_vNNN.prproj --seq <シーケンス名> \\
      [--cuts <版>/_work/cuts_vNNN.json] [--out <版>/checks_gakaku.json] [--intended 意図.json] [--near 15]
  出力：--out（省くと .prproj と同じフォルダの checks_gakaku.json）。画面に「画角が変わる所 N、× N、…」
  トラックの役目は 02 の output_tracks の並び（V5 説明・V6 字幕・V7 強調・V8/V9 右上・V10 ボード・V12〜V14 札）。違う並びの案件は
  --strict "V5:説明,V6:字幕,V7:強調" --soft "V8:右上（シリーズ名）,…" --camera V1 --screen V2 で変える
"""
import argparse
import json
import os
import sys

ROOT = os.path.expanduser("~/Desktop/video_edit_rules")
sys.path.insert(0, os.path.join(ROOT, "tools"))
from native_prproj import Prproj, TPS  # noqa: E402
from prproj_motion import motion_of, is_muted  # noqa: E402

STRICT = "V5:説明,V6:字幕,V7:強調"
SOFT = "V8:右上（シリーズ名）,V9:右上（話題）,V10:ボード,V12:札1,V13:札2,V14:札3"


def roles(s):
    out = {}
    for part in [p for p in s.split(",") if p.strip()]:
        k, v = part.split(":", 1)
        out[k.strip()] = v.strip()
    return out


def main():
    ap = argparse.ArgumentParser(description="画角の変わり目でテロップが残る・先に出る・またぐ所を探す（04 の zoom.gakaku_check）")
    ap.add_argument("--proj", required=True, help="調べる .prproj（AI が組み立てたもの。読むだけ）")
    ap.add_argument("--seq", required=True, help="シーケンス名")
    ap.add_argument("--out", help="出力の JSON（省くと .prproj と同じフォルダの checks_gakaku.json）")
    ap.add_argument("--cuts", help="cuts_vNNN.json（highlight_external_frames＝冒頭ハイライトのコマ数を読む。その間は数えない）")
    ap.add_argument("--hl-frames", type=int, help="冒頭ハイライトのコマ数（--cuts より優先）")
    ap.add_argument("--intended", help="意図してまたがせたテロップ {文言の頭: 理由} の JSON")
    ap.add_argument("--near", type=int, default=15, help="ずれを × にするコマ数（既定 15）")
    ap.add_argument("--strict", default=STRICT, help=f"またいだら × のトラック（既定 {STRICT}）")
    ap.add_argument("--soft", default=SOFT, help="またいでも一覧だけのトラック")
    ap.add_argument("--camera", default="V1", help="カメラのトラック（既定 V1）")
    ap.add_argument("--screen", default="V2", help="画面のトラック（既定 V2）")
    ap.add_argument("--show", type=int, default=30, help="画面に出す行数")
    a = ap.parse_args()

    pj = Prproj.load(a.proj)
    seq = pj.sequence(a.seq)
    FT = pj.frame_ticks(seq)
    fps = TPS / FT
    tr = dict(pj.tracks(seq))

    def spans(name):
        if name not in tr:
            return []
        out = []
        for it in pj.items(tr[name]):
            s, e = pj.span(it)
            out.append((s // FT, e // FT, it))
        return sorted(out, key=lambda x: x[0])

    def ts(f):
        s = f / fps
        return f"{int(s // 60)}:{s % 60:05.2f}"

    def text_of(it):
        try:
            return "".join("".join(r) for r in pj.item_texts(it)).replace("\r", "／")[:30]
        except Exception:
            return ""

    cam = []
    for s, e, it in spans(a.camera):
        sc, _, _ = motion_of(pj, it)
        cam.append((s, e, round(sc, 1), is_muted(it)))
    changes = []
    for (s0, e0, c0, m0), (s1, e1, c1, m1) in zip(cam, cam[1:]):
        if c0 != c1 and e0 == s1 and not (m0 and m1):    # 画面の下（カメラが前後とも無効）の大きさの切れ目は見えないので数えない
            changes.append((s1, f"カメラの大きさ {c0:g}→{c1:g}"))
    scr = []
    for s, e, it in spans(a.screen):
        if is_muted(it):                                 # 無効のクリップ（映さない所）は画面に数えない（環境設定 v004 点検[36]）
            continue
        if scr and scr[-1][1] == s:
            scr[-1][1] = e
        else:
            scr.append([s, e])
    for s, e in scr:
        changes += [(s, "画面に切り替わる"), (e, "カメラに戻る")]
    hl = a.hl_frames
    if hl is None and a.cuts:
        hl = json.load(open(a.cuts, encoding="utf-8")).get("highlight_external_frames", 0)
    hl = hl or 0
    changes = sorted(c for c in changes if c[0] > hl)
    strict, soft = roles(a.strict), roles(a.soft)
    intended_map = json.load(open(a.intended, encoding="utf-8")) if a.intended else {}
    bad, note, intended = [], [], []
    tel = {n: spans(n) for n in list(strict) + list(soft)}
    for f, what in changes:
        for n, lst in tel.items():
            kind = strict.get(n) or soft.get(n)
            for s, e, it in lst:
                for edge, g in (("頭", s), ("終わり", e)):
                    if g != f and abs(g - f) <= a.near:
                        bad.append({"at": ts(f), "frame": f, "change": what, "track": n, "kind": kind, "edge": edge, "off_frames": g - f,
                                    "telop": text_of(it)})
                if s < f - a.near and e > f + a.near:
                    row = {"at": ts(f), "frame": f, "change": what, "track": n, "kind": kind, "telop": text_of(it), "span": [ts(s), ts(e)]}
                    why = [w for k, w in intended_map.items() if row["telop"].replace("／", "").startswith(k)]
                    if n in strict and why:
                        row["why"] = why[0]
                        intended.append(row)
                    else:
                        (bad if n in strict else note).append(row)
    out = {"proj": os.path.abspath(a.proj), "sequence": a.seq, "changes": len(changes), "bad": bad, "straddle_soft": note,
           "straddle_intended": intended,
           "rule": f"画角が変わるコマで、前のテロップを残さない・先に出さない（04 の zoom）。{a.near}コマ以内のずれは×、"
                   f"{'・'.join(strict.values())}のまたぎは×（V2 の無効のクリップは画面に数えない。画面の下のカメラの大きさの切れ目は数えない）"}
    dst = a.out or os.path.join(os.path.dirname(os.path.abspath(a.proj)), "checks_gakaku.json")
    json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"画角が変わる所 {len(changes)}、× {len(bad)}、またぐ右上タイトル・札・ボード {len(note)}、意図したまたぎ {len(intended)} → {dst}")
    for r in bad[:a.show]:
        print("  ×", r["at"], r["change"], r["kind"], r.get("edge", "またぐ"), r.get("off_frames", ""), r["telop"])
    for r in intended:
        print("  意図", r["at"], r["change"], r["kind"], r["telop"], r["span"], r["why"][:40])
    for r in note[:a.show]:
        print("  注意", r["at"], r["change"], r["kind"], r["telop"], r["span"])


if __name__ == "__main__":
    main()
