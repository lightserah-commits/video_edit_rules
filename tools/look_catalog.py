#!/usr/bin/env python3
"""完成版の全テロップを「実際の見た目」で分類し、見た目カタログと確認用XMLを作る。

入力:
  --list   全テロップを1クリップずつ並べたXML（例: 03_編集ルール定義/XMLテロップ確認/02_全テロップ_一覧.xml）
  --index  そのXMLの目次（確認目次.json。各クリップの元シーケンス・トラック・有効状態・本文）
  --atlas  演出図鑑の catalogue.json（任意。名前付きスタイルID S01〜S21 を付けるため）
出力（--out フォルダ）:
  looks.json / looks.csv   見た目ごとの件数・フォント・色・縁・箱・位置・実例
  looks_render.xml         見た目ごとの代表クリップを2秒ずつ並べたXML（Premiereで画像にして確認する用）

見た目の指紋に使うもの: 文字レイヤーごとのフォント・サイズ・塗り・縁（色・太さ・重ね数）・影・揃え、
箱などの図形レイヤーの設定、レイヤー構成、クリップ全体の拡大率。位置は指紋に入れず、別に集計する。
文字データの読み取りは颯太さんの解析ツール（プロマネ静的解析.py の Flat）を使う。
"""
import argparse
import ast
import base64
import copy
import csv
import hashlib
import json
import os
import re
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict

FLAT_SRC = os.path.expanduser("~/Downloads/林社長コラボ_v007_颯太引継ぎ_20260922_draft/workspace/projects/"
            "動画制作案件/2026-09-09_YouTube編集ルール定義/資料/プロマネ静的解析.py")


def load_flat():
    import math, struct  # noqa: F401  Flat が使う
    tree = ast.parse(open(FLAT_SRC, encoding="utf-8").read())
    node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Flat")
    ns = {"struct": struct, "math": math, "json": json}
    exec(compile(ast.Module(body=[node], type_ignores=[]), FLAT_SRC, "exec"), ns)
    return ns["Flat"]


Flat = None


def r(x, n=1):
    try:
        return round(float(x), n)
    except (TypeError, ValueError):
        return x


def value_of(param):
    v = param.findtext("value") or ""
    parts = v.split(",")
    return parts[1] if len(parts) > 1 else v


def text_layer_signature(effect):
    params = {p.findtext("parameterid"): p for p in effect.findall("parameter")}
    blob = base64.b64decode(params["1"].findtext("value"))
    d = Flat(blob).decode()
    fonts = d.get("fonts_postscript_saved", [])
    styles = set()
    for run in d.get("runs", []):
        fi = run.get("font_index_raw")
        font = fonts[fi] if isinstance(fi, int) and 0 <= fi < len(fonts) else (fonts[0] if fonts else None)
        fill = (run.get("fill_color_candidate") or {}).get("field_bytes")
        strokes = tuple((tuple((l.get("color_candidate") or {}).get("field_bytes") or ()), l.get("enabled_candidate_raw"),
                         r(l.get("width_candidate_raw"))) for l in run.get("stroke_layers", []))
        styles.add((font, r(run.get("source_font_size_saved")), tuple(fill or ()), strokes, bool(run.get("gradient_or_fill_structure"))))
    sh = d.get("shadow_candidates", {})
    shadow = (tuple((sh.get("color_candidate") or {}).get("field_bytes") or ()), sh.get("enabled_candidate_raw"),
              r(sh.get("opacity_candidate_raw")), r(sh.get("distance_candidate_raw")), r(sh.get("blur_candidate_raw")))
    names = {(p.findtext("name") or "").strip(): value_of(p) for p in effect.findall("parameter")}
    sig = {"styles": sorted(styles, key=str), "shadow": shadow, "align": d.get("paragraph_alignment_enum_raw"),
           "layer_scale": r(names.get("スケール"), 0)}
    info = {"text": d.get("text", ""), "fonts": fonts, "position": names.get("位置"),
            "size": sorted({s[1] for s in styles if s[1] is not None}),
            "strokes": max((len(s[3]) for s in styles), default=0)}
    return sig, info


