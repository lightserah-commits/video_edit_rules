#!/usr/bin/env python3
"""テロップ見本集から「部品集」（背景の映像なしの軽い版。AI が案件を組み立てる時の元）を作る。

見本集（見本/テロップ見本集.prproj）は人が見る用にそのまま残し、そのコピーから次を外す：
  - シーケンス「テロップ見本集」の中の、見本（目次の T・E・S。D の場面見本は除く）以外のクリップ
    （背景のカメラ映像・声・字幕・一緒に置かれていた調整レイヤーや SE など）
  - 残した見本から参照されない、プロジェクトパネルのクリップ・シーケンス・空になったビン
さらに、残った素材のうち video_edit_rules/素材/ に同じ名前のファイルがあるものは、そちらを指すようにする
（SE・BGM・画像。相対パスも書くので、ユーザー名が違う Mac でも見つかる）。

シーケンス名「テロップ見本集」と型ID・時刻は見本集と同じなので、reproduce.py の Library・目次・types.json はそのまま使える。
場面見本（D01〜D07）は入らないので、reproduce.py の demo と verify_library.py は見本集で使う。

素材の絶対パスには Mac のユーザー名が入るので、案件で使う時は --case-copy でコピーする
（この Mac の 素材/ と、案件のフォルダから見た相対パスに書き直す。video_edit_rules の中は書き換えないので iMac でも使える）。

使い方:
  python3 build_parts.py                       # 見本/テロップ見本集.prproj → 見本/テロップ部品集.prproj（見本集に型を足したら作り直す）
  python3 build_parts.py --library 入力.prproj --out 出力.prproj
  python3 build_parts.py --case-copy 案件/edit/v001/案件_v001.prproj   # 部品集を案件の版のフォルダへコピー

作った時に、元の見本集・目次・型の分類の指紋を 見本/テロップ部品集_元.json に残す。--case-copy は今の見本集と比べ、
違えば（見本集に型を足して作り直していない）止める。素材が欠けている・素材/ の外を指す素材がある時も、書く前に止める。
"""
import argparse
import hashlib
import json
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from native_prproj import Prproj  # noqa: E402

ROOT = os.path.expanduser("~/Desktop/video_edit_rules")
LIBRARY = os.path.join(ROOT, "見本", "テロップ見本集.prproj")
OUT = os.path.join(ROOT, "見本", "テロップ部品集.prproj")
INDEX = os.path.join(ROOT, "見本", "テロップ見本集_目次.json")
TYPES = os.path.join(ROOT, "見本", "分類", "types.json")
MATERIAL_DIRS = [os.path.join(ROOT, "素材", d) for d in ("SE", "BGM", "画像", "イラスト")]


def nfc(s):
    return unicodedata.normalize("NFC", s or "")


def same_file(a, b):
    with open(a, "rb") as fa, open(b, "rb") as fb:
        return hashlib.md5(fa.read()).digest() == hashlib.md5(fb.read()).digest()


