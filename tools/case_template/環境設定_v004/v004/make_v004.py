#!/usr/bin/env python3
"""Air v001 を組み立てる（素材から作る）。ワークの完全解説 v001（~/Desktop/みかみ案件依頼書/0927 claude cowork/edit/v004/make_v004.py）の作り方を、
整理後のルール（02 の output_tracks・P10・P11 の問い、07 の both_tracks・demo_label・wipe）に合わせたもの。

入力  _work/v004_stills.prproj … 見本集のコピーに base_v004.xml を読み込み、オフラインの SE・BGM を 素材/ につなぎ直し、
      赤枠の画像を V4 に置いて保存したもの（_work/place_stills.py）
判定  plan_v004.py（装飾）、_work/captions_v004.json（字幕）、_work/base_v004_map.json（字幕のタイムラインの位置・画面の区間）
出力  kankyo_v004.prproj、v004_記録.json、decoration_plan.csv

トラック（02 の output_tracks。案件で決めた所は 00_案件メモ.md）:
  V1 カメラ（全部）／V2 画面（映す所だけ有効）／V3 代弁の黒帯（E003）／V4 画面の赤枠／V6 通常字幕／V7 強調・代弁のセリフ／
  V8 右上のシリーズ名（カメラの間）・左上の実演の札（画面の間）／V9 右上の話題タイトル・章の番号見出し（T015）／
  V10 ボード（P09・P14）・章の項目名カード（T093）／V11 ワイプ（画面と一緒に有効）／V12〜V14 並べる座布団・聞き手の問い（P11）
  A1・A2 声／A3 BGM／A4 SE
  ~/Desktop/video_edit_rules/env/bin/python v004/make_v004.py
"""
import csv
import json
import os
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
CASE = os.path.dirname(HERE)
ROOT = os.path.expanduser("~/Desktop/video_edit_rules")   # ルールと道具の場所
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, HERE)
from native_prproj import Prproj, TPS  # noqa: E402,F401
from reproduce import Library  # noqa: E402
import telop_size  # noqa: E402
import kyocho_check  # noqa: E402
import plan_v004 as plan  # noqa: E402
from prj_helpers import (add_gain_db, add_motion, break_text, component_param, detach, fix_fonts,  # noqa: E402
                         get_static, set_static)

W = os.path.join(HERE, "_work")
SRC = os.path.join(W, "v004_stills.prproj")
OUT = os.path.join(HERE, "kankyo_v004.prproj")
MAP = json.load(open(os.path.join(W, "base_v004_map.json"), encoding="utf-8"))
CUTS = json.load(open(os.path.join(W, "cuts_v004.json"), encoding="utf-8"))
CAPJ = json.load(open(os.path.join(W, "captions_v004.json"), encoding="utf-8"))
FRAMES_JSON = os.path.join(W, "red_frames.json")
SEQ = MAP["sequence"]
BREAKS = plan.line_breaks()
FPS = 30000 / 1001
SCREEN_W = 1920
TITLE_MIN = 1.0
LABEL_MIN = 2.0                    # 07 の demo_label：2秒未満の札は出さない
TITLE_DY = {"T002": 0.0, "T005": -0.01}
# 青の札 T030（聞き手の問い・図解の札）の置き方（v001）。v002 の書き出しの画像で測った値：
#   グループの位置の縦 0.434 の時、文字の中心は y≈925.5px。横は見本のまま置くと札の左端が x=306px
#   札の幅＝文字の送り幅（tools/telop_size.measure）＋左右 7.8px ずつ（「Astraをどう活用してる？」1094.4→1110px、「Astraの何がすごい？」914.4→930px）
#   1行の通常字幕の文字の中心は y≈998px（2行の字幕の2行目。1行目は y≈890px）
ASK_Y0, ASK_TEXT_CY0, PLATE_LEFT0, PLATE_PAD = 0.434, 925.5, 306.0, 7.8
T200_CY0 = 697.0                   # v004 G5：見本の T200（白い座布団）の文字の中心（見本/確認/v006_20261002_FGH の書き出しで測った）
T200_CY = {1: 998.0, 2: 998.0, 3: 998.0}   # 行の数ごとの置く高さ（Premiere の書き出しで測って直す）
AI_NOTE, AI_ON, AI_OFF, AI_NOTE_DY = "※AI指示中", 54, 6, 0.0   # v004 G5：注釈を出すコマ・間のコマ、ふつうの※の位置からの上下のずらし（px）
AI_FADE = 18                       # v004 G5：出る・消えるのディゾルブ（コマ）。小川さん「点滅が激しすぎる。じわじわってディゾルブで消える・現れるぐらい。すごくゆっくりで大丈夫」
CAPTION_CY = 998.0                 # 問いの札の下の行の文字の中心＝1行の字幕と同じ高さ（2026-09-29 小川さん 案A）
PLATE_PITCH = 125.0                # （v003）2行の問いを行ごとの札にした時の行の間
PLATE_LEADING = 108.0              # v001：1枚の札の2行の、行の中心の間（見本の T030 の行送り。書き出しの画像で確かめる）
PLATE_FONT = "WanpakuRuika-08"     # T030 の字体（短い行を真ん中に寄せる空白の幅を測る）
DIAGRAM_LEFT = 60.0                # 図解の札の左端（v002 の T172〜T174 と同じくらい）
DIAGRAM_CY = [346.0, 494.0, 644.0]  # 図解の札の文字の中心（v002 の T172〜T174 と同じ高さ）
T_CAP, T_EMP, T_SERIES, T_TOPIC, T_BOARD, T_WIPE = "V6", "V7", "V8", "V9", "V10", "V11"
PLATE_TRACKS = ["V12", "V13", "V14"]


def sec(t):
    return t / TPS


ZUKAI = os.path.join(HERE, "zukai", "out")       # v002：AI が描く動く図解（zukai/make_zukai.py。build_v004.py が V15・V16 に置いた）


def zukai_manifests():
    out = []
    if os.path.isdir(ZUKAI):
        for k in sorted(os.listdir(ZUKAI)):
            p = os.path.join(ZUKAI, k, "manifest.json")
            if k.startswith("Z") and not k.lower().startswith("ztest") and os.path.exists(p):
                out.append((k, json.load(open(p, encoding="utf-8"))))
    out.sort(key=lambda x: x[1]["tl_start_f"])
    return out


