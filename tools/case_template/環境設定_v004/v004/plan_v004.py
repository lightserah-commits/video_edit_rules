"""環境設定について v001 の判定：カメラと画面（07）、溜め、装飾（01〜06。図解 09 は工程6）。字幕は台本（script_v004.txt）の ID（区切りの番号、途中からは「番号+n」）で指す。
astra の Air 版 v006 の plan を写し、中身（字幕ごとの判定）は塊ごとの判定のファイル plan_parts/dNN_<表>.txt から読むようにした
（2026-10-02。装飾係が塊ごとに 01_判断フロー.md を上から読んで書いた。表の書き方は下の各表の説明と同じ）。
音量（04 の bgm.balance）：声の大きさを測ってから決める（今は astra と同じ 声 +3dB・BGM と SE -9dB）。
ズームはカメラの所だけ・みかみさんの字幕だけ（04 の zoom。make_v004.py が画面・聞き手の字幕のズームを外して記録する）。
"""
import glob
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PARTS = os.path.join(HERE, "plan_parts")

STYLE = {"P01": ("T147", "強調赤黄"), "P02": ("T184", "ゴージャス金"), "P03": ("T175", "ゴージャス青"),
         "P04": ("T010", "シュールテロップ"), "P05": ("T020", "ヒラギノ白シャドウ"), "P06": ("T086", "ツッコミ"),
         "P07": ("T023", "白テキ"), "P08": ("T153", "基本テロップ赤"), "P14": ("T147", "強調赤黄")}
SE = {"ピピ": "S001", "cursor": "S002", "キーン": "S003", "キランッ": "S004", "ピピ7": "S005", "キッ": "S006",
      "しゃん": "S008", "クリック": "S009", "決定": "S010", "ドスッ": "S011", "ポカン": "S012", "ドン": "S013",
      "シャーン": "S014", "ピラリーン": "S015", "グキッ": "S016", "シャラーン": "S017", "ドドン": "S018",
      "ピコンッ": "S019", "キラ": "S020", "カカッ": "S021", "キキッ": "S022", "ピアノ": "S023", "チーン": "S024", "キラーー": "S025"}
VOICE_GAIN_DB = 3.0
BGM_GAIN_DB = -9.0
SE_OFFSET_DB = -9.0
TITLE_SCALE = 0.7
TITLE_DISSOLVE_SEC = 0.5
SERIES = "AI時代の環境設定"
FRAME_SE = "S009"          # 画面の赤枠の音（クリック、小さめ）
FRAME_SE_OFFSET_DB = -4.0
FACE = (0.578, 0.343)      # カメラの中の顔の位置（画像の比。analysis/face/ の16枚を Mac の顔検出で測った中央値 1110×370px）
FACE_TARGET = (0.55, 0.40)  # 寄った時に顔を置く位置


def part(name):
    """plan_parts/dNN_<name>.txt を塊の順につなげた表（無ければ空）"""
    out = []
    for f in sorted(glob.glob(os.path.join(PARTS, f"d*_{name}.txt"))):
        out.append(open(f, encoding="utf-8").read())
    return "\n".join(out)


# 溜め：オチ・ツッコミ・短い反応の前は、間を 0.35秒残す（08 の pauses.keep_as_tame）。字幕ID を1行に1つ
TAME = [x.split("|")[0].strip() for x in part("TAME").splitlines() if x.strip() and not x.startswith("#")]
# 溜めの秒（TAME の2列目が数の時だけ。無ければ cuts_plan の TAME_HEAD＝0.35秒）
TAME_SEC = {}
for _x in part("TAME").splitlines():
    _p = _x.split("|")
    if len(_p) >= 2 and _x.strip() and not _x.startswith("#"):
        try:
            TAME_SEC[_p[0].strip()] = float(_p[1])
        except ValueError:
            pass

# 画面を映す字幕の範囲：最初の字幕|最後の字幕|左上の札（07 の demo_label）|理由（07 の to_screen のどれか）
SCREEN = [tuple((r.split("|") + ["", "", "", ""])[:4]) for r in part("SCREEN").splitlines() if r.strip() and not r.startswith("#")]


def screen_caption_ids(order):
    """SCREEN の範囲を、字幕の並び order（ID の一覧）で広げた集合"""
    pos = {k: i for i, k in enumerate(order)}
    out = set()
    for a, b, *_ in SCREEN:
        for k in order[pos[a]:pos[b] + 1]:
            out.add(k)
    return out


def screen_labels(order):
    """字幕ID → 左上の札の文言"""
    pos = {k: i for i, k in enumerate(order)}
    out = {}
    for a, b, lab, _ in SCREEN:
        for k in order[pos[a]:pos[b] + 1]:
            out[k] = lab
    return out


# 冒頭のハイライト（台本の h）。v001 は別に作る（P15。astra v007 の作り方）ので空
HIGHLIGHT = ""
# 強調：字幕|パターン|SE|ズーム|BGM|種類（意味／感情）|文（必須）|理由|まとめる最後の字幕
EMPHASIS = part("EMPHASIS")
# SE だけ（通常字幕のまま）：字幕|SE|理由
SE_ONLY = part("SE_ONLY")
# 章の入り（P10）：番号を言った字幕|項目名の字幕|終わりの字幕|番号見出し（T015 の2段。+で区切る）|項目名（T093）|理由
CHAPTERS = part("CHAPTERS")
# ボード：開始の字幕|終わりの字幕|型|見出し（+で区切る）|本文（\r で改行）|SE|理由|文字の大きさの倍率
BOARDS = part("BOARDS")
# 並べる座布団・問い（P11）：種類|項目（字幕のID:文字 を ; で区切る）|この字幕の終わりで全部消す|SE|理由
PLATES = part("PLATES")
# 図解（09）：型|見出しを出す字幕:見出し|項目（字幕のID:文字 を ; で区切る）|この字幕の終わりで全部消す|理由
DIAGRAMS = part("DIAGRAMS")
# 代弁（P16 アホなふり）：セリフ（字幕のID:文字:帯 を ; で区切る）|理由
ROLEPLAY = part("ROLEPLAY")
# 右上の話題タイトル（2段目）：切り替わる字幕|文言（11文字くらいまで）
TOPICS = part("TOPICS")
# 説明（01 の手順3。※の補足・↑の一言）：字幕|文言|型（T132＝※注釈 V9）|SE|理由
NOTES = part("NOTES")
# v004 G5：三上さんが AI に話しかけて頼んでいる区間（字幕を T200 白い座布団に黒い文字・※AI指示中 が点滅）：最初の字幕|最後の字幕|理由
AITALK = part("AITALK")