def fingerprint(library):
    """部品集の元（見本集・目次・型の分類）の指紋。見本集に型を足したのに部品集を作り直し忘れたら気づけるように"""
    def md5(p):
        with open(p, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()
    return {"library": md5(library), "index": md5(INDEX), "types": md5(TYPES)}


def sidecar(parts):
    return os.path.splitext(parts)[0] + "_元.json"


def key(e):
    return e.attrib.get("ObjectID") or e.attrib.get("ObjectUID")


def refs_of(pj, o):
    """o が指す部品。プロジェクトの表示設定（ProjectViewState.List）のように、中に別の番号の振り方を持つ
    埋め込みのデータの中の参照は、全体の部品の番号ではないのでたどらない（たどると関係ない部品を残してしまう）。"""
    stack = [o]
    while stack:
        n = stack.pop()
        for ch in n:
            if "ObjectID" in ch.attrib or "ObjectUID" in ch.attrib:
                continue            # 埋め込みのデータ（全体の部品は root の直下にしか無い）
            t = pj.ref(ch)
            if t is not None:
                yield t
            stack.append(ch)


def reachable(pj, starts):
    seen, stack = set(), list(starts)
    while stack:
        o = stack.pop()
        k = key(o)
        if k in seen:
            continue
        seen.add(k)
        for t in refs_of(pj, o):
            if key(t) not in seen:
                stack.append(t)
    return seen


def gc(pj):
    """Project からたどれない部品を消す（native_prproj の gc と同じ。ただし埋め込みのデータの中の参照はたどらない）。"""
    start = [e for e in pj.root if e.tag == "Project" and "ObjectID" in e.attrib]
    seen = reachable(pj, start)
    blobs_before = dict(pj.blobs)
    # root の子を作り直す（1つずつ remove すると部品が多い時に遅い。並びは元のまま）
    kept = [e for e in pj.root if key(e) is None or key(e) in seen]
    removed = len(pj.root) - len(kept)
    pj.root[:] = kept
    # 中身（BinaryHash）を持っていた部品を消した場合は、残った参照側に中身を書き込む
    defined = {e.attrib["BinaryHash"] for e in pj.root.iter() if e.attrib.get("BinaryHash") and (e.text or "").strip()}
    for e in pj.root.iter():
        h = e.attrib.get("BinaryHash")
        if h and h not in defined and not (e.text or "").strip() and h in blobs_before:
            e.text = blobs_before[h]
            defined.add(h)
    pj._index()
    return removed


def keep_samples(pj, seq, index):
    """目次の見本（D 以外）のクリップを探す。見つからない見本があれば止める。"""
    keep, missing = set(), []
    for s in index["samples"]:
        if s["id"].startswith("D"):
            continue
        try:
            it = pj.item_at(seq, s["source"]["track"], s["start"], tol=0.02)
        except KeyError:
            it = None
        if it is None:
            missing.append(s["id"])
        else:
            keep.add(key(it))
    if missing:
        raise SystemExit(f"見本のクリップが見つかりません: {missing}")
    return keep


def drop_other_items(pj, seq, keep):
    """見本以外のクリップをトラックから外す。外したクリップを指すリンクも外す。"""
    dropped = set()
    for _, tr in pj.tracks(seq):
        for path in ("ClipTrack/ClipItems/TrackItems", "ClipTrack/TransitionItems/TrackItems"):
            lst = tr.find(path)
            if lst is None:
                continue
            for r in list(lst.findall("TrackItem")):
                it = pj.ref(r)
                if it is None or key(it) not in keep:
                    if it is not None:
                        dropped.add(key(it))
                    lst.remove(r)
            for i, r in enumerate(lst.findall("TrackItem")):     # Premiere の保存と同じく 0..n-1 に振り直す
                r.set("Index", str(i))
    links = seq.find("PersistentGroupContainer/LinkContainer/Links")
    if links is not None:
        for l in list(links):
            if any(key(t) in dropped for t in (pj.ref(e) for e in l.iter()) if t is not None):
                links.remove(l)
    return len(dropped)


def master_points_to(pj, master, uid, depth=4):
    """MasterClip から数段たどって、シーケンス（uid）に行き着くか（シーケンス自身のプロジェクトパネルの項目か）"""
    frontier, seen = [master], set()
    for _ in range(depth):
        nxt = []
        for o in frontier:
            for t in refs_of(pj, o):
                if key(t) == uid:
                    return True
                if key(t) not in seen:
                    seen.add(key(t))
                    nxt.append(t)
        frontier = nxt
    return False


def prune_project_panel(pj, seq):
    """残した見本から参照されないプロジェクトパネルの項目と、空になったビンを外す。"""
    used = reachable(pj, [seq])
    seq_uid = seq.attrib.get("ObjectUID")
    drop = set()
    for pi in pj.root.findall("ClipProjectItem"):
        m = pj.ref(pi.find("MasterClip"))
        if m is None:
            continue
        if key(m) in used or master_points_to(pj, m, seq_uid):
            continue
        drop.add(key(pi))
    # 空になったビンは、外に向かって何度か繰り返して外す
    containers = [pj.root.find("RootProjectItem")] + pj.root.findall("BinProjectItem")
    while True:
        changed = False
        for c in containers:
            items = c.find("ProjectItemContainer/Items")
            if items is None:
                continue
            for it in list(items.findall("Item")):
                if it.attrib.get("ObjectURef") in drop:
                    items.remove(it)
                    changed = True
            for i, it in enumerate(items.findall("Item")):
                it.set("Index", str(i))
        for b in pj.root.findall("BinProjectItem"):
            items = b.find("ProjectItemContainer/Items")
            if key(b) not in drop and (items is None or not items.findall("Item")):
                drop.add(key(b))
                changed = True
        if not changed:
            break
    return len([d for d in drop])


def relink_to_materials(pj, out_dir):
    """素材/ に同じ名前のファイルがある素材は、そちらを指す（絶対パスと、部品集から見た相対パス）。"""
    by_name = {}
    for d in MATERIAL_DIRS:
        if os.path.isdir(d):
            for f in os.listdir(d):
                by_name.setdefault(nfc(f), os.path.join(d, f))
    done, left = [], []
    for m in pj.root.findall("Media"):
        p = nfc(m.findtext("ActualMediaFilePath") or m.findtext("FilePath"))
        if not p.startswith("/") and ":\\" not in p:
            continue        # 調整レイヤー・グラフィックなど、ファイルの無いもの
        name = os.path.basename(p.replace("\\", "/"))
        new = by_name.get(name)
        if new is None:
            # Premiere が付けた連番（キーン（ポイント）_002.wav など）は、中身が同じ時だけ元の名前のファイルを指す
            base = by_name.get(re.sub(r"_\d{3}(\.[^.]+)$", r"\1", name))
            if base and os.path.exists(p) and same_file(p, base):
                new = base
        if new is None:
            left.append(p)
            continue
        point_media(m, new, out_dir)
        done.append(name)
    return done, left


def point_media(m, path, out_dir):
    """素材（Media）が path を指すようにする（絶対パスと、プロジェクトの置き場から見た相対パス）。"""
    for tag in ("ActualMediaFilePath", "FilePath"):
        e = m.find(tag)
        if e is not None:
            e.text = path
    rels = m.findall("RelativePath")
    if rels:
        rels[0].text = os.path.relpath(path, out_dir)
    t = m.find("CCFileModTime")
    if t is not None and os.path.exists(path):
        t.text = str(int(os.path.getmtime(path)) * 1_000_000)     # Premiere と同じく秒で切り捨て


def file_media(pj):
    """ファイルを指す素材（Media）と、そのパス。調整レイヤー・グラフィックなどファイルの無いものは除く。"""
    for m in pj.root.findall("Media"):
        p = nfc(m.findtext("ActualMediaFilePath") or m.findtext("FilePath"))
        if p.startswith("/") or ":\\" in p:
            yield m, p


def same_path(a, b):
    """同じファイルか（濁点の分かれた綴り・大文字小文字・リンク越しも同じとみなす）"""
    a, b = os.path.expanduser(a), os.path.expanduser(b)
    if os.path.exists(a) and os.path.exists(b):
        return os.path.samefile(a, b)
    norm = lambda p: unicodedata.normalize("NFC", os.path.realpath(p)).casefold()
    return norm(a) == norm(b)


def inside_root(path):
    """path（まだ無くてよい）の置き場が video_edit_rules そのものかその中か（リンクは解く。濁点・大文字小文字の違いも同じとみなす）"""
    norm = lambda p: unicodedata.normalize("NFC", p).casefold()
    d, r = norm(os.path.realpath(os.path.dirname(os.path.abspath(path)))), norm(os.path.realpath(ROOT))
    return d == r or d.startswith(r + os.sep)


def save_stable(pj, path):
    """Prproj.save と同じ中身を、gzip の時刻を 0 にして書く（作り直しても中身が同じならファイルも同じ＝git に差が出ない）"""
    import gzip
    import xml.etree.ElementTree as ET
    xml = '<?xml version="1.0" encoding="UTF-8" ?>\n' + ET.tostring(pj.root, encoding="unicode")
    with open(path, "wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as f:
        f.write(xml.encode("utf-8"))


def check_indexes(pj):
    """トラックのクリップ一覧の Index が 0..n-1 か（Premiere が保存したファイルは必ずそう）。違う一覧の数を返す"""
    bad = 0
    for lst in pj.root.iter("TrackItems"):
        idx = [r.attrib.get("Index") for r in lst.findall("TrackItem")]
        if idx != [str(i) for i in range(len(idx))]:
            bad += 1
    return bad


def case_copy(parts, out):
    """部品集を案件の置き場へコピーし、素材/ を指す素材を、この Mac の video_edit_rules/素材/ に向け直す。
    （ユーザー名が違う Mac でも、案件のフォルダからでも見つかるように。video_edit_rules の中は書き換えない）
    素材が欠けている・素材/ の外を指す素材がある時は、ファイルを書く前に止める。"""
    parts, out = os.path.expanduser(parts), os.path.expanduser(out)
    if os.path.exists(out):
        raise SystemExit(f"上書きしません（版ごとにフォルダを分ける）: {out}")
    if same_path(out, LIBRARY) or inside_root(out):
        raise SystemExit(f"video_edit_rules の中には作りません。案件フォルダの絶対パスで渡す"
                         f"（例 ~/Desktop/みかみ案件依頼書/<案件>/edit/v001/<案件>_v001.prproj）: {out}")
    if not os.path.exists(parts):
        raise SystemExit(f"部品集がありません: {parts}（python3 tools/build_parts.py で作る）")
    try:
        made_from = json.load(open(sidecar(parts), encoding="utf-8"))["fingerprint"]
    except (OSError, ValueError, KeyError, TypeError):
        raise SystemExit(f"部品集の元の記録がありません・読めません: {sidecar(parts)}（python3 tools/build_parts.py で作り直す）")
    if made_from != fingerprint(LIBRARY):
        raise SystemExit("部品集が見本集・目次・型の分類より古い（見本集に型を足した後、作り直していない）。"
                         "python3 tools/build_parts.py で作り直してから使う（iMac では Air で作り直して反映する）")
    pj = Prproj.load(parts)
    out_dir = os.path.dirname(os.path.realpath(os.path.abspath(out)))     # リンク（work など）は解いた実際の置き場から相対パスを作る
    mark = "/video_edit_rules/素材/"
    done, missing, outside = 0, [], []
    for m, p in file_media(pj):
        if mark not in p:
            outside.append(p)
            continue
        new = os.path.join(ROOT, "素材", p.split(mark, 1)[1])
        if not os.path.exists(new):
            missing.append(new)
        point_media(m, new, out_dir)
        done += 1
    if missing or outside:
        print(json.dumps({"missing": missing, "outside_materials": outside}, ensure_ascii=False, indent=1))
        raise SystemExit("素材/ に無いファイル（missing）か、素材/ の外を指す素材（outside_materials）があります。何も書いていません")
    info = pj.check_binaries()
    if any(info.values()):
        raise SystemExit(f"共有バイナリの決まりに違反しています: {info}")
    os.makedirs(out_dir, exist_ok=True)
    save_stable(pj, out)
    print(json.dumps({"parts": parts, "out": out, "relinked": done}, ensure_ascii=False, indent=1))


def build(library, out):
    library, out = os.path.expanduser(library), os.path.expanduser(out)
    if any(same_path(out, p) for p in (library, LIBRARY, INDEX, TYPES)) or not out.lower().endswith(".prproj"):
        raise SystemExit("見本集・目次・型の分類を上書きしません。--out は別の .prproj にしてください")
    pj = Prproj.load(library)
    index = json.load(open(INDEX, encoding="utf-8"))
    seq = pj.sequence(index["sequence"])
    keep = keep_samples(pj, seq, index)
    n_items = drop_other_items(pj, seq, keep)
    n_panel = prune_project_panel(pj, seq)
    n_gc = gc(pj)
    done, left = relink_to_materials(pj, os.path.dirname(os.path.realpath(os.path.abspath(out))))
    if left:
        print(json.dumps({"outside_materials": left}, ensure_ascii=False, indent=1))
        raise SystemExit("素材/ に無い素材が残りました（上の一覧を 素材/ に足すか、見本から外す）。何も書いていません")
    info = pj.check_binaries()
    if any(info.values()):
        raise SystemExit(f"共有バイナリの決まりに違反しています: {info}")
    if check_indexes(pj):
        raise SystemExit(f"トラックのクリップ一覧の Index が 0..n-1 になっていない一覧が {check_indexes(pj)} 本あります")
    save_stable(pj, out)
    seqs = sorted({s.findtext("Name") for s in pj.root.findall("Sequence")})
    rec = {"library": library, "out": out, "samples": len(keep), "dropped_clips": n_items,
           "dropped_panel_items": n_panel, "gc_removed": n_gc, "sequences": seqs,
           "relinked_to_materials": len(done), "other_media": left,
           "size_before": os.path.getsize(library), "size_after": os.path.getsize(out)}
    json.dump({"made_with": "tools/build_parts.py", "fingerprint": fingerprint(library), "samples": len(keep)},
              open(sidecar(out), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(rec, ensure_ascii=False, indent=1))
    return rec


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--library", default=LIBRARY, help="元の見本集（既定 見本/テロップ見本集.prproj。ほかを渡すのは試しだけ："
                    "--case-copy は既定の見本集と比べるので、ほかから作った部品集は「古い」で止まる）")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--case-copy", metavar="案件の.prproj", help="部品集（--parts）を案件の置き場へコピーし、素材をこの Mac の 素材/ に向け直す")
    ap.add_argument("--parts", default=OUT, help="--case-copy の元（既定 見本/テロップ部品集.prproj）")
    a = ap.parse_args()
    if a.case_copy:
        case_copy(a.parts, a.case_copy)
        return
    build(a.library, a.out)


if __name__ == "__main__":
    main()
