#!/usr/bin/env python3
"""timeline.json から、ブラウザで重ねるテロップの表（telops.json）を作る。
  python3 make_telops.py timeline.json telops.json"""
import json, sys
W, H = 1920, 1080

def nums(v):
    return [float(x) for x in str(v).rstrip(".").split(":")]

def prop(p, name, clip_in):
    """パラメータの値と、クリップの頭からの秒のキーフレーム"""
    e = p.get(name)
    if not e:
        return None
    if e.get("k"):
        return {"k": [[round(t - clip_in, 4), nums(v)] for t, v in e["k"]]}
    return {"v": nums(e["v"])}

def xform(c, clip_in, kind):
    p = c["params"]
    if kind == "geometry":
        return {"pos": prop(p, "位置", clip_in), "anchor": prop(p, "アンカーポイント", clip_in), "scale": prop(p, "スケール (高さ)", clip_in),
                "scale_w": prop(p, "スケール (幅)", clip_in), "opacity": prop(p, "不透明度", clip_in), "rot": prop(p, "回転", clip_in)}
    return {"pos": prop(p, "位置", clip_in), "anchor": prop(p, "アンカーポイント", clip_in), "scale": prop(p, "スケール", clip_in), "opacity": prop(p, "不透明度", clip_in), "rot": prop(p, "回転", clip_in)}

def main(src, out):
    d = json.load(open(src, encoding="utf-8"))
    items, shape_rows = [], 0
    for r in d["rows"]:
        if not r["track"].startswith("V") or r["muted"]:
            continue
        cs = r["comps"]
        if not any(c["match"] == "AE.ADBE Text" for c in cs):
            continue
        it = {"track": int(r["track"][1:]), "start": round(r["start"], 4), "end": round(r["end"], 4), "effects": [], "group": None, "motion": None, "layers": []}
        for c in cs:
            m = c["match"]
            if m == "AE.ADBE Graphic Group":
                it["group"] = xform(c, r["in"], "group")
            elif m == "AE.ADBE Motion":
                it["motion"] = xform(c, r["in"], "motion")
            elif m in ("AE.ADBE Geometry2", "AE.ADBE Geometry"):
                it["effects"].append(xform(c, r["in"], "geometry"))
            elif m == "AE.ADBE Text" and c.get("style"):
                s = c["style"]
                it["layers"].append({"style": s, "x": xform(c, r["in"], "text")})
            elif m == "AE.ADBE Shape" and c.get("bbox"):
                shape_rows += 1
                it["layers"].append({"shape": {"bbox": c["bbox"], "fill": c.get("fill")}, "x": xform(c, r["in"], "text")})
        fades = []
        for a, b, _m in d.get("transitions", {}).get(r["track"], []):
            if abs(a - r["start"]) < 0.02 or (a <= r["start"] <= b):
                fades.append([round(a, 4), round(b, 4), "in"])
            elif abs(b - r["end"]) < 0.02 or (a <= r["end"] <= b):
                fades.append([round(a, 4), round(b, 4), "out"])
        it["fades"] = fades
        items.append(it)
    items.sort(key=lambda x: (x["track"], x["start"]))
    # 図解（V15）の間は、下の段のテロップは Premiere でも板の下に隠れて読めない
    over = [[round(r["start"], 4), round(r["end"], 4)] for r in d["rows"] if r["track"] == "V15" and not r["muted"]]
    json.dump({"w": W, "h": H, "items": items, "over": over}, open(out, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("テロップ", len(items), "図形の層", shape_rows)

if __name__ == "__main__":
    main(*sys.argv[1:3])
