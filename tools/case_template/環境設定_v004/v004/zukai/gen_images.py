#!/usr/bin/env python3
"""v004 G3（2026-10-04 小川さん「話す人が『これ！』と特定の物を指す時（ザ・ペン）は画像。結構画像があった方がいい」）：
画像を出す所（I01〜I14）の page.html と diagram.json を、字幕の時刻から作る（黒い板・ワイプなしの透明の動画。build が V16 に置く）。
  - 写真：白い縁 14px・角丸・影（02 の画像：真ん中・白い縁・画面の6割ぐらい）。ポンと出る（pop）
  - ロゴ：白いカードにロゴと名前（L1 と同じ形）。左から流れてくる（slideL）・右から（slide）
  - 部品の出るコマは、その言葉の字幕の頭（tl.caps の s）。消えるのは次の字幕の頭など（ずっとなら最後まで）
  - 出る時の SE：写真は「ピコンッ」、カードは「cursor」（make が manifest の se_events を鳴らす）
  python3 zukai/gen_images.py [I01 ...]   → zukai/I??/page.html・diagram.json（そのあと python3 zukai/make_zukai.py I??）
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tl import TL, ts  # noqa: E402

HERE = Path(__file__).resolve().parent
tl = TL()


def S(cap):
    return tl.caps[cap]["s"]


def E(cap):
    return tl.caps[cap]["e"]


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
    st = f"left:{x}px;top:{y}px"
    f1a = f' data-f1="{f1}"' if f1 is not None else ""
    css = ([f"filter:{filt}"] if filt else []) + ([f"object-position:{objpos}"] if objpos else [])   # objpos：細い枠で切る時に残す側（例 "15% 50%"）
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


def build_specs():
    # I01 スパイク（3:31.8〜3:49.0）。161 横の写真 → 162「ポイントあるやん」裏の写真 → 169 平らな底と並べる → 170 ポイント付き
    s0 = S("161"); r = lambda c: S(c) - s0
    # v004 最後の直し（点検[4][5]）：平らな底は 168「みんなポイントなしで」の頭に前倒し。見比べの2枚は上端・下端をそろえ、
    # 強調「こっちの方が圧倒的に良くない？」（170 の中、3:46.5〜）の上の黒い帯（y0〜130）より下（y150〜670）に収める
    spec("I01", "スパイク（横 → 裏のポイント → 平らな底と見比べ）", "161", S("172"), [
        photo("p1", "img_spike_side.jpg", 510, 110, 900, 600, 0, r("162")),
        photo("p2", "img_spike_sole.jpg", 735, 80, 450, 600, r("162"), r("168"), label="スパイクの裏"),
        photo("p3", "img_flat_sole.jpg", 150, 150, 780, 520, r("168"), label="ポイントなし"),
        # 確かめ役の指摘（2回目）：x1130 だと 3:44〜3:48 に三上さんの右目と顔の右半分が隠れた（右目は x≈1110〜1175、頬の端 x≈1195）。
        # 左の端を x1190 へ戻し、右の端は前と同じ x1520（幅 330。右上タイトル2段目 x≥1548 に影もかけない）。細い分、靴底の鋲が残るよう左寄りで切る
        photo("p4", "img_spike_sole.jpg", 1190, 150, 330, 520, r("170"), label="ポイント付き", objpos="15% 50%"),
    ], [(0, "ピコンッ"), (r("162"), "ピコンッ"), (r("168"), "ピコンッ"), (r("170"), "ピコンッ")],
        "161「サッカーのスパイクってさ」横の写真 → 162「ポイントあるやん」裏の写真をポンと（小川さん「裏ここなんだろう→あれですねの瞬間にポンと裏側の画像」）→ 168「みんなポイントなしで」ポイントなしの平らな底（言葉の頭に前倒し）→ 170「俺だけポイント付きのスパイク」右に裏の写真（2枚とも上端 y150・下端 y670。強調の黒い帯にかけない。右の写真は x1190〜1520：顔の右半分と右上タイトルを避ける）。172 の頭で消す")
    # I02 男は黙って Claude Code／Codex（2:32.5〜2:39.4）
    s0 = S("75"); r = lambda c: S(c) - s0
    spec("I02", "Claude Code と Codex の公式ロゴ", "75", S("78"), [
        card("c1", "logo_claude_symbol.svg", "Claude Code", 60, 222, 0),
        card("c2", "logo_openai_symbol.svg", "Codex", 60, 430, r("76")),
    ], [(0, "cursor"), (r("76"), "cursor")], "75「男は黙ってClaude Code」→ 76「男は黙ってCodex」。L1 と同じ左上のロゴの札。77 の終わりで消す")
    # I03 Cursor VS OpenAI・Anthropic → Addness VS OpenAI（18:39.5〜18:54.7）
    s0 = S("1179"); r = lambda c: S(c) - s0
    spec("I03", "Cursor VS OpenAI・Anthropic → Addness VS OpenAI", "1179", S("1188"), [
        # 顔（画面の右寄り）にかからないよう、左に縦に並べる（上：Cursor → Addness、真ん中：VS、下：OpenAI・Anthropic）
        card("c1", "logo_cursor.svg", "", 60, 170, 0, r("1187"), logo_h=100),
        # v004 最後の直し（点検[9]）：Addness は背景を抜いた公式ロゴ（logo_addness_clear.png）。灰色の箱・斜めの帯が出ない
        card("c4", "logo_addness_clear.png", "", 60, 170, r("1187"), logo_h=80),
        text("vs", "VS", 330, 420, r("1185"), size=150),
        card("c2", "logo_openai_wordmark.svg", "", 60, 510, r("1184"), logo_h=90),
        # 点検[6]：「いつAddness対OpenAIになるか」で Cursor が Addness に替わるコマで ANTHROPIC を消す（絵を「Addness 対 OpenAI」にする）
        card("c3", "logo_anthropic.svg", "", 60, 680, r("1184") + 8, r("1187"), logo_h=60),
    ], [(0, "cursor"), (r("1184"), "cursor"), (r("1185"), "ドン"), (r("1187"), "cursor")],
        "1179「Cursorも使ってる人は少なくなってきた」左に Cursor → 1184「OpenAIとAnthropicのAチーム」右に2つ → 1185「Cursorと殴り合ってる」VS → 1187「いつAddness対OpenAIになるか」左が Addness に替わり、同じコマで ANTHROPIC を消す。1188 の強調の頭で消す")
    # I04 Orca の画面（19:29.3〜図解 Z5 の頭）
    s0 = S("1209")
    z5 = json.load(open(HERE / "out" / "Z5" / "manifest.json", encoding="utf-8"))["tl_start_f"]
    spec("I04", "Orca の画面（1か所で動かせる）", "1209", min(S("1215"), z5), [
        photo("p1", "orca_readme_hero.jpg", 430, 100, 1060, 663, 0, label="Orca"),
    ], [(0, "ピコンッ")], "1209「そういうことをやる人向けに」〜1210「1か所で動かせるようにしますっていうのがOrcaかな」。図解 Z5 の頭で消す")
    # I05 包丁（21:05.8〜21:18.0）。d08_PLATES の文字の札（1259・1261）を並列画像に替えた
    s0 = S("1257"); r = lambda c: S(c) - s0
    spec("I05", "出刃包丁と野菜用の繊細な包丁", "1257", S("1264"), [
        photo("p1", "img_knife_big.jpg", 70, 150, 640, 292, 0, label="すっげえやばい出刃包丁", contain=True, m="slideL"),
        photo("p2", "img_knife_thin.jpg", 70, 560, 640, 143, r("1261"), label="野菜用の繊細なやつ", contain=True, m="slideL"),
    ], [], "1257「すっげえやばい出刃包丁」→ 1261「野菜は すげえ野菜用の繊細なやつで」。1263 の終わりで消す（SE は d08_PLATES の並列画像の cursor）")
    # I06 Obsidian のグラフの画面（22:17.2〜22:22.5）
    spec("I06", "Obsidian のグラフの画面", "1320", S("1323"), [
        # 公式ヘルプの見本のグラフはメモが少なく線が見えなかったので、グラフの見た目を描いた絵（イメージ）にした
        photo("p1", "img_obsidian_graph_illust.svg", 460, 100, 1000, 640, 0, label="Obsidian のグラフ（イメージ）"),
    ], [(0, "ピコンッ")], "1320「Obsidianって いっぱい知識がつながってて」1321「これ俺の脳みそだって言ったら映える」。1323 の強調の頭で消す")
    # I07 このキュウリ（23:41.8〜23:45.6）
    s0 = S("1389")
    spec("I07", "このキュウリはやばいから捨てよ", "1389", S("1391"), [
        # v004 最後の直し（点検[8]）：CSS で色を落とすと焼いたパンに見え、下の縁に赤いにじみが出た → 黄ばんだ緑＋茶色の傷みに描いた絵
        # （img_cucumber_rotten.jpg。白地と影はそのまま）。×は写真の枠の真ん中（右上のタイトルにかけない。点検[1]）
        photo("p1", "img_cucumber_rotten.jpg", 500, 150, 920, 357, 0),
        cross("x1", 835, 203, 250, 42),
    ], [(0, "ピコンッ"), (42, "ドスッ")], "1389「このキュウリはやばいから捨てよ」：傷んだキュウリ（白地の写真を黄ばんだ緑と茶色の傷みにした絵）→「捨てよ」で写真の真ん中に赤い×。1391 の頭で消す")
    # I08 Slack・Gmail → LINE（32:23.0〜32:31.6）
    s0 = S("1649"); r = lambda c: S(c) - s0
    spec("I08", "Slack・Gmail と LINE", "1649", S("1656+1"), [
        card("c1", "logo_slack.svg", "Slack", 60, 222, 0, logo_h=110),
        card("c2", "logo_gmail.svg", "Gmail", 60, 430, 40, logo_h=100),
        card("c3", "logo_line.svg", "LINE", 60, 650, r("1651"), logo_h=110),   # 田中さんと三上さんの2人の画面。顔にかからない左下の机の所
    ], [(0, "cursor"), (40, "cursor"), (r("1651"), "ピコンッ")], "田中さん 1649「今まで Slackとか Gmailぐらいはできた」左に2つ → 1651「LINE多いじゃないですか」右に LINE を大きく。1656+1 の頭で消す")
    # I09 うな重（33:28.5〜33:32.2）
    spec("I09", "うなぎ（うな重）", "1687", E("1687"), [
        photo("p1", "img_unaju.jpg", 70, 80, 420, 560, 0),   # 2人の画面。田中さん（左）の顔にかからない左上
    ], [(0, "ピコンッ")], "田中さん 1687「今まで食べたうなぎじゃないみたいな」")
    # I10 三上さん本人の東大の入学式の写真（28:02.0〜28:10.7）
    spec("I10", "三上さん本人（東京大学 入学式）", "1601", S("1607"), [
        photo("p1", "img_mikami_todai.jpeg", 735, 80, 450, 601, 0),
    ], [(0, "ピコンッ")], "聞き手 1601「当時3ヶ月だけ東大受かるために」〜1606。小川さんがくれた本人の写真。1607 の問いの札の頭で消す")
    # I11 ChatGPT の中の Addness（14:04.2〜14:14.7）
    s0 = S("717"); r = lambda c: S(c) - s0
    spec("I11", "ChatGPT のアプリに Addness", "717", S("733"), [
        card("c1", "logo_openai_symbol.svg", "ChatGPT", 60, 222, 0, sub="のアプリ"),
        # 727 は三上さんがスマホ（ChatGPT で Addness を出した画面）をカメラに見せている → 右には何も置かず、左に縦に並べる
        text("a1", "↓", 270, 420, r("727"), size=110),
        photo("p1", "img_addness_ogp.png", 60, 490, 560, 294, r("727"), m="slideL"),
    ], [(0, "cursor"), (r("727"), "ピコンッ")], "717「（ChatGPTの）プラグインが公式のところになってる」左に ChatGPT → 727「Addnessって調べたら Addnessって出てくる」矢印と Addness（小川さんがくれた画像と同じ公式の画像）")
    # I12 Addness（0:29.8〜0:35.4。聞き手が初めて名前を出す所）
    spec("I12", "Addness", "11", E("12"), [
        photo("p1", "img_addness_ogp.png", 60, 150, 640, 336, 0, m="slideL"),   # 三上さんの顔にかからない左上
    ], [(0, "ピコンッ")], "聞き手 11「よく動画でも Addnessで環境設定するのがいいとか」12「最近Addnessも結構話題に」。問いの札（下）と重ならない上の方")
    # I13 dots ＋ Addness（33:43.4〜33:48.2）
    s0 = S("1739+1"); r = lambda c: S(c) - s0
    spec("I13", "dots と Addness", "1739+1", S("1743"), [
        # v004 最後の直し（点検[0][9][10]）：Addness の札が三上さんの目の高さ（y270〜400）にかかっていた → 顔（x≈900〜1200）にかけず、
        # dots と名札の下の左の列に縦に並べる（dots → ＋ → Addness。列の真ん中 x270）。Addness は背景を抜いた公式ロゴ。
        # dots の名札は、にじみの行と上の縁の青を消して、黒地に「みかみの dot」1行だけで描き直した絵（img_dots_clean.png）
        photo("p1", "img_dots_clean.png", 100, 140, 340, 340, 0, contain=True, label="dots"),
        text("pl", "+", 270, 612, r("1741"), size=110, font="Hv"),   # Tsk の「＋」は星の形に見えた
        card("c1", "logo_addness_clear.png", "", 50, 672, r("1741"), logo_h=76),
    ], [(0, "ピコンッ"), (r("1741"), "cursor")], "1739+1「（OpenAIの）dotsとか いろいろ出てるけど」dots（案件 dots開設 の素材から顔と名札だけ）→ 1741「このAddnessとかとは うまく組み合わされる」左の列の下に ＋ Addness（顔にかけない）")
    # I14 OpenAI → サム・アルトマン（33:51.3〜33:57.5）
    s0 = S("1744"); r = lambda c: S(c) - s0
    spec("I14", "OpenAI とサム・アルトマン", "1744", E("1746"), [
        card("c1", "logo_openai_wordmark.svg", "", 60, 222, 0, logo_h=100),
        photo("p1", "img_sam_altman.jpg", 760, 80, 560, 560, r("1745"), label="サム・アルトマン\nOpenAI の CEO",
              credit="Photo: James Tamim / CC BY 2.0"),
    ], [(0, "cursor"), (r("1745"), "ピコンッ")], "1744「OpenAIがどう出てくるかって めっちゃ読んでる」OpenAI → 1745「サム・アルトマンの次の次の次ぐらい」本人の写真（Wikimedia Commons、CC BY 2.0）")


def write(key):
    sp = SPECS[key]
    s0 = S(sp["anchor"])
    n = sp["end_f"] - s0
    d = HERE / key
    d.mkdir(exist_ok=True)
    html, js = "", ""
    for h, j in sp["parts"]:
        html += h
        js += j
    page = (f'<!doctype html><html><head><meta charset="utf-8">\n<!-- {key}（v004 G3）{sp["title"]}。gen_images.py が作った（手で直さない） -->\n'
            f'<link rel="stylesheet" href="../lib/zukai.css"><script src="../lib/zukai.js"></script>\n<style>{CSS}</style>\n</head><body>\n'
            f'{html}<script>\nwindow.ZUKAI = {{ frames: {n} }};\n{js}</script></body></html>\n')
    (d / "page.html").write_text(page, encoding="utf-8")
    dj = {"key": key, "title": sp["title"], "start_f": s0, "end_f": sp["end_f"], "anchor": {"cap": sp["anchor"], "f": s0},
          "wipe": {"show": False}, "se": [{"f": f, "se": s, "why": "画像が出る"} for f, s in sp["se"]], "hide_caption_ids": [],
          "removes": "", "checks": [5, max(6, n // 2), n - 5], "story": sp["story"]}
    (d / "diagram.json").write_text(json.dumps(dj, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{key}: {ts(s0)}〜{ts(sp['end_f'])}（{n}コマ）{sp['title']}")


if __name__ == "__main__":
    build_specs()
    keys = sys.argv[1:] or sorted(SPECS)
    for k in keys:
        write(k)
