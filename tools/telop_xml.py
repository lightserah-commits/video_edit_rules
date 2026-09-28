#!/usr/bin/env python3
"""Premiere本来のテロップ（エッセンシャルグラフィックスの文字）を、Final Cut Pro 7 XMLで作るツール（試作）。

仕組み:
  Premiereから書き出した見本XMLには、テロップの書式ごとの文字データ（ソーステキスト＝FlatBuffer）が入っている。
  見本クリップを複製し、その中の文字列だけを新しい文字に付け替える。書体・色・縁・影・位置は見本のまま。
  文字列は「ラン」（書式が同じ文字のまとまり）ごとに入っている。1つのクリップに文字レイヤーが複数ある場合もある。

使い方:
  python3 telop_xml.py list  --templates 見本.xml
  python3 telop_xml.py build --templates 見本.xml --spec spec.json --out out.xml

spec.json の形:
  {"sequence_name": "テロップ差し替えテスト", "clip_frames": 150,
   "items": [
     {"style": "S19", "text": "通常テロップの文字"},              ← 文字レイヤー1つ・ラン1つのスタイル
     {"style": "S21", "layers": [["ポイント"], ["本文の文字"]]},   ← レイヤーごとに、ランごとの文字を指定
     {"style": "S11", "text": "原文のまま", "keep": true}           ← 差し替えない（比較用）
   ]}
  改行は "\\r"（Premiereの改行コード）。"\\n" を書いた場合も "\\r" に変換する。
"""
import argparse
import base64
import copy
import json
import re
import struct
import sys
import xml.etree.ElementTree as ET

HEADER = 12  # 先頭12バイト: [0:4]=残りの長さ, [4:8]=0, [8:12]=目印。FlatBuffer本体は12バイト目から

# 1行の文字数の上限（完成版 みかみCH0726 の実測：通常字幕は95%が19字以内・最大20〜24字、強調は最大15字、ボード本文は最大22字）
# 試作では、通常字幕の書式で18字は画面に収まり、30字ははみ出した。
MAX_LINE_CHARS = {"S19": 20, "S09": 20, "S08": 20, "S04": 18, "S11": 15, "S05": 15, "S12": 15, "S07": 15, "S06": 15,
                  "S03": 19, "S13": 20, "S14": 20, "S21": 22, "S17": 20}
DEFAULT_MAX_LINE_CHARS = 20


def u32(b, p):
    return struct.unpack_from("<I", b, p)[0]


def i32(b, p):
    return struct.unpack_from("<i", b, p)[0]


def u16(b, p):
    return struct.unpack_from("<H", b, p)[0]


def fields(b, pos):
    vt = pos - i32(b, pos)
    n = (u16(b, vt) - 4) // 2
    return {i: pos + u16(b, vt + 4 + 2 * i) for i in range(n) if u16(b, vt + 4 + 2 * i)}


def deref(b, p):
    return p + u32(b, p)


def read_string(b, p):
    return b[p + 4:p + 4 + u32(b, p)].decode("utf-8")


def text_runs(blob):
    """文字データから、ランごとの (文字列, 文字列への参照がある位置) を返す。"""
    env = HEADER + u32(blob, HEADER)
    doc = deref(blob, fields(blob, env)[0])
    runs_vec = deref(blob, fields(blob, doc)[0])
    out = []
    for i in range(u32(blob, runs_vec)):
        run = deref(blob, runs_vec + 4 + 4 * i)
        ref_at = fields(blob, run)[0]
        out.append((read_string(blob, deref(blob, ref_at)), ref_at))
    return out


def fonts_of(blob):
    env = HEADER + u32(blob, HEADER)
    doc = deref(blob, fields(blob, env)[0])
    f = fields(blob, doc)
    if 1 not in f:
        return []
    vec = deref(blob, f[1])
    return [read_string(blob, deref(blob, vec + 4 + 4 * i)) for i in range(u32(blob, vec))]


def replace_runs(blob, new_texts):
    """各ランの文字列を付け替えた新しい文字データを返す。

    新しい文字列はデータの末尾に足し、ランからの参照（前方向の相対位置）だけを書き換える。
    古い文字列は参照されないまま残る（FlatBufferとしては問題ない）。
    """
    runs = text_runs(blob)
    if len(new_texts) != len(runs):
        raise ValueError(f"ランの数が合いません（見本 {len(runs)}、指定 {len(new_texts)}）: {[r[0] for r in runs]}")
    out = bytearray(blob)
    for (old, ref_at), new in zip(runs, new_texts):
        while len(out) % 4:
            out.append(0)
        data = new.encode("utf-8")
        pos = len(out)
        out += struct.pack("<I", len(data)) + data + b"\x00"
        struct.pack_into("<I", out, ref_at, pos - ref_at)
    while len(out) % 4:
        out.append(0)
    struct.pack_into("<I", out, 0, len(out) - HEADER)
    return bytes(out)


def normalize_text(s):
    return s.replace("\r\n", "\r").replace("\n", "\r")