def ai_talk():
    return [{"from": a, "to": b, "reason": w} for a, b, w in rows(AITALK, 3)]


def rows(block, n):
    out = []
    for line in block.strip().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("|")
        parts += [""] * (n - len(parts))
        out.append(parts[:n])
    return out


def emphasis():
    """種類（意味／感情）と文は必須（make_v004.py が tools/kyocho_check.require_texts で確かめる。字幕の文字で埋めない）"""
    out = []
    for idx, p, se, zoom, bgm, kind, text, why, until in rows(EMPHASIS, 9):
        out.append({"id": idx, "pattern": p, "type": STYLE[p][0], "style": STYLE[p][1], "se": SE[se] if se else "",
                    "zoom": zoom, "bgm_stop": bgm == "停止", "kind": kind, "text_fix": text, "reason": why, "until": until or idx})
    return out


def highlight():
    return [{"id": i, "pattern": p, "type": STYLE[p][0], "se": SE[s] if s else "", "zoom": z, "kind": k, "text_fix": t,
             "until": u or i} for i, p, s, z, k, t, u in rows(HIGHLIGHT, 7)]


def se_only():
    return [{"id": i, "se": SE[s], "reason": w} for i, s, w in rows(SE_ONLY, 3)]


def chapters():
    return [{"num_id": a, "item_id": b, "end": c, "head": h.split("+"), "item": t, "reason": w} for a, b, c, h, t, w in rows(CHAPTERS, 6)]


def boards():
    return [{"from": a, "to": b, "type": t, "head": h.split("+"), "body": body.replace("\\r", "\r"), "se": SE[s], "reason": w,
             "scale": float(k) if k else None} for a, b, t, h, body, s, w, k in rows(BOARDS, 8)]


def plates():
    out = []
    for kind, items, end, se, why in rows(PLATES, 5):
        its = [tuple(x.split(":", 1)) for x in items.split(";")]
        out.append({"kind": kind, "items": its, "end": end, "se": SE[se] if se else "", "reason": why})
    return out


def notes():
    return [{"id": i, "text": t.replace("\\r", "\r"), "type": ty or "T132", "se": SE[se] if se else "", "reason": w} for i, t, ty, se, w in rows(NOTES, 5)]


def roleplay():
    out = []
    for line in ROLEPLAY.strip().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        lines, why = line.rsplit("|", 1)
        ls = [tuple(x.rsplit(":", 1)[0].split(":", 1)) + (x.rsplit(":", 1)[1],) for x in lines.split(";")]
        out.append({"lines": ls, "reason": why})
    return out


def diagrams():
    out = []
    for kind, head, items, end, why in rows(DIAGRAMS, 5):
        hid, htext = head.split(":", 1)
        its = [tuple(x.split(":", 1)) for x in items.split(";")]
        out.append({"kind": kind, "head_id": hid, "head": htext, "items": its, "end": end, "reason": why})
    return out


def topics():
    return [(i, t) for i, t in rows(TOPICS, 2)]


def line_breaks():
    """2行にする時の改行（06）：強調の文の半角の間（真ん中に近い所）で改行する"""
    out = {}
    names = ["Claude Code", "Sonnet 5.5", "Opus 5.5", "Fable 5.1", "6.1 Sol", "Hermes Agent", "GPT-6 Astra", "Google ドライブ", "Google カレンダー",
             "Google Japan", "Dev Day", "Google Drive"]
    for e in emphasis() + highlight():
        t = e["text_fix"]
        inner = set()                                   # 名前の中の空白（「Claude Code」など）では改行しない
        for nm in names:
            k0 = t.find(nm)
            while k0 >= 0:
                inner |= {k0 + j for j, ch in enumerate(nm) if ch == " "}
                k0 = t.find(nm, k0 + 1)
        sp = [k for k, ch in enumerate(t) if ch == " " and k not in inner]
        if sp:
            k = min(sp, key=lambda x: abs(x - len(t) / 2))
            out[e["id"]] = t[:k] + "\r" + t[k + 1:]
    return out


def zoom_value(z):
    """寄り120 → (1.20 倍, 位置 x, y)。寄りは顔（FACE）が FACE_TARGET に来る位置、引きは真ん中（04 の zoom）"""
    if not z:
        return None
    n = float("".join(ch for ch in z if ch.isdigit() or ch == "."))
    s = n / 100
    if s <= 1:
        return n, 0.5, 0.5
    x = FACE_TARGET[0] - (FACE[0] - 0.5) * s
    y = FACE_TARGET[1] - (FACE[1] - 0.5) * s
    x = min(max(x, 1 - s / 2), s / 2)          # 画面の端が出ないように
    y = min(max(y, 1 - s / 2), s / 2)
    return n, round(x, 4), round(y, 4)
