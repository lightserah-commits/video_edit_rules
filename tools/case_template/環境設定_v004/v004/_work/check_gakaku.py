"""v003 G1（2026-10-04 小川さん「縮小入る瞬間に若干このテロップが残ってる…基本、画角変化が入る時はテロップ消すように」）の検査。
画角が変わるコマ（V1 のカメラの大きさ＝ズーム・引きが変わる所、V2 の画面の出入り）で、テロップの出入りがそのコマにそろっているかを見る。
  ×：テロップの頭か終わりが、画角の変わるコマの前後 15コマ以内にあって、そのコマとずれている（数コマだけ前の絵・後の絵に残る・先に出る）
  ×：字幕（V6）・強調（V7）・説明（V5）が、画角の変わるコマをまたいでいる
  注意：右上タイトル（V8・V9）・札（V12〜V14）・ボード（V10）がまたいでいる（つなぎの札は寄りの上に重ねる作り。一覧だけ）
出力 checks_gakaku.json
  python3 v004/_work/check_gakaku.py"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
V = os.path.dirname(HERE)
sys.path.insert(0, os.path.expanduser("~/Desktop/video_edit_rules/tools"))
sys.path.insert(0, V)
from native_prproj import Prproj  # noqa: E402
from prj_helpers import component_param, get_static  # noqa: E402

NEAR = 15
pj = Prproj.load(os.path.join(V, "kankyo_v004.prproj"))
seq = pj.sequence("kankyo_v004")
FT = pj.frame_ticks(seq)
tr = dict(pj.tracks(seq))
FPS = 30000 / 1001


def spans(name):
    out = []
    for it in pj.items(tr[name]):
        a, b = pj.span(it)
        out.append((a // FT, b // FT, it))
    return sorted(out, key=lambda x: x[0])


def ts(f):
    s = f / FPS
    return f"{int(s // 60)}:{s % 60:05.2f}"


def text_of(it):
    try:
        return "".join("".join(r) for r in pj.item_texts(it)).replace("\r", "／")[:30]
    except Exception:
        return ""


def muted(it):
    return (it.findtext("ClipTrackItem/IsMuted") or "").strip() == "true"


v1 = []
for a, b, it in spans("V1"):
    mp = component_param(pj, it, "AE.ADBE Motion", {"スケール"})
    sc = float(get_static(mp["スケール"]).rstrip(".")) if "スケール" in mp else 100.0
    v1.append((a, b, round(sc, 1), muted(it)))
changes = []
for (a0, b0, s0, m0), (a1, b1, s1, m1) in zip(v1, v1[1:]):
    if s0 != s1 and b0 == a1 and not (m0 and m1):    # 画面の下（V1 が無効）の大きさの切れ目は見えないので数えない
        changes.append((a1, f"カメラの大きさ {s0:g}→{s1:g}"))
scr = []
for a, b, it in spans("V2"):
    # v004 点検[36]：V2 は全部の区間にクリップがあり、映さない所は無効（ClipTrackItem の IsMuted=true）。無効のクリップは画面に数えない
    if muted(it):
        continue
    if scr and scr[-1][1] == a:
        scr[-1][1] = b
    else:
        scr.append([a, b])
for a, b in scr:
    changes += [(a, "画面に切り替わる"), (b, "カメラに戻る")]
hl = json.load(open(os.path.join(HERE, "cuts_v004.json"))).get("highlight_external_frames", 0)
changes = sorted(c for c in changes if c[0] > hl)
STRICT = {"V5": "説明", "V6": "字幕", "V7": "強調"}
SOFT = {"V8": "右上（シリーズ名）", "V9": "右上（話題）", "V10": "ボード", "V12": "札1", "V13": "札2", "V14": "札3"}
# 意図してまたがせた強調（plan_parts に理由が書いてあるもの）。×には数えず intended に出す（決め直すならここから外す）
INTENDED = {"環境設定をポチポチでできる仕組みを": "plan_parts/d10_EMPHASIS.txt 1753：2つ目の CTA の言い切り。一文（1753〜1755）を1枚で出す。"
            "画面への切り替えは強調の途中（直し係 2026-10-03 の判断。v003 G1 の決まりより前）"}
bad, note, intended = [], [], []
tel = {n: spans(n) for n in list(STRICT) + list(SOFT)}
for f, what in changes:
    for n, lst in tel.items():
        kind = STRICT.get(n) or SOFT.get(n)
        for a, b, it in lst:
            for edge, g in (("頭", a), ("終わり", b)):
                if g != f and abs(g - f) <= NEAR:
                    bad.append({"at": ts(f), "frame": f, "change": what, "track": n, "kind": kind, "edge": edge, "off_frames": g - f,
                                "telop": text_of(it)})
            if a < f - NEAR and b > f + NEAR:
                row = {"at": ts(f), "frame": f, "change": what, "track": n, "kind": kind, "telop": text_of(it), "span": [ts(a), ts(b)]}
                why = [w for k, w in INTENDED.items() if row["telop"].replace("／", "").startswith(k)]
                if n in STRICT and why:
                    row["why"] = why[0]
                    intended.append(row)
                else:
                    (bad if n in STRICT else note).append(row)
out = {"changes": len(changes), "bad": bad, "straddle_soft": note, "straddle_intended": intended,
       "rule": "画角が変わるコマで、前のテロップを残さない・先に出さない（v003 G1）。15コマ以内のずれは×、字幕・強調・説明のまたぎは×"
               "（V2 の無効のクリップは画面に数えない。画面の下のカメラの大きさの切れ目は数えない）"}
json.dump(out, open(os.path.join(V, "checks_gakaku.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"画角が変わる所 {len(changes)}、× {len(bad)}、またぐ右上タイトル・札・ボード {len(note)}、意図したまたぎ {len(intended)}")
for r in bad[:30]:
    print("  ×", r["at"], r["change"], r["kind"], r.get("edge", "またぐ"), r.get("off_frames", ""), r["telop"])
for r in intended:
    print("  意図", r["at"], r["change"], r["kind"], r["telop"], r["span"], r["why"][:40])
for r in note[:30]:
    print("  注意", r["at"], r["change"], r["kind"], r["telop"], r["span"])
