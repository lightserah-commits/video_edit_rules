#!/usr/bin/env python3
"""Premiereプロジェクト（.prproj＝gzip圧縮されたXML）の中で、テロップを「部品ごと完全に複製」するツール。

コピー＆ペーストと同じ結果を、ファイル上で作る。
  - テロップ1本は、タイムライン項目 → サブクリップ → クリップ → 素材ソース → エフェクト部品 → パラメーター（キーフレーム込み）
    という部品のつながり（ObjectRef）でできている。これを丸ごと複製し、新しい ObjectID を振る。
  - 共有物（元クリップ MasterClip・素材 Media・保存スタイル）への参照（ObjectURef）はそのまま指す。
    → 同じプロジェクト（または同じ共有物を持つコピー）の中で使う。
  - 図形・文字の書式・位置・クリップに付いたエフェクト（トランスフォーム等）・キーフレーム（アニメーション）まで元と同じになる。
  - 文字は、文字データ（FlatBuffer）のランの文字列だけを付け替える（telop_xml.py と同じ方式）。

使い方（Pythonから）:
  pj = Prproj.load("in.prproj")
  seq = pj.sequence("テロップ見本集")
  src = pj.item_at(seq, "V8", 25.46)                 # 見本のテロップ（トラックと開始秒）
  pj.clone_item(src, seq, "V6", start=100.0, duration=2.0, texts=[["新しい文字"]])
  pj.save("out.prproj")
"""
import base64
import copy
import gzip
import re
import struct
import uuid
import xml.etree.ElementTree as ET

TPS = 254016000000  # 1秒あたりの ticks
HEADER = 12


# ---------- 文字データ（FlatBuffer）の差し替え ----------
def _u32(b, p):
    return struct.unpack_from("<I", b, p)[0]


def _fields(b, pos):
    vt = pos - struct.unpack_from("<i", b, pos)[0]
    n = (struct.unpack_from("<H", b, vt)[0] - 4) // 2
    return {i: pos + struct.unpack_from("<H", b, vt + 4 + 2 * i)[0] for i in range(n) if struct.unpack_from("<H", b, vt + 4 + 2 * i)[0]}


def _deref(b, p):
    return p + _u32(b, p)


def text_runs(blob):
    env = HEADER + _u32(blob, HEADER)
    f_env = _fields(blob, env)
    if 0 not in f_env:
        return []
    f_doc = _fields(blob, _deref(blob, f_env[0]))
    if 0 not in f_doc:          # 文字が空のレイヤー（ランが1つもない）
        return []
    vec = _deref(blob, f_doc[0])
    out = []
    for i in range(_u32(blob, vec)):
        run = _deref(blob, vec + 4 + 4 * i)
        ref_at = _fields(blob, run)[0]
        sp = _deref(blob, ref_at)
        out.append((blob[sp + 4:sp + 4 + _u32(blob, sp)].decode("utf-8"), ref_at))
    return out


def run_styles(blob):
    """ランごとの文字・フォント名・文字の大きさ（px）。大きさはランの書式の表の1番目の値（32ビット小数）。
    size_at はその値のバイト位置（書き換えに使う）。複数のランが同じ書式の表を指すこともある。"""
    env = HEADER + _u32(blob, HEADER)
    f_env = _fields(blob, env)
    if 0 not in f_env:
        return []
    doc = _deref(blob, f_env[0])
    f_doc = _fields(blob, doc)
    if 0 not in f_doc:
        return []
    fonts = []
    if 1 in f_doc:
        fv = _deref(blob, f_doc[1])
        for i in range(_u32(blob, fv)):
            sp = _deref(blob, fv + 4 + 4 * i)
            fonts.append(blob[sp + 4:sp + 4 + _u32(blob, sp)].decode("utf-8"))
    vec = _deref(blob, f_doc[0])
    out = []
    for i in range(_u32(blob, vec)):
        run = _deref(blob, vec + 4 + 4 * i)
        fr = _fields(blob, run)
        sp = _deref(blob, fr[0])
        item = {"text": blob[sp + 4:sp + 4 + _u32(blob, sp)].decode("utf-8"), "font": None, "size": None, "size_at": None}
        if 1 in fr:
            fs = _fields(blob, _deref(blob, fr[1]))
            fi = _u32(blob, fs[0]) if 0 in fs else 0
            item["font"] = fonts[fi] if fi < len(fonts) else None
            if 1 in fs:
                item["size_at"] = fs[1]
                item["size"] = struct.unpack_from("<f", blob, fs[1])[0]
        out.append(item)
    return out