def text_effects(clipitem):
    """クリップ内の文字レイヤー（GraphicAndType）の effect 要素を順に返す。"""
    res = []
    for f in clipitem.findall("filter"):
        e = f.find("effect")
        if e is not None and e.findtext("effectid") == "GraphicAndType":
            res.append(e)
    return res


def param(effect, pid):
    for p in effect.findall("parameter"):
        if p.findtext("parameterid") == str(pid):
            return p
    return None


def set_value(p, value):
    v = p.find("value")
    v.text = value


def load_templates(path):
    tree = ET.parse(path)
    templates = {}
    for c in tree.getroot().iter("clipitem"):
        m = re.match(r"(S\d{2})\b", c.findtext("name") or "")
        if m and text_effects(c) and m.group(1) not in templates:
            templates[m.group(1)] = c
    return tree, templates


def describe(clipitem):
    layers = []
    for e in text_effects(clipitem):
        blob = base64.b64decode(param(e, 1).findtext("value"))
        layers.append({"runs": [r[0] for r in text_runs(blob)], "fonts": fonts_of(blob)})
    return layers


def make_telop(template, layers_texts, idx, start, end):
    """見本クリップを複製し、文字を差し替えたクリップを返す。"""
    c = copy.deepcopy(template)
    effects = text_effects(c)
    if len(layers_texts) != len(effects):
        raise ValueError(f"文字レイヤーの数が合いません（見本 {len(effects)}、指定 {len(layers_texts)}）")
    for e, texts in zip(effects, layers_texts):
        texts = [normalize_text(t) for t in texts]
        p = param(e, 1)
        blob = base64.b64decode(p.findtext("value"))
        new_blob = replace_runs(blob, texts)
        if [r[0] for r in text_runs(new_blob)] != texts:
            raise AssertionError("差し替え後の読み戻しが一致しません")
        set_value(p, base64.b64encode(new_blob).decode("ascii"))
        e.find("name").text = "".join(texts)
        for pid in (13, 14):  # 編集時の文字選択位置。新しい文字では解除する
            sp = param(e, pid)
            if sp is not None:
                parts = sp.findtext("value").split(",")
                parts[1] = "-1."
                set_value(sp, ",".join(parts))
    label = " / ".join("".join(t) for t in layers_texts).replace("\r", " ")
    c.set("id", f"clipitem-telop-{idx}")
    c.find("name").text = label[:60]
    length = end - start
    c.find("start").text = str(start)
    c.find("end").text = str(end)
    f = c.find("file")
    if f is not None:
        f.set("id", f"file-telop-{idx}")
    return c


def build(templates_path, spec, out_path):
    tree, templates = load_templates(templates_path)
    root = tree.getroot()
    seq = root.find("sequence")
    video = seq.find("media/video")
    tracks = video.findall("track")
    telop_track = tracks[-1]
    for c in list(telop_track.findall("clipitem")):
        telop_track.remove(c)
    frames = int(spec.get("clip_frames", 150))
    t = 0
    report = []
    for i, item in enumerate(spec["items"], 1):
        tpl = templates[item["style"]]
        if item.get("keep"):
            layers = [[r for r in l["runs"]] for l in describe(tpl)]
        elif "layers" in item:
            layers = item["layers"]
        else:
            layers = [[item["text"]]]
        limit = MAX_LINE_CHARS.get(item["style"], DEFAULT_MAX_LINE_CHARS)
        for layer in layers:
            for line in normalize_text("".join(layer)).split("\r"):
                n = len(line.replace(" ", "").replace("\u3000", ""))
                if n > limit:
                    print(f"警告: {i}本目（{item['style']}）の1行が{n}字で上限{limit}字を超えています。改行してください: {line}", file=sys.stderr)
        clip = make_telop(tpl, layers, i, t, t + frames)
        telop_track.append(clip)
        report.append({"no": i, "style": item["style"], "start_frame": t, "layers": describe(clip), "keep": bool(item.get("keep"))})
        t += frames
    # 背景（下のトラック）を全体の長さに合わせる
    for tr in tracks[:-1]:
        for c in tr.findall("clipitem"):
            c.find("end").text = str(t)
            if c.find("in") is not None and c.find("out") is not None:
                c.find("out").text = str(int(c.findtext("in")) + t)
    seq.find("duration").text = str(t)
    if spec.get("sequence_name"):
        seq.find("name").text = spec["sequence_name"]
    tree.write(out_path, encoding="utf-8", xml_declaration=True)
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("list")
    a.add_argument("--templates", required=True)
    b = sub.add_parser("build")
    b.add_argument("--templates", required=True)
    b.add_argument("--spec", required=True)
    b.add_argument("--out", required=True)
    args = ap.parse_args()
    if args.cmd == "list":
        _, templates = load_templates(args.templates)
        for sid, c in sorted(templates.items()):
            print(sid, c.findtext("name"), json.dumps(describe(c), ensure_ascii=False))
        return
    spec = json.load(open(args.spec, encoding="utf-8"))
    report = build(args.templates, spec, args.out)
    for r in report:
        print(json.dumps(r, ensure_ascii=False))


if __name__ == "__main__":
    main()
