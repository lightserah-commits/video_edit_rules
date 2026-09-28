#!/usr/bin/env python3
"""完成版のPremiereプロジェクトから「演出の部品棚」を作る（型の分類）。

3つの棚:
  テロップ型（T###）… 見た目（図形・文字の書式・位置）とアニメーション（クリップのエフェクトとキーフレーム）が同じもの
  画面効果（E###）  … 調整レイヤー（ズーム・引き・シネスコ帯・反転など）の中身が同じもの
  SE（S###）        … 同じ音源・同じ音量設定のもの

各型に「代表の実物」（元のトラックと開始秒）を1つ決める。見本集づくり（build_library.py）と再現（reproduce.py）はこの代表を複製する。

使い方:
  python3 type_catalog.py 完成.prproj --sequence シーケンス名 --out 出力フォルダ
出力: types.json（機械用）、types.csv / types.md（人が読む用）
"""
import argparse
import base64
import csv
import hashlib
import json
import os
import re
import statistics
import sys
import unicodedata
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from native_prproj import Prproj, TPS  # noqa: E402
from look_catalog import load_flat  # noqa: E402

FRAME = TPS * 1001 / 30000
GRAPHIC = {"AE.ADBE Text", "AE.ADBE Shape", "AE.ADBE Graphic Group", "AE.ADBE Graphic SubGroup"}
SKIP_PARAM = {"start", "end"}  # 編集時の文字選択位置（見た目に関係しない）
AUDIO_EXT = re.compile(r"\.(wav|mp3|aiff?|m4a)$", re.I)


def rnd(v):
    """値の表記ゆれを丸める（小数2〜3桁）"""
    def num(m):
        x = float(m.group(0))
        return f"{x:.3f}".rstrip("0").rstrip(".")
    return re.sub(r"-?\d+\.\d+", num, v)


class Catalog:
    def __init__(self, pj):
        self.pj = pj
        self.Flat = load_flat()
        self.styles = {s.get("ObjectUID"): unicodedata.normalize("NFC", s.findtext("ProjectItem/Name") or "")
                       for s in pj.root.findall("StyleProjectItem")}

    def blob(self, pe):
        sk = pe.find("StartKeyframeValue")
        if sk is None:
            return b""
        b = (sk.text or "").strip() or self.pj.blobs.get(sk.attrib.get("BinaryHash"), "")
        return base64.b64decode(b) if b else b""

    def text_style(self, raw):
        d = self.Flat(raw).decode()
        fonts = d.get("fonts_postscript_saved", [])
        runs = set()
        for r in d.get("runs", []):
            fi = r.get("font_index_raw")
            font = fonts[fi] if isinstance(fi, int) and 0 <= fi < len(fonts) else (fonts[0] if fonts else None)
            fill = tuple((r.get("fill_color_candidate") or {}).get("field_bytes") or ())
            strokes = tuple((tuple((l.get("color_candidate") or {}).get("field_bytes") or ()), l.get("enabled_candidate_raw"),
                             round(l.get("width_candidate_raw") or 0, 1)) for l in r.get("stroke_layers", []))
            size = r.get("source_font_size_saved")
            runs.add((font, round(size, 1) if size else None, fill, strokes, bool(r.get("gradient_or_fill_structure"))))
        sh = d.get("shadow_candidates", {})
        shadow = (tuple((sh.get("color_candidate") or {}).get("field_bytes") or ()), sh.get("enabled_candidate_raw"),
                  sh.get("opacity_candidate_raw"), sh.get("distance_candidate_raw"), sh.get("blur_candidate_raw"))
        return {"runs": sorted(runs, key=str), "shadow": shadow, "align": d.get("paragraph_alignment_enum_raw")}, d.get("text", ""), fonts

    def component(self, ce, inpoint):
        mn = ce.findtext("MatchName") or ""
        dn = ce.findtext("Component/DisplayName") or mn
        params, text, fonts, style_name = [], None, [], None
        ps = ce.find("Component/ParentStyle")
        if ps is not None:
            style_name = self.styles.get(ps.attrib.get("ObjectURef"))
        for p in ce.findall("Component/Params/Param"):
            pe = self.pj.ref(p)
            if pe is None:
                continue
            nm = (pe.findtext("Name") or "").strip()
            if nm in SKIP_PARAM:
                continue
            if pe.tag == "ArbVideoComponentParam":
                raw = self.blob(pe)
                if mn == "AE.ADBE Text" and pe.findtext("ParameterID") == "1" and raw:
                    sig, text, fonts = self.text_style(raw)
                    params.append(("style", json.dumps(sig, sort_keys=True, default=str)))
                elif raw:
                    params.append((nm, hashlib.sha1(raw).hexdigest()[:10]))
                continue
            v = pe.findtext("StartKeyframe") or ""
            val = rnd(v.split(",")[1]) if "," in v else rnd(v)
            kfs = [k for k in (pe.findtext("Keyframes") or "").strip().split(";") if k]
            if kfs:
                pattern = [(round((int(k.split(",")[0]) - inpoint) / TPS, 3), rnd(k.split(",")[1])) for k in kfs]
                params.append((nm, "KF", tuple(pattern)))
            else:
                params.append((nm, val))
        return {"match": mn, "name": dn, "params": params, "text": text, "fonts": fonts, "style": style_name}

    def item(self, it):
        sub = self.pj.ref(it.find("ClipTrackItem/SubClip"))
        clip = self.pj.ref(sub.find("Clip")) if sub is not None else None
        inpoint = int(clip.findtext("Clip/InPoint") or 0) if clip is not None and clip.find("Clip") is not None else 0
        chain = self.pj.ref(it.find("ClipTrackItem/ComponentOwner/Components"))
        comps = []
        if chain is not None:
            for c in chain.findall("ComponentChain/Components/Component"):
                ce = self.pj.ref(c)
                if ce is not None:
                    comps.append(self.component(ce, inpoint))
        return comps, (sub.findtext("Name") if sub is not None else "")


