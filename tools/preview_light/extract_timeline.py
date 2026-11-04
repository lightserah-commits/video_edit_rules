#!/usr/bin/env python3
"""案件の .prproj のシーケンスを、Premiere を使わずに読み、確認用の映像が使う表（JSON）にする。読むだけで書き換えない。
  python3 extract_timeline.py <prproj> <シーケンス名> <出力.json>"""
import base64, json, os, re, struct, sys
ROOT = os.path.expanduser("~/Desktop/video_edit_rules")
sys.path.insert(0, os.path.join(ROOT, "tools"))
from native_prproj import Prproj, TPS, HEADER, _u32, _fields, _deref, run_styles  # noqa
from prproj_motion import is_muted  # noqa

def f32(b, p):
    return struct.unpack_from("<f", b, p)[0]

def rgb(b, t):
    f = _fields(b, t)
    return [b[f[i]] if i in f else 255 for i in range(3)]

def style_of(b):
    """文字データから、ランごとの文字・字体・大きさ・塗り・縁と、段落の揃え・枠・影・背景を読む"""
    env = HEADER + _u32(b, HEADER)
    doc = _deref(b, _fields(b, env)[0])
    fd = _fields(b, doc)
    fonts = []
    if 1 in fd:
        fv = _deref(b, fd[1])
        for i in range(_u32(b, fv)):
            sp = _deref(b, fv + 4 + 4 * i)
            fonts.append(b[sp + 4:sp + 4 + _u32(b, sp)].decode("utf-8"))
    out = {"halign": b[fd[4]] if 4 in fd else 0, "valign": b[fd[5]] if 5 in fd else 0,
           "box": [f32(b, fd[2]) if 2 in fd else None, f32(b, fd[3]) if 3 in fd else None], "x30": b[fd[30]] if 30 in fd else None}
    if 10 in fd:
        out["shadow"] = {"color": rgb(b, fd[10] + _u32(b, fd[10])), "on": b[fd[11]] if 11 in fd else 0, "opacity": f32(b, fd[12]) if 12 in fd else 100,
                         "angle": f32(b, fd[13]) if 13 in fd else 0, "dist": f32(b, fd[14]) if 14 in fd else 0, "size": f32(b, fd[15]) if 15 in fd else 0, "blur": f32(b, fd[16]) if 16 in fd else 0}
    if 17 in fd:
        out["bg"] = {"color": rgb(b, fd[17] + _u32(b, fd[17])), "on": b[fd[18]] if 18 in fd else 0, "opacity": f32(b, fd[19]) if 19 in fd else 100, "pad": f32(b, fd[20]) if 20 in fd else 0}
    runs = []
    vec = _deref(b, fd[0])
    for i in range(_u32(b, vec)):
        run = _deref(b, vec + 4 + 4 * i)
        fr = _fields(b, run)
        sp = _deref(b, fr[0])
        r = {"text": b[sp + 4:sp + 4 + _u32(b, sp)].decode("utf-8"), "len": None}
        if 1 in fr:
            s = _deref(b, fr[1])
            fs = _fields(b, s)
            r["font"] = fonts[_u32(b, fs[0])] if 0 in fs and _u32(b, fs[0]) < len(fonts) else (fonts[0] if fonts else None)
            r["size"] = f32(b, fs[1]) if 1 in fs else 100.0  # 書かれていない時の既定は 100（※注釈が 60% で 1文字 60px）
            r["fill"] = rgb(b, fs[2] + _u32(b, fs[2])) if 2 in fs else [255, 255, 255]
            r["c4"] = rgb(b, fs[4] + _u32(b, fs[4])) if 4 in fs else None
            r["f6"] = f32(b, fs[6]) if 6 in fs else None
            r["f9"] = f32(b, fs[9]) if 9 in fs else None
            r["x5"] = b[fs[5]] if 5 in fs else None
            st = []
            if 17 in fs:
                q = fs[17] + _u32(b, fs[17])
                for j in range(_u32(b, q)):
                    e = q + 4 + 4 * j + _u32(b, q + 4 + 4 * j)
                    fe = _fields(b, e)
                    st.append({"color": rgb(b, fe[0] + _u32(b, fe[0])) if 0 in fe else [255, 255, 255], "on": b[fe[1]] if 1 in fe else None,
                               "width": f32(b, fe[2]) if 2 in fe else None, "kind": b[fe[5]] if 5 in fe else None})
            r["strokes"] = st
        runs.append(r)
    return {**out, "runs": runs, "fonts": fonts}