def scale_run_sizes(blob, factor):
    """全部のランの文字の大きさを factor 倍にした文字データを返す（その場で書き換え。長さは変わらない）"""
    out = bytearray(blob)
    for at in {r["size_at"] for r in run_styles(blob) if r["size_at"] is not None}:
        struct.pack_into("<f", out, at, struct.unpack_from("<f", blob, at)[0] * factor)
    return bytes(out)


def replace_runs(blob, new_texts):
    runs = text_runs(blob)
    if len(new_texts) != len(runs):
        raise ValueError(f"ランの数が合いません（見本 {len(runs)}: {[r[0] for r in runs]}、指定 {len(new_texts)}）")
    out = bytearray(blob)
    for (_, ref_at), new in zip(runs, new_texts):
        while len(out) % 4:
            out.append(0)
        data = new.replace("\r\n", "\r").replace("\n", "\r").encode("utf-8")
        pos = len(out)
        out += struct.pack("<I", len(data)) + data + b"\x00"
        struct.pack_into("<I", out, ref_at, pos - ref_at)
    while len(out) % 4:
        out.append(0)
    struct.pack_into("<I", out, 0, len(out) - HEADER)
    return bytes(out)


# ---------- プロジェクト ----------
class Prproj:
    def __init__(self, root):
        self.root = root
        self._index()

    @classmethod
    def load(cls, path):
        data = open(path, "rb").read()
        if data[:2] == b"\x1f\x8b":
            data = gzip.decompress(data)
        return cls(ET.fromstring(data))

    def _index(self):
        self.ids, self.uids = {}, {}
        for e in self.root:
            if "ObjectID" in e.attrib:
                self.ids[e.attrib["ObjectID"]] = e
            if "ObjectUID" in e.attrib:
                self.uids[e.attrib["ObjectUID"]] = e
        self.next_id = max(int(k) for k in self.ids) + 1
        # バイナリの中身（BinaryHash）。同じ中身は最初の1か所だけが持ち、他は番号で指す
        self.blobs = {}
        for e in self.root.iter():
            h = e.attrib.get("BinaryHash")
            if h and e.text and e.text.strip() and h not in self.blobs:
                self.blobs[h] = e.text.strip()
        node_ids = [int(n.findtext("ID")) for n in self.root.iter("Node") if (n.findtext("ID") or "").isdigit()]
        self.next_node_id = max(node_ids) + 1 if node_ids else 1000000

    def save(self, path):
        body = ET.tostring(self.root, encoding="unicode")
        xml = '<?xml version="1.0" encoding="UTF-8" ?>\n' + body
        with gzip.open(path, "wb") as f:
            f.write(xml.encode("utf-8"))

    def ref(self, e):
        if e is None:
            return None
        if "ObjectRef" in e.attrib:
            return self.ids.get(e.attrib["ObjectRef"])
        if "ObjectURef" in e.attrib:
            return self.uids.get(e.attrib["ObjectURef"])
        return None

    # --- シーケンス・トラック ---
    def sequence(self, name):
        cands = [s for s in self.root.findall("Sequence") if s.findtext("Name") == name]
        if not cands:
            raise KeyError(f"シーケンスがありません: {name}")
        return max(cands, key=lambda s: len(list(self.tracks(s))))

    def tracks(self, seq):
        for tg in seq.findall("TrackGroups/TrackGroup"):
            g = self.ref(tg.find("Second"))
            if g is None or g.tag not in ("VideoTrackGroup", "AudioTrackGroup"):
                continue
            p = "V" if g.tag == "VideoTrackGroup" else "A"
            for i, t in enumerate(g.findall("TrackGroup/Tracks/Track")):
                tr = self.ref(t)
                if tr is not None:
                    yield p + str(i + 1), tr

    def frame_ticks(self, seq):
        """シーケンスの1フレームの長さ（ticks）。29.97fps＝8475667200、30fps＝8467200000"""
        for tg in seq.findall("TrackGroups/TrackGroup"):
            g = self.ref(tg.find("Second"))
            if g is not None and g.tag == "VideoTrackGroup" and (g.findtext("TrackGroup/FrameRate") or "").isdigit():
                return int(g.findtext("TrackGroup/FrameRate"))
        return 8475667200

    def track(self, seq, name):
        for n, tr in self.tracks(seq):
            if n == name:
                return tr
        raise KeyError(f"トラックがありません: {name}")

    def items(self, track):
        out = []
        for ti in track.findall("ClipTrack/ClipItems/TrackItems/TrackItem"):
            it = self.ref(ti)
            if it is not None:
                out.append(it)
        return out

    @staticmethod
    def span(item):
        ti = item.find("ClipTrackItem/TrackItem")
        return int(ti.findtext("Start") or 0), int(ti.findtext("End") or 0)

    @staticmethod
    def range_holder(clip):
        """クリップ（VideoClip・AudioClip・RemixClip）の中で InPoint/OutPoint を持つ要素。
        リミックスしたBGM（RemixClip）は、中の AudioClip の方に持っている。"""
        if clip is None:
            return None
        for path in ("Clip", "AudioClip/Clip", "VideoClip/Clip"):
            c = clip.find(path)
            if c is not None and c.find("InPoint") is not None and c.find("OutPoint") is not None:
                return c
        return None

    def item_at(self, seq, track_name, seconds, tol=0.05):
        for it in self.items(self.track(seq, track_name)):
            s, _ = self.span(it)
            if abs(s / TPS - seconds) <= tol:
                return it
        raise KeyError(f"{track_name} の {seconds}秒 にクリップがありません")

    # --- 複製 ---
    def subgraph(self, item):
        """ObjectRef でたどれる部品一式（この項目だけが持つもの）"""
        seen, order, stack = set(), [], [item]
        while stack:
            o = stack.pop()
            oid = o.attrib.get("ObjectID")
            if oid in seen:
                continue
            seen.add(oid)
            order.append(o)
            for e in o.iter():
                if e is not o and "ObjectRef" in e.attrib:
                    t = self.ids.get(e.attrib["ObjectRef"])
                    if t is not None and t.attrib.get("ObjectID") not in seen:
                        stack.append(t)
        return order

    def text_components(self, item):
        chain = self.ref(item.find("ClipTrackItem/ComponentOwner/Components"))
        comps = []
        if chain is None:
            return comps
        for c in chain.findall("ComponentChain/Components/Component"):
            ce = self.ref(c)
            if ce is not None and ce.findtext("MatchName") == "AE.ADBE Text":
                comps.append(ce)
        return comps

    def item_texts(self, item):
        """テロップの文字（文字レイヤーごと・ランごと）"""
        out = []
        for ce in self.text_components(item):
            for p in ce.findall("Component/Params/Param"):
                pe = self.ref(p)
                if pe is not None and pe.tag == "ArbVideoComponentParam" and pe.findtext("ParameterID") == "1":
                    sk = pe.find("StartKeyframeValue")
                    b = (sk.text or "").strip() or self.blobs.get(sk.attrib.get("BinaryHash"), "")
                    out.append([r[0] for r in text_runs(base64.b64decode(b))] if b else [])
        return out

    def text_blobs(self, item):
        """item の文字レイヤーごとの (値の要素, 文字データ)"""
        out = []
        for ce in self.text_components(item):
            for p in ce.findall("Component/Params/Param"):
                pe = self.ref(p)
                if pe is not None and pe.tag == "ArbVideoComponentParam" and pe.findtext("ParameterID") == "1":
                    sk = pe.find("StartKeyframeValue")
                    b = (sk.text or "").strip() or self.blobs.get(sk.attrib.get("BinaryHash"), "")
                    if b:
                        out.append((sk, base64.b64decode(b)))
        return out

    def scale_font_sizes(self, item, factor):
        """item の文字の大きさを全部 factor 倍にする（縁取りの太さ・位置は変えない）。書き換えた文字レイヤーの数を返す。
        文字データは新しい番号（BinaryHash）で持たせるので、見本や他のクリップには影響しない。"""
        n = 0
        for sk, raw in self.text_blobs(item):
            h = str(uuid.uuid4())
            sk.attrib["BinaryHash"] = h
            sk.text = base64.b64encode(scale_run_sizes(raw, factor)).decode("ascii")
            self.blobs[h] = sk.text
            n += 1
        return n

    def clone_item(self, src, seq, track_name, start=None, duration=None, texts=None, name=None, src_offset=0.0,
                   start_ticks=None, duration_ticks=None, src_offset_ticks=None):
        """src（タイムライン項目）を部品ごと複製して、seq の track_name の start 秒に置く。
        src_offset: 元のクリップの何秒目から使うか（背景の映像などを途中から切り出すとき）。
        *_ticks を渡すと秒の代わりに ticks で正確に指定できる（フレームの区切りに合わせるときに使う）。"""
        start_t = start_ticks if start_ticks is not None else int(round(start * TPS))
        s0, e0 = self.span(src)
        off_t = src_offset_ticks if src_offset_ticks is not None else int(round(src_offset * TPS))
        if duration_ticks is not None:
            dur_t = duration_ticks
        else:
            dur_t = int(round(duration * TPS)) if duration is not None else (e0 - s0 - off_t)
        end_t = start_t + dur_t
        track = self.track(seq, track_name)
        for it in self.items(track):
            a, b = self.span(it)
            if a < end_t and start_t < b:
                raise ValueError(f"{track_name} の {start_t / TPS:.3f}〜{end_t / TPS:.3f}秒 は既存クリップと重なります")
        # 部品一式を複製して ObjectID を振り直す
        parts = self.subgraph(src)
        remap = {}
        for o in parts:
            remap[o.attrib["ObjectID"]] = str(self.next_id)
            self.next_id += 1
        new_parts = []
        for o in parts:
            c = copy.deepcopy(o)
            c.attrib["ObjectID"] = remap[o.attrib["ObjectID"]]
            for e in c.iter():
                if "ObjectRef" in e.attrib and e.attrib["ObjectRef"] in remap:
                    e.attrib["ObjectRef"] = remap[e.attrib["ObjectRef"]]
            new_parts.append(c)
        # 共有バイナリ（BinaryHash）は、ファイル全体で中身を1か所だけに持つ決まり。
        # 複製では中身を書かず番号で指すだけにする（元が中身を持っていた場合は、複製側を参照に変える）。
        for c in new_parts:
            for e in c.iter():
                if e.attrib.get("BinaryHash") and (e.text or "").strip():
                    e.text = None
        by_id = {c.attrib["ObjectID"]: c for c in new_parts}
        new_item = by_id[remap[src.attrib["ObjectID"]]]
        # クリップ固有の番号を振り直す
        for c in new_parts:
            if c.tag.endswith("ClipTrackItem"):
                nid = c.find("ClipTrackItem/TrackItem/Node/ID")
                if nid is not None:
                    nid.text = str(self.next_node_id)
                    self.next_node_id += 1
            for cid in c.iter("ClipID"):
                cid.text = str(uuid.uuid4())
        # 位置と長さ
        ti = new_item.find("ClipTrackItem/TrackItem")
        st = ti.find("Start")
        if st is None:
            st = ET.Element("Start")
            ti.insert(list(ti).index(ti.find("End")), st)
        st.text = str(start_t)
        ti.find("End").text = str(end_t)
        sub = by_id[new_item.find("ClipTrackItem/SubClip").attrib["ObjectRef"]]
        clip = by_id.get(sub.find("Clip").attrib.get("ObjectRef")) if sub.find("Clip") is not None else None
        holder = self.range_holder(clip)
        if holder is not None:
            new_in = int(holder.findtext("InPoint")) + off_t
            holder.find("InPoint").text = str(new_in)
            holder.find("OutPoint").text = str(new_in + dur_t)
        muted = new_item.find("ClipTrackItem/IsMuted")
        if muted is not None:
            new_item.find("ClipTrackItem").remove(muted)
        # 文字の差し替え
        if texts is not None:
            comps = []
            chain = by_id[new_item.find("ClipTrackItem/ComponentOwner/Components").attrib["ObjectRef"]]
            for cref in chain.findall("ComponentChain/Components/Component"):
                ce = by_id.get(cref.attrib["ObjectRef"])
                if ce is not None and ce.findtext("MatchName") == "AE.ADBE Text":
                    comps.append(ce)
            if len(texts) != len(comps):
                raise ValueError(f"文字レイヤーの数が合いません（見本 {len(comps)}、指定 {len(texts)}）")
            for ce, runs in zip(comps, texts):
                for p in ce.findall("Component/Params/Param"):
                    pe = by_id.get(p.attrib["ObjectRef"])
                    if pe is None:
                        continue
                    if pe.tag == "ArbVideoComponentParam" and pe.findtext("ParameterID") == "1":
                        sk = pe.find("StartKeyframeValue")
                        b = (sk.text or "").strip() or self.blobs.get(sk.attrib.get("BinaryHash"), "")
                        new_blob = replace_runs(base64.b64decode(b), runs)
                        h = str(uuid.uuid4())
                        sk.attrib["BinaryHash"] = h
                        sk.text = base64.b64encode(new_blob).decode("ascii")
                        self.blobs[h] = sk.text
                    elif (pe.findtext("Name") or "").strip() in ("start", "end") and pe.findtext("StartKeyframe"):
                        parts_v = pe.findtext("StartKeyframe").split(",")
                        parts_v[1] = "-1."
                        pe.find("StartKeyframe").text = ",".join(parts_v)
                inst = ce.find("Component/InstanceName")
                if inst is not None:
                    inst.text = "".join(runs).replace("\n", "\r")
        label = name or (" ".join("".join(r) for r in texts).replace("\n", " ") if texts else sub.findtext("Name"))
        if sub.find("Name") is not None and label:
            sub.find("Name").text = label
        # プロジェクトに追加し、トラックに登録（時刻順に並べ直す）
        for c in new_parts:
            self.root.append(c)
            self.ids[c.attrib["ObjectID"]] = c
        items_el = track.find("ClipTrack/ClipItems/TrackItems")
        refs = list(items_el.findall("TrackItem"))
        new_ref = ET.Element("TrackItem", {"Index": "0", "ObjectRef": new_item.attrib["ObjectID"]})
        refs.append(new_ref)
        refs.sort(key=lambda r: self.span(self.ids[r.attrib["ObjectRef"]])[0])
        for r in list(items_el.findall("TrackItem")):
            items_el.remove(r)
        for i, r in enumerate(refs):
            r.attrib["Index"] = str(i)
            items_el.append(r)
        return new_item


    # --- 見本集づくりの補助 ---
    def detach_all(self, seq):
        """seq の全トラックからクリップを外し（部品は残す）、リンクとマーカーも外す。外したクリップの一覧を返す。"""
        detached = []
        for _, tr in self.tracks(seq):
            for path in ("ClipTrack/ClipItems/TrackItems", "ClipTrack/TransitionItems/TrackItems"):
                lst = tr.find(path)
                if lst is None:
                    continue
                for r in list(lst.findall("TrackItem")):
                    it = self.ref(r)
                    if it is not None:
                        detached.append(it)
                    lst.remove(r)
        links = seq.find("PersistentGroupContainer/LinkContainer/Links")
        if links is not None:
            for l in list(links):
                links.remove(l)
        mk = self.ref(seq.find("MarkerOwner/Markers"))
        if mk is not None and mk.find("Markers") is not None:
            for m in list(mk.find("Markers")):
                mk.find("Markers").remove(m)
        return detached

    def rename_sequence(self, seq, new_name):
        """シーケンス名と、プロジェクトパネルに出る名前（MasterClip・ProjectItem）を変える。"""
        uid = seq.attrib.get("ObjectUID")
        old = seq.findtext("Name")
        seq.find("Name").text = new_name
        masters = set()
        for e in self.root.iter():
            if e.attrib.get("ObjectURef") == uid and e.tag == "Sequence":
                pass
        for mc in self.root.findall("MasterClip"):
            found = False
            for e in mc.iter():
                if "ObjectRef" in e.attrib:
                    o = self.ids.get(e.attrib["ObjectRef"])
                    if o is not None:
                        for x in o.iter():
                            if "ObjectRef" in x.attrib:
                                src = self.ids.get(x.attrib["ObjectRef"])
                                if src is not None and any(y.attrib.get("ObjectURef") == uid for y in src.iter()):
                                    found = True
            if found and mc.findtext("Name") == old:
                mc.find("Name").text = new_name
                masters.add(mc.attrib.get("ObjectUID"))
        for pi in self.root.findall("ClipProjectItem"):
            m = pi.find("MasterClip")
            if m is not None and m.attrib.get("ObjectURef") in masters and pi.find("ProjectItem/Name") is not None:
                pi.find("ProjectItem/Name").text = new_name
        return len(masters)

    def replace_font(self, item, old_font, new_font):
        """item の文字データの中のフォント名を付け替える（フォントの一覧の文字列を差し替える）。"""
        n = 0
        for o in self.subgraph(item):
            if o.tag != "ArbVideoComponentParam" or o.findtext("ParameterID") != "1":
                continue
            sk = o.find("StartKeyframeValue")
            if sk is None:
                continue
            b = (sk.text or "").strip() or self.blobs.get(sk.attrib.get("BinaryHash"), "")
            if not b:
                continue
            raw = bytearray(base64.b64decode(b))
            try:
                env = HEADER + _u32(raw, HEADER)
                doc = _deref(raw, _fields(raw, env)[0])
                f = _fields(raw, doc)
            except Exception:
                continue
            if 1 not in f:
                continue
            vec = _deref(raw, f[1])
            changed = False
            for i in range(_u32(raw, vec)):
                slot = vec + 4 + 4 * i
                sp = _deref(raw, slot)
                if raw[sp + 4:sp + 4 + _u32(raw, sp)].decode("utf-8", "ignore") == old_font:
                    while len(raw) % 4:
                        raw.append(0)
                    data = new_font.encode("utf-8")
                    pos = len(raw)
                    raw += struct.pack("<I", len(data)) + data + b"\x00"
                    struct.pack_into("<I", raw, slot, pos - slot)
                    changed = True
            if changed:
                while len(raw) % 4:
                    raw.append(0)
                struct.pack_into("<I", raw, 0, len(raw) - HEADER)
                h = str(uuid.uuid4())
                sk.attrib["BinaryHash"] = h
                sk.text = base64.b64encode(bytes(raw)).decode("ascii")
                self.blobs[h] = sk.text
                n += 1
        return n

    def replace_font_all(self, table):
        """プロジェクトの全部の文字データで、フォントの一覧の名前を置き換える（table = {古い名前: 新しい名前}）。
        タイムラインに置いていない見本や、使われていない名前も含めて置き換えるので、開いたときの「解決不能」の警告が出なくなる。
        置き換えた数を {古い名前: 数} で返す。（2026-09-26、画面解説の案件で使った置き換えをツールに移したもの）"""
        count = {}
        for o in list(self.root):
            if o.tag != "ArbVideoComponentParam" or o.findtext("ParameterID") != "1":
                continue
            sk = o.find("StartKeyframeValue")
            if sk is None:
                continue
            b = (sk.text or "").strip() or self.blobs.get(sk.attrib.get("BinaryHash"), "")
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
                h = str(uuid.uuid4())
                sk.attrib["BinaryHash"] = h
                sk.text = base64.b64encode(bytes(raw)).decode("ascii")
                self.blobs[h] = sk.text
        return count

    def gc(self):
        """Project からたどれない部品を削除する（外したクリップの残骸の掃除）。削除数を返す。"""
        start = [e for e in self.root if e.tag == "Project" and "ObjectID" in e.attrib]
        seen, stack = set(), list(start)
        while stack:
            o = stack.pop()
            key = o.attrib.get("ObjectID") or o.attrib.get("ObjectUID")
            if key in seen:
                continue
            seen.add(key)
            for e in o.iter():
                t = None
                if "ObjectRef" in e.attrib:
                    t = self.ids.get(e.attrib["ObjectRef"])
                elif "ObjectURef" in e.attrib:
                    t = self.uids.get(e.attrib["ObjectURef"])
                if t is not None:
                    k = t.attrib.get("ObjectID") or t.attrib.get("ObjectUID")
                    if k not in seen:
                        stack.append(t)
        removed = 0
        blobs_before = dict(self.blobs)
        for e in list(self.root):
            key = e.attrib.get("ObjectID") or e.attrib.get("ObjectUID")
            if key is not None and key not in seen:
                self.root.remove(e)
                removed += 1
        # 中身を持っていた部品を消した場合は、残った参照側に中身を書き込む
        defined = {e.attrib["BinaryHash"] for e in self.root.iter() if e.attrib.get("BinaryHash") and (e.text or "").strip()}
        for e in self.root.iter():
            h = e.attrib.get("BinaryHash")
            if h and h not in defined and not (e.text or "").strip() and h in blobs_before:
                e.text = blobs_before[h]
                defined.add(h)
        self._index()
        return removed


    def check_binaries(self):
        """共有バイナリの決まり（中身は番号ごとに1か所・参照より前）を確かめる。問題の件数を返す。"""
        seen_def, first_ref, dup, before, missing = {}, {}, 0, 0, 0
        for i, e in enumerate(self.root.iter()):
            h = e.attrib.get("BinaryHash")
            if not h:
                continue
            if (e.text or "").strip():
                if h in seen_def:
                    dup += 1
                seen_def.setdefault(h, i)
            else:
                first_ref.setdefault(h, i)
        for h, i in first_ref.items():
            if h not in seen_def:
                missing += 1
            elif seen_def[h] > i:
                before += 1
        return {"duplicate_definitions": dup, "reference_before_definition": before, "missing_definitions": missing}