def other_effect_signature(effect):
    eid = effect.findtext("effectid")
    vals = []
    for p in effect.findall("parameter"):
        nm = (p.findtext("name") or "").strip()
        if nm in ("位置", "アンカーポイント"):  # 位置は指紋に入れない
            continue
        v = value_of(p)
        v = re.sub(r"(\d+\.\d{2})\d+", r"\1", v)
        kf = bool(p.findall("keyframe"))
        vals.append((nm, v[:80], kf))
    return (eid, tuple(vals))


def clip_signature(c):
    layers, texts, fonts, sizes, strokes, positions = [], [], [], [], 0, []
    has_kf = False
    for f in c.findall("filter"):
        e = f.find("effect")
        if e is None:
            continue
        eid = e.findtext("effectid")
        if e.findall(".//keyframe"):
            has_kf = True
        if eid == "GraphicAndType":
            sig, info = text_layer_signature(e)
            layers.append(("text", json.dumps(sig, sort_keys=True, default=str)))
            texts.append(info["text"])
            fonts += info["fonts"]
            sizes += info["size"]
            strokes = max(strokes, info["strokes"])
            positions.append(info["position"])
        elif eid == "GraphicGroup":
            vals = {(p.findtext("name") or "").strip(): value_of(p) for p in e.findall("parameter")}
            layers.append(("group", r(vals.get("スケール"), 0)))
            positions.append(vals.get("位置"))
        else:
            layers.append(("fx",) + other_effect_signature(e))
    key = hashlib.sha1(json.dumps(layers, sort_keys=True, default=str).encode()).hexdigest()[:10]
    return key, {"texts": texts, "fonts": sorted(set(fonts)), "sizes": sorted(set(sizes)), "strokes": strokes,
                 "layer_kinds": [l[0] if l[0] != "fx" else l[1] for l in layers], "positions": positions, "has_keyframes": has_kf}


def pos_bucket(p):
    try:
        x, y = [float(v) for v in str(p).split(":")[:2]]
        return f"{round(x * 10) / 10:.1f},{round(y * 10) / 10:.1f}"
    except Exception:
        return "?"


