#!/usr/bin/env python3
"""「よく使う素材」ビンとプリセット「よく使うアニメーション」を作る（中身の一覧は tools/favorites.py）。2026-09-27 ユーザー依頼。

  1. setup：Premiere で、ビン「よく使う素材」「テロップ（SEつき）」「SE」と、空のシーケンス（名前だけ）を作り、SE を読み込んで保存して閉じる
       python3 tools/build_favorites.py setup <prproj> <元にするシーケンス名>
  2. fill：ファイルで、空のシーケンスの中身を入れ替える（見本集の実物からテロップ・画面効果・SE を複製。SE は見本集と同じ音量＋ --se-db）
       python3 tools/build_favorites.py fill <prproj> [--se-db -12]
  3. presets：見本集のテロップに付いている動きを抜き出して、エフェクトプリセットのファイル（.prfpset）を作る
       python3 tools/build_favorites.py presets <出力.prfpset>
     Premiere のエフェクトパネルのメニュー「プリセットの読み込み」で読み込む。クリップの頭に合わせて動く（インポイントにアンカー）
"""
import copy
import json
import math
import os
import sys
import uuid
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import favorites as fav  # noqa: E402

LIBRARY = os.path.join(ROOT, "見本", "テロップ見本集.prproj")
SE_DIR = os.path.join(ROOT, "素材", "SE")


def setup(prproj, base_seq, close=True):
    from premiere_bridge import run, preflight
    print(preflight())
    names = [t[0] for t in fav.TELOPS]
    ses = [[os.path.join(SE_DIR, f), n] for f, n in fav.SES]
    missing = [p for p, _ in ses if not os.path.exists(p)]
    assert not missing, missing
    js = open(os.path.join(HERE, "premiere_helpers.jsx"), encoding="utf-8").read() + "\n" + \
        open(os.path.join(HERE, "favorites_setup.jsx"), encoding="utf-8").read() \
        .replace("__PROJ__", os.path.abspath(prproj)).replace("__BASE__", base_seq) \
        .replace("__NAMES__", json.dumps(names, ensure_ascii=False)).replace("__SES__", json.dumps(ses, ensure_ascii=False)) \
        .replace("__CLOSE__", "true" if close else "false").replace("__BIN_ROOT__", fav.BIN_ROOT) \
        .replace("__BIN_TELOP__", fav.BIN_TELOP).replace("__BIN_SE__", fav.BIN_SE)
    r = run(js, timeout=900)
    print(json.dumps(r, ensure_ascii=False, indent=1) if isinstance(r, dict) else r)
    return r


def add_gain_db(pj, item, db):
    clip = pj.ref(pj.ref(item.find("ClipTrackItem/SubClip")).find("Clip"))
    g = clip.find("Gain")
    g0 = float(g.text) if g is not None else 1.0
    if g is None:
        g = ET.SubElement(clip, "Gain")
    g.text = repr(g0 * 10 ** (db / 20))
    return 20 * math.log10(g0)


def fill(prproj, se_db=0.0, out=None):
    from reproduce import Library
    lib = Library(prproj)
    pj = lib.pj
    rec = []
    for name, tid, sid, eid in fav.TELOPS:
        seq = pj.sequence(name)
        for tn, tr in pj.tracks(seq):                  # サブシーケンスで入ってきたクリップを外す
            for path in ("ClipTrack/ClipItems/TrackItems", "ClipTrack/TransitionItems/TrackItems"):
                lst = tr.find(path)
                if lst is not None:
                    for x in list(lst):
                        lst.remove(x)
            ci = tr.find("ClipTrack/ClipItems")         # 空のトラックにはクリップ一覧の入れ物が無い（他のトラックと同じ形で足す）
            if ci is not None and ci.find("TrackItems") is None:
                ci.insert(0, ET.Element("TrackItems", {"Version": "1"}))
        sample, _ = lib.sample_item(tid)
        dur = (pj.span(sample)[1] - pj.span(sample)[0]) / 254016000000
        dur = max(dur, 2.0)
        vt = "V1"
        if eid:
            lib.add_effect(seq, eid, start=0, duration=dur, track="V1")
            vt = "V2"
        lib.add_telop(seq, tid, lib.type_texts(tid), start=0, duration=dur, track=vt, size=None)
        g = None
        if sid:
            se = lib.add_se(seq, sid, start=0, track="A1")
            if se_db:
                g = add_gain_db(pj, se, se_db)
        rec.append({"sequence": name, "telop": tid, "se": sid, "effect": eid, "sec": round(dur, 2)})
    pj.gc()
    lib.save(out or prproj)
    print(json.dumps(rec, ensure_ascii=False, indent=1))
    return rec


