#!/usr/bin/env python3
"""Premiere のプロジェクト（.prproj）の中の、このMacに無いフォント名を、ある フォント名に置き換える。
開くたびに出る「フォントを解決（解決不能：デフォルトフォントに置き換えられます）」の画面を出さないため（2026-09-26 ユーザー指示）。

  テロップの文字データ（FlatBuffer）の中の文字列を、構造を読まずに置き換える：
    - 文字列は「4バイトの長さ＋中身＋\\0」で入っている。長さが一致する所だけを文字列とみなす
    - 新しい名前が同じか短い：その場で書き換え（長さを直し、余りは 0 で埋める）
    - 新しい名前が長い：末尾に新しい文字列を足し、元の文字列を指していた相対位置（4バイト境界）をすべて付け替える
  共有バイナリ（BinaryHash）は、中身を持つ所だけを書き換える（番号はそのままなので、同じ番号を指す所も同じ中身になる）。

使い方:
  python3 tools/font_fix.py 入力.prproj 出力.prproj        … 既定の置き換え表で置き換えて保存（入力と同じパスは不可）
  python3 tools/font_fix.py --scan 入力.prproj             … 無いフォント名がどこに何か所あるかだけ数える
"""
import argparse
import base64
import gzip
import re
import struct
import sys

# 無いフォント → 代わり（このMacにあるもの）
TABLE = {
    "HiraKakuStdN-W8": "HiraginoSans-W8",                    # ヒラギノ角ゴ StdN W8 → ヒラギノ角ゴシック W8（同じデザイン）
    "Corporate-Logo-Rounded-Bold-ver3": "HiraMaruProN-W4",   # コーポレート・ロゴ丸 → ヒラギノ丸ゴ ProN W4（丸い書体で一番近い）
    "YuGothic-Bold": "HiraginoSans-W6",                      # 游ゴシック Bold（Windows）→ ヒラギノ角ゴシック W6
}
HEADER = 12
B64 = re.compile(r"^[A-Za-z0-9+/=\s]{40,}$")


def find_strings(buf, name):
    """buf の中の、長さつき文字列 name の開始位置（長さの4バイトの位置）"""
    nb = name.encode("utf-8")
    out = []
    i = buf.find(nb)
    while i >= 0:
        p = i - 4
        if p >= 0 and struct.unpack_from("<I", buf, p)[0] == len(nb) and (i + len(nb) >= len(buf) or buf[i + len(nb)] == 0):
            out.append(p)
        i = buf.find(nb, i + 1)
    return out


def replace_in_blob(raw, table):
    buf = bytearray(raw)
    count = {}
    for old, new in table.items():
        for p in find_strings(buf, old):
            ob, nbytes = old.encode("utf-8"), new.encode("utf-8")
            if len(nbytes) <= len(ob):
                struct.pack_into("<I", buf, p, len(nbytes))
                buf[p + 4:p + 4 + len(ob) + 1] = nbytes + b"\x00" * (len(ob) - len(nbytes) + 1)
            else:
                refs = [q for q in range(0, len(buf) - 3, 4) if q != p and q + struct.unpack_from("<I", buf, q)[0] == p]
                if not refs:
                    continue                                     # 指している所が見つからないものは触らない
                while len(buf) % 4:
                    buf.append(0)
                pos = len(buf)
                buf += struct.pack("<I", len(nbytes)) + nbytes + b"\x00"
                while len(buf) % 4:
                    buf.append(0)
                for q in refs:
                    struct.pack_into("<I", buf, q, pos - q)
                struct.pack_into("<I", buf, 0, len(buf) - HEADER)
            count[old] = count.get(old, 0) + 1
    return bytes(buf), count


def process(data, table, scan=False):
    """data（.prproj の中身の XML 文字列）の中の base64 の中身を置き換える。(新しい XML, 数) を返す"""
    total = {}
    names = [n.encode("utf-8") for n in table]

    def repl(m):
        head, body, tail = m.group(1), m.group(2), m.group(3)
        if not B64.match(body):
            return m.group(0)
        try:
            raw = base64.b64decode(body)
        except Exception:
            return m.group(0)
        if not any(n in raw for n in names):
            return m.group(0)
        new, c = replace_in_blob(raw, table)
        for k, v in c.items():
            total[k] = total.get(k, 0) + v
        if scan or new == raw:
            return m.group(0)
        return head + base64.b64encode(new).decode("ascii") + tail

    out = re.sub(r"(<StartKeyframeValue[^>]*>)([^<]+)(</StartKeyframeValue>)", repl, data)
    out = re.sub(r"(<Value[^>]*>)([^<]{40,})(</Value>)", repl, out)
    plain = {n: out.count(n) for n in table if n in out}      # base64 でない所に残っている名前
    return out, total, plain


def load(path):
    b = open(path, "rb").read()
    return (gzip.decompress(b) if b[:2] == b"\x1f\x8b" else b).decode("utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src")
    ap.add_argument("out", nargs="?")
    ap.add_argument("--scan", action="store_true")
    a = ap.parse_args()
    data = load(a.src)
    new, total, plain = process(data, TABLE, scan=a.scan)
    if a.scan or not a.out:
        print({"found_in_blobs": total, "found_in_plain_text": plain})
        return
    if a.out == a.src:
        sys.exit("入力と同じパスには書かない（元を残す）")
    with gzip.open(a.out, "wb") as f:
        f.write(new.encode("utf-8"))
    left = process(new, TABLE, scan=True)
    print({"replaced": total, "left_in_blobs": left[1], "left_in_plain_text": left[2]})


if __name__ == "__main__":
    main()
