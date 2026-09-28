#!/usr/bin/env python3
"""完成したプロジェクトから「座布団（背景の図形つきテロップ）の並べ方」と「代弁（誰かのふり）の演出」を抜き出す（ルールづくり用）。

  座布団：テロップの部品に図形（AE.ADBE Shape）があるもの。同じ時刻に2枚以上出ている所を「積み上げ」としてまとめ、
          出る順・トラック・位置（図形のグループの位置）・消える時刻・一緒の SE を出す
  代弁  ：クロップ（上・下）を持つ調整レイヤー（黒帯）の区間。その間のテロップ（スタイル・文字）・SE・BGM の有無・左右反転

使い方: python3 tools/plates_roleplay.py <prproj> <シーケンス名> <出力.json>
  2026-09-26 に完成版・2本目を解析して、02 の P11（並べる座布団）・P16（代弁）を作った（結果は work/gamen_kyoyu_20260926/analysis/ルール調査/）。
  新しい完成版をもらったら、これで同じ数字（並べる数・間隔・一斉に消えるか、代弁の黒帯の長さ・反転）を取り、ルールと比べる
"""
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from decoration_report import Project, TPS  # noqa: E402


def fmt(t):
    return f"{int(t // 60):02d}:{t % 60:05.2f}"


class P2(Project):
    def shape_info(self, it):
        """テロップの部品の中の図形の数と、グループ・文字の位置（0〜1の比率）"""
        cti = it.find("ClipTrackItem")
        chain = self.ref(cti.find("ComponentOwner/Components"))
        shapes, pos, texts = 0, [], 0
        if chain is None:
            return shapes, pos, texts
        for c in chain.findall("ComponentChain/Components/Component"):
            ce = self.ref(c)
            if ce is None:
                continue
            mn = ce.findtext("MatchName") or ""
            if mn == "AE.ADBE Shape":
                shapes += 1
            if mn == "AE.ADBE Text":
                texts += 1
            if mn in ("AE.ADBE Graphic Group", "AE.ADBE Text", "AE.ADBE Shape"):
                for p in ce.findall("Component/Params/Param"):
                    pe = self.ref(p)
                    if pe is not None and (pe.findtext("Name") or "").strip() == "位置":
                        v = self.param_value(pe)
                        if ":" in v:
                            pos.append((mn.split(".")[-1].replace("ADBE ", ""), v))
                        break
        return shapes, pos, texts