def param_map(comp_el, pj):
    out = {}
    for p in comp_el.findall("Component/Params/Param"):
        pe = pj.ref(p)
        if pe is None:
            continue
        nm = (pe.findtext("Name") or "").strip()
        if not nm or nm in out:
            continue
        v = pe.findtext("StartKeyframe") or ""
        val = v.split(",")[1] if "," in v else v
        kfs = [k for k in (pe.findtext("Keyframes") or "").strip().split(";") if k]
        out[nm] = {"v": val, "k": [[int(k.split(",")[0]) / TPS, k.split(",")[1]] for k in kfs] if kfs else None}
    return out

def media_of(pj, it):
    sub = pj.ref(it.find("ClipTrackItem/SubClip"))
    if sub is None:
        return None, None, 0.0
    name = sub.findtext("Name")
    clip = pj.ref(sub.find("Clip"))
    inp = 0
    path = None
    if clip is not None:
        c = clip.find("Clip")
        if c is not None:
            inp = int(c.findtext("InPoint") or 0)
            src = pj.ref(c.find("Source"))
            if src is not None:
                ms = src.find("MediaSource")
                m = pj.ref(ms.find("Media")) if ms is not None and ms.find("Media") is not None else None
                if m is not None:
                    path = m.findtext("FilePath") or m.findtext("ActualMediaFilePath")
    return name, path, inp

def main(path, seqname, out):
    pj = Prproj.load(path)
    seq = pj.sequence(seqname)
    rows = []
    for tn, tr in pj.tracks(seq):
        for it in pj.items(tr):
            s, e = pj.span(it)
            name, media, inp = media_of(pj, it)
            row = {"track": tn, "start": s / TPS, "end": e / TPS, "name": name, "media": media, "in": inp / TPS, "muted": bool(is_muted(it)), "comps": []}
            chain = pj.ref(it.find("ClipTrackItem/ComponentOwner/Components"))
            if chain is not None:
                for c in chain.findall("ComponentChain/Components/Component"):
                    ce = pj.ref(c)
                    if ce is None:
                        continue
                    mn = ce.findtext("MatchName") or ""
                    cd = {"match": mn, "params": param_map(ce, pj)}
                    if mn == "AE.ADBE Text":
                        for p in ce.findall("Component/Params/Param"):
                            pe = pj.ref(p)
                            if pe is not None and pe.tag == "ArbVideoComponentParam" and pe.findtext("ParameterID") == "1":
                                sk = pe.find("StartKeyframeValue")
                                raw = (sk.text or "").strip() or pj.blobs.get(sk.attrib.get("BinaryHash"), "")
                                if raw:
                                    try:
                                        cd["style"] = style_of(base64.b64decode(raw))
                                    except Exception as ex:
                                        cd["style_err"] = repr(ex)
                    if mn == "AE.ADBE Shape":
                        for p in ce.findall("Component/Params/Param"):
                            pe = pj.ref(p)
                            if pe is not None and pe.tag == "ArbVideoComponentParam" and (pe.findtext("Name") or "").strip() == "パス":
                                sk = pe.find("StartKeyframeValue")
                                raw = (sk.text or "").strip() or pj.blobs.get(sk.attrib.get("BinaryHash"), "")
                                if raw:
                                    b = base64.b64decode(raw)
                                    pts = [struct.unpack_from("<f", b, i)[0] for i in range(12, len(b) - 3, 4)]
                                    xs = pts[0::7] + pts[2::7] + pts[4::7]
                                    ys = pts[1::7] + pts[3::7] + pts[5::7]
                                    cd["bbox"] = [min(xs), min(ys), max(xs), max(ys)]
                            if pe is not None and pe.tag == "ArbVideoComponentParam" and (pe.findtext("Name") or "").strip() == "アピアランス":
                                sk = pe.find("StartKeyframeValue")
                                raw = (sk.text or "").strip() or pj.blobs.get(sk.attrib.get("BinaryHash"), "")
                                if raw:
                                    b = base64.b64decode(raw)
                                    # 塗りの色。424 バイトの形だけ確かめた（さらささん v002 の章の札）。ほかの長さは色を決めない
                                    if len(b) == 424:
                                        cd["fill"] = list(b[403:406])
                    row["comps"].append(cd)
            rows.append(row)
    trans = {}
    for tn, tr in pj.tracks(seq):
        if tn.startswith("V"):
            t_ = pj.transitions(seq, tn)
            if t_:
                trans[tn] = [[a / TPS, b / TPS, m] for a, b, m in t_]
    json.dump({"source": path, "sequence": seqname, "rows": rows, "transitions": trans}, open(out, "w", encoding="utf-8"), ensure_ascii=False)
    print(len(rows))

if __name__ == "__main__":
    main(*sys.argv[1:4])