def main():
    global Flat
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", required=True)
    ap.add_argument("--index", required=True)
    ap.add_argument("--atlas")
    ap.add_argument("--out", required=True)
    ap.add_argument("--render-frames", type=int, default=60)
    a = ap.parse_args()
    Flat = load_flat()
    os.makedirs(a.out, exist_ok=True)

    idx = {x["number"]: x for x in json.load(open(a.index, encoding="utf-8"))["all"]}
    atlas_by = defaultdict(list)
    if a.atlas:
        for o in json.load(open(a.atlas, encoding="utf-8"))["occurrences"]:
            atlas_by[(o["sequence"], o["track"], o["text"].replace("\r", " ").strip())].append(o["catalog_id"])

    tree = ET.parse(a.list)
    root = tree.getroot()
    groups = defaultdict(list)
    templates = {}
    for c in root.iter("clipitem"):
        m = re.match(r"(\d{4}) ", c.findtext("name") or "")
        if not m:
            continue
        num = int(m.group(1))
        meta = idx.get(num, {})
        note = meta.get("note", "").split(" / ")
        seq, track = (note + ["", ""])[:2]
        enabled = "元の有効状態=TRUE" in meta.get("note", "")
        try:
            key, info = clip_signature(c)
        except Exception as ex:  # 読めないクリップは別枠
            key, info = "unreadable", {"texts": [], "fonts": [], "sizes": [], "strokes": 0, "layer_kinds": [], "positions": [], "has_keyframes": False, "error": str(ex)}
        text = " / ".join(t.replace("\r", " ").strip() for t in info["texts"] if t.strip())
        styles = sorted({s for t in info["texts"] for s in atlas_by.get((seq, track, t.replace("\r", " ").strip()), [])})
        groups[key].append({"number": num, "sequence": seq, "track": track, "enabled": enabled, "text": text,
                            "styles": styles, "pos": pos_bucket(info["positions"][0] if info["positions"] else None), **info})
        templates.setdefault(key, {})[num] = c

    looks = []
    for key, items in groups.items():
        main_enabled = [x for x in items if x["enabled"] and x["sequence"] == "AI使いこなす習慣7選"]
        rep_pool = main_enabled or items
        rep = sorted(rep_pool, key=lambda x: (len(x["text"]) > 30, abs(len(x["text"]) - 10)))[0]
        looks.append({
            "key": key, "count_all": len(items), "count_main_enabled": len(main_enabled),
            "fonts": rep["fonts"], "sizes": rep["sizes"], "strokes": rep["strokes"], "layers": rep["layer_kinds"],
            "styles": sorted({s for x in items for s in x["styles"]}),
            "tracks": dict(Counter(x["track"] for x in main_enabled).most_common()),
            "positions": dict(Counter(x["pos"] for x in main_enabled).most_common(3)),
            "animated": sum(1 for x in items if x["has_keyframes"]),
            "rep_number": rep["number"], "rep_text": rep["text"],
            "examples": [x["text"] for x in main_enabled[:6]],
        })
    looks.sort(key=lambda x: (-x["count_main_enabled"], -x["count_all"]))
    for i, l in enumerate(looks, 1):
        l["look_id"] = f"L{i:03d}"

    json.dump(looks, open(os.path.join(a.out, "looks.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    with open(os.path.join(a.out, "looks.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["look_id", "本編で有効な件数", "全件数", "名前付きスタイル", "フォント", "サイズ", "縁の重ね数", "レイヤー構成", "トラック", "位置(x,y)", "動きあり", "代表の本文", "実例"])
        for l in looks:
            w.writerow([l["look_id"], l["count_main_enabled"], l["count_all"], " ".join(l["styles"]), " ".join(l["fonts"]),
                        " ".join(str(s) for s in l["sizes"]), l["strokes"], " > ".join(map(str, l["layers"])),
                        json.dumps(l["tracks"], ensure_ascii=False), json.dumps(l["positions"], ensure_ascii=False),
                        l["animated"], l["rep_text"], " | ".join(l["examples"])])

    # 確認用XML: 代表クリップを render-frames ずつ並べる（見た目の多い順）
    seq = root.find("sequence")
    video = seq.find("media/video")
    tracks = video.findall("track")
    telop_track = tracks[-1]
    for c in list(telop_track.findall("clipitem")):
        telop_track.remove(c)
    n = a.render_frames
    t = 0
    for l in looks:
        c = copy.deepcopy(templates[l["key"]][l["rep_number"]])
        c.set("id", f"clipitem-look-{l['look_id']}")
        c.find("name").text = f"{l['look_id']} {l['rep_text'][:30]}"
        f = c.find("file")
        if f is not None:
            f.set("id", f"file-look-{l['look_id']}")
        c.find("start").text = str(t)
        c.find("end").text = str(t + n)
        telop_track.append(c)
        l["render_start_frame"] = t
        t += n
    for tr in tracks[:-1]:
        for c in tr.findall("clipitem"):
            c.find("end").text = str(t)
            if c.find("in") is not None:
                c.find("out").text = str(int(c.findtext("in")) + t)
    seq.find("duration").text = str(t)
    seq.find("name").text = "見た目カタログ_代表"
    tree.write(os.path.join(a.out, "looks_render.xml"), encoding="utf-8", xml_declaration=True)
    json.dump(looks, open(os.path.join(a.out, "looks.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"見た目 {len(looks)} 種（本編で有効なもの {sum(1 for l in looks if l['count_main_enabled'])} 種）→ {a.out}")


if __name__ == "__main__":
    main()