def main():
    path, seq_name, out = sys.argv[1], sys.argv[2], sys.argv[3]
    pj = P2(path)
    seqs = [s for s in pj.sequences() if s.findtext("Name") == seq_name]
    seq = max(seqs, key=lambda s: sum(len(pj.items(t)) for _, t in pj.tracks(s)))
    clips = []
    for tn, tr in pj.tracks(seq):
        for it in pj.items(tr):
            c = pj.clip(tn, it)
            if c["disabled"]:
                continue
            if tn.startswith("V"):
                sh, pos, nt = pj.shape_info(it)
                c["shapes"], c["pos"], c["n_text"] = sh, pos, nt
            clips.append(c)
    V = [c for c in clips if c["track"].startswith("V")]
    A = [c for c in clips if c["track"].startswith("A")]
    plates = [c for c in V if c.get("layers") and c.get("shapes")]
    # 積み上げ：同時に出ている座布団のまとまり（重なりでつなぐ）
    plates.sort(key=lambda c: c["start"])
    groups, cur = [], []
    for c in plates:
        if cur and c["start"] < max(x["end"] for x in cur) - 0.05:
            cur.append(c)
        else:
            if cur:
                groups.append(cur)
            cur = [c]
    if cur:
        groups.append(cur)
    se_like = [c for c in A if not c["media"].lower().endswith((".mov", ".mp4")) and c["end"] - c["start"] < 6]

    def se_at(t):
        return [c["media"] for c in se_like if abs(c["start"] - t) <= 0.12]

    stacks = []
    for g in groups:
        tracks = {c["track"] for c in g}
        if len(g) < 2 or len(tracks) < 2:
            continue
        stacks.append({"from": fmt(g[0]["start"]), "to": fmt(max(c["end"] for c in g)),
                       "items": [{"start": fmt(c["start"]), "end": fmt(c["end"]), "track": c["track"],
                                  "style": sorted({l["style"] or ("font:" + ",".join(l["fonts"])) for l in c["layers"]}),
                                  "text": " / ".join(l["text"] for l in c["layers"] if l["text"])[:60], "pos": c["pos"][:3],
                                  "se": se_at(c["start"])} for c in g]})
    # 座布団の使われ方（スタイルごとの数・同時に出る最大数）
    style_count = Counter(sorted({l["style"] or ("font:" + ",".join(l["fonts"])) for l in c["layers"]})[0] for c in plates)
    # 代弁：上下のクロップを持つクリップ（調整レイヤー）
    crops = [c for c in V if "クロップ" in c.get("fx", []) and (c.get("crop_上") or c.get("crop_下"))]
    role = []
    for c in sorted(crops, key=lambda x: x["start"]):
        s, e = c["start"], c["end"]
        tel = [x for x in V if x.get("layers") and x["start"] < e and s < x["end"] and x is not c]
        ses = [x["media"] for x in se_like if s - 0.05 <= x["start"] < e]
        role.append({"from": fmt(s), "to": fmt(e), "sec": round(e - s, 2), "track": c["track"], "crop": [c.get("crop_上"), c.get("crop_下")],
                     "flip": "水平反転" in c.get("fx", []), "fx": c.get("fx"),
                     "telops": [{"start": fmt(x["start"]), "end": fmt(x["end"]), "track": x["track"],
                                 "style": sorted({l["style"] or ("font:" + ",".join(l["fonts"])) for l in x["layers"]}),
                                 "text": " / ".join(l["text"] for l in x["layers"] if l["text"])[:50]} for x in sorted(tel, key=lambda x: x["start"])],
                     "se": ses})
    # 並べて出す座布団（文字スタイルの背景で作るものも含む）：通常字幕・右上タイトル以外のテロップが、時間差で出て同時に並ぶ所
    tel = [c for c in V if c.get("layers")]
    sty = Counter(sorted({l["style"] or "" for l in c["layers"]})[0] for c in tel)
    base = {k for k, n in sty.items() if n >= 0.08 * len(tel)}
    txt_count = Counter(" / ".join(l["text"] for l in c["layers"]) for c in tel)
    cand = [c for c in tel if not ({l["style"] or "" for l in c["layers"]} <= base)
            and txt_count[" / ".join(l["text"] for l in c["layers"])] < 5 and c["end"] - c["start"] < 60]
    cand.sort(key=lambda c: c["start"])
    lists, cur = [], []
    for c in cand:
        if cur and c["start"] < max(x["end"] for x in cur) - 0.05:
            cur.append(c)
        else:
            if cur:
                lists.append(cur)
            cur = [c]
    if cur:
        lists.append(cur)
    stacked = []
    for g in lists:
        starts = sorted({round(c["start"], 2) for c in g})
        if len(g) >= 2 and len({c["track"] for c in g}) >= 2 and starts[-1] - starts[0] >= 0.3:
            stacked.append({"from": fmt(g[0]["start"]), "to": fmt(max(c["end"] for c in g)),
                            "items": [{"start": fmt(c["start"]), "end": fmt(c["end"]), "track": c["track"],
                                       "style": sorted({l["style"] or ("font:" + ",".join(l["fonts"])) for l in c["layers"]}),
                                       "text": " / ".join(l["text"] for l in c["layers"] if l["text"])[:60], "pos": c["pos"][:3],
                                       "shapes": c.get("shapes"), "se": se_at(c["start"])} for c in g]})
    res = {"project": path, "sequence": seq_name, "plates_total": len(plates), "plate_styles": style_count.most_common(),
           "base_styles": sorted(base), "stacked_lists": stacked,
           "stacks": stacks, "roleplay": role}
    json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(seq_name, "座布団（図形）", len(plates), "CTA枠の組", len(stacks), "時間差で並ぶテロップ", len(stacked), "代弁（黒帯）", len(role))


if __name__ == "__main__":
    main()