def main():
    lib = Library(SRC)
    pj = lib.pj
    seq = pj.sequence(SEQ)
    FT = pj.frame_ticks(seq)
    assert FT == 8475667200, FT
    tr = dict(pj.tracks(seq))
    assert [n for n in tr] == [f"V{i}" for i in range(1, 17)] + [f"A{i}" for i in range(1, 6)], list(tr)   # v002：V15・V16＝図解
    hl_ext_t = CUTS.get("highlight_external_frames", 0) * FT          # 冒頭ハイライト（hl/）。A4 の効果音・V14 の白から戻る素材は build で置いてある
    for n in ("V3", "V5", "V6", "V7", "V8", "V9", "V10", "V12", "V13", "A5"):
        assert not pj.items(tr[n]), f"{n} が空ではない"
    for n, lim in (("A4", hl_ext_t), ("V14", hl_ext_t + 30 * FT)):
        assert all(pj.span(i)[1] <= lim for i in pj.items(tr[n])), f"{n} にハイライトの外のクリップがある"
    for n, t in tr.items():
        ci = t.find("ClipTrack/ClipItems")
        if ci is not None and ci.find("TrackItems") is None:
            ci.insert(0, ET.Element("TrackItems", {"Version": "1"}))
    rec = {"source": os.path.relpath(SRC, CASE), "output": os.path.relpath(OUT, CASE), "sequence": SEQ, "captions": 0,
           "telops": [], "highlight": [], "boards": [], "chapters": [], "se": [], "zooms": [], "bgm": {}, "titles": [], "labels": [],
           "notes": []}
    total = MAP["total_frames"] * FT
    screen_spans = [(a * FT, b * FT) for a, b in MAP["screen_spans"]]
    screen_spans0 = list(screen_spans)                # build が決めた画面の区間（下の[35]で頭を前へ出す前）

    def _inp(it):
        sub = pj.ref(it.find("ClipTrackItem/SubClip"))
        clip = pj.ref(sub.find("Clip")) if sub is not None and sub.find("Clip") is not None else None
        h = pj.range_holder(clip)
        return int(h.findtext("InPoint")) if h is not None else None

    def _cont(x, y):                                  # x の続きが y（素材が続いている＝カットではない）
        ix, iy = _inp(x), _inp(y)
        return ix is not None and iy is not None and pj.span(x)[1] == pj.span(y)[0] and iy - ix == pj.span(y)[0] - pj.span(x)[0]

    def _set_muted(it, on):
        cti = it.find("ClipTrackItem")
        m = cti.find("IsMuted")
        if on and m is None:
            m = ET.Element("IsMuted")
            m.text = "true"
            cti.insert(list(cti).index(cti.find("SubClip")) + 1, m)
        elif on:
            m.text = "true"
        elif m is not None:
            cti.remove(m)
    # v004 点検[35]（7:02.02〜7:02.36：カットの後に体をひねるカメラが 10コマだけ残ってから画面へ飛ぶ）：
    #   画面の頭の 12コマ以内の前にカット（素材が飛ぶ V1 の切れ目）があり、その間がカメラの短い切れ端なら、画面をカットのコマから出す。
    #   V1 のその切れ端を無効にし、V2（画面）・V11（ワイプ）の同じ所を有効にする（build は全部の区間にクリップを置き、映さない所を無効にしている）。
    #   画面の録画はカメラと同期しているので、V2 のその所は画面の頭と素材が続いている時だけにする（続いていなければ前に出さない）
    SCREEN_LEAD_F = 12
    rec["screen_lead"] = []
    screen_ext = {}                                   # 前に出した画面の頭 → 元の頭（ticks）
    ext_v1 = set()                                    # 無効にした V1 の切れ端（ズームを付けない）
    v1_ = sorted(pj.items(tr["V1"]), key=lambda i: pj.span(i)[0])
    v2_ = {pj.span(i): i for i in pj.items(tr["V2"])}
    v11_ = {pj.span(i): i for i in pj.items(tr["V11"])}
    for k_, (a_, b_) in enumerate(screen_spans):
        if a_ <= MAP["highlight_end"] * FT:
            continue
        head = [i for i in v1_ if pj.span(i)[1] == a_]
        if not head:
            continue
        j = v1_.index(head[0])
        piece = [v1_[j]]                              # 画面の頭の前の、素材が続いているカメラ
        while j - 1 >= 0 and _cont(v1_[j - 1], v1_[j]):
            j -= 1
            piece.insert(0, v1_[j])
        cut_ = pj.span(piece[0])[0]
        if j == 0 or a_ - cut_ > SCREEN_LEAD_F * FT or pj.span(v1_[j - 1])[1] != cut_:
            continue
        v2p = [v2_.get(pj.span(i)) for i in piece]
        v11p = [v11_.get(pj.span(i)) for i in piece]
        nxt2 = [i for s_, i in v2_.items() if s_[0] == a_]
        if None in v2p or None in v11p or not nxt2 or not _cont(v2p[-1], nxt2[0]):
            rec["notes"].append(f"[35] 画面の頭 {sec(a_):.2f} の前のカメラの切れ端は、画面の素材が続いていないので前に出さない")
            continue
        for i in piece:
            _set_muted(i, True)
            ext_v1.add(i)
        for i in v2p + v11p:
            _set_muted(i, False)
        screen_spans[k_] = (cut_, b_)
        screen_ext[cut_] = a_
        rec["screen_lead"].append({"at": round(sec(cut_), 3), "was": round(sec(a_), 3), "frames": round((a_ - cut_) / FT)})
    print(f"[35] 画面の頭をカットへ前に出した {len(rec['screen_lead'])}")

    def on_screen(s, e):
        return any(a < e and s < b for a, b in screen_spans)

    def on_screen0(s, e):
        return any(a < e and s < b for a, b in screen_spans0)

    # ---- 字幕（本編）----
    caps_all = [c for c in CAPJ["captions"] if c["mode"] != "drop" and "src" in c]
    ctl = MAP["caption_tl"]
    order = sorted(caps_all, key=lambda c: ctl[c["id"]])
    caps = {}
    for k, c in enumerate(order):
        s = ctl[c["id"]] * FT
        e = ctl[order[k + 1]["id"]] * FT if k + 1 < len(order) else total
        caps[c["id"]] = {"id": c["id"], "s": s, "e": e, "text": c["text"], "who": c["who"], "k": k}
    ids = [c["id"] for c in order]
    pos = {i: k for k, i in enumerate(ids)}

    def span_ids(a, b):
        return ids[pos[a]:pos[b] + 1]
    items = {}
    # v004 G5（2026-10-04 小川さん「AIに三上さんが指示している瞬間は、テロップは白ベースの座布団に黒い文字」）：区間（d00_AITALK）の三上さんの字幕は
    #   T200（白い座布団に黒い文字。完成版2本目の「白背景」）。大きさは 06 の auto、置く高さは文字の中心を通常の字幕と同じ高さへ（見本の T200 は中心 697px）
    # v004 小川さんの直し（2026-10-04 20:16 に Premiere で直して保存したもの。読み取って入れた）：「多分Obsidianの開発者は」（1100）の後の
    #   無言の顔まね（溜め。カメラの素材 3102.50秒から 56コマ）を、ボケとして見せる。その間はカメラを 151%（位置は小川さんが合わせた値）に寄せ、
    #   字幕・右上タイトル・BGM を外し、頭にポカン。1101「ってなると思う」からは元どおり
    FACE_SRC, FACE_ZOOM = 3102.50, (151.0, 0.39791667461395264, 0.56759262084960938)
    face = None
    for it_ in pj.items(tr["V1"]):
        sub_ = pj.ref(it_.find("ClipTrackItem/SubClip"))
        h_ = pj.range_holder(pj.ref(sub_.find("Clip"))) if sub_ is not None and sub_.find("Clip") is not None else None
        if h_ is not None and abs(int(h_.findtext("InPoint")) / TPS - FACE_SRC) < 0.05:
            face = pj.span(it_)
    assert face is not None and face[1] == caps["1101"]["s"] and caps["1100"]["s"] < face[0], ("顔まねのクリップが見つからない", face)
    caps["1100"]["e"] = face[0]
    ai_ids = set()
    for sp_ in plan.ai_talk():
        ai_ids |= {i for i in span_ids(sp_["from"], sp_["to"]) if caps[i]["who"] == "み"}
    for i in ids:
        c = caps[i]
        if i in ai_ids:
            it = lib.add_telop(seq, "T200", [[c["text"]]], start=sec(c["s"]), duration=sec(c["e"] - c["s"]), track=T_CAP, size="auto")
            gg_ = component_param(pj, it, "AE.ADBE Graphic Group", {"位置"})["位置"]
            x_, y_ = get_static(gg_).split(":")
            n_lines = len(c["text"].split("\r"))
            set_static(gg_, f"{x_}:{float(y_) + (T200_CY[n_lines] - T200_CY0) / 1080:.5f}")
            items[i] = it
        else:
            items[i] = lib.add_telop(seq, "T001" if c["who"] == "み" else "T003", [[c["text"]]], start=sec(c["s"]),
                                     duration=sec(c["e"] - c["s"]), track=T_CAP, size=None)
        c["screen"] = on_screen(c["s"], c["e"])
    rec["captions"] = len(ids)
    removed = set()

    def take(i, why):
        if i in removed:
            raise ValueError(f"字幕{i}はすでに別の演出にしている（{why}）")
        detach(pj, tr[T_CAP], items[i])
        removed.add(i)

    # ---- v002：AI が描く動く図解の区間（09：黒い板の図解の間は通常字幕・右上タイトル・強調・SE・ズームを外す。図の中の字が字幕の代わり）----
    anim = [] if os.environ.get("ZUKAI_OFF") else zukai_manifests()    # ZUKAI_OFF=1：図解なしの土台で試す時
    anim_spans = [(m["tl_start_f"] * FT, m["tl_end_f"] * FT, k) for k, m in anim]
    vt = {n: [pj.span(i) for i in pj.items(tr[n])] for n in ("V15", "V16")}
    for k, m in anim:
        s0, e0 = m["tl_start_f"] * FT, m["tl_end_f"] * FT
        assert (s0, e0) in vt["V15"], f"図解 {k} の overlay が V15 に無い（build_v004.py を流し直す）"
        if m.get("wipe"):
            assert (s0, e0) in vt["V16"], f"図解 {k} のワイプが V16 に無い"
        for i in m["hide_caption_ids"]:
            if i in caps and i not in removed:
                take(i, f"図解 {k}")
            if i in caps and (caps[i]["s"] < s0 or caps[i]["e"] > e0):
                rec["notes"].append(f"図解 {k}：字幕 {i}（{sec(caps[i]['s']):.2f}〜{sec(caps[i]['e']):.2f}）が図解の外にはみ出す")

    def in_anim(s, e, what):
        for a, b, k in anim_spans:
            if s < b and a < e:
                rec["notes"].append(f"図解 {k} の間なので外した：{what}")
                return True
        return False

    fonts = telop_size.Fonts()

    def add_plate(text, s, dur, track):
        return lib.add_telop(seq, "T030", [[text]], start=sec(s), duration=sec(dur), track=track, size=None)

    def plate_width(it):
        return max(w for w, _ in telop_size.measure(pj, it, fonts)["lines"])

    PLATE_DX = json.load(open(os.path.join(W, "plate_dx_v004.json"), encoding="utf-8")) if os.path.exists(os.path.join(W, "plate_dx_v004.json")) else {}

    PLATE_FIX = json.load(open(os.path.join(W, "plate_fix_v004.json"), encoding="utf-8")) if os.path.exists(os.path.join(W, "plate_fix_v004.json")) else {}

    def pad_combo(pad):
        """空白の幅 pad（px）に一番近い 全角（90px）×b ＋ 半角（28.8px）×a"""
        best = min(((b, a) for b in range(0, 12) for a in range(0, 8)), key=lambda x: (abs(x[0] * 90.0 + x[1] * 28.8 - pad), x[0] + x[1]))
        return best

    def position_plate(it, cy, left=None, scale=1.0, dx=0.0):
        """青の札 T030 を置く：文字の中心の高さ cy（px）、札の左端 left（px。None なら左右の中央）。scale は文字の大きさの倍率
        中央に置く札は、Premiere で書き出した画像で測ったずれ（_work/plate_dx_v004.json。カタカナの詰めなどで測った幅と数px違う）を足す"""
        if abs(scale - 1.0) > 1e-3:
            pj.scale_font_sizes(it, scale)
        box_w = plate_width(it) + 2 * PLATE_PAD
        txt = "".join("".join(r) for r in pj.item_texts(it))
        L = (SCREEN_W - box_w) / 2 + PLATE_DX.get(txt, 0.0) + dx if left is None else left
        gg = component_param(pj, it, "AE.ADBE Graphic Group", {"位置"})["位置"]
        x0 = float(get_static(gg).split(":")[0])
        set_static(gg, f"{x0 + (L - PLATE_LEFT0) / SCREEN_W:.5f}:{ASK_Y0 + (cy - ASK_TEXT_CY0) / 1080:.5f}")
        rec.setdefault("plate_pos", []).append({"text": "".join("".join(r) for r in pj.item_texts(it)), "left": round(L, 1),
                                                "box_w": round(box_w, 1), "cy": cy, "scale": round(scale, 3)})

    stops, zooms, se_events = [], [], []
    v1 = sorted(pj.items(tr["V1"]), key=lambda i: pj.span(i)[0])

    def zoom_ok(s, e, who, why, speaker_zoom=False):
        if on_screen(s, e):
            rec["notes"].append(f"{why}：画面の区間にかかるのでズームしない")
            return False
        if who != "み" and not speaker_zoom:
            rec["notes"].append(f"{why}：聞き手の字幕なのでズームしない（04 の zoom）")
            return False
        return True

    START_FIX = json.load(open(os.path.join(W, "kyocho_start_fix.json"), encoding="utf-8")) \
        if os.path.exists(os.path.join(W, "kyocho_start_fix.json")) else {}

    def place_emphasis(e, c_first, c_last, track, key):
        text = e["text_fix"]
        if not text:
            raise SystemExit(f"{key}：強調の文が書かれていない")
        s, en = c_first["s"], c_last["e"]
        fx_ = START_FIX.get(str(s // FT))
        _n = lambda x: x.replace("\r", "").replace(" ", "").replace("　", "")
        # v003（2026-10-04 小川さん「縮小入る瞬間に若干このテロップが残ってる…基本、画角変化が入る時はテロップ消すように」）：
        #   ズームはカメラのクリップごとにかかる（字幕の頭＝クリップの頭から）ので、ズームの付く強調は聞こえ始めまで遅らせず、画角が変わるコマから出す
        #   （遅らせると、その間だけ前の字幕と右上タイトルが寄り・引きの絵に残る。v002 の 1:31.1・21:26.8・22:28.6）
        zoom_here = bool(e.get("zoom")) and (c_first["who"] == "み" or e.get("speaker_zoom")) and not on_screen0(s, en)
        if fx_ and zoom_here and c_first["s"] < fx_["to"] * FT < en:
            rec["notes"].append(f"{key}：ズーム（{e['zoom']}）が付くので、聞こえ始め（+{sec(fx_['to'] * FT - c_first['s']):.2f}秒）まで遅らせず、"
                                f"画角が変わるコマ（字幕の頭）から出した（v003 G1）")
        elif fx_ and c_first["s"] < fx_["to"] * FT < en and en - fx_["to"] * FT >= int(1.2 * FPS) * FT and _n(fx_["text"]) == _n(text):
            s = fx_["to"] * FT                            # 01「出す時刻」：書いた最初の言葉の聞こえ始めから（_work/kyocho_start_fix.py。残りが 1.2秒以上・同じ文の時だけ）
        for a_, b_ in screen_spans:                       # 強調の終わりが画面の区間に 0.2秒以下だけかかる時は、画面の頭で切る（文字が画面に残らず、ズームも外れない）
            if s < a_ < en and (en - a_ <= 6 * FT or (a_ in screen_ext and en <= screen_ext[a_] + 6 * FT)):   # [35] 前に出した頭も
                en = a_
        item = lib.add_telop(seq, e["type"], [[text]], start=sec(s), duration=sec(en - s), track=track)
        info = lib.size_log[-1]
        redo = None
        if info.get("rule") == "基本テロップ赤" and "\r" not in text and (info.get("size_after", 90) < 89.5 or info.get("chars_longest_line", 0) > 17):
            # 基本テロップ赤（P08）は 06 で「改行：字幕」なので telop_size が「2行にする」を出さず、1行のまま縮んでいた（v001 の画像。18件）。
            #   通常字幕と同じく 17字を超えたら2行にして大きさ 90 を保つ（08 の captions.layout）。改行は表の半角の空白（plan.line_breaks）か、助詞の後ろ
            redo = BREAKS.get(e["id"]) or break_text(text)
            rec["notes"].append(f"{key}：基本テロップ赤を2行にした（{redo!r}）")
        elif any("1行にする" in n for n in info["notes"]):
            redo = text.replace("\r", " ")
        elif any("2行にする" in n for n in info["notes"]) and "\r" not in text:
            redo = BREAKS.get(e["id"])
            if redo is None or redo.replace("\r", "").replace(" ", "") != text.replace(" ", ""):
                redo = break_text(text)
                rec["notes"].append(f"{key}：強調の改行の指定が無いので機械的に入れた（{redo!r}）。確認が要る")
        if redo is not None:
            detach(pj, tr[track], item)
            lib.size_log.pop()
            item = lib.add_telop(seq, e["type"], [[redo]], start=sec(s), duration=sec(en - s), track=track)
            info = lib.size_log[-1]
            info["line_change"] = f"{text!r} → {redo!r}"
            text = redo
        return item, text, info, s, en

    # ---- 強調の文を確かめる（文・種類が無い、途中で切れた文があれば組み立てずに止まる）----
    def source_of(e):
        return " / ".join(caps[x]["text"].replace("\r", " ") for x in span_ids(e["id"], e["until"]))
    check_items = []
    for e in plan.emphasis():
        e["source"] = source_of(e)
        check_items.append({"at": f"字幕{e['id']}", "text": e["text_fix"], "kind": e["kind"], "source": e["source"]})
    for h in plan.highlight():
        check_items.append({"at": f"ハイライト{h['id']}", "text": h["text_fix"], "kind": h["kind"], "source": ""})
    kyocho_check.require_texts(check_items)
    rec["notes"].append(f"強調の文の確認（require_texts）：{len(check_items)}件、止まる所なし")

    # ---- 冒頭のハイライト（通常字幕は置かず、強調だけ）----
    hl_caps = []
    t0 = 0
    for a, b in CUTS["highlight_frames"]:
        inside = [c for c in caps_all if a <= int(c["src"] * FPS) < b]
        inside.sort(key=lambda c: c["src"])
        for k, c in enumerate(inside):
            f = int(c["src"] * FPS) - a
            s = (t0 + (f if f >= 5 else 0)) * FT
            e_ = (t0 + (int(inside[k + 1]["src"] * FPS) - a if k + 1 < len(inside) else b - a)) * FT
            hl_caps.append({"id": c["id"], "s": s, "e": e_, "text": c["text"], "who": c["who"]})
        t0 += b - a
    hl_by = {c["id"]: c for c in hl_caps}
    hl_done = set()
    for h in plan.highlight():
        c1, c2 = hl_by[h["id"]], hl_by[h["until"]]
        item, text, info, s, en = place_emphasis(h, c1, c2, T_EMP, f"ハイライト {h['id']}")
        for c in hl_caps:
            if c1["s"] <= c["s"] < en:
                hl_done.add(c["id"])
        if h["se"]:
            se_events.append((s, h["se"], f"ハイライト {h['id']}"))
        if h["zoom"] and zoom_ok(s, en, c1["who"], f"ハイライト {h['id']}"):
            zooms.append((s, en, plan.zoom_value(h["zoom"]), f"ハイライト {h['id']} {h['zoom']}"))
        rec["highlight"].append({"id": h["id"], "until": h["until"], "text": text, "type": h["type"], "kind": h["kind"],
                                 "source": " / ".join(c["text"].replace("\r", " ") for c in hl_caps if c1["s"] <= c["s"] < en),
                                 "start": round(sec(s), 3), "end": round(sec(en), 3), "size": info})
    for c in hl_caps:
        if c["id"] not in hl_done:
            lib.add_telop(seq, "T001" if c["who"] == "み" else "T003", [[c["text"]]], start=sec(c["s"]),
                          duration=sec(c["e"] - c["s"]), track=T_CAP, size=None)
            rec["notes"].append(f"ハイライトの字幕 {c['id']} は通常字幕で出す")

    # ---- 強調（V7）----
    for e in plan.emphasis():
        e["source"] = source_of(e)
        c1, c2 = caps[e["id"]], caps[e["until"]]
        if in_anim(c1["s"], c2["e"], f"強調 {e['id']}「{e['text_fix']}」"):
            continue
        for i in span_ids(e["id"], e["until"]):
            take(i, f"強調 {e['id']}")
        item, text, info, s, en = place_emphasis(e, c1, c2, T_EMP, f"字幕{e['id']}")
        if s > c1["s"]:                                   # 前置きの間：0.6秒未満なら前の字幕を延ばし、長ければこの字幕をその間だけ出す（01「出す時刻」）
            k_ = pos[e["id"]]
            prev = ids[k_ - 1] if k_ else None
            if prev and prev not in removed and s - c1["s"] < int(0.6 * FPS) * FT:
                pc = caps[prev]
                detach(pj, tr[T_CAP], items[prev])
                items[prev] = lib.add_telop(seq, "T001" if pc["who"] == "み" else "T003", [[pc["text"]]], start=sec(pc["s"]),
                                            duration=sec(s - pc["s"]), track=T_CAP, size=None)
                pc["e"] = s
                how = f"前の字幕 {prev} を延ばした"
            else:
                lib.add_telop(seq, "T001" if c1["who"] == "み" else "T003", [[c1["text"]]], start=sec(c1["s"]), duration=sec(s - c1["s"]),
                              track=T_CAP, size=None)
                how = f"字幕 {e['id']} を前置きの間だけ出した"
            rec["notes"].append(f"強調 {e['id']}：書いた最初の言葉の聞こえ始め（+{sec(s - c1['s']):.2f}秒）から出した。{how}")
        if e["se"]:
            se_events.append((s, e["se"], f"強調 {e['id']}"))
        z = e["zoom"]
        if z and not zoom_ok(s, en, c1["who"], f"字幕{e['id']} の{z}"):
            z = ""
        if z:
            zooms.append((s, en, plan.zoom_value(z), f"字幕{e['id']} {z}"))
        if e["bgm_stop"]:
            stops.append((s, en, e["id"]))
        rec["telops"].append({"id": e["id"], "until": e["until"], "pattern": e["pattern"], "type": e["type"], "text": text, "se": e["se"],
                              "kind": e["kind"], "source": e["source"], "zoom": z, "bgm_stop": e["bgm_stop"], "reason": e["reason"],
                              "start": round(sec(s), 3), "end": round(sec(en), 3), "screen": on_screen(s, en), "size": info})

    # ---- SE だけ ----
    for x in plan.se_only():
        if in_anim(caps[x["id"]]["s"], caps[x["id"]]["s"] + FT, f"SEのみ {x['id']}"):
            continue
        se_events.append((caps[x["id"]]["s"], x["se"], f"SEのみ {x['id']}"))

    # ---- v004 小川さんの直し：1100 の後の顔まね（上の face）に、寄り 151%・ポカン・BGM 停止（右上タイトルは寄りの間なので外れる）----
    zooms.append((face[0], face[1], FACE_ZOOM, "小川さん 顔まね（1100 の後）寄り151"))
    se_events.append((face[0], plan.SE["ポカン"], "小川さん 顔まね（1100 の後）"))
    stops.append((face[0], face[1], "顔まね"))
    rec["notes"].append(f"小川さんの直し：顔まね {sec(face[0]):.2f}〜{sec(face[1]):.2f} に寄り151・ポカン・BGM停止、字幕1100 はその前で終える")

    # ---- 説明（01 の手順3。※の補足・↑の一言。V5。通常字幕は外さない）----
    #   この案件では V9 を右上の話題タイトルに使っているので（astra と同じ）、補足テロップは空いている V5 に置く（00_案件メモ.md のトラック）
    #   出す長さ：その字幕の間。短い時は 2.5秒まで延ばす（次の説明とは重ねない）
    nts = sorted([x for x in plan.notes() if not in_anim(caps[x["id"]]["s"], caps[x["id"]]["e"], f"説明 {x['id']}")],
                 key=lambda x: caps[x["id"]]["s"])
    note_items = []
    for k, x in enumerate(nts):
        c = caps[x["id"]]
        s0 = c["s"]
        n_ch = len(x["text"].replace("\r", ""))
        want = max(2.5, n_ch * 0.13)                      # 1秒に約8字（08 の captions.layout の読む速さ）。短い時も 2.5秒
        e0 = max(c["e"], s0 + int(want * FPS) * FT)
        if k + 1 < len(nts):
            e0 = min(e0, caps[nts[k + 1]["id"]]["s"])
        emp_starts = sorted(int(round(t["start"] * TPS / FT)) * FT for t in rec["telops"] if t["start"] * TPS > s0 + FT)
        nxt_emp = [t for t in emp_starts if t >= s0 + int(2.5 * FPS) * FT]
        if nxt_emp:                                       # 次の強調が出たら消す（重なって読めなくなる。2.5秒は出す）
            e0 = min(e0, max(c["e"], nxt_emp[0]))
        # 次の問い・並べる座布団・代弁の頭、画面の区間の終わりでも止める（2.5秒は出す。v001 2回目の検査係）
        stops_ = [caps[k_]["s"] for g_ in plan.plates() for k_, _ in g_["items"][:1] if k_ in caps]
        stops_ += [caps[k_]["s"] for rp_ in plan.roleplay() for k_, *_ in rp_["lines"][:1] if k_ in caps]
        stops_ += [b_ for a_, b_ in screen_spans if a_ <= s0 < b_]
        for st_ in sorted(stops_):
            if s0 + int(2.5 * FPS) * FT <= st_ < e0:
                e0 = st_
                break
        e0 = min(e0, total)
        if sec(e0 - s0) + 0.05 < want:
            rec["notes"].append(f"説明 {x['id']}：{sec(e0 - s0):.1f}秒しか出せない（{n_ch}字、1秒{n_ch / max(0.1, sec(e0 - s0)):.0f}字）")
        ty = x["type"]
        it = lib.add_telop(seq, ty, [[x["text"]]], start=sec(s0), duration=sec(e0 - s0), track="V5", size=None)
        note_items.append((it, x["id"]))
        if ty == "T132":
            # T132（※音声入力中）は文字の大きさの値を持たない型（06 で大きさを変えられない）。グループの大きさと位置で置く（v001 で Premiere の書き出しで測った）：
            #   文字の箱の中心 x(px) ＝ 1920×位置x ＋ 607.5×大きさ（見本は 位置x −0.096875・大きさ 0.8 で中心 300px）、行は左ぞろえ・行を足すと上へ伸びる
            #   文字の幅は HiraginoSans-W8 の 97.5px 相当×大きさ。左端を 60px に、大きさは 0.6（1文字 約58px）まで、最大 1780px に収める
            w100 = max(fonts.width("HiraginoSans-W8", 100.0, ln) for ln in x["text"].split("\r"))
            sc = min(0.6, 1780 / (w100 * 0.975))
            wpx = w100 * 0.975 * sc
            gg = component_param(pj, it, "AE.ADBE Graphic Group", {"位置", "スケール"})
            set_static(gg["スケール"], f"{sc * 100:.2f}")
            y0 = get_static(gg["位置"]).split(":")[1]
            set_static(gg["位置"], f"{(60 + wpx / 2 - 607.5 * sc) / 1920:.6f}:{y0}")
        if x["se"]:
            se_events.append((s0, x["se"], f"説明 {x['id']}"))
        rec.setdefault("notes_added", []).append({"id": x["id"], "text": x["text"], "type": x["type"], "start": round(sec(s0), 3),
                                                   "end": round(sec(e0), 3), "reason": x["reason"]})

    # ---- v004 G5：AI に話しかけて頼んでいる間、※AI指示中 をゆっくり出したり消したりする（V5。54コマ出して 6コマ空ける。出る・消えるは 18コマのディゾルブ。
    #   ディゾルブは G1 の寄せの後に付ける）。効果音なし（小川さん「指示の間ずっと」「効果音はいらない」「点滅が激しすぎる。じわじわ」）----
    rec["ai_talk"] = []
    g5_items = []
    for sp_ in plan.ai_talk():
        a_, b_ = caps[sp_["from"]]["s"], caps[sp_["to"]]["e"]
        if in_anim(a_, b_, f"AI指示中 {sp_['from']}"):
            continue
        t_, n_ = a_, 0
        w100 = fonts.width("HiraginoSans-W8", 100.0, AI_NOTE)
        sc = min(0.6, 1780 / (w100 * 0.975))
        wpx = w100 * 0.975 * sc
        while t_ < b_:
            e_ = min(t_ + AI_ON * FT, b_)
            if n_ and e_ - t_ < 2 * AI_FADE * FT:
                # 点検[34]：区間の最後に残る短い点灯（6:58.89 の 9コマ・4:40.71 の 12コマ・6:38.36 の 16コマ）は置かず、1つ前の消えるディゾルブで終える。
                #   出る・消えるのディゾルブ（AI_FADE）が両方入るには 2×AI_FADE コマ要る。それより短いと、ディゾルブが付かないか短くなり、
                #   最後だけチカッと光る（小川さん「じわじわってディゾルブで消える・現れる」）
                rec["notes"].append(f"G5 {sp_['from']}：最後の点灯（{sec(t_):.2f}〜、{(e_ - t_) // FT}コマ）は {2 * AI_FADE}コマより短いので置かない")
                break
            if e_ - t_ >= 3 * FT:
                it = lib.add_telop(seq, "T132", [[AI_NOTE]], start=sec(t_), duration=sec(e_ - t_), track="V5", size=None)
                gg = component_param(pj, it, "AE.ADBE Graphic Group", {"位置", "スケール"})
                set_static(gg["スケール"], f"{sc * 100:.2f}")
                y0 = get_static(gg["位置"]).split(":")[1]
                set_static(gg["位置"], f"{(60 + wpx / 2 - 607.5 * sc) / 1920:.6f}:{float(y0) + AI_NOTE_DY / 1080:.6f}")
                g5_items.append(it)
                n_ += 1
            t_ += (AI_ON + AI_OFF) * FT
        rec["ai_talk"].append({"from": sp_["from"], "to": sp_["to"], "start": round(sec(a_), 3), "end": round(sec(b_), 3), "blinks": n_,
                               "captions": len([i for i in span_ids(sp_["from"], sp_["to"]) if i in ai_ids]), "reason": sp_["reason"]})

    fonts = telop_size.Fonts()
    board_spans, chapter_spans = [], []
    # ---- 章の入り（P10。V9 に番号見出し T015、V10 に項目名カード T093。字幕を外す）----
    for ch in plan.chapters():
        a, b, z = caps[ch["num_id"]], caps[ch["item_id"]], caps[ch["end"]]
        if in_anim(a["s"], z["e"], f"章 {ch['num_id']}"):
            continue
        for i in span_ids(ch["num_id"], ch["end"]):
            take(i, f"章 {ch['num_id']}")
        lib.add_telop(seq, "T015", [[ch["head"][0]], [ch["head"][1]]], start=sec(a["s"]), duration=sec(z["e"] - a["s"]), track=T_TOPIC, size=None)
        lib.add_telop(seq, "T093", [[ch["item"]]], start=sec(b["s"]), duration=sec(z["e"] - b["s"]), track=T_BOARD, size=None)
        se_events.append((a["s"], "S001", f"章 {ch['num_id']} 番号見出し"))
        if b["s"] != a["s"]:
            se_events.append((b["s"], "S003", f"章 {ch['num_id']} 項目名"))
        if zoom_ok(a["s"], z["e"], "み", f"章 {ch['num_id']} 寄り120"):
            zooms.append((a["s"], z["e"], plan.zoom_value("寄り120"), f"章 {ch['num_id']} 寄り120"))
        chapter_spans.append((a["s"], z["e"]))
        rec["chapters"].append({"num": ch["num_id"], "item": ch["item_id"], "end": ch["end"], "head": ch["head"], "text": ch["item"],
                                "start": round(sec(a["s"]), 3), "end_sec": round(sec(z["e"]), 3), "reason": ch["reason"]})

    # ---- ボード（V10。字幕を外す）----
    for bd in plan.boards():
        a, z = caps[bd["from"]], caps[bd["to"]]
        if in_anim(a["s"], z["e"], f"ボード {bd['from']}「{bd['body']}」"):
            continue
        for i in span_ids(bd["from"], bd["to"]):
            take(i, f"ボード {bd['from']}")
        sample_item, _ = lib.sample_item(bd["type"])
        w_s = max(w for w, _ in telop_size.measure(pj, sample_item, fonts)["lines"])
        item = lib.add_telop(seq, bd["type"], [bd["head"], [bd["body"]]], start=sec(a["s"]), duration=sec(z["e"] - a["s"]),
                             track=T_BOARD, size=None)
        if bd["scale"]:
            pj.scale_font_sizes(item, bd["scale"])
        w_n = max(w for w, _ in telop_size.measure(pj, item, fonts)["lines"])
        gg = component_param(pj, item, "AE.ADBE Graphic Group", {"位置"})
        moved = None
        if "位置" in gg and bd["type"] == "T028":
            x, y = get_static(gg["位置"]).split(":")
            nx = float(x) - (w_n - w_s) / 2 / SCREEN_W
            set_static(gg["位置"], f"{nx}:{y}")
            moved = [float(x), nx]
        board_spans.append((a["s"], z["e"]))
        se_events.append((a["s"], bd["se"], f"ボード {bd['from']}"))
        rec["boards"].append({"from": bd["from"], "to": bd["to"], "type": bd["type"], "text": bd["body"], "start": round(sec(a["s"]), 3),
                              "end": round(sec(z["e"]), 3), "width_px": round(w_n), "group_x": moved, "reason": bd["reason"]})

    # ---- 代弁（P16 アホなふり。V3 に黒帯、V7 に白い明朝 T009）----
    roleplay_spans = []
    for rp in plan.roleplay():
        if in_anim(caps[rp["lines"][0][0]]["s"], caps[rp["lines"][-1][0]]["e"], f"代弁 {rp['lines'][0][0]}"):
            continue
        spans = []
        for key, text, band in rp["lines"]:
            u = caps[key]
            take(key, f"代弁 {key}")
            lib.add_effect(seq, band, start=sec(u["s"]), duration=sec(u["e"] - u["s"]), track="V3")
            s_ = u["s"]
            fx_ = START_FIX.get(str(s_ // FT))
            if fx_ and s_ < fx_["to"] * FT < u["e"]:          # セリフも、書いた最初の言葉の聞こえ始めから（黒帯は字幕の頭から）
                s_ = fx_["to"] * FT
            lib.add_telop(seq, "T009", [[text]], start=sec(s_), duration=sec(u["e"] - s_), track=T_EMP, size="auto", pattern="P16")
            spans.append((u["s"], u["e"]))
            if u["screen"]:
                rec["notes"].append(f"代弁の字幕{key}は画面の区間にかかっている")
        roleplay_spans.append((spans[0][0], spans[-1][1]))
        rec.setdefault("roleplay", []).append({"lines": rp["lines"], "start": round(sec(spans[0][0]), 3), "end": round(sec(spans[-1][1]), 3),
                                               "reason": rp["reason"]})

    # ---- 並べる座布団・聞き手の問い（P11。V12〜V14）----
    se_only_ids = {x["id"] for x in plan.se_only()}
    for g in plan.plates():
        end = caps[g["end"]]["e"]
        if in_anim(caps[g["items"][0][0]]["s"], end, f"{g['kind']} {g['items'][0][0]}「{g['items'][0][1]}」"):
            continue
        placed = []
        if g["kind"] == "問い":
            key, text = g["items"][0]
            s0 = caps[key]["s"]
            for i in span_ids(key, g["end"]):
                take(i, f"問い {key}")
            lines = text.split("／")
            n = len(lines)
            # v001 小川さん「問いの札は2つに分けず1つに」：2行でも札は1枚。T030 は文字が左寄せなので、短い方の行の頭に空白を足して
            #   行の真ん中をそろえる（WanpakuRuika に細い空白の字は無いので、全角 90px と半角 28.8px を組み合わせる。ずれは最大 約7px）
            fx = PLATE_FIX.get(key, {})
            if n == 1:
                body = lines[0]
            else:
                ws = [fonts.width(PLATE_FONT, 90.0, ln) for ln in lines]
                wmax = max(ws)
                padded = []
                for i, (ln, w) in enumerate(zip(lines, ws)):
                    pad = (wmax - w) / 2
                    if fx and i == fx["short"]:
                        pad = fx["pad"]          # 書き出した画像で測って直した空白の幅（_work/plate_fix_v004.json）
                    full, half = pad_combo(pad)
                    padded.append("\u3000" * full + " " * half + ln)
                body = "\r".join(padded)
            it = add_plate(body, s0, end - s0, PLATE_TRACKS[0])
            scale = min(1.0, (0.9 * SCREEN_W - 2 * PLATE_PAD) / plate_width(it))   # 02 の P11 layout：画面の90%を超える時だけ縮める
            position_plate(it, CAPTION_CY, left=None, scale=scale, dx=fx.get("dx", 0.0))   # T030 は最後の行の位置で置かれる（2行でも下の行が字幕の高さ）
            if scale < 1.0:
                rec["notes"].append(f"問い {key}：画面の90%に収まるよう文字を {scale:.0%} にした")
            se_events.append((s0, g["se"], f"問い {key}"))
            placed.append((key, text, round(sec(s0), 3)))
        else:
            for i, (key, text) in enumerate(g["items"]):
                s0 = caps[key]["s"]
                track = PLATE_TRACKS[i]
                if g["kind"] == "並列":
                    lib.add_telop(seq, ["T172", "T173", "T174"][i], [[text]], start=sec(s0), duration=sec(end - s0), track=track, size=None)
                elif g["kind"] == "並列画像":
                    pass        # v003：公式のロゴの札（zukai/L1 の透明の動画。build_v004.py が V16 に置く）。ここでは SE と記録だけ
                else:
                    raise ValueError(f"座布団の種類 {g['kind']} はこの版では使わない")
                if key not in se_only_ids and g["se"]:
                    se_events.append((s0, g["se"], f"座布団 {key}"))
                placed.append((key, text, round(sec(s0), 3)))
        rec.setdefault("plates", []).append({"kind": g["kind"], "items": placed, "end": round(sec(end), 3), "reason": g["reason"]})

    # ---- 図解（工程6。09 の型3：ぼかし E016 を V3・見出し T201 を V9・青の札を V12〜V14 に1つずつ積む）----
    diagram_spans = []
    for k, m in anim:                                 # v002：動く図解の SE と区間
        for ev in m.get("se_events", []):
            if ev["se"] not in plan.SE:
                raise SystemExit(f"図解 {k} の SE「{ev['se']}」が plan_v004.SE に無い")
            se_events.append((ev["tl_f"] * FT, plan.SE[ev["se"]], f"図解 {k} {ev.get('why', '')}".strip()))
        diagram_spans.append((m["tl_start_f"] * FT, m["tl_end_f"] * FT))
        rec.setdefault("anim_diagrams", []).append({"key": k, "title": m.get("title", ""), "start": round(m["tl_start_f"] / FPS, 3),
                                                    "end": round(m["tl_end_f"] / FPS, 3), "hidden_captions": m["hide_caption_ids"],
                                                    "se": len(m.get("se_events", [])), "overlay": m["overlay"]["file"],
                                                    "wipe": (m.get("wipe") or {}).get("file")})
    # v004 G3：画像（zukai/I*。build が V16 に置いた）とロゴの札（zukai/L*）の SE と記録。字幕などは外さない
    rec["images"] = []
    for k in sorted(os.listdir(ZUKAI)) if os.path.isdir(ZUKAI) else []:
        mpath = os.path.join(ZUKAI, k, "manifest.json")
        if k[:1] not in ("I", "L") or not os.path.exists(mpath):
            continue
        m = json.load(open(mpath, encoding="utf-8"))
        for ev in m.get("se_events", []):
            if ev["se"] not in plan.SE:
                raise SystemExit(f"画像 {k} の SE「{ev['se']}」が plan_v004.SE に無い")
            se_events.append((ev["tl_f"] * FT, plan.SE[ev["se"]], f"画像 {k}"))
        rec["images"].append({"key": k, "title": m.get("title", ""), "start": round(m["tl_start_f"] / FPS, 3), "end": round(m["tl_end_f"] / FPS, 3),
                              "se": len(m.get("se_events", [])), "overlay": m["overlay"]["file"]})
    for dg in plan.diagrams():
        h = caps[dg["head_id"]]
        s0, end = h["s"], caps[dg["end"]]["e"]
        if in_anim(s0, end, f"v001 の図解（型3）{dg['head_id']}「{dg['head']}」"):
            continue
        lib.add_effect(seq, "E016", start=sec(s0), duration=sec(end - s0), track="V3")
        lib.add_telop(seq, "T201", [[dg["head"]]], start=sec(s0), duration=sec(end - s0), track=T_TOPIC, size=None)
        se_events.append((s0, "S003", f"図解 {dg['head_id']} 見出し"))
        placed, its = [], []
        for i, (key, text) in enumerate(dg["items"]):
            s1 = caps[key]["s"]
            its.append(add_plate(text, s1, end - s1, PLATE_TRACKS[i]))
            se_events.append((s1, "S002", f"図解 {dg['head_id']} 札{i + 1}"))
            placed.append((key, text, round(sec(s1), 3)))
        # 1つの図解の札は同じ文字の大きさ。一番長い札が画面（左右 DIAGRAM_LEFT の余白）に収まる大きさにそろえる（v001）
        wmax = max(plate_width(it) for it in its)
        scale = min(1.0, (SCREEN_W - 2 * DIAGRAM_LEFT - 2 * PLATE_PAD) / wmax)
        for i, it in enumerate(its):
            position_plate(it, DIAGRAM_CY[i], left=DIAGRAM_LEFT, scale=scale)
        if scale < 1.0:
            rec["notes"].append(f"図解 {dg['head_id']}：札が画面に収まるよう文字を {scale:.0%} にした")
        for t in rec["telops"]:
            if t["start"] < sec(end) and sec(s0) < t["end"]:
                rec["notes"].append(f"図解 {dg['head_id']} の間に強調 {t['id']} がある（09：外す）")
        diagram_spans.append((s0, end))
        rec.setdefault("diagrams", []).append({"kind": dg["kind"], "head": dg["head"], "items": placed, "start": round(sec(s0), 3),
                                               "end": round(sec(end), 3), "reason": dg["reason"]})
    kept_z = []
    for z in zooms:                                   # 09：図解の間はズームを外す
        if any(a < z[1] and z[0] < b for a, b in diagram_spans):
            rec["notes"].append(f"図解の間なのでズームを外した：{z[3]}")
        else:
            kept_z.append(z)
    zooms[:] = kept_z

    # ---- ズーム（カメラ直接：V1 のカメラのクリップの大きさ・位置を変える。04 の zoom の camera_direct）----
    template = None
    for it in sorted(pj.items(tr["V2"]), key=lambda i: pj.span(i)[0]):
        mp = component_param(pj, it, "AE.ADBE Motion", {"スケール", "位置"})
        if len(mp) == 2:
            chain = pj.ref(it.find("ClipTrackItem/ComponentOwner/Components"))
            for cc in chain.findall("ComponentChain/Components/Component"):
                ce = pj.ref(cc)
                if ce is not None and ce.findtext("MatchName") == "AE.ADBE Motion":
                    template = ce
            break
    assert template is not None
    added_motion = 0
    zooms.sort()
    for k in range(1, len(zooms)):                   # 重なるズームは前を詰める
        if zooms[k][0] < zooms[k - 1][1]:
            zooms[k - 1] = (zooms[k - 1][0], zooms[k][0]) + zooms[k - 1][2:]
    for s, e, (scale, x, y), why in zooms:
        if e <= s:
            continue
        ov = [it for it in v1 if pj.span(it)[0] < e and s < pj.span(it)[1] and it not in ext_v1]   # [35] 画面の下にしたカメラは寄せない
        for it in ov:
            a, b = pj.span(it)
            tol = int(0.35 * FPS) * FT                    # 0.35秒までのはみ出しはそのクリップごと寄せる（ズームが言葉の途中から急に始まらないように。v001 の画像）
            if (a < s or b > e) and (a < s - tol or b > e + tol):
                rec["notes"].append(f"ズームの区間 {sec(s):.2f}〜{sec(e):.2f} をカメラのクリップがはみ出すのでそのクリップは外した（{sec(a):.2f}〜{sec(b):.2f}）{why}")
                continue
            mp = component_param(pj, it, "AE.ADBE Motion", {"スケール", "位置"})
            if len(mp) < 2:
                add_motion(pj, it, template)
                added_motion += 1
                mp = component_param(pj, it, "AE.ADBE Motion", {"スケール", "位置"})
            set_static(mp["スケール"], f"{scale:g}.")
            set_static(mp["位置"], f"{x}:{y}")
        rec["zooms"].append({"start": round(sec(s), 3), "end": round(sec(e), 3), "scale": scale, "pos": [x, y], "clips": len(ov), "why": why})
    # v003 G1：カットの直後・直前に、前のズームの大きさのまま 8コマ以下だけ残る所（v002 で 42か所。カット → 2コマ後に画角が変わる）を、
    #   同じショットの隣の大きさ・位置にそろえて、画角の変わり目をカットにそろえる（テロップは下の G1 の寄せで同じコマへ）
    def in_point(it):
        sub = pj.ref(it.find("ClipTrackItem/SubClip"))
        clip = pj.ref(sub.find("Clip")) if sub is not None and sub.find("Clip") is not None else None
        h = pj.range_holder(clip)
        return int(h.findtext("InPoint")) if h is not None else None

    def cont(x, y):                                   # x の続きが y（素材が続いている＝カットではない）
        ix, iy = in_point(x), in_point(y)
        return ix is not None and iy is not None and iy - ix == pj.span(y)[0] - pj.span(x)[0]

    def motion_of(it):
        mp_ = component_param(pj, it, "AE.ADBE Motion", {"スケール", "位置"})
        if len(mp_) < 2:
            return ("100.", "0.5:0.5")
        return (get_static(mp_["スケール"]), get_static(mp_["位置"]))

    def set_motion(it, val):
        nonlocal added_motion
        mp_ = component_param(pj, it, "AE.ADBE Motion", {"スケール", "位置"})
        if len(mp_) < 2:
            add_motion(pj, it, template)
            added_motion += 1
            mp_ = component_param(pj, it, "AE.ADBE Motion", {"スケール", "位置"})
        set_static(mp_["スケール"], val[0])
        set_static(mp_["位置"], val[1])
    cams = [it for it in sorted(pj.items(tr["V1"]), key=lambda i: pj.span(i)[0]) if pj.span(it)[0] >= MAP["highlight_end"] * FT]   # 本編のカメラ
    rec["g1_pieces"] = []
    for k in range(1, len(cams) - 1):
        pc, pv, nx = cams[k], cams[k - 1], cams[k + 1]
        a, b = pj.span(pc)
        if b - a > 8 * FT or pj.span(pv)[1] != a or pj.span(nx)[0] != b:
            continue
        cb, ca = not cont(pv, pc), not cont(pc, nx)
        m_p, m_k, m_n = motion_of(pv), motion_of(pc), motion_of(nx)
        if cb and not ca and m_k != m_n:
            set_motion(pc, m_n)
            rec["g1_pieces"].append({"at": round(sec(a), 3), "frames": round((b - a) / FT), "from": m_k[0], "to": m_n[0], "how": "カットの直後を後ろの大きさに"})
        elif ca and not cb and m_k != m_p:
            set_motion(pc, m_p)
            rec["g1_pieces"].append({"at": round(sec(a), 3), "frames": round((b - a) / FT), "from": m_k[0], "to": m_p[0], "how": "カットの直前を前の大きさに"})
    print(f"G1：カットの前後の短い所をそろえた {len(rec['g1_pieces'])}")
    rec["motion_components_added"] = added_motion

    # ---- 画面の赤枠（V4。Premiere で置いたもの）に小さいクリック音 ----
    frames = json.load(open(FRAMES_JSON, encoding="utf-8"))["frames"] if os.path.exists(FRAMES_JSON) else []
    if frames:
        its = sorted(pj.items(tr["V4"]), key=lambda i: pj.span(i)[0])
        assert len(its) == len(frames), (len(its), len(frames))
        # [35] 画面の頭を前に出した所で、画面の頭から出ていた赤枠は、新しい頭（カットのコマ）から出す。
        #   その所の字幕の頭も G1 の寄せで新しい頭へ来るので、画面・左上の札・字幕・赤枠（とクリック音）が同じコマで出る。
        #   画面の録画は続いている（上で確かめた）ので、枠の場所は変わらない
        lead_new = {old: new for new, old in screen_ext.items()}
        for fr in frames:
            if fr["start"] in lead_new:
                rec["notes"].append(f"[35] 赤枠 {fr['id_from']} の頭を画面の頭に合わせて {sec(fr['start']):.2f} → {sec(lead_new[fr['start']]):.2f}")
                fr["start"] = lead_new[fr["start"]]
        for it, fr in zip(its, sorted(frames, key=lambda f: f["start"])):
            ti = it.find("ClipTrackItem/TrackItem")
            ti.find("Start").text, ti.find("End").text = str(fr["start"]), str(fr["end"])     # Premiere は静止画を1フレーム短く置くことがある
            h = pj.range_holder(pj.ref(pj.ref(it.find("ClipTrackItem/SubClip")).find("Clip")))
            if h is not None:
                h.find("OutPoint").text = str(int(h.findtext("InPoint")) + fr["end"] - fr["start"])
            se_events.append((fr["start"], plan.FRAME_SE, f"赤枠 {fr['id_from']}"))
            rec.setdefault("frames", []).append({"start": round(sec(fr["start"]), 3), "end": round(sec(fr["end"]), 3), "from": fr["id_from"],
                                                 "to": fr["id_to"], "read": fr["read"]})

    # ---- 左上の実演の札（07 の demo_label。V8、画面を映している間だけ）----
    labels = plan.screen_labels(ids)
    lab_runs = []
    for a, b in screen_spans:
        runs = []
        for i in ids:
            c = caps[i]
            if c["e"] <= a or c["s"] >= b or i not in labels:
                continue
            if runs and runs[-1][2] == labels[i]:
                continue
            runs.append([max(a, c["s"]), None, labels[i]])
        if not runs:
            continue
        runs[0][0] = a
        for k in range(len(runs) - 1):
            runs[k][1] = runs[k + 1][0]
        runs[-1][1] = b
        lab_runs += runs
    for s0, e0, text in lab_runs:
        if sec(e0 - s0) < LABEL_MIN:
            rec["notes"].append(f"札「{text}」は {sec(e0 - s0):.1f}秒しかないので出さない")
            continue
        lib.add_telop(seq, "T203", [[text]], start=sec(s0), duration=sec(e0 - s0), track=T_SERIES, size=None)
        rec["labels"].append({"start": round(sec(s0), 3), "end": round(sec(e0), 3), "text": text})

    # ---- SE（A4。次の音の手前で切る）。音量は plan.SE_OFFSET_DB（赤枠の音はさらに下げる）----
    if screen_ext:                                    # [35] 前に出した画面の頭：元の頭で鳴らす音（SEのみ・座布団など）も新しい頭へ（字幕も G1 でそこへ来る）
        lead_new_ = {old: new for new, old in screen_ext.items()}
        se_events[:] = [(lead_new_.get(s, s), sid, why) for s, sid, why in se_events]
    kept_se = []
    for ev in se_events:                              # v002：動く図解の間は図解の SE だけ（09：重なる SE を外す）
        hit = [k for a, b, k in anim_spans if a <= ev[0] < b]
        if hit and not ev[2].startswith(f"図解 {hit[0]}"):
            rec["notes"].append(f"図解 {hit[0]} の間なので SE を外した：{ev[2]}（{sec(ev[0]):.2f}秒）")
            continue
        kept_se.append(ev)
    se_events[:] = kept_se
    se_events.sort(key=lambda x: (x[0], x[2].startswith("赤枠"), x[1]))
    seen = {}
    for s, sid, why in se_events:
        if s in seen:
            rec["notes"].append(f"SE の開始が同じ（{sec(s):.2f}秒 {seen[s]} と {why}）。{why} の音は置かない")
            continue
        seen[s] = why
    se_list = sorted((s, sid, why) for s, sid, why in se_events if seen.get(s) == why)
    for k, (s, sid, why) in enumerate(se_list):
        sample, _ = lib.sample_item(sid)
        length = pj.span(sample)[1] - pj.span(sample)[0]
        nxt = se_list[k + 1][0] if k + 1 < len(se_list) else None
        dur = length if nxt is None or s + length <= nxt else nxt - s
        new = lib.add_se(seq, sid, start=sec(s), track="A4", duration=sec(dur))
        off_db = plan.SE_OFFSET_DB + (plan.FRAME_SE_OFFSET_DB if why.startswith("赤枠") else 0)
        g0 = add_gain_db(pj, new, off_db)
        rec["se"].append({"start": round(sec(s), 3), "se": sid, "why": why, "cut": dur < length, "gain_db": round(g0 + off_db, 2)})

    # ---- BGM の止める区間（A3 のクリップを切って、間を無効化。曲は止めた分も進む）----
    merged = []
    for s, e, i in sorted(stops):
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    n_muted = 0
    for base in sorted(pj.items(tr["A3"]), key=lambda i: pj.span(i)[0]):
        b0, b1 = pj.span(base)
        cuts_in = [(max(s, b0), min(e, b1)) for s, e in merged if s < b1 and b0 < e]
        if not cuts_in:
            continue
        edges = sorted({b0, b1} | {x for ab in cuts_in for x in ab})
        detach(pj, tr["A3"], base)
        for s, e in zip(edges, edges[1:]):
            new = pj.clone_item(base, seq, "A3", start_ticks=s, duration_ticks=e - s, src_offset_ticks=s - b0)
            if any(a <= s and e <= b for a, b in cuts_in):
                cti = new.find("ClipTrackItem")
                m = ET.Element("IsMuted")
                m.text = "true"
                cti.insert(list(cti).index(cti.find("SubClip")) + 1, m)
                n_muted += 1
    rec["bgm"] = {"main_gain_db": plan.BGM_GAIN_DB, "voice_gain_db": plan.VOICE_GAIN_DB, "stops": [[round(sec(s), 3), round(sec(e), 3)] for s, e in merged],
                  "muted": n_muted}

    # ---- 右上のタイトル（V8 シリーズ名・V9 話題タイトル）。カメラの間だけ。寄り・引き・代弁・ボード・章・ハイライトの間と最初の話題の前は出さない ----
    cam_ranges = []
    t = MAP["highlight_end"] * FT
    for a, b in screen_spans + [(total, total)]:
        if a > t:
            cam_ranges.append([t, a])
        t = max(t, b)
    tops = plan.topics()
    holes = [(z[0], z[1]) for z in zooms] + roleplay_spans + board_spans + chapter_spans + diagram_spans + [(0, caps[tops[0][0]]["s"])]

    def subtract(ranges, hs):
        out = []
        for s, e in ranges:
            cur = [(s, e)]
            for a, b in hs:
                nxt = []
                for x, y in cur:
                    if b <= x or y <= a:
                        nxt.append((x, y))
                    else:
                        if x < a:
                            nxt.append((x, a))
                        if b < y:
                            nxt.append((b, y))
                cur = nxt
            out += cur
        return [(a, b) for a, b in out if sec(b - a) >= TITLE_MIN]
    # 点検[11]（02 の P13「出している間は右上のタイトルを出さない」・titles.not_shown「画像・図解を出している間」）：
    #   真ん中に出す画像（zukai/out/<KEY>/manifest.json の tl_start_f〜tl_end_f）の間は、図解と同じく右上タイトルを外す。
    #   左上の小さいロゴの札（L1・I02・I03・I08・I11・I12・I13）と左に寄せた画像（I05・I09）はタイトルを残す（v003 の L1 で小川さんが OK した形）
    CENTER_IMAGES = ("I01", "I04", "I06", "I07", "I10", "I14")
    image_holes = []
    for k_ in CENTER_IMAGES:
        mp_ = os.path.join(ZUKAI, k_, "manifest.json")
        if os.path.exists(mp_):
            m_ = json.load(open(mp_, encoding="utf-8"))
            image_holes.append((m_["tl_start_f"] * FT, m_["tl_end_f"] * FT))
            rec["notes"].append(f"[11] 画像 {k_}（{sec(image_holes[-1][0]):.2f}〜{sec(image_holes[-1][1]):.2f}）の間は右上タイトルを出さない")
    holes += image_holes
    title_ranges = subtract(cam_ranges, holes)
    # 点検[37]（6:59.12〜7:00.62 の右上タイトルが 1.5秒だけ出る）：画面（左上の札・G5 の区間）や真ん中の画像が消えた直後に
    #   TITLE_FLASH 秒未満だけ出る右上タイトルは置かない（3秒ほどの間に上の表示が何度も替わってチラつく。前の話題のタイトルが一瞬戻るだけ）。
    #   寄り（ズーム）の後の短いタイトルは残す（16:38 頃の顔まねの後の 1.3秒は小川さんが残した形）
    TITLE_FLASH = 2.0
    after_ = {b for a, b in screen_spans} | {b for a, b in image_holes}
    rec["titles_dropped"] = [{"start": round(sec(a), 3), "end": round(sec(b), 3), "sec": round(sec(b - a), 2),
                              "after": "画面" if a in {y for x, y in screen_spans} else "画像"}
                             for a, b in title_ranges if a in after_ and sec(b - a) < TITLE_FLASH]
    title_ranges = [(a, b) for a, b in title_ranges if not (a in after_ and sec(b - a) < TITLE_FLASH)]
    print(f"[37] 画面・画像の直後に {TITLE_FLASH}秒未満だけ出る右上タイトルを置かない {len(rec['titles_dropped'])}")

    def place_title(type_id, text, ranges, track):
        sample, _ = lib.sample_item(type_id)
        w_s = max(w for w, _ in telop_size.measure(pj, sample, fonts)["lines"])
        n, w_n = 0, 0
        for s, e in ranges:
            item = lib.add_telop(seq, type_id, [[text]], start=sec(s), duration=sec(e - s), track=track, size=None)
            pj.scale_font_sizes(item, plan.TITLE_SCALE)
            w_n = max(w for w, _ in telop_size.measure(pj, item, fonts)["lines"])
            gg = component_param(pj, item, "AE.ADBE Graphic Group", {"位置"})
            x, y = get_static(gg["位置"]).split(":")
            set_static(gg["位置"], f"{float(x) - (w_n - w_s) / SCREEN_W}:{float(y) + TITLE_DY.get(type_id, 0.0)}")
            n += 1
        return n, w_n
    n, w = place_title("T002", plan.SERIES, title_ranges, T_SERIES)
    rec["titles"].append({"kind": "シリーズ名", "text": plan.SERIES, "clips": n, "width_px": round(w)})
    for k, (i, text) in enumerate(tops):
        s0 = caps[i]["s"]
        e0 = caps[tops[k + 1][0]]["s"] if k + 1 < len(tops) else total
        rs = [(max(a, s0), min(b, e0)) for a, b in title_ranges if a < e0 and s0 < b]
        rs = [(a, b) for a, b in rs if sec(b - a) >= TITLE_MIN]
        if not rs:
            rec["notes"].append(f"話題タイトル「{text}」はカメラの区間が無いので出ない")
            continue
        n, w = place_title("T005", text, rs, T_TOPIC)
        rec["titles"].append({"kind": "話題タイトル", "text": text, "from": i, "clips": n, "width_px": round(w)})

    # ---- v003 G1：画角が変わるコマに、テロップの出入りをそろえる（2026-10-04 小川さん「縮小入る瞬間に若干このテロップが残ってる。
    #   気持ち悪いから、基本、画角変化が入る時はテロップ消すようにしてください」）----
    #   画角が変わるコマ＝V1 のカメラの大きさが変わる切れ目（ズームはクリップごとにかかるので、強調の頭・終わりと数コマずれることがある）と、
    #   画面の出入り。その前後 15コマ以内にあるテロップの頭・終わりを、そのコマへ寄せる（前の絵に残る・先に出る数コマを無くす）。
    #   検査は _work/check_gakaku.py（checks_gakaku.json）
    def scale_of(it):
        mp_ = component_param(pj, it, "AE.ADBE Motion", {"スケール"})
        return float(get_static(mp_["スケール"]).rstrip(".")) if "スケール" in mp_ else 100.0

    def retime(it, na, nb):
        ti = it.find("ClipTrackItem/TrackItem")
        st = ti.find("Start")
        if st is None:
            st = ET.Element("Start")
            ti.insert(list(ti).index(ti.find("End")), st)
        st.text, ti.find("End").text = str(na), str(nb)
        sub = pj.ref(it.find("ClipTrackItem/SubClip"))
        clip = pj.ref(sub.find("Clip")) if sub is not None and sub.find("Clip") is not None else None
        h = pj.range_holder(clip)
        if h is not None:
            h.find("OutPoint").text = str(int(h.findtext("InPoint")) + (nb - na))
    v1s = sorted(pj.items(tr["V1"]), key=lambda i: pj.span(i)[0])
    def muted(it):
        return (it.findtext("ClipTrackItem/IsMuted") or "").strip() == "true"
    # 画面の下（V1 が無効）のカメラの大きさの切れ目は見えないので数えない
    chg = [pj.span(y)[0] for x, y in zip(v1s, v1s[1:]) if pj.span(x)[1] == pj.span(y)[0] and abs(scale_of(x) - scale_of(y)) > 0.05
           and not (muted(x) and muted(y))]
    v2_runs = []                                     # 画面の出入りは V2 の実際のクリップで見る（build がカットの切れ目へ寄せたので、表の区間と数コマ違う）
    for it in sorted(pj.items(tr["V2"]), key=lambda i: pj.span(i)[0]):
        if muted(it):                                # 点検[36]：V2 は全部の区間にクリップがあり、映さない所は無効。無効のクリップは画面に数えない
            continue                                 #   （数えていたので、画面の出入りが chg に入っていなかった）
        a, b = pj.span(it)
        if v2_runs and v2_runs[-1][1] == a:
            v2_runs[-1][1] = b
        else:
            v2_runs.append([a, b])
    for a, b in v2_runs:
        chg += [a, b]
    chg = sorted({c for c in chg if c > MAP["highlight_end"] * FT})
    NEAR_F = 15
    rec["g1_aligned"] = []
    head_map, emp_map = {}, {}                        # 動かしたテロップの頭（元 → 新）。下で SE を一緒に動かす
    for tn in ("V5", T_CAP, T_EMP, T_SERIES, T_TOPIC, "V10", *PLATE_TRACKS):
        for it in sorted(pj.items(tr[tn]), key=lambda i: pj.span(i)[0]):
            a, b = pj.span(it)
            na, nb = a, b
            ca = min(chg, key=lambda g: abs(g - a)) if chg else a
            cb = min(chg, key=lambda g: abs(g - b)) if chg else b
            if ca != a and abs(ca - a) <= NEAR_F * FT:
                na = ca
            if cb != b and abs(cb - b) <= NEAR_F * FT:
                nb = cb
            if (na, nb) == (a, b):
                continue
            txt_ = "".join("".join(r) for r in pj.item_texts(it)).replace("\r", "／")[:24]
            if nb - na < 6 * FT:
                rec["notes"].append(f"G1：{tn}「{txt_}」は画角の変わり目に寄せると 0.2秒未満になるので寄せない（{sec(a):.2f}〜{sec(b):.2f}）")
                continue
            retime(it, na, nb)
            if na != a and tn not in (T_SERIES, T_TOPIC):
                head_map.setdefault(a, set()).add(na)
                if tn == T_EMP:
                    emp_map[a] = na
            rec["g1_aligned"].append({"track": tn, "text": txt_, "from": [round(sec(a), 3), round(sec(b), 3)], "to": [round(sec(na), 3), round(sec(nb), 3)],
                                      "frames": [round((na - a) / FT), round((nb - b) / FT)]})
    print(f"G1：画角が変わる所 {len(chg)}、寄せたテロップ {len(rec['g1_aligned'])}")
    # v004（v003 の最後の点検で見つけた所：1:55.9・12:08.5・14:54.6）：つなぎ（素材が飛ぶカット）の 1〜5コマ後に、
    #   札（V12〜V14）・右上タイトル（V8・V9）・ボード（V10）が切り替わる所を、カットのコマへ寄せる（新しい絵の上に数コマ残らないように）。
    #   字幕（V6）は寄せない（字幕は聞こえ始めで出す決まり。08 timing。話す人が替わる所は G4 で cuts_plan が寄せた）
    cams_ = sorted(pj.items(tr["V1"]), key=lambda i: pj.span(i)[0])
    jumps = [pj.span(y)[0] for x, y in zip(cams_, cams_[1:]) if pj.span(x)[1] == pj.span(y)[0] and pj.span(y)[0] >= MAP["highlight_end"] * FT
             and not cont(x, y)]
    # 点検[40]（27:44.86・20:21.75・21:17.94）：動く図解（V15。zukai/out/Z*）や真ん中の画像の幕の下に隠れているつなぎと、
    #   図解・画像（I*・L*）の終わりの 1〜5コマ前のつなぎには、右上タイトル・札・ボードを寄せない（図解・画像が消える前に、幕の上に先に出る）。
    #   下の[38]の字幕・強調の寄せも同じ（図解 Z7 の終わりの 2コマに字幕が幕の上に出た）
    hidden_ = [(a, b) for a, b, k in anim_spans] + list(image_holes)
    for k_ in sorted(os.listdir(ZUKAI)) if os.path.isdir(ZUKAI) else []:
        mp_ = os.path.join(ZUKAI, k_, "manifest.json")
        if k_[:1] in ("I", "L", "Z") and not k_.lower().startswith("ztest") and os.path.exists(mp_):
            m_ = json.load(open(mp_, encoding="utf-8"))
            hidden_.append(((m_["tl_end_f"] - 5) * FT, m_["tl_end_f"] * FT))
    all_jumps = list(jumps)
    jumps = [j_ for j_ in jumps if not any(a <= j_ < b for a, b in hidden_)]
    n_j = len(all_jumps)
    rec["notes"].append(f"[40] 図解・画像の幕の下・終わりの5コマのつなぎ {n_j - len(jumps)} か所には、字幕・強調・右上タイトル・札・ボードを寄せない")
    # 点検[38]（3:06.89：字幕の境目がカット 5601 の 1コマ後。3:03.15：強調の終わりと字幕124 の頭がカット 5489 の 2コマ後）：
    #   字幕・強調（V6・V7）の境目（新しい字幕・強調の頭がある所＝話す人が替わる・新しい言葉が始まる所）が、つなぎ（素材が飛ぶ V1 の切れ目）の
    #   1〜3コマ後ろにある時は、その境目の頭と終わりをカットのコマへ寄せる（前の字幕が新しい絵に 1〜3コマ残らないように）。
    #   画角の変わり目に寄せた所（chg）は動かさない。寄せると 0.2秒未満になるものは動かさない
    chg_set = set(chg)
    rec["cut_aligned"] = []
    edge_at = {}
    for tn in (T_CAP, T_EMP):
        for it in pj.items(tr[tn]):
            a, b = pj.span(it)
            if a >= MAP["highlight_end"] * FT:
                edge_at.setdefault(a, []).append((tn, it, "head"))
                edge_at.setdefault(b, []).append((tn, it, "end"))
    for j_ in jumps:
        hs = [j_ + d * FT for d in (1, 2, 3) if j_ + d * FT in edge_at and j_ + d * FT not in chg_set]
        hs = [h for h in hs if max([x for x in all_jumps if x < h]) == j_]      # いちばん近い前のカットだけ
        if not any(k == "head" for h in hs for _, _, k in edge_at[h]):
            continue
        if any(k == "head" and tn == T_EMP for h in hs for tn, _, k in edge_at[h]):
            # 強調の頭は動かさない（01「出す時刻」：書いた最初の言葉の聞こえ始めから。2〜3コマ前に出すと check_kyocho_timing で「早い」になる）
            continue
        moves = {}
        for h in hs:
            for tn, it, k in edge_at[h]:
                cur = moves[id(it)][1] if id(it) in moves else pj.span(it)
                moves[id(it)] = (it, (j_, cur[1]) if k == "head" else (cur[0], j_), tn)
        if any(nb - na < 6 * FT for it, (na, nb), tn in moves.values()):
            rec["notes"].append(f"[38] {sec(j_):.2f} のカットへ寄せると 0.2秒未満になるので寄せない")
            continue
        clash = [1 for it, (na, nb), tn in moves.values() for o in pj.items(tr[tn])
                 if id(o) not in moves and pj.span(o)[0] < nb and na < pj.span(o)[1]]
        if clash:
            rec["notes"].append(f"[38] {sec(j_):.2f} のカットへ寄せると同じトラックの前のテロップに重なるので寄せない")
            continue
        for it, (na, nb), tn in moves.values():
            a, b = pj.span(it)
            retime(it, na, nb)
            if na != a:
                head_map.setdefault(a, set()).add(na)
            rec["cut_aligned"].append({"track": tn, "text": "".join("".join(r) for r in pj.item_texts(it)).replace("\r", "／")[:24],
                                       "from": [round(sec(a), 3), round(sec(b), 3)], "to": [round(sec(na), 3), round(sec(nb), 3)],
                                       "frames": [round((na - a) / FT), round((nb - b) / FT)]})
        for h in hs:                                  # 同じ境目を2度動かさない
            edge_at.pop(h)
    print(f"[38] 字幕・強調の境目をつなぎのカットへ寄せた {len(rec['cut_aligned'])}")
    rec["jump_aligned"] = []
    for tn in (T_SERIES, T_TOPIC, "V10", *PLATE_TRACKS):
        for it in sorted(pj.items(tr[tn]), key=lambda i: pj.span(i)[0]):
            a, b = pj.span(it)
            na, nb = a, b
            for j_ in jumps:
                if 1 <= (a - j_) // FT <= 5:
                    na = j_
                if 1 <= (b - j_) // FT <= 5:
                    nb = j_
            if (na, nb) == (a, b) or nb - na < 6 * FT:
                continue
            retime(it, na, nb)
            if na != a and tn not in (T_SERIES, T_TOPIC):
                head_map.setdefault(a, set()).add(na)
            rec["jump_aligned"].append({"track": tn, "text": "".join("".join(r) for r in pj.item_texts(it)).replace("\r", "／")[:24],
                                        "from": [round(sec(a), 3), round(sec(b), 3)], "to": [round(sec(na), 3), round(sec(nb), 3)]})
    print(f"つなぎのカットに札・右上タイトル・ボードを寄せた {len(rec['jump_aligned'])}")

    # 点検[36]の寄せで、強調・字幕・札などの頭が画面の出入りへ動いた所（5:51.88 の強調「もうできた」など）は、その頭で鳴らしていた SE も一緒に動かす
    #   （SE は上で寄せる前の頭に置いている。図解・画像の音は、絵が動かないので動かさない。赤枠の音は上で寄せた赤枠と一緒に動く。
    #   動かした先に別の音がある時は動かさない）
    for t_ in rec["telops"]:
        f_ = round(t_["start"] * FPS) * FT
        if f_ in emp_map:
            t_["start"] = round(sec(emp_map[f_]), 3)
    # 赤枠（V4）は字幕の頭から出している（_work/red_frames_g2.py）。字幕の頭・境目を上で寄せた所（画面の出入り・つなぎのカット）は、
    #   赤枠の頭と終わりも同じコマへ寄せる（4:41.08：字幕は画面の頭へ寄ったのに、赤枠だけ 1コマ後から出ていた）
    v4 = sorted(pj.items(tr["V4"]), key=lambda i: pj.span(i)[0])
    rec["frames_moved"] = []
    for k_, it in enumerate(v4):
        a, b = pj.span(it)
        na = next(iter(head_map[a])) if len(head_map.get(a, ())) == 1 else a
        nb = next(iter(head_map[b])) if len(head_map.get(b, ())) == 1 else b
        if (na, nb) == (a, b):
            continue
        prv = pj.span(v4[k_ - 1]) if k_ else None
        nxt = pj.span(v4[k_ + 1]) if k_ + 1 < len(v4) else None
        inside = any(x <= na and nb <= y for x, y in screen_spans)          # 画面の外（カメラの上）へはみ出さない
        if nb - na < 6 * FT or (prv and prv[1] > na) or (nxt and nxt[0] < nb and nxt[0] != b) or not inside:
            rec["notes"].append(f"赤枠（{sec(a):.2f}〜{sec(b):.2f}）は字幕に合わせて寄せると重なる・短くなるので寄せない")
            continue
        retime(it, na, nb)
        for fr_ in rec.get("frames", []):
            if round(fr_["start"] * FPS) * FT == a:
                fr_["start"], fr_["end"] = round(sec(na), 3), round(sec(nb), 3)
        rec["frames_moved"].append({"from": [round(sec(a), 3), round(sec(b), 3)], "to": [round(sec(na), 3), round(sec(nb), 3)]})
    print(f"字幕の頭に合わせて寄せた赤枠 {len(rec['frames_moved'])}")
    a4 = sorted([i for i in pj.items(tr["A4"]) if pj.span(i)[0] >= MAP["highlight_end"] * FT], key=lambda i: pj.span(i)[0])
    se_by_f = {round(s_["start"] * FPS): s_ for s_ in rec["se"]}
    se_starts = {pj.span(i)[0] for i in a4}
    rec["se_moved"] = []
    for k_, it in enumerate(a4):
        a, b = pj.span(it)
        tgt = head_map.get(a)
        ev = se_by_f.get(a // FT)
        if not tgt or len(tgt) != 1 or ev is None or ev["why"].startswith(("画像", "図解")):
            continue                                  # 図解・画像の音は、動かない overlay の中の出るコマに合わせてある
        na = next(iter(tgt))
        prv = a4[k_ - 1] if k_ else None
        nxt = a4[k_ + 1] if k_ + 1 < len(a4) else None
        nb = na + (b - a)
        if nxt is not None and nb > pj.span(nxt)[0]:
            nb = pj.span(nxt)[0]
        if na in se_starts or (prv is not None and pj.span(prv)[0] >= na) or nb - na < 3 * FT:
            rec["notes"].append(f"SE「{ev['why']}」（{sec(a):.2f}）は動かした先に別の音があるので動かさない")
            continue
        if prv is not None and pj.span(prv)[1] > na:
            retime(prv, pj.span(prv)[0], na)          # 前の音は次の音の手前で切る（上の SE の置き方と同じ）
        retime(it, na, nb)
        se_starts.discard(a)
        se_starts.add(na)
        ev["start"], ev["cut"] = round(sec(na), 3), ev["cut"] or nb - na < b - a
        rec["se_moved"].append({"why": ev["why"], "from": round(sec(a), 3), "to": round(sec(na), 3)})
    print(f"テロップの頭と一緒に動かした SE {len(rec['se_moved'])}")

    # ---- v002：ディゾルブ（2026-10-04 小川さん「dots で言ったことを元に」＝dots v003「消える時に全部ディゾルブで」・02 の P13・titles）----
    #   ※の説明（V5 の T132）の終わりと、右上タイトル（V8 シリーズ名・V9 話題タイトル）の最初に出る所に、クロスディゾルブ 0.5秒を
    #   プロジェクトに直接書く（tools/native_prproj.py の add_dissolve。手本 tools/dissolve_template.xml。QE の addTransition は使わない）
    DIS = 15
    rec["dissolves"] = []
    for it, nid_ in note_items:
        a, b = pj.span(it)
        if b - a <= DIS * FT:
            rec["notes"].append(f"説明 {nid_}：{sec(b - a):.2f}秒しかないのでディゾルブを付けない")
            continue
        pj.add_dissolve(seq, "V5", it, DIS, at_end=True)
        rec["dissolves"].append({"track": "V5", "what": f"説明 {nid_} の終わり", "clip": [round(sec(a), 3), round(sec(b), 3)]})
    for it in g5_items:                                # v004 G5：※AI指示中 の出る・消えるディゾルブ
        a, b = pj.span(it)
        f_ = min(AI_FADE, (b - a) // FT // 2 - 1)
        if f_ >= 4:
            pj.add_dissolve(seq, "V5", it, f_, at_end=False)
            pj.add_dissolve(seq, "V5", it, f_, at_end=True)
    rec["dissolves"].append({"track": "V5", "what": f"※AI指示中 {len(g5_items)}本の出る・消える（{AI_FADE}コマ）", "clip": []})
    for tn in (T_SERIES, T_TOPIC):
        its_ = sorted([i for i in pj.items(tr[tn]) if pj.span(i)[0] >= MAP["highlight_end"] * FT], key=lambda i: pj.span(i)[0])
        lab_s = {round(lb["start"] * FPS) for lb in rec["labels"]}          # V8 の左上の実演の札（画面の間）は除く
        its_ = [i for i in its_ if not (tn == T_SERIES and round(pj.span(i)[0] / FT) in lab_s)]
        if its_:
            a, b = pj.span(its_[0])
            pj.add_dissolve(seq, tn, its_[0], DIS, at_end=False)
            rec["dissolves"].append({"track": tn, "what": "右上タイトルの最初", "clip": [round(sec(a), 3), round(sec(b), 3)]})

    # ---- 検査・保存 ----
    checks = {}
    for n, t in pj.tracks(seq):
        sp = sorted(pj.span(it) for it in pj.items(t))
        checks[f"{n}_clips"] = len(sp)
        assert all(a[1] <= b[0] for a, b in zip(sp, sp[1:])), f"{n} でクリップが重なっている"
    checks["captions_placed"] = len(ids) - len(removed)
    checks["captions_replaced"] = len(removed)
    se_starts = {round(s["start"] * FPS) for s in rec["se"]}
    checks["emphasis_se_start_match"] = all(round(t["start"] * FPS) in se_starts for t in rec["telops"] if t["se"])
    rec["font_fix"] = fix_fonts(pj, {"HiraKakuStdN-W8": "HiraginoSans-W8", "Corporate-Logo-Rounded-Bold-ver3": "HiraginoSans-W8"})
    pj.gc()
    bad = pj.check_binaries()
    assert not any(bad.values()), bad
    rec["checks"] = checks
    rec["size_log"] = lib.size_log
    lib.save(OUT)
    json.dump(rec, open(os.path.join(HERE, "v004_記録.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    write_plan_csv(rec, os.path.join(HERE, "decoration_plan.csv"))
    print(json.dumps({k: rec[k] for k in ("checks", "bgm")}, ensure_ascii=False, indent=1))
    print("字幕", rec["captions"], "強調", len(rec["telops"]), "ハイライト", len(rec["highlight"]), "章", len(rec["chapters"]), "ボード", len(rec["boards"]),
          "代弁", len(rec.get("roleplay", [])), "座布団・問い", len(rec.get("plates", [])), "SE", len(rec["se"]), "ズーム", len(rec["zooms"]),
          "赤枠", len(rec.get("frames", [])), "札", len(rec["labels"]), "図解", len(rec.get("diagrams", [])), "注意", len(rec["notes"]))


def write_plan_csv(rec, path):
    rows = []

    def mmss(t):
        return f"{int(t // 60):02d}:{t % 60:05.2f}"
    for t in rec["highlight"]:
        rows.append([mmss(t["start"]), t["start"], t["end"], "P15", t["type"], t["text"].replace("\r", " / "), "", "", "", f"字幕{t['id']}", "冒頭のハイライト",
                     t["kind"], t["source"]])
    for t in rec["telops"]:
        rows.append([mmss(t["start"]), t["start"], t["end"], t["pattern"], t["type"], t["text"].replace("\r", " / "), t["se"], t["zoom"],
                     "停止" if t["bgm_stop"] else "", f"字幕{t['id']}" + (f"〜{t['until']}" if t["until"] != t["id"] else ""), t["reason"],
                     t["kind"], t["source"]])
    for c in rec["chapters"]:
        rows.append([mmss(c["start"]), c["start"], c["end_sec"], "P10", "T015+T093", " / ".join(c["head"]) + " / " + c["text"], "S001+S003", "寄り120", "",
                     f"字幕{c['num']}〜{c['end']}", c["reason"]])
    for b in rec["boards"]:
        rows.append([mmss(b["start"]), b["start"], b["end"], "P09" if b["type"] == "T028" else "P14", b["type"], b["text"].replace("\r", " / "),
                     "", "", "", f"字幕{b['from']}〜{b['to']}", b["reason"]])
    for r in rec.get("roleplay", []):
        rows.append([mmss(r["start"]), r["start"], r["end"], "P16", "T009+E003", " / ".join(x[1] for x in r["lines"]), "", "", "",
                     "字幕" + "・".join(x[0] for x in r["lines"]), r["reason"]])
    for g in rec.get("plates", []):
        rows.append([mmss(g["items"][0][2]), g["items"][0][2], g["end"], "P11", g["kind"], " / ".join(x[1] for x in g["items"]),
                     "S001" if g["kind"] == "問い" else "S002", "", "", "字幕" + "・".join(x[0] for x in g["items"]), g["reason"]])
    for dg in rec.get("diagrams", []):
        rows.append([mmss(dg["start"]), dg["start"], dg["end"], "図解", dg["kind"] + "（E016+T201+T172〜T174）", dg["head"] + " / " + " / ".join(x[1] for x in dg["items"]),
                     "S003+S002", "", "", "字幕" + "・".join(x[0] for x in dg["items"]), dg["reason"]])
    for fr in rec.get("frames", []):
        rows.append([mmss(fr["start"]), fr["start"], fr["end"], "赤枠", "画像", fr["read"], "S009", "", "", f"字幕{fr['from']}〜{fr['to']}", "画面の中を読んでいる所"])
    for lb in rec["labels"]:
        rows.append([mmss(lb["start"]), lb["start"], lb["end"], "実演の札", "T203", lb["text"], "", "", "", "", "07 の demo_label"])
    for s in rec["se"]:
        if s["why"].startswith("SEのみ"):
            rows.append([mmss(s["start"]), s["start"], "", "SEのみ", "", "", s["se"], "", "", s["why"], ""])
    rows.sort(key=lambda r: r[1])
    with open(path, "w", encoding="utf-8-sig", newline="") as fo:
        w = csv.writer(fo)
        w.writerow(["時刻", "開始秒", "終了秒", "パターンID", "型ID", "文字・内容", "SE型ID", "ズーム", "BGM停止", "字幕", "理由", "種類", "元の言葉"])
        w.writerows(r + [""] * (13 - len(r)) for r in rows)


if __name__ == "__main__":
    main()
