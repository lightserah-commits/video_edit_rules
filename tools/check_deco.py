#!/usr/bin/env python3
"""装飾の検査（編集の依頼文.md の工程9）。元は work/gamen_kyoyu_20260926/analysis/check_deco.py。

  - SE の開始が、どのテロップ・画像・画面の開始とも合っていないもの（01 手順4：SE は装飾テロップの開始フレーム）
  - カメラのクリップのズーム（スケールが100でないもの）の数
  - 右上タイトルが、ズーム・画面や画像を置くトラック・文字の無いクリップ（画像・図解の部品）と重なっている所（02 の titles）
  - 15秒以上、SE・ズーム・画面の出入りのどれも起きていない区間（01 手順6）

使い方:
  python3 tools/check_deco.py 版.prproj --seq シーケンス名 --camera V1 --cover V2 --visual V2-V10 --se A4 \\
      --titles V5,V6 --after 306 --out checks_deco.json
  トラックは案件ごとに違う（画面解説：V1 映像・V2 ワイプ・V3 字幕・V4 強調・V5/V6 右上・A4 SE、
  画面共有装飾：V2 画面・V11/V12 右上・A2 SE）。--after は冒頭ハイライトなど、検査しない頭のフレーム数
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from native_prproj import Prproj, TPS  # noqa: E402


def tracklist(spec):
    out = []
    for part in [x for x in spec.split(",") if x]:
        if "-" in part:
            a, b = part.split("-")
            out += [f"{a[0]}{i}" for i in range(int(a[1:]), int(b[1:]) + 1)]
        else:
            out.append(part)
    return out


def component_param(pj, item, match_name, names):
    chain = pj.ref(item.find("ClipTrackItem/ComponentOwner/Components"))
    out = {}
    if chain is None:
        return out
    for c in chain.findall("ComponentChain/Components/Component"):
        ce = pj.ref(c)
        if ce is None or ce.findtext("MatchName") != match_name:
            continue
        for p in ce.findall("Component/Params/Param"):
            pe = pj.ref(p)
            nm = (pe.findtext("Name") or "").strip() if pe is not None else ""
            if nm in names and nm not in out:
                out[nm] = pe
        if out:
            return out
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--seq", required=True)
    ap.add_argument("--camera", default="V1")
    ap.add_argument("--cover", default="", help="画面録画・画像など、カメラを覆うトラック")
    ap.add_argument("--visual", default="V2-V10", help="テロップ・画像を置くトラック（SE の開始と比べる）")
    ap.add_argument("--se", default="A4")
    ap.add_argument("--titles", default="", help="右上のシリーズ名・話題タイトルのトラック")
    ap.add_argument("--after", type=int, default=0)
    ap.add_argument("--gap", type=float, default=15.0)
    ap.add_argument("--out")
    a = ap.parse_args()

    pj = Prproj.load(a.project)
    seq = pj.sequence(a.seq)
    ft = pj.frame_ticks(seq)
    fps = TPS / ft
    tr = dict(pj.tracks(seq))

    def sp(it):
        s, e = pj.span(it)
        return s // ft, e // ft

    def name(it):
        sub = pj.ref(it.find("ClipTrackItem/SubClip"))
        return sub.findtext("Name") if sub is not None else ""

    def muted(it):
        m = it.find("ClipTrackItem/IsMuted")
        return m is not None and m.text == "true"

    def texts(it):
        try:
            return pj.item_texts(it)
        except Exception:
            return [["?"]]

    def tc(f):
        s = f / fps
        return f"{int(s // 60):02d}:{s % 60:05.2f}"

    def items(tn):
        return [it for it in pj.items(tr[tn]) if not muted(it)] if tn in tr else []

    res = {"project": a.project, "sequence": a.seq, "fps": round(fps, 3)}
    visual = [t for t in tracklist(a.visual) if t not in tracklist(a.titles)]
    starts = {sp(it)[0] for tn in visual for it in items(tn)}
    se = [(sp(it)[0], name(it)) for tn in tracklist(a.se) for it in items(tn) if sp(it)[0] >= a.after]
    res["se_total"] = len(se)
    res["se_not_on_visual_start"] = [(tc(s), n) for s, n in se if s not in starts]

    zooms = []
    for it in items(a.camera):
        mp = component_param(pj, it, "AE.ADBE Motion", {"スケール"})
        if mp and mp["スケール"].find("StartKeyframe") is not None \
                and mp["スケール"].find("StartKeyframe").text.split(",")[1] not in ("100.", "100"):
            zooms.append(sp(it))
    res["zoom_count"] = len(zooms)

    cover = [sp(it) for tn in tracklist(a.cover) for it in items(tn)]
    imgs = [sp(it) for tn in visual if tn not in tracklist(a.cover) for it in items(tn) if not texts(it)]
    bad = []
    for tn in tracklist(a.titles):
        for it in items(tn):
            s, e = sp(it)
            for kind, rs in (("ズーム", zooms), ("画面・画像のトラック", cover), ("文字の無いクリップ（画像・図解）", imgs)):
                hit = next(((x, y) for x, y in rs if x < e and s < y), None)
                if hit:
                    bad.append((tn, tc(s), kind, tc(hit[0])))
                    break
    res["title_overlaps"] = bad

    end = max((sp(it)[1] for tn in tr for it in items(tn)), default=0)
    ev = sorted({s for s, _ in se} | {x for x, _ in zooms} | {x for x, _ in cover} | {y for _, y in cover})
    ev = [a.after] + [x for x in ev if x > a.after] + [end]
    res["gaps_over"] = [(tc(x), tc(y), round((y - x) / fps, 1)) for x, y in zip(ev, ev[1:]) if y - x >= a.gap * fps]

    if a.out:
        json.dump(res, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False, indent=1)[:4000])


if __name__ == "__main__":
    main()
