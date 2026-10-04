"""v002 の組み立てで使う .prproj の部品操作。画面解説 v008（work/gamen_kaisetsu_20260926/v008/make_v008.py）の関数をそのまま移したもの。"""
import copy
import math
import xml.etree.ElementTree as ET

BREAK_AFTER = "はがをにでとのもへやよねか、"   # 2行にするときに切ってよい文字（この後ろで切る）


def detach(pj, track, item):
    lst = track.find("ClipTrack/ClipItems/TrackItems")
    refs = [r for r in lst.findall("TrackItem") if r.attrib["ObjectRef"] != item.attrib["ObjectID"]]
    if len(refs) == len(lst.findall("TrackItem")):
        raise KeyError("トラックに無いクリップ")
    for r in list(lst.findall("TrackItem")):
        lst.remove(r)
    for i, r in enumerate(refs):
        r.attrib["Index"] = str(i)
        lst.append(r)


def component_param(pj, item, match_name, names):
    chain = pj.ref(item.find("ClipTrackItem/ComponentOwner/Components"))
    out = {}
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


def set_static(pe, value):
    if (pe.findtext("Keyframes") or "").strip():
        raise ValueError("キーフレームのある値は想定していない")
    sk = pe.find("StartKeyframe")
    parts = sk.text.split(",")
    parts[1] = value
    sk.text = ",".join(parts)


def get_static(pe):
    return pe.find("StartKeyframe").text.split(",")[1]


def add_motion(pj, item, template):
    """モーションの部品を持たないクリップ（Premiere の初期値のまま＝DefaultMotion）に、template（大きさ100・中央の
    モーションの部品）を複製して付ける。付け方は Premiere が保存した形（DefaultMotion を消して部品を1つ持つ）と同じ。"""
    chain = pj.ref(item.find("ClipTrackItem/ComponentOwner/Components"))
    cc = chain.find("ComponentChain")
    if cc.find("Components") is not None and len(cc.find("Components")):
        raise ValueError("すでに部品がある")
    parts = pj.subgraph(template)
    remap = {}
    for o in parts:
        remap[o.attrib["ObjectID"]] = str(pj.next_id)
        pj.next_id += 1
    new_top = None
    for o in parts:
        c = copy.deepcopy(o)
        c.attrib["ObjectID"] = remap[o.attrib["ObjectID"]]
        for e in c.iter():
            if "ObjectRef" in e.attrib and e.attrib["ObjectRef"] in remap:
                e.attrib["ObjectRef"] = remap[e.attrib["ObjectRef"]]
            if e.attrib.get("BinaryHash") and (e.text or "").strip():
                e.text = None
        pj.root.append(c)
        pj.ids[c.attrib["ObjectID"]] = c
        if o is template:
            new_top = c
    for tag in ("DefaultMotion", "DefaultMotionComponentID"):
        el = chain.find(tag)
        if el is not None:
            chain.remove(el)
    comps = cc.find("Components")
    if comps is None:
        comps = ET.SubElement(cc, "Components", {"Version": "1"})
    ET.SubElement(comps, "Component", {"Index": "0", "ObjectRef": new_top.attrib["ObjectID"]})
    return new_top


def add_component(pj, item, template):
    """クリップの効果の並びの最後に、template（見本の効果の部品）を複製して足す。足した部品を返す"""
    chain = pj.ref(item.find("ClipTrackItem/ComponentOwner/Components"))
    cc = chain.find("ComponentChain")
    comps = cc.find("Components")
    if comps is None:
        comps = ET.SubElement(cc, "Components", {"Version": "1"})
    parts = pj.subgraph(template)
    remap = {}
    for o in parts:
        remap[o.attrib["ObjectID"]] = str(pj.next_id)
        pj.next_id += 1
    top = None
    for o in parts:
        c = copy.deepcopy(o)
        c.attrib["ObjectID"] = remap[o.attrib["ObjectID"]]
        for e in c.iter():
            if "ObjectRef" in e.attrib and e.attrib["ObjectRef"] in remap:
                e.attrib["ObjectRef"] = remap[e.attrib["ObjectRef"]]
            if e.attrib.get("BinaryHash") and (e.text or "").strip():
                e.text = None
        pj.root.append(c)
        pj.ids[c.attrib["ObjectID"]] = c
        if o is template:
            top = c
    ET.SubElement(comps, "Component", {"Index": str(len(comps)), "ObjectRef": top.attrib["ObjectID"]})
    return top


