"""tools/premiere_case/ の共通（Premiere の MCP Bridge へ送る前の準備）。どの案件でも使える。
- Premiere に送るのは run() を呼んだ時だけ（--help や --dry では Premiere に触らない）
- ExtendScript に入れる文字（パス・名前）は JSON の文字列にして埋め込む（引用符・日本語・空白をそのまま扱う）
"""
import hashlib
import json
import os
import sys

ROOT = os.path.expanduser("~/Desktop/video_edit_rules")
TOOLS = os.path.join(ROOT, "tools")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)


def js_str(s):
    return json.dumps(str(s), ensure_ascii=False)


def script(jsx_name, values):
    """premiere_helpers.jsx ＋ HERE/jsx_name。values の {"__PROJ__": 値} を JSON にして置き換える（文字は js_str、ほかは json.dumps）"""
    body = open(os.path.join(HERE, jsx_name), encoding="utf-8").read()
    for k, v in values.items():
        body = body.replace(k, js_str(v) if isinstance(v, str) else json.dumps(v, ensure_ascii=False))
    left = [w for w in ("__PROJ__", "__SEQ__", "__OUT__", "__JOBS__") if w in body]
    if left:
        raise SystemExit(f"{jsx_name} の {left} が埋まっていない")
    return open(os.path.join(TOOLS, "premiere_helpers.jsx"), encoding="utf-8").read() + "\n" + body


def bridge():
    """premiere_bridge（run・preflight）。使う時だけ読む"""
    import premiere_bridge
    return premiere_bridge


def font_check(proj):
    """開く前に、このMacに無いフォントが0件か（tools/font_fix.py --scan と同じ）。あれば止める（「フォントを解決」の画面を出さない）"""
    import font_fix
    _, blobs, plain = font_fix.process(font_fix.load(proj), font_fix.TABLE, scan=True)
    if blobs or plain:
        raise SystemExit(f"無いフォントがある {blobs} {plain}：python3 tools/font_fix.py で別名のコピーに直してから開く")


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def need_file(path, what="プロジェクト"):
    if not os.path.exists(path):
        raise SystemExit(f"{what}が無い：{path}")
    return os.path.abspath(path)
