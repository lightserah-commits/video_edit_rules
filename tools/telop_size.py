#!/usr/bin/env python3
"""テロップの大きさを、06_テロップの大きさ.yaml の決まりで自動で決める。

  1. テロップの文字を、実際のフォント（このMacに入っているもの）で測る
  2. スタイルの「基本の大きさ」で置く。一番長い行が「短い一言の文字数」以下なら倍率を掛ける（上限まで）
  3. 横幅が画面の上限（90%）を超えるなら、収まるまで小さくする
  4. 文字の大きさだけを書き換える（縁取りの太さ・位置はそのまま。行間は文字の大きさに合わせて自動）

大きさ ＝ 文字の大きさ（px）× テロップ全体の拡大率（ベクトルモーション・モーション・トランスフォーム・文字レイヤーのスケール）。

使い方（Pythonから）:
  from telop_size import auto_size
  info = auto_size(pj, item, ["強調赤黄"])            # pj は native_prproj.Prproj、item は置いたテロップ
  info = auto_size(pj, item, ["シュールテロップ"], pattern="P16")   # 再現シーン

使い方（コマンドラインから。フォントが見つかるかと、文字の幅の確認）:
  python3 telop_size.py fonts
  python3 telop_size.py measure Ruika-09 160 "全然違う"
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from native_prproj import run_styles  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
RULES_PATH = os.path.join(HERE, "..", "06_テロップの大きさ.yaml")
FONT_DIRS = [
    os.path.expanduser("~/Library/Application Support/Adobe/CoreSync/plugins/livetype"),   # Adobe Fonts（隠しフォルダ）
    os.path.expanduser("~/Library/Fonts"),
    "/Library/Fonts",
    "/System/Library/Fonts",
]
# このMacに無いフォントの代わり（見本集でも同じ置き換えをしている）
FONT_SUBSTITUTE = {"HiraKakuStdN-W8": "HiraginoSans-W8"}
SPACES = " 　\t"


# ---------- 決まり（06_テロップの大きさ.yaml の common と by_style だけを読む） ----------
def load_rules(path=RULES_PATH):
    common, by_style, section = {}, {}, None
    with open(path, encoding="utf-8") as f:
        for line in f:
            s = line.split("#", 1)[0].rstrip()
            if not s.strip():
                continue
            if not line[0].isspace():
                section = s.split(":", 1)[0].strip()
                continue
            if section == "common":
                k, v = s.strip().split(":", 1)
                common[k.strip()] = float(v)
            elif section == "by_style":
                k, v = s.strip().split(":", 1)
                v = v.strip()
                if not (v.startswith("{") and v.endswith("}")):
                    raise ValueError(f"06_テロップの大きさ.yaml の by_style の書き方が違います: {line.strip()}")
                row = {}
                for part in v[1:-1].split(","):
                    kk, vv = part.split(":", 1)
                    try:
                        row[kk.strip()] = float(vv)
                    except ValueError:
                        row[kk.strip()] = vv.strip()     # 例: 改行: 字幕
                by_style[k.strip()] = row
    for key in ("横幅の上限", "画面の幅", "短い一言の文字数", "2行にする縮み"):
        if key not in common:
            raise ValueError(f"06_テロップの大きさ.yaml の common に {key} がありません")
    return {"common": common, "by_style": by_style}


def rule_for(rules, styles, pattern=None):
    """スタイル名（複数あれば順に）とパターンから、使う行を選ぶ。無ければ None"""
    for st in styles:
        if pattern and f"{st}/{pattern}" in rules["by_style"]:
            return f"{st}/{pattern}", rules["by_style"][f"{st}/{pattern}"]
        if st in rules["by_style"]:
            return st, rules["by_style"][st]
    return None, None


# ---------- フォント（ファイルの中の PostScript 名で探す） ----------
def _ps_names(path):
    """フォントファイル（.otf/.ttf/.ttc）に入っている (PostScript名, 番号) の一覧"""
    out = []
    with open(path, "rb") as f:
        head = f.read(12)
        if len(head) < 12:
            return out
        offsets = [0]
        if head[:4] == b"ttcf":
            n = struct.unpack(">I", head[8:12])[0]
            offsets = list(struct.unpack(f">{n}I", f.read(4 * n)))
        for idx, off in enumerate(offsets):
            f.seek(off)
            sfnt = f.read(12)
            if len(sfnt) < 12:
                continue
            num = struct.unpack(">H", sfnt[4:6])[0]
            recs = f.read(16 * num)
            name_off = None
            for i in range(num):
                tag, _, o, _ = struct.unpack(">4sIII", recs[16 * i:16 * i + 16])
                if tag == b"name":
                    name_off = o
            if name_off is None:
                continue
            f.seek(name_off)
            _, count, str_off = struct.unpack(">HHH", f.read(6))
            records = f.read(12 * count)
            found = None
            for i in range(count):
                pid, eid, _, nid, length, o = struct.unpack(">HHHHHH", records[12 * i:12 * i + 12])
                if nid != 6:
                    continue
                f.seek(name_off + str_off + o)
                raw = f.read(length)
                try:
                    found = raw.decode("utf-16-be") if pid in (0, 3) else raw.decode("mac_roman")
                except UnicodeDecodeError:
                    continue
                if pid in (0, 3):
                    break
            if found:
                out.append((found.strip("\x00"), idx))
    return out


class Fonts:
    def __init__(self, dirs=FONT_DIRS):
        self.index, self._pil = {}, {}
        for d in dirs:
            for root, _, files in os.walk(d):
                for fn in files:
                    if fn.lower().endswith((".otf", ".ttf", ".ttc")):
                        p = os.path.join(root, fn)
                        try:
                            for name, idx in _ps_names(p):
                                self.index.setdefault(name, (p, idx))
                        except (OSError, struct.error):
                            pass

    def find(self, psname):
        name = psname if psname in self.index else FONT_SUBSTITUTE.get(psname, psname)
        return self.index.get(name)

    def width(self, psname, size, text):
        """text を psname・size（px）で書いたときの横幅（px）。フォントが無ければ None"""
        from PIL import ImageFont
        loc = self.find(psname)
        if loc is None:
            return None
        if loc not in self._pil:
            self._pil[loc] = ImageFont.truetype(loc[0], 100, index=loc[1])
        return self._pil[loc].getlength(text) * size / 100


# ---------- テロップを測る ----------
def _param_values(pj, ce):
    """部品のパラメーター名 → 値（キーフレームがあれば最後の値＝止まったときの値）"""
    vals = {}
    for p in ce.findall("Component/Params/Param"):
        pe = pj.ref(p)
        if pe is None:
            continue
        name = (pe.findtext("Name") or "").strip()
        kfs = [k for k in (pe.findtext("Keyframes") or "").strip().split(";") if k]
        sk = pe.findtext("StartKeyframe") or ""
        v = kfs[-1].split(",")[1] if kfs else (sk.split(",")[1] if "," in sk else sk)
        vals.setdefault(name, v)
    return vals


def _num(v, default=100.0):
    try:
        return float(str(v).split(":")[0])
    except ValueError:
        return default


def horizontal_scale(pj, item):
    """テロップ全体の横方向の拡大率（1.0 = 等倍）"""
    hs = 1.0
    chain = pj.ref(item.find("ClipTrackItem/ComponentOwner/Components"))
    if chain is None:
        return hs
    for c in chain.findall("ComponentChain/Components/Component"):
        ce = pj.ref(c)
        if ce is None:
            continue
        mn, v = ce.findtext("MatchName"), None
        if mn in ("AE.ADBE Graphic Group", "AE.ADBE Motion"):
            v = _param_values(pj, ce)
            hs *= _num(v.get("スケール")) / 100 * _num(v.get("スケール (幅)")) / 100
        elif mn == "AE.ADBE Geometry2":
            v = _param_values(pj, ce)
            hs *= _num(v.get("スケール (幅)", v.get("スケール"))) / 100
        elif mn == "AE.ADBE Text":
            v = _param_values(pj, ce)
            hs *= _num(v.get("スケール")) / 100 * _num(v.get("水平比率")) / 100
    return hs


def measure(pj, item, fonts):
    """今の文字の大きさでの、行ごとの横幅（px、拡大率込み）と文字数。大きさ（一番大きいラン × 拡大率）も返す"""
    hs = horizontal_scale(pj, item)
    lines, size, missing, no_size = [], 0.0, set(), False
    for _, raw in pj.text_blobs(item):
        cur = [[0.0, 0]]
        for r in run_styles(raw):
            if r["size"]:
                size = max(size, r["size"])
            else:
                no_size = True   # 文字の大きさの値が入っていない（既定値のまま）。この形は書き換えられない
            for k, part in enumerate(r["text"].replace("\r\n", "\r").replace("\n", "\r").split("\r")):
                if k > 0:
                    cur.append([0.0, 0])
                if not part:
                    continue
                w = fonts.width(r["font"], r["size"] or 0, part)
                if w is None:
                    missing.add(r["font"])
                    w = 0.0
                cur[-1][0] += w
                cur[-1][1] += len(part.strip(SPACES))
        lines += [(w * hs, n) for w, n in cur if n]
    return {"lines": lines, "size": size * hs, "scale": hs, "missing_fonts": sorted(f for f in missing if f), "no_size": no_size}


def auto_size(pj, item, styles, pattern=None, rules=None, fonts=None):
    """06_テロップの大きさ.yaml の決まりで文字の大きさを書き換える。決まりの無いスタイルは変えない。
    戻り値: 何をしたか（大きさ・横幅・注意）"""
    rules = rules or load_rules()
    fonts = fonts or Fonts()
    key, rule = rule_for(rules, styles, pattern)
    m = measure(pj, item, fonts)
    cm = rules["common"]
    screen = cm["画面の幅"]
    info = {"rule": key, "size_before": round(m["size"], 1), "notes": []}
    if m["no_size"]:
        info["notes"].append("文字の大きさの値が入っていない見本（既定の大きさのまま）なので、大きさは変えない")
        return info
    if m["missing_fonts"]:
        info["notes"].append(f"フォントが見つからないので測れない: {', '.join(m['missing_fonts'])}")
    if not m["lines"] or m["size"] <= 0:
        info["notes"].append("文字が無い")
        return info
    width = max(w for w, _ in m["lines"])
    chars = max(n for _, n in m["lines"])
    info["chars_longest_line"] = chars
    info["lines"] = len(m["lines"])
    if rule is None or m["missing_fonts"]:
        info["size_after"] = info["size_before"]
        info["width_pct"] = round(width / screen * 100, 1)
        if width > screen:
            info["notes"].append(f"横幅が画面を超えている（{info['width_pct']}%）")
        return info
    target = rule["基本"] * (rule["短い一言の倍率"] if chars <= cm["短い一言の文字数"] else 1.0)
    target = min(target, rule.get("上限", target))
    limit = cm["横幅の上限"] * screen
    if width * target / m["size"] > limit:
        target = limit * m["size"] / width
    pj.scale_font_sizes(item, target / m["size"])
    info["size_after"] = round(target, 1)
    info["width_pct"] = round(width * target / m["size"] / screen * 100, 1)
    # 1行か2行か: 1行のまま横幅の上限に収めると、基本の大きさの何倍まで縮むか（縮み）で決める
    if rule.get("改行") != "字幕":
        joined = sum(w for w, _ in m["lines"]) * rule["基本"] / m["size"]     # 1行につなげて基本の大きさで置いた幅
        shrink = min(1.0, limit / joined)
        info["shrink_one_line"] = round(shrink, 2)
        th = cm["2行にする縮み"]
        if len(m["lines"]) == 1 and shrink < th:
            info["notes"].append(f"1行のままだと基本の大きさの{shrink:.0%}まで縮む（{th:.0%}未満）。2行にする（改行の位置は文節で）")
        elif len(m["lines"]) >= 2 and shrink >= th:
            info["notes"].append(f"1行にまとめても基本の大きさの{shrink:.0%}で収まる（{th:.0%}以上）。1行にする")
    return info


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "fonts":
        f = Fonts()
        for name in ["Ruika-09", "WanpakuRuika-08", "ReggaeOne-Regular", "HiraMinProN-W6", "HiraKakuStdN-W8",
                     "HiraginoSans-W8", "NotoSerifJP-Black", "PA1GothicStd-Bold", "SourceHanSans-Heavy"]:
            print(f"{name:22} → {f.find(name)}")
        return
    if len(sys.argv) == 5 and sys.argv[1] == "measure":
        f = Fonts()
        w = f.width(sys.argv[2], float(sys.argv[3]), sys.argv[4])
        print(f"{w:.1f}px（画面の{w / 1920 * 100:.1f}%）" if w is not None else "フォントが見つかりません")
        return
    print(__doc__)


if __name__ == "__main__":
    main()