def set_param(pj, comp, name, value):
    for p in comp.findall("Component/Params/Param"):
        pe = pj.ref(p)
        if pe is not None and (pe.findtext("Name") or "").strip() == name:
            set_static(pe, value)
            return
    raise KeyError(name)


def fix_fonts(pj, table):
    """プロジェクトの全部の文字データで、フォントの一覧の名前を置き換える（使っていない名前も含む）。置き換えた数を返す"""
    import base64, struct, uuid as _uuid
    from native_prproj import _u32, _deref, _fields, HEADER
    count = {}
    for o in list(pj.root):
        if o.tag != "ArbVideoComponentParam" or o.findtext("ParameterID") != "1":
            continue
        sk = o.find("StartKeyframeValue")
        if sk is None:
            continue
        b = (sk.text or "").strip() or pj.blobs.get(sk.attrib.get("BinaryHash"), "")
        if not b:
            continue
        raw = bytearray(base64.b64decode(b))
        try:
            env = HEADER + _u32(raw, HEADER)
            f = _fields(raw, _deref(raw, _fields(raw, env)[0]))
        except Exception:
            continue
        if 1 not in f:
            continue
        vec = _deref(raw, f[1])
        changed = False
        for i in range(_u32(raw, vec)):
            slot = vec + 4 + 4 * i
            sp = _deref(raw, slot)
            name = raw[sp + 4:sp + 4 + _u32(raw, sp)].decode("utf-8", "ignore")
            if name in table:
                while len(raw) % 4:
                    raw.append(0)
                data = table[name].encode("utf-8")
                pos = len(raw)
                raw += struct.pack("<I", len(data)) + data + b"\x00"
                struct.pack_into("<I", raw, slot, pos - slot)
                changed = True
                count[name] = count.get(name, 0) + 1
        if changed:
            while len(raw) % 4:
                raw.append(0)
            struct.pack_into("<I", raw, 0, len(raw) - HEADER)
            h = str(_uuid.uuid4())
            sk.attrib["BinaryHash"] = h
            sk.text = base64.b64encode(bytes(raw)).decode("ascii")
            pj.blobs[h] = sk.text
    return count


def shift_transform(pj, item, dx, dy):
    """トランスフォーム（Geometry2）の位置を、キーフレームごと dx・dy だけずらす（動きは同じまま置く所を変える）"""
    chain = pj.ref(item.find("ClipTrackItem/ComponentOwner/Components"))
    for c in chain.findall("ComponentChain/Components/Component"):
        ce = pj.ref(c)
        if ce is None or ce.findtext("MatchName") != "AE.ADBE Geometry2":
            continue
        for p in ce.findall("Component/Params/Param"):
            pe = pj.ref(p)
            if pe is None or (pe.findtext("Name") or "").strip() != "位置":
                continue
            def mv(v):
                x, y = v.split(":")
                return f"{float(x) + dx!r}:{float(y) + dy!r}"
            sk = pe.find("StartKeyframe")
            parts = sk.text.split(",")
            parts[1] = mv(parts[1])
            sk.text = ",".join(parts)
            kf = pe.find("Keyframes")
            if kf is not None and (kf.text or "").strip():
                out = []
                for ent in kf.text.split(";"):
                    if not ent.strip():
                        out.append(ent)
                        continue
                    f = ent.split(",")
                    f[1] = mv(f[1])
                    out.append(",".join(f))
                kf.text = ";".join(out)
            return True
    raise KeyError("トランスフォームの位置が無い")


def add_gain_db(pj, item, db):
    """音のクリップの Gain（倍率）に db を足す。Gain が無ければ 0dB として足す。元の dB を返す"""
    clip = pj.ref(pj.ref(item.find("ClipTrackItem/SubClip")).find("Clip"))
    g = clip.find("Gain")
    g0 = float(g.text) if g is not None else 1.0
    import math
    if g is None:
        g = ET.SubElement(clip, "Gain")
    g.text = repr(g0 * 10 ** (db / 20))
    return 20 * math.log10(g0)


def break_text(text):
    """1行を2行に分ける：真ん中に近い、助詞などの後ろで切る"""
    n = len(text)
    best = None
    for i in range(2, n - 1):
        if text[i - 1] in BREAK_AFTER and text[i] not in "、。ー！？!?）」":
            score = abs(i - n / 2)
            if best is None or score < best[0]:
                best = (score, i)
    i = best[1] if best else n // 2
    return text[:i] + "\r" + text[i:]