def anim_summary(effect_comps):
    parts = []
    for c in effect_comps:
        kf = [p for p in c["params"] if len(p) == 3 and p[1] == "KF"]
        if kf:
            dur = max(p[2][-1][0] - p[2][0][0] for p in kf)
            parts.append(f"{c['name']}（{'・'.join(p[0] for p in kf)}、{dur:.2f}秒）")
    return " + ".join(parts) or "なし"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("prproj")
    ap.add_argument("--sequence", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    pj = Prproj.load(a.prproj)
    cat = Catalog(pj)
    seq = pj.sequence(a.sequence)

    entries = []
    for tname, tr in pj.tracks(seq):
        for it in pj.items(tr):
            if it.find("ClipTrackItem/IsMuted") is not None:
                continue
            s, e = pj.span(it)
            sub = pj.ref(it.find("ClipTrackItem/SubClip"))
            nm = unicodedata.normalize("NFC", sub.findtext("Name") or "") if sub is not None else ""
            entries.append({"track": tname, "s": s, "e": e, "name": nm, "el": it})

    telops, adjusts, ses = [], [], []
    for x in entries:
        if x["track"].startswith("A"):
            clip = pj.ref(pj.ref(x["el"].find("ClipTrackItem/SubClip")).find("Clip"))
            is_bgm = "メインテーマ" in x["name"] or "BGM" in x["name"]
            if AUDIO_EXT.search(x["name"]) and (x["e"] - x["s"]) / TPS < 10 and not is_bgm:
                g = clip.findtext("Gain") if clip is not None else None
                x["gain"] = round(20 * __import__("math").log10(float(g)), 2) if g and float(g) > 0 else 0.0
                ses.append(x)
            continue
        comps, _ = cat.item(x["el"])
        x["comps"] = comps
        if x["name"] == "調整レイヤー":
            adjusts.append(x)
        elif any(c["match"] in GRAPHIC for c in comps):
            telops.append(x)

    def key_of(comps, graphic):
        sel = [c for c in comps if (c["match"] in GRAPHIC) == graphic]
        return json.dumps([(c["match"], c["params"]) for c in sel], sort_keys=True, default=str)

    # テロップ型
    groups = defaultdict(list)
    for x in telops:
        look = key_of(x["comps"], True)
        anim = key_of(x["comps"], False)
        x["look_key"] = hashlib.sha1(look.encode()).hexdigest()[:10]
        x["anim_key"] = hashlib.sha1(anim.encode()).hexdigest()[:10]
        groups[(x["look_key"], x["anim_key"])].append(x)
    types = []
    for (lk, ak), xs in groups.items():
        texts = [" / ".join(c["text"].replace("\r", " ") for c in x["comps"] if c["text"]) for x in xs]
        med = statistics.median(len(t) for t in texts)
        rep = min(range(len(xs)), key=lambda i: (abs(len(texts[i]) - med), xs[i]["s"]))
        r = xs[rep]
        eff = [c for c in r["comps"] if c["match"] not in GRAPHIC]
        styles = sorted({c["style"] for c in r["comps"] if c["style"]})
        fonts = sorted({f for c in r["comps"] for f in c["fonts"]})
        # 同時に置かれた SE・画面効果
        se_with, adj_with = Counter(), Counter()
        for x in xs:
            for s in ses:
                if abs(s["s"] - x["s"]) <= 2 * FRAME:
                    se_with[s["name"]] += 1
            for ad in adjusts:
                if abs(ad["s"] - x["s"]) <= 2 * FRAME:
                    adj_with[hashlib.sha1(key_of(ad["comps"], False).encode()).hexdigest()[:10]] += 1
        types.append({
            "look_key": lk, "anim_key": ak, "count": len(xs),
            "styles": styles, "fonts": fonts,
            "layers": [c["name"] for c in r["comps"] if c["match"] in GRAPHIC],
            "animation": anim_summary(eff),
            "effects": [c["name"] for c in eff if c["match"] not in ("AE.ADBE Motion", "AE.ADBE Opacity")],
            "tracks": dict(Counter(x["track"] for x in xs).most_common()),
            "duration_median": round(statistics.median((x["e"] - x["s"]) / TPS for x in xs), 2),
            "rep": {"track": r["track"], "start": round(r["s"] / TPS, 3), "end": round(r["e"] / TPS, 3), "text": texts[rep]},
            "examples": [{"track": x["track"], "start": round(x["s"] / TPS, 3), "text": t} for x, t in list(zip(xs, texts))[:8]],
            "members": [{"track": x["track"], "start": round(x["s"] / TPS, 4), "end": round(x["e"] / TPS, 4), "text": t} for x, t in zip(xs, texts)],
            "se_with": dict(se_with.most_common()), "adjust_with_keys": dict(adj_with.most_common()),
        })
    types.sort(key=lambda t: (-t["count"], t["rep"]["start"]))
    for i, t in enumerate(types, 1):
        t["id"] = f"T{i:03d}"

    # 画面効果（調整レイヤー）
    agroups = defaultdict(list)
    for ad in adjusts:
        agroups[hashlib.sha1(key_of(ad["comps"], False).encode()).hexdigest()[:10]].append(ad)
    effects = []
    for k, xs in agroups.items():
        r = sorted(xs, key=lambda x: x["s"])[0]
        comps = r["comps"]
        summary = []
        for c in comps:
            if c["match"] in ("AE.ADBE Motion", "AE.ADBE Opacity"):
                continue
            vals = {p[0]: (p[1] if len(p) == 2 else "KF") for p in c["params"]}
            if c["match"].startswith("AE.ADBE Geometry"):
                summary.append(f"{c['name']} スケール{vals.get('スケール (高さ)', vals.get('スケール'))}% 位置{vals.get('位置')}")
            elif c["match"] == "AE.ADBE AECrop":
                summary.append(f"クロップ 上{vals.get('上')} 下{vals.get('下')}")
            else:
                summary.append(c["name"])
        effects.append({"key": k, "count": len(xs), "summary": " + ".join(summary) or "（エフェクトなし）",
                        "members": [{"track": x["track"], "start": round(x["s"] / TPS, 4), "end": round(x["e"] / TPS, 4)} for x in xs],
                        "animation": anim_summary([c for c in comps if c["match"] not in GRAPHIC]),
                        "tracks": dict(Counter(x["track"] for x in xs)),
                        "duration_median": round(statistics.median((x["e"] - x["s"]) / TPS for x in xs), 2),
                        "rep": {"track": r["track"], "start": round(r["s"] / TPS, 3), "end": round(r["e"] / TPS, 3)}})
    effects.sort(key=lambda e: -e["count"])
    ekey2id = {}
    for i, e in enumerate(effects, 1):
        e["id"] = f"E{i:03d}"
        ekey2id[e["key"]] = e["id"]
    for t in types:
        t["adjust_with"] = {ekey2id.get(k, k): v for k, v in t.pop("adjust_with_keys").items()}

    # SE
    sgroups = defaultdict(list)
    for s in ses:
        sgroups[(s["name"], s["gain"])].append(s)
    se_lib = []
    for (nm, g), xs in sorted(sgroups.items(), key=lambda kv: -len(kv[1])):
        r = xs[0]
        se_lib.append({"file": nm, "gain_db": g, "count": len(xs), "tracks": dict(Counter(x["track"] for x in xs)),
                       "members": [{"track": x["track"], "start": round(x["s"] / TPS, 4), "end": round(x["e"] / TPS, 4)} for x in xs],
                       "rep": {"track": r["track"], "start": round(r["s"] / TPS, 3), "end": round(r["e"] / TPS, 3)}})
    for i, s in enumerate(se_lib, 1):
        s["id"] = f"S{i:03d}"

    out = {"source": os.path.basename(a.prproj), "sequence": a.sequence, "telop_types": types, "screen_effects": effects, "se": se_lib}
    json.dump(out, open(os.path.join(a.out, "types.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    with open(os.path.join(a.out, "types.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["型ID", "件数", "保存スタイル", "フォント", "レイヤー", "アニメーション", "トラック", "長さ中央値", "代表（トラック・秒）", "代表の文字", "一緒に鳴ったSE", "一緒の画面効果"])
        for t in types:
            w.writerow([t["id"], t["count"], " ".join(t["styles"]), " ".join(t["fonts"]), " > ".join(t["layers"]), t["animation"],
                        json.dumps(t["tracks"], ensure_ascii=False), t["duration_median"], f"{t['rep']['track']} {t['rep']['start']}",
                        t["rep"]["text"], json.dumps(t["se_with"], ensure_ascii=False), json.dumps(t["adjust_with"], ensure_ascii=False)])
    print(f"テロップ型 {len(types)}（うち2回以上 {sum(1 for t in types if t['count'] > 1)}）／画面効果 {len(effects)}／SE {len(se_lib)} → {a.out}")


if __name__ == "__main__":
    main()
