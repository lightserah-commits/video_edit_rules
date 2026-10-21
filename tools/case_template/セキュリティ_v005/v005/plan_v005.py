"""セキュリティについて v005 の判定（2026-10-16。AI動画編集 v005 の雛形を写した。カメラ1本・画面なし＝SCREEN は空・Loom の範囲は無い）。以下は元の説明：AI動画編集 v005 の判定（2026-10-16。1015claude project開設 v005 の plan を写した。画面＝Loom の間は全部画面〔カメラが無い〕・寄りの顔の位置は素材ごとに顔検出〔make の refit〕）。以下は元の説明：1015claude project開設 v005 の判定（1003 AIで稼ぐ系 v005 の plan を写した。表の中身は plan_parts/ から読む）。1003 では v005 の判定（v005 の plan を写して、v005 の直しの表を足した）。もとは環境設定について v005 の判定：カメラと画面（07）、溜め、装飾（01〜06。図解 09 は工程6）。字幕は台本（script_v005.txt）の ID（区切りの番号、途中からは「番号+n」）で指す。
astra の Air 版 v006 の plan を写し、中身（字幕ごとの判定）は塊ごとの判定のファイル plan_parts/dNN_<表>.txt から読むようにした
（2026-10-02。装飾係が塊ごとに 01_判断フロー.md を上から読んで書いた。表の書き方は下の各表の説明と同じ）。
音量（04 の bgm.balance）：声の大きさを測ってから決める（今は astra と同じ 声 +3dB・BGM と SE -9dB）。
ズームはカメラの所だけ・みかみさんの字幕だけ（04 の zoom。make_v005.py が画面・聞き手の字幕のズームを外して記録する）。
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
VOICE_FILE = os.path.join(os.path.dirname(HERE), "media", "camera_voice_comp_v004.wav")   # v005 Q3（小川さん「声が小さくて SE が大きい」→ リミッター OK）：素材の声に +17dB・コンプレッサー（-18dB・3:1）・リミッター（-2dB）を掛けた作業用の声（ffmpeg。素材全体 -25.4 LUFS・ピーク -2.5 dBFS）。A1・A2 はこれを置く
VOICE_GAIN_DB = -1.0  # v005 測った結果：0.0 では本編 -22.0 LUFS・真のピーク 0.0 dBFS（2:59.8 の笑いが AAC で +0.02）。-1dB で完成版の約 -23 LUFS・ピーク約 -1 に。   # v005：+17dB は VOICE_FILE に入っている（完成版は声の素材 -40 LUFS に +17.02dB で約 -23 LUFS）。以下は v003 までの説明：  # v005 確かめ係2回目 B1：本編が -32.7 LUFS で冒頭ハイライト（-25.1）より 7.6 LU 小さかった。素材の声のピークが -9.5 dBFS（+3dB で書き出しのピーク -3.5）なので、割れない所（-1 dBFS）まで +2.5dB 上げ、BGM・SE も同じだけ上げて差を保つ（04 の balance）
BGM_GAIN_DB = -1.0   # v005：声と同じだけ下げて差を保つ。    # v005：声が完成版と同じ大きさになったので、BGM も完成版と同じ 0dB（04 の bgm.balance。差 約19 LU）。v003 は -6.5
SE_OFFSET_DB = -1.0  # v005：声と同じだけ下げて差を保つ。   # v005：SE も完成版の gain_db のまま（03 の volume）。v003 は -6.5
TITLE_SCALE = 0.7
TITLE_DISSOLVE_SEC = 0.5
SERIES = "AI時代のセキュリティ"   # 右上1段目のシリーズ名（AI が決めた仮。3-1 で決め直す。7-1 で確かめる）
FRAME_SE = "S009"          # 画面の赤枠の音（クリック、小さめ）
FRAME_SE_OFFSET_DB = -4.0
FACE = (0.567, 0.27)       # カメラの中の顔の位置（画像の比）の既定（セキュリティについて：18:00 のコマで見た三上さんの顔）。AI動画編集では make_v005.py の refit が寄りごとにその時のコマの顔を検出して置き直す（三上さん〔1314・1315〕とこういちさん〔1317〕で位置が違う）
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


import json as _json
_A = os.path.join(os.path.dirname(HERE), "analysis")
_SYNC = _json.load(open(os.path.join(_A, "sync", "sync.json")))
_UNITS = {u["u"]: u for u in _json.load(open(os.path.join(_A, "units.json")))} if os.path.exists(os.path.join(_A, "units.json")) else {}
LOOM_START = _SYNC.get("N_SCREEN", -1) * 1001 / 30000            # 通しのカメラの秒（Loom の頭）。セキュリティについては画面が無いので -1（当たらない）
LOOM_END = _SYNC.get("screen_end_frame", -1) * 1001 / 30000       # Loom の終わり


def in_loom(cid):
    u = _UNITS.get(int(str(cid).split("+")[0]))
    return u is not None and LOOM_START <= u["start"] < LOOM_END


def screen_caption_ids(order):
    """AI動画編集：Loom の間の字幕は全部画面（カメラが無い）。ほかに SCREEN の範囲があれば足す"""
    pos = {k: i for i, k in enumerate(order)}
    out = {k for k in order if in_loom(k)}
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


# 冒頭のハイライト（台本の h）。v005 は別に作る（P15。astra v007 の作り方）ので空
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
# v005 G5：三上さんが AI に話しかけて頼んでいる区間（字幕を T200 白い座布団に黒い文字・※AI指示中 が点滅）：最初の字幕|最後の字幕|理由
AITALK = part("AITALK")


# v005：聞き手の字幕などにかける寄り（強調にしない所。2026-10-05 小川さん「三上さんもうちょっとスケールして」）：字幕|ズーム|理由
ZOOM = part("ZOOM")


def zoom_only():
    return [{"id": i, "zoom": z, "reason": w} for i, z, w in rows(ZOOM, 3)]


def ai_talk():
    return [{"from": a, "to": b, "reason": w} for a, b, w in rows(AITALK, 3)]


def rows(block, n):
    out = []
    for line in block.strip().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("  #", 1)[0].rstrip().split("|")   # 2026-10-21：行の後ろの注記（「  # …」）を外す（1018 v002・v003 は右上の話題タイトルに注記が文字で出ていた）
        parts += [""] * (n - len(parts))
        out.append(parts[:n])
    return out


def emphasis():
    """種類（意味／感情）と文は必須（make_v005.py が tools/kyocho_check.require_texts で確かめる。字幕の文字で埋めない）"""
    out = []
    for idx, p, se, zoom, bgm, kind, text, why, until in rows(EMPHASIS, 9):
        out.append({"id": idx, "pattern": p, "type": STYLE[p][0], "style": STYLE[p][1], "se": SE[se] if se else "",
                    "zoom": zoom, "bgm_stop": bgm == "停止", "kind": kind, "text_fix": text, "reason": why, "until": until or idx})
    return out


def highlight():
    return [{"id": i, "pattern": p, "type": STYLE[p][0], "se": SE[s] if s else "", "zoom": z, "kind": k, "text_fix": t,
             "until": u or i} for i, p, s, z, k, t, u in rows(HIGHLIGHT, 7)]


def se_only():
    """v005：字幕の列に「ID@言葉」と書くと、その字幕の中のその言葉の聞こえ始め（文字起こしの語の時刻）で鳴らす"""
    out = []
    for i, s, w in rows(SE_ONLY, 3):
        key, _, word = i.partition("@")
        out.append({"id": key, "word": word, "se": SE[s], "reason": w})
    return out


def chapters():
    return [{"num_id": a, "item_id": b, "end": c, "head": h.split("+"), "item": t, "reason": w} for a, b, c, h, t, w in rows(CHAPTERS, 6)]


def boards():
    return [{"from": a, "to": b, "type": t, "head": h.split("+"), "body": body.replace("\\r", "\r"), "se": SE[s], "reason": w,
             "scale": float(k) if k else None} for a, b, t, h, body, s, w, k in rows(BOARDS, 8)]


def plates():
    """v005：種類「両立」は2つの札を横に並べる（2026-10-05 小川さん G5）。項目の字幕を「ID@言葉」と書くと、その言葉の聞こえ始めで出す。
    締めの音は「この字幕の終わりで消す」の後に「|SE|理由」の SE の列とは別に、SE_ONLY の「ID@言葉」で鳴らす"""
    out = []
    for kind, items, end, se, why in rows(PLATES, 5):
        its, words = [], {}
        for x in items.split(";"):
            k, t = x.split(":", 1)
            key, _, word = k.partition("@")
            its.append((key, t))
            if word:
                words[key] = word
        out.append({"kind": kind, "items": its, "words": words, "end": end, "se": SE[se] if se else "", "reason": why})
    return out


def notes():
    """v005：6列目に上下のずらし（px。負で上へ）を書ける（強調の大きな文字の裏に隠れる※を上へ逃がす時）"""
    return [{"id": i, "text": t.replace("\\r", "\r"), "type": ty or "T132", "se": SE[se] if se else "", "reason": w, "dy": float(dy) if dy.strip() else 0.0}
            for i, t, ty, se, w, dy in rows(NOTES, 6)]


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
             "Google Japan", "Dev Day", "Google Drive", "Premiere Pro", "AI 自動編集", "XML ファイル"]
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


def zoom_value_face(n, face):
    """寄り n% を、その時のコマの顔の位置 face（画像の比）に合わせて置く（AI動画編集。make_v005.py の refit）"""
    s = n / 100
    if s <= 1:
        return n, 0.5, 0.5
    x = FACE_TARGET[0] - (face[0] - 0.5) * s
    y = FACE_TARGET[1] - (face[1] - 0.5) * s
    x = min(max(x, 1 - s / 2), s / 2)
    y = min(max(y, 1 - s / 2), s / 2)
    return n, round(x, 4), round(y, 4)


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
IMAGES = part("IMAGES")   # AI動画編集：装飾係が書く画像の候補（字幕ID@言葉|何の画像か|部分か全体か|出どころ|理由）。作るのはメインの AI（zukai/images_spec.py）
