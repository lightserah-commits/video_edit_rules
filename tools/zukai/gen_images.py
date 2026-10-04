#!/usr/bin/env python3
"""画像を出す所（I01…。02 の画像：話す人が「これ」と特定の物を指す時）の page.html と diagram.json を、字幕の時刻から作る（どの案件でも使える道具）。
黒い板・ワイプなしの透明の動画にする（build が V16 に置く）。元：環境設定 v004 の zukai/gen_images.py（中身の I01〜I14 は案件の例 examples/）。
  - 写真（photo）：白い縁 14px・角丸・影（02 の画像：真ん中・白い縁・画面の6割ぐらい）。ポンと出る（pop）。label で下に名前、credit で左下に出典
  - ロゴ（card）：白いカードにロゴと名前。左から流れてくる（slideL）・右から（slide）
  - 文字（text）・矢印（arrow）・赤い×（cross）
  - 部品の出るコマは、その言葉の字幕の頭（S("字幕ID") − 図解の頭）。消えるのは次の字幕の頭など（省くと最後まで）
  - 出る時の SE：写真は「ピコンッ」、カードは「cursor」（make が manifest の se_events を鳴らす）

  python3 tools/zukai/gen_images.py --ver <edit/vNNN> [--spec <図解のフォルダ>/images_spec.py] [I01 …]
    → <図解のフォルダ>/I??/page.html・diagram.json（そのあと python3 tools/zukai/make_zukai.py --ver … I??）
  images_spec.py（案件ごと。既定 <図解のフォルダ>/images_spec.py）は、下の道具をそのまま使える Python：
    s0 = S("161"); r = lambda c: S(c) - s0
    spec("I01", "スパイク", "161", S("172"), [photo("p1", "img_spike_side.jpg", 510, 110, 900, 600, 0, r("162")), …],
         [(0, "ピコンッ"), (r("162"), "ピコンッ")], "161「…」横の写真 → 162「…」裏の写真")
  使える名前：S(字幕ID)・E(字幕ID)（字幕の頭・終わりのコマ）・spec・photo・card・text・arrow・cross・tl・ZUKAI（図解のフォルダ）・OUT・json
  画像は <図解のフォルダ>/assets/ に置き、名前だけ書く（ページからは ../assets/名前）。例：examples/images_spec_example.py
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from case import Case, add_args  # noqa: E402
from tl import TL, ts  # noqa: E402

A = "../assets/"
CSS = """
  .ph { position: relative; background: #fff; border: 14px solid #fff; border-radius: 14px; box-shadow: 0 14px 40px rgba(0,0,0,.6); overflow: hidden; box-sizing: border-box; }
  .ph img { display: block; width: 100%; height: 100%; object-fit: cover; }
  .ph.contain img { object-fit: contain; background: #fff; }
  .card { display: flex; align-items: center; gap: 24px; background: #fff; border: 5px solid #000; border-radius: 26px; padding: 16px 40px 16px 22px;
          box-shadow: 0 8px 22px rgba(0,0,0,.45); box-sizing: border-box; }
  .card .logo { height: 120px; width: auto; max-width: 420px; display: block; flex: none; }
  .card .nm { font-family: Lbl; font-size: 80px; line-height: 1.0; color: #111; white-space: nowrap; padding-bottom: 4px; }
  .card .sub { font-family: Lbl; font-size: 38px; line-height: 1.1; color: #1b5fd1; white-space: nowrap; }
  .credit { font-family: 'Hiragino Sans'; font-weight: 600; font-size: 22px; color: #fff; text-shadow: 0 0 4px #000, 0 0 2px #000; white-space: nowrap; }
"""


def photo(pid, src, x, y, w, h, f0, f1=None, label=None, contain=False, filt=None, credit=None, m="pop", objpos=None):
    """写真。objpos：細い枠で切る時に残す側（例 "15% 50%"）。filt：CSS の filter"""
    st = f"left:{x}px;top:{y}px"
    f1a = f' data-f1="{f1}"' if f1 is not None else ""
    css = ([f"filter:{filt}"] if filt else []) + ([f"object-position:{objpos}"] if objpos else [])
    img_style = f' style="{";".join(css)}"' if css else ""
    html = (f'<div class="part" id="{pid}" data-f0="{f0}"{f1a} data-m="{m}" style="{st}"><div class="in">'
            f'<div class="ph{" contain" if contain else ""}" style="width:{w}px;height:{h}px"><img src="{A}{src}"{img_style}></div></div></div>\n')
    js = ""
    if label:
        html += (f'<div class="part" id="{pid}L" data-f0="{f0}"{f1a} data-m="{m}" style="left:{x + w // 2}px;top:{y + h + 10}px">'
                 f'<div class="in"><div id="{pid}Lt" style="position:relative;display:inline-block;transform:translateX(-50%)"></div></div></div>\n')
        js += f"document.getElementById('{pid}Lt').innerHTML = Z.stk({json.dumps(label, ensure_ascii=False)}, {{size: 58}});\n"
    if credit:
        html += (f'<div class="part" id="{pid}C" data-f0="{f0}"{f1a} data-m="{m}" style="left:{x + 18}px;top:{y + h - 44}px">'
                 f'<div class="in credit">{credit}</div></div>\n')
    return html, js


def card(pid, logo, name, x, y, f0, f1=None, sub=None, m="slideL", logo_h=120):
    f1a = f' data-f1="{f1}"' if f1 is not None else ""
    nm = f'<div><div class="nm">{name}</div>' + (f'<div class="sub">{sub}</div>' if sub else "") + "</div>" if name else ""
    return (f'<div class="part" id="{pid}" data-f0="{f0}"{f1a} data-m="{m}" style="left:{x}px;top:{y}px"><div class="in">'
            f'<div class="card"><img class="logo" style="height:{logo_h}px" src="{A}{logo}">{nm}</div></div></div>\n'), ""


def text(pid, s, x, y, f0, f1=None, size=120, fill="#f5e63a", m="pop", font="Tsk"):
    """叩きつける一言（x・y は字の真ん中）。Tsk の「＋」は星の形に見えるので、記号は font="Hv" に"""
    f1a = f' data-f1="{f1}"' if f1 is not None else ""
    return (f'<div class="part" id="{pid}" data-f0="{f0}"{f1a} data-m="{m}" style="left:{x}px;top:{y}px"><div class="in"><div id="{pid}t" style="position:relative;display:inline-block;transform:translate(-50%,-50%)"></div></div></div>\n',
            f"document.getElementById('{pid}t').innerHTML = Z.stk({json.dumps(s, ensure_ascii=False)}, {{size: {size}, fill: '{fill}', font: '{font}', strokes: [['#000', 18]]}});\n")


def arrow(pid, x, y, length, f0, f1=None):
    f1a = f' data-f1="{f1}"' if f1 is not None else ""
    return (f'<div class="part" id="{pid}" data-f0="{f0}"{f1a} data-m="grow" style="left:{x}px;top:{y}px"><div class="in" id="{pid}a"></div></div>\n',
            f"document.getElementById('{pid}a').innerHTML = Z.arrow({{len: {length}, dir: 'right', color: '#f5e63a'}});\n")


def cross(pid, x, y, size, f0, f1=None):
    f1a = f' data-f1="{f1}"' if f1 is not None else ""
    svg = (f'<svg width="{size}" height="{size}" viewBox="0 0 100 100"><path d="M14 14 L86 86 M86 14 L14 86" stroke="#000" stroke-width="22" stroke-linecap="round"/>'
           f'<path d="M14 14 L86 86 M86 14 L14 86" stroke="#ff1e1e" stroke-width="14" stroke-linecap="round"/></svg>')
    return f'<div class="part" id="{pid}" data-f0="{f0}"{f1a} data-m="pop" style="left:{x}px;top:{y}px"><div class="in">{svg}</div></div>\n', ""


SPECS = {}


def spec(key, title, anchor, end_f, parts, se, story):
    SPECS[key] = dict(title=title, anchor=anchor, end_f=end_f, parts=parts, se=se, story=story)


def write(zdir, tl, key):
    sp = SPECS[key]
    s0 = tl.caps[sp["anchor"]]["s"]
    n = sp["end_f"] - s0
    d = zdir / key
    d.mkdir(parents=True, exist_ok=True)
    html, js = "", ""
    for h, j in sp["parts"]:
        html += h
        js += j
    page = (f'<!doctype html><html><head><meta charset="utf-8">\n<!-- {key} {sp["title"]}。tools/zukai/gen_images.py が作った（手で直さない。images_spec.py を直す） -->\n'
            f'<link rel="stylesheet" href="../lib/zukai.css"><script src="../lib/zukai.js"></script>\n<style>{CSS}</style>\n</head><body>\n'
            f'{html}<script>\nwindow.ZUKAI = {{ frames: {n} }};\n{js}</script></body></html>\n')
    (d / "page.html").write_text(page, encoding="utf-8")
    dj = {"key": key, "title": sp["title"], "start_f": s0, "end_f": sp["end_f"], "anchor": {"cap": sp["anchor"], "f": s0},
          "wipe": {"show": False}, "se": [{"f": f, "se": s, "why": "画像が出る"} for f, s in sp["se"]], "hide_caption_ids": [],
          "removes": "", "checks": [5, max(6, n // 2), n - 5], "story": sp["story"]}
    (d / "diagram.json").write_text(json.dumps(dj, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{key}: {ts(s0)}〜{ts(sp['end_f'])}（{n}コマ）{sp['title']}")


def main():
    ap = argparse.ArgumentParser(description="画像を出す所の page.html と diagram.json を作る", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    add_args(ap)
    ap.add_argument("--spec", help="案件の images_spec.py（既定 <図解のフォルダ>/images_spec.py）")
    ap.add_argument("keys", nargs="*", help="作るもの（省くと spec の全部）")
    a = ap.parse_args()
    K = Case(a)
    K.ensure_lib()
    tl = TL.of(K)
    path = Path(a.spec) if a.spec else K.zukai / "images_spec.py"
    if not path.exists():
        raise SystemExit(f"{path} が無い（tools/zukai/examples/images_spec_example.py を見て書く）")
    env = {"S": lambda c: tl.caps[c]["s"], "E": lambda c: tl.caps[c]["e"], "spec": spec, "photo": photo, "card": card, "text": text,
           "arrow": arrow, "cross": cross, "tl": tl, "ZUKAI": K.zukai, "OUT": K.out, "json": json, "__file__": str(path)}
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), env)
    for k in a.keys or sorted(SPECS):
        write(K.zukai, tl, k)


if __name__ == "__main__":
    main()