# ---------- プリセット ----------
def presets(out_path):
    from reproduce import Library
    lib = Library(LIBRARY)
    pj = lib.pj
    root = ET.Element("PremiereData", {"Version": "3"})
    ids = [100]

    def nid():
        ids[0] += 1
        return str(ids[0])

    def el(parent, tag, text=None, **attrs):
        e = ET.SubElement(parent, tag, attrs)
        if text is not None:
            e.text = text
        return e

    def bin_item(oid, name, item_refs, presets_bin=False, data_ref=None):
        b = ET.Element("BinTreeItem", {"ObjectID": oid, "ClassID": "5e0f46fa-384f-4c09-bc53-0b8e2b7005b5", "Version": "4"})
        el(b, "Expanded", "true")
        el(b, "Sorted", "false")
        tb = el(b, "TreeItemBase", Version="4")
        el(tb, "Name", name)
        node = el(tb, "Node", Version="1")
        if presets_bin:
            pr = el(node, "Properties", Version="1")
            el(pr, "HandlerEffects.EffectItemTree.PresetsBin", "1")
        if data_ref:
            el(tb, "Data", ObjectRef=data_ref)
        el(tb, "Locked", "false")
        its = el(b, "Items", Version="1")
        for i, r in enumerate(item_refs):
            el(its, "Item", Index=str(i), ObjectRef=r)
        return b

    tree = el(root, "Tree", ObjectRef="1")
    t = el(root, "Tree", ObjectID="1", ClassID="177f2841-dd5b-43bd-9d9a-79e231bd47dd", Version="1")
    el(t, "Node", Version="1")
    el(t, "RootBin", ObjectRef="2")
    objs = []
    preset_items = []
    rec = []
    for pname, tid, comp_names, freeze in fav.PRESETS:
        sample, _ = lib.sample_item(tid)
        sub = pj.ref(sample.find("ClipTrackItem/SubClip"))
        h = pj.range_holder(pj.ref(sub.find("Clip")))
        a_in, a_out = h.findtext("InPoint"), h.findtext("OutPoint")
        chain = pj.ref(sample.find("ClipTrackItem/ComponentOwner/Components"))
        comps = []
        for c in chain.iter("Component"):
            if "ObjectRef" not in c.attrib:
                continue
            comp = pj.ref(c)
            if comp is not None and comp.findtext("Component/DisplayName") in comp_names:
                comps.append(comp)
        got = sorted({c.findtext("Component/DisplayName") for c in comps})
        assert set(got) == set(comp_names), (pname, tid, got)
        fp_refs = []
        for comp in comps:
            # 部品一式（エフェクトとパラメータ）を複製して番号を振り直す
            parts = pj.subgraph(comp)
            remap = {o.attrib["ObjectID"]: nid() for o in parts}
            copies = []
            for o in parts:
                cp = copy.deepcopy(o)
                cp.attrib["ObjectID"] = remap[o.attrib["ObjectID"]]
                for e in cp.iter():
                    if "ObjectRef" in e.attrib and e.attrib["ObjectRef"] in remap:
                        e.attrib["ObjectRef"] = remap[e.attrib["ObjectRef"]]
                copies.append(cp)
            top = copies[0]
            assert top.tag.endswith("FilterComponent"), top.tag
            for pr_ref in top.iter("Param"):          # 止めるパラメータ：キーフレームを外して最後の値にする
                if "ObjectRef" not in pr_ref.attrib:
                    continue
                prm = next((x for x in copies if x.attrib["ObjectID"] == pr_ref.attrib["ObjectRef"]), None)
                if prm is None or prm.findtext("Name") not in freeze:
                    continue
                kf = [k for k in (prm.findtext("Keyframes") or "").split(";") if k.strip()]
                if kf:
                    last = kf[-1].split(",")
                    sk = prm.find("StartKeyframe").text.split(",")
                    sk[1] = last[1]
                    prm.find("StartKeyframe").text = ",".join(sk)
                    prm.find("Keyframes").text = ""
                    prm.find("IsTimeVarying").text = "false"
            objs.extend(copies)
            fpid = nid()
            fp = ET.Element("FilterPreset", {"ObjectID": fpid, "ClassID": "ee52a7d2-069e-47f7-aa30-e3e3286b65a3", "Version": "3"})
            el(fp, "MediaType", "228cda18-3625-4d2d-951e-348879e4ed93")
            el(fp, "Node", Version="1")
            el(fp, "Type", "1")                        # インポイントにアンカー
            el(fp, "AnchorInPoint", a_in)
            el(fp, "AnchorOutPoint", a_out)
            el(fp, "Speed", "1.")
            el(fp, "TransitionDuration", "0")
            el(fp, "FilterMatchName", top.findtext("MatchName"))
            el(fp, "Component", ObjectRef=top.attrib["ObjectID"])
            el(fp, "Description", f"見本集 {tid} の動き（{top.findtext('Component/DisplayName')}）")
            objs.append(fp)
            fp_refs.append(fpid)
        fpi = nid()
        fpit = ET.Element("FilterPresetItem", {"ObjectID": fpi, "ClassID": "e56c9ba0-91cb-4f21-9174-c1b52448c6c9", "Version": "2"})
        ei = el(fpit, "EffectItem", Version="1")
        el(ei, "EffectFlavor", "5")
        el(ei, "EffectIsShorcut", "false")
        fps = el(fpit, "FilterPresets", Version="1")
        for i, r in enumerate(fp_refs):
            el(fps, "FilterPreset", Index=str(i), ObjectRef=r)
        objs.append(fpit)
        ti = nid()
        tit = ET.Element("TreeItem", {"ObjectID": ti, "ClassID": "025f59ac-1f29-42c0-9897-ada1059bd547", "Version": "3"})
        tb = el(tit, "TreeItemBase", Version="4")
        el(tb, "Name", pname)
        node = el(tb, "Node", Version="1")
        prp = el(node, "Properties", Version="1")
        el(prp, "MZ.EffectPresets.PresetUID", str(uuid.uuid4()))
        el(tb, "Data", ObjectRef=fpi)
        el(tb, "Locked", "false")
        objs.append(tit)
        preset_items.append(ti)
        rec.append({"name": pname, "from": tid, "effects": [c.findtext("Component/DisplayName") for c in comps]})
    # Root → よく使うアニメーション（プリセットの読み込みで「プリセット」の下に入る）
    fav_bin = bin_item("3", fav.PRESET_BIN, preset_items)
    root.append(bin_item("2", "Root", ["3"]))
    root.append(fav_bin)
    for o in objs:
        root.append(o)
    ET.indent(root, "\t")
    data = b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="utf-8")
    open(out_path, "wb").write(data)
    print(json.dumps(rec, ensure_ascii=False, indent=1))
    print(out_path, len(rec), "presets")
    return rec


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "setup":
        setup(sys.argv[2], sys.argv[3])
    elif cmd == "fill":
        db = float(sys.argv[sys.argv.index("--se-db") + 1]) if "--se-db" in sys.argv else 0.0
        fill(sys.argv[2], db)
    elif cmd == "presets":
        presets(sys.argv[2])
    else:
        sys.exit(__doc__)
