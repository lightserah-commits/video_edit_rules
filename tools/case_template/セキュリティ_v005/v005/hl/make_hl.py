#!/usr/bin/env python3
"""冒頭のハイライト（セキュリティについて v001。02 の P15）を作る。AI動画編集 v001 の make_hl.py を写して、構成（セリフ・文字・図形）をこの動画用に作り直した（2026-10-16）。
切り抜きのように本人（三上さん）のセリフを細かく切ってつなぎ、激しい文字グラフィックを乗せる。文字はセリフの書き起こしにせず、要約とつなぎの言葉で1本の流れにする
（小川さん「文字起こししすぎ。引きを作るように要約、前後が繋がる形に」）。答え（守り方＝情報を分ける・二段構え・変化に適応する）は見せない
（小川さん「ネタバレしなくて『え？』っていう興味付け」）。聞き手（創太くん）の声は使わない。攻撃のやり方は話した以上に具体的にしない。

流れ：サイバー攻撃のやり方 俺わかる → 暇だったら やる → セットで漏れると ヤバい → 守るための 穴チェックリスト → 悪用すれば → 攻撃リスト
      → 大企業でも やられる → AIの申請中に ハッキング → 世界のルールは 変わった
      → 「じゃあ、どう守ればいい？」→ ホワイトアウト → タイトルコール「年商25億AI社長が語る AI時代のセキュリティ 本当の守り方」（BGM なし・指鳴らし・2.6秒）
      → 白く飛んで本編へ（後半は Premiere に白から戻る素材）

  1. clips.tsv のセリフ（カメラの秒。入り・出は波形の谷で決め、asr_clips.py でクリップだけを文字起こしして確かめた）を ORDER の順に詰めて並べる
  2. 場面ごとの寄り（顔の位置は Mac の顔検出 _work/facedet）・文字（声の区間に合わせて出す）・図形・光を決めて hl.js に書く
  3. 背景のカメラの1コマずつを _work/bg/ に書き出し、page.html を Chrome で1コマずつ描く（render.mjs、並行数は NICE 前提で 2〜4）
  4. 声（話している所の大きさを -27dBFS にそろえる）・BGM（ダイジェスト用。声の間は下げ、問いの札から止める）・効果音を混ぜる
  5. 確認用の音つき mp4、Premiere 用の映像だけの mp4（コマ数をそろえる）・声・BGM・効果音の WAV（同じ長さ）・白から戻る素材・hl_manifest.json
  python3 make_hl.py [--plan] [--no-bg] [--no-render] [--only 10,200,...] [--jobs 3]
"""
import datetime
import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
EDIT = HERE.parent.parent
CAM = EDIT / "media" / "camera_CFR2997.mov"
ROOT = Path(os.path.expanduser("~/Desktop/video_edit_rules"))
SE_DIR = ROOT / "素材" / "SE"
BGM = ROOT / "素材" / "BGM" / "ダイジェスト用BGM.mp3"
LIVETYPE = Path(os.path.expanduser("~/Library/Application Support/Adobe/CoreSync/plugins/livetype/.r"))
W = HERE / "_work"
NAME = "sec_hl_v001"
OUT = HERE / f"{NAME}.mp4"
FPS_N, FPS_D = 30000, 1001
FPS = FPS_N / FPS_D
JOBS = int(sys.argv[sys.argv.index("--jobs") + 1]) if "--jobs" in sys.argv else 3

# ---------- 書体（Adobe Fonts は PostScript 名で探したファイル。環境設定・astra v007 と同じ） ----------
FONT_FILES = {
    "Toppan": LIVETYPE / ".42307.otf",      # 凸版文久見出しゴシック EB（地の文字）
    "SHSHeavy": LIVETYPE / ".41309.otf",    # 源ノ角ゴシック Heavy（叩きつける言葉）
    # "SHSerifH"（源ノ明朝 Heavy .33854.otf）は 2026-10-15 にこの Mac の Adobe Fonts から消えていた（このハイライトでは使わない）
}
JP, HV, MIN, LAT, HIRA = "'Toppan'", "'SHSHeavy'", "'SHSerifH'", "'Avenir Next Condensed'", "'Hiragino Sans'"
WHITE, YEL, RED, BLUE, GREEN, ORANGE = "#FFFFFF", "#FFD23F", "#FF2D46", "#4DA3FF", "#A8D84E", "#FF9A5A"
GOLD = ["#FFF6B8", "#FFD23F", "#E59A00"]       # 金色の文字（上から下へ）

# ---------- セリフの並び（id, この後の間（秒）） ----------
# 声と声の間は、クリップの頭と終わりに残した無音（波形の谷）と、ここの間と、コマ単位への切り上げの合計。_work/tune_gaps.py で、-50dB で見た
# 声と声の間が 0.15〜0.19秒（-45dB で見ても 0.16〜0.31秒）になる間を選んだ（_work/gaps.py で確かめる。小川さん dots のとき「間を思いっきり詰めて」）。
# H2→H3 は元の話が切れ目なしの続き（0.00秒）で、そのままだと 0.06秒に詰まるので 0.10秒あけた
ORDER = [("H1", 0.06), ("H2", 0.03), ("H3", 0.00), ("H4", 0.07), ("H5", 0.04), ("H6", 0.03), ("H7", 0.00), ("H8", 0.00), ("H9", 0.00)]   # セキュリティ：声と声の間（-50dB）が 0.11〜0.32秒（H3 の「け」は小さいので残した）
HOLD = 1.80                                    # 最後の言葉の後、問いの札を見せる秒
WO = 0.30                                      # 白く飛ぶまでの秒
TITLE_SRC, TITLE_SEC = 1303.95, 2.6           # タイトルコールの映像（通しのカメラの秒。21:44 の CTA の後、声なし 1303.3〜1306.2 で前を向いて口を閉じている）と長さ
# 顔の中心（カメラの画素。各クリップの 20%・50%・80% のコマを Mac の顔検出 _work/face.swift で測った平均 2026-10-16。_work/facedet）
FACE = {"TT": (1059, 372), "H1": (1000, 366), "H2": (998, 366), "H3": (1038, 365), "H4": (944, 361), "H5": (938, 359),
        "H6": (938, 347), "H7": (1031, 408), "H8": (1107, 371), "H9": (1063, 369)}

# 寄り（z の始め・終わり、顔を置く画面の位置）
FRAMING = {"wide": (1.08, 1.12, 1270, 440), "med": (1.30, 1.36, 1300, 450), "close": (1.62, 1.70, 1320, 470),
           "xclose": (2.20, 2.34, 1400, 480), "cen": (1.22, 1.28, 960, 430)}


def load_clips():
    rows = {}
    for ln in (HERE / "clips.tsv").read_text(encoding="utf-8").splitlines():
        if not ln.strip() or ln.startswith("#"):
            continue
        cid, a, b, txt = ln.split("\t")
        rows[cid] = (float(a), float(b), txt)
    return rows


CL = load_clips()
T = {}                      # クリップの置き場所（ハイライトの秒）
t = 0.0
for cid, gap in ORDER:
    t = math.ceil(t * FPS - 1e-6) / FPS      # コマの頭にそろえる（前のセリフと重ならないよう切り上げ）
    T[cid] = t
    a, b, _ = CL[cid]
    t += (b - a) + gap
T_WO = t + HOLD                                # 白く飛び始める
T_TITLE = math.ceil((T_WO + WO) * FPS - 1e-6) / FPS   # タイトルコールの始め（真っ白）
TOTAL = round((T_TITLE + TITLE_SEC) * FPS) / FPS
NFR = round(TOTAL * FPS)
IDS = [c for c, _ in ORDER]


def R(cid, rel):
    return T[cid] + rel


def end(cid):
    a, b, _ = CL[cid]
    return T[cid] + (b - a)


def nxt(cid):
    """次のセリフの始め（最後は白く飛ぶ所）。文字は次の場面まで残す（間の数コマだけ文字が消えないように）"""
    i = IDS.index(cid)
    return T[IDS[i + 1]] if i + 1 < len(IDS) else T_WO


def span(text, t0, t1):
    """文字ごとの出る時刻（t0〜t1 に等しく。空白は前の文字と同じ）"""
    n = len(text)
    return [round(t0 + (t1 - t0) * i / max(1, n), 4) for i in range(n)]


els, fx, ses, shots = [], [], [], []


def txt(text, t0, t1, x, y, size, font=JP, say=None, **kw):
    it = {"type": "txt", "text": text, "t0": t0, "t1": t1, "x": x, "y": y, "size": size, "font": font}
    it["weight"] = 800 if font in (LAT, HIRA) else 400
    if say:
        it["ct"] = span(text, *say)
        it["t0"] = min(it["t0"], say[0])
    it.update(kw)
    els.append(it)
    return it


def shot(cid, rel0, framing, **kw):
    z0, z1, tx, ty = FRAMING[framing]
    fxp, fyp = FACE[cid]
    s = {"t0": R(cid, rel0), "t1": None, "z0": z0, "z1": z1,
         "cx0": fxp - (tx - 960) / z0, "cy0": fyp - (ty - 540) / z0, "cx1": fxp - (tx - 960) / z1, "cy1": fyp - (ty - 540) / z1,
         "tint": "#0f3d66", "tintA": 0.32, "cid": cid}
    s.update(kw)
    shots.append(s)


def se(t0, name, db=0.0):
    ses.append((round(t0, 3), name, db))


def colors_of(text, parts):
    """text の中の部分文字列ごとに色を決める（{部分文字列: 色}）→ txt の colors（文字の番号 → 色）"""
    cs = {}
    for part, col in parts.items():
        i = text.index(part)
        for k in range(i, i + len(part)):
            cs[str(k)] = col
    return cs


# =================== 構成（文字は書き起こさず、要約とつなぎの言葉で1本の流れにする） ===================
# セキュリティについて（2026-10-16）。流れ：サイバー攻撃のやり方 俺わかる → 暇だったら やる → セットで漏れると ヤバい
#   → 守るための 穴チェックリスト → 悪用すれば → どこを攻撃すればいいか 攻撃リスト → 大企業でも やられる → AIの申請中に ハッキング
#   → 世界のルールは 変わった → 「じゃあ、どう守ればいい？」→ ホワイトアウト → タイトルコール「年商25億AI社長が語る AI時代のセキュリティ 本当の守り方」
#   答え（情報を分ける・二段構え・変化に適応する）は見せない。攻撃のやり方は話した以上に具体的にしない（リストの行は中身のないバー）。聞き手（創太くん）の声は使わない
# 言葉の時刻（クリップの頭からの秒）は asr_clips.py の語の時刻（_work/asr_clips.log）

# 1. サイバー攻撃のやり方 俺わかる
c = "H1"   # 声：俺やり方わかるけど（俺 0.00・や 0.20・方 0.40・わか 0.52・けど 0.84）
shot(c, 0, "med", tint="#4a0a12", tintA=0.40)
txt("サイバー攻撃のやり方", R(c, 0.00), nxt(c), 110, 250, 96, say=(R(c, 0.00), R(c, 0.50)), colors=colors_of("サイバー攻撃のやり方", {"サイバー攻撃": RED}))
txt("俺わかる", R(c, 0.52), nxt(c), 110, 800, 280, font=HV, color=WHITE, stroke=12, strokeColor=RED, anim="slam", from_=2.6, jolt=26,
    glow="rgba(255,45,70,.8)", echo=2, echoColor=WHITE)
fx += [{"type": "glitch", "t": R(c, 0.0), "d": 0.25, "amt": 0.8}, {"type": "flash", "t": R(c, 0), "d": 0.12, "a": 0.5},
       {"type": "punch", "t": R(c, 0.52), "d": 0.35, "amt": 0.08}, {"type": "shake", "t": R(c, 0.52), "d": 0.25, "amp": 18}]
se(R(c, 0.0), "syn:glitch", -11)
se(R(c, 0.52), "【ツッコミ】ドスッ.wav", -4)

# 2. 暇だったら やる
c = "H2"   # 声：俺も暇だったらやるもん（俺 0.06・暇 0.38・ら 0.76・や 0.84・もん 1.02）
shot(c, 0, "close", tint="#4a0a12", tintA=0.42)
txt("俺も暇だったら", R(c, 0.06), nxt(c), 110, 260, 120, say=(R(c, 0.06), R(c, 0.76)))   # 場面の頭から文字を出す（「暇」からだと 0.3秒文字なし）
txt("やる", R(c, 0.84), nxt(c), 110, 780, 400, font=HV, color=RED, stroke=14, strokeColor=WHITE, anim="slam", from_=3.0, jolt=32,
    glow="rgba(255,45,70,.85)", echo=3, echoColor=WHITE, rgb=0.25)
fx += [{"type": "glitch", "t": R(c, 0.84), "d": 0.3, "amt": 0.9}, {"type": "punch", "t": R(c, 0.84), "d": 0.35, "amt": 0.09},
       {"type": "shake", "t": R(c, 0.84), "d": 0.3, "amp": 24}]
se(R(c, 0.06), "syn:pop", -10)
se(R(c, 0.84), "【汎用,太鼓】太鼓(ドドン).wav", -5)

# 3. セットで漏れると ヤバい（メアド・パスワード・クレカ・住所の札が1つにまとまって、赤く漏れる）
c = "H3"   # 声：セットで漏れるとやばいわけ（セ 0.00・で 0.36・漏 0.48・と 0.76・や 0.88・ばい 1.00・わけ 1.18〜1.28）
shot(c, 0, "med", tint="#1a0a14", tintA=0.42)
txt("セットで漏れると", R(c, 0.00), nxt(c), 110, 200, 100, say=(R(c, 0.00), R(c, 0.80)), colors=colors_of("セットで漏れると", {"セット": YEL}))
els.append({"type": "dataset", "t0": R(c, 0.0), "t1": nxt(c), "labels": ["メアド", "パスワード", "クレカ", "住所"], "ts": [R(c, x) for x in (0.0, 0.12, 0.24, 0.36)],
            "tj": R(c, 0.50), "tl": R(c, 0.88), "x": 110, "y": 300, "cw": 236, "ch": 108, "gap": 12, "fs": 42})
txt("ヤバい", R(c, 0.88), nxt(c), 110, 800, 320, font=HV, color=WHITE, stroke=14, strokeColor=RED, anim="slam", from_=2.8, jolt=30,
    glow="rgba(255,45,70,.85)", echo=3, echoColor=WHITE)
fx += [{"type": "punch", "t": R(c, 0.88), "d": 0.35, "amt": 0.09}, {"type": "shake", "t": R(c, 0.88), "d": 0.3, "amp": 22},
       {"type": "flash", "t": R(c, 0.88), "d": 0.12, "a": 0.35, "color": "#ffb3bd"}]
for x in (0.0, 0.12, 0.24, 0.36):
    se(R(c, x), "syn:tick", -9)
se(R(c, 0.50), "syn:pop", -10)
se(R(c, 0.88), "【汎用,太鼓】太鼓(ドン).wav", -5)
se(R(c, 0.90), "syn:error", -13)

# 4. 守るための 穴チェックリスト（チェックの一覧。H6 の「攻撃」で裏返って攻撃リストになる）
c = "H4"   # 声：逆に言うとこの穴チェックリストを（逆 0.06・と 0.50・この 0.58・穴 0.76・チ 0.90・ック 1.14・リ 1.28・スト 1.42・を 1.64）
shot(c, 0, "med", tint="#0f3d66", tintA=0.40)
txt("守るための", R(c, 0.06), nxt(c), 110, 190, 92, say=(R(c, 0.06), R(c, 0.50)))
txt("穴チェックリスト", R(c, 0.76), nxt(c), 110, 320, 112, font=HV, color=BLUE, stroke=8, strokeColor=WHITE, anim="slam", from_=2.2, jolt=20,
    glow="rgba(77,163,255,.8)", echo=2, echoColor=WHITE)
els.append({"type": "holes", "t0": R(c, 0.58), "t1": T["H7"], "x": 110, "y": 410, "w": 760, "rh": 66, "n": 4, "fs": 48,
            "title": "守るための穴チェックリスト", "title2": "攻撃リスト", "ts": [R(c, x) for x in (0.90, 1.05, 1.20, 1.35)], "tf": R("H6", 0.24)})
fx += [{"type": "punch", "t": R(c, 0.76), "d": 0.3, "amt": 0.06}, {"type": "flash", "t": R(c, 0.76), "d": 0.12, "a": 0.3, "color": "#bfe0ff"}]
se(R(c, 0.06), "syn:whoosh", -12)
se(R(c, 0.76), "syn:hit", -7)
for x in (0.90, 1.05, 1.20, 1.35):
    se(R(c, x), "syn:tick", -10)

# 5. 悪用すれば
c = "H5"   # 声：悪用すれば（悪 0.00・用 0.30・す 0.46・ば 0.74）
shot(c, 0, "close", tint="#4a0a12", tintA=0.42)
txt("悪用すれば", R(c, 0.00), nxt(c), 110, 900, 210, font=HV, color=WHITE, stroke=12, strokeColor=RED, anim="slam", from_=2.6, jolt=26,
    glow="rgba(255,45,70,.85)", echo=2, echoColor=WHITE, rgb=0.2)
fx += [{"type": "glitch", "t": R(c, 0.0), "d": 0.3, "amt": 0.9}, {"type": "shake", "t": R(c, 0.02), "d": 0.25, "amp": 20}]
se(R(c, 0.0), "syn:glitch", -11)
se(R(c, 0.02), "【ツッコミ】ドスッ.wav", -5)

# 6. どこを攻撃すればいいか 攻撃リスト（「攻撃」で一覧が裏返って赤くなる）
c = "H6"   # 声：どこ攻撃すればいいかリストなのよ（こ 0.12・攻 0.24・撃 0.40・いい 0.82・か 0.92・リ 1.08・スト 1.28・なのよ 1.46〜1.72）
shot(c, 0, "med", tint="#4a0a12", tintA=0.42)
txt("どこを攻撃すればいいか", R(c, 0.00), nxt(c), 110, 250, 90, say=(R(c, 0.00), R(c, 0.92)), colors=colors_of("どこを攻撃すればいいか", {"攻撃": RED}))
txt("攻撃リスト", R(c, 1.08), nxt(c), 110, 900, 230, font=HV, color=RED, stroke=10, strokeColor=WHITE, anim="slam", from_=2.8, jolt=30,
    glow="rgba(255,45,70,.9)", echo=3, echoColor=WHITE, rgb=0.25)
fx += [{"type": "flash", "t": R(c, 0.24), "d": 0.12, "a": 0.35, "color": "#ff6070"}, {"type": "punch", "t": R(c, 1.08), "d": 0.35, "amt": 0.09},
       {"type": "shake", "t": R(c, 1.08), "d": 0.3, "amp": 24}]
se(R(c, 0.24), "syn:whoosh", -11)
se(R(c, 0.28), "syn:error", -13)
se(R(c, 1.08), "【汎用,太鼓】太鼓(ドドン).wav", -5)

# 7. 大企業でも やられる
c = "H7"   # 声：大企業でもやられるこれがポイント（大 0.00・企 0.26・業 0.50・でも 0.68・や 0.90・れる 1.10・これ 1.20・ポ 1.50）
shot(c, 0, "close", tint="#2a2a2a", tintA=0.40)
txt("大企業でも", R(c, 0.00), nxt(c), 110, 250, 140, say=(R(c, 0.00), R(c, 0.70)), colors=colors_of("大企業でも", {"大企業": YEL}))
txt("やられる", R(c, 0.90), nxt(c), 110, 840, 280, font=HV, color=WHITE, stroke=14, strokeColor=RED, anim="slam", from_=2.8, jolt=30,
    glow="rgba(255,45,70,.85)", echo=3, echoColor=WHITE)
els.append({"type": "burst", "t0": R(c, 0.89), "t1": R(c, 1.45), "x": 560, "y": 820, "r": 300, "ringMax": 1.5, "color": RED, "color2": WHITE})
fx += [{"type": "punch", "t": R(c, 0.90), "d": 0.4, "amt": 0.10}, {"type": "shake", "t": R(c, 0.90), "d": 0.3, "amp": 24},
       {"type": "flash", "t": R(c, 0.90), "d": 0.12, "a": 0.4, "color": "#ffb3bd"}]
se(R(c, 0.00), "syn:whoosh", -12)
se(R(c, 0.90), "【汎用,太鼓】太鼓(ドン).wav", -5)
se(R(c, 0.92), "syn:boom", -11)

# 8. AIの申請中に ハッキング（承認待ちの札 → 赤く割り込まれる・警告の帯）
c = "H8"   # 声：AIの申請してる間にハッキングされる（AI 0.00・の 0.28・申 0.46・請 0.68・間 1.14・に 1.26・ハ 1.40・ング 1.80・される 1.90〜2.06）
shot(c, 0, "med", tint="#0f2a4a", tintA=0.42)
txt("AIの申請中に", R(c, 0.00), nxt(c), 110, 190, 112, say=(R(c, 0.00), R(c, 1.26)), colors=colors_of("AIの申請中に", {"AI": ORANGE}))
els.append({"type": "pending", "t0": R(c, 0.46), "t1": nxt(c), "th": R(c, 1.40), "x": 110, "y": 290, "w": 820, "h": 180, "fs": 56,
            "label": "AI利用の申請 承認待ち", "label2": "侵入を検知"})
txt("ハッキング", R(c, 1.40), nxt(c), 110, 860, 240, font=HV, color=RED, stroke=10, strokeColor=WHITE, anim="slam", from_=2.8, jolt=30,
    glow="rgba(255,45,70,.9)", echo=3, echoColor=WHITE, rgb=0.3)
els.append({"type": "warn", "t0": R(c, 1.40), "t1": nxt(c), "y": 30, "label": "WARNING", "label2": "UNAUTHORIZED ACCESS"})
fx += [{"type": "glitch", "t": R(c, 1.40), "d": 0.4, "amt": 1.0}, {"type": "punch", "t": R(c, 1.40), "d": 0.35, "amt": 0.09},
       {"type": "shake", "t": R(c, 1.40), "d": 0.3, "amp": 24}]
se(R(c, 0.46), "syn:tick", -10)
se(R(c, 1.40), "syn:glitch", -10)
se(R(c, 1.42), "【汎用,太鼓】太鼓(カカッ).wav", -5)
se(R(c, 1.46), "syn:error", -11)

# 9. 世界のルールは 変わった（青と金）
c = "H9"   # 声：もう世界のルールは変わりました（もう 0.10・世界 0.34・の 0.54・ル 0.66・は 0.84・変 0.92・わ 1.04・りました 1.12）
shot(c, 0, "med", tint="#0a2f6b", tintA=0.40)
H9_OUT = end(c) + 0.02                    # 問いの札が出る前に文字を消す（前の案件の最後のセリフと同じ）
txt("もう世界のルールは", R(c, 0.10), H9_OUT, 110, 250, 112, say=(R(c, 0.10), R(c, 0.84)), exit="fade", ed=0.12,   # 「もう」から出す（場面の頭の文字なしを短く）
    colors=colors_of("もう世界のルールは", {"世界のルール": BLUE}))
txt("変わった", R(c, 0.92), H9_OUT, 110, 820, 300, exit="fade", ed=0.12, font=HV, grad=GOLD, anim="slam", from_=2.6, echo=3, echoColor=YEL, jolt=30,
    glow="rgba(255,200,40,.65)")
els.append({"type": "burst", "t0": R(c, 0.91), "t1": R(c, 1.45), "x": 560, "y": 800, "r": 300, "ringMax": 1.4, "color": YEL, "color2": WHITE})
els.append({"type": "sweep", "t0": R(c, 0.95), "t1": R(c, 1.40), "y0": 640, "y1": 1000, "a": 0.6})
fx += [{"type": "punch", "t": R(c, 0.92), "d": 0.4, "amt": 0.10}, {"type": "shake", "t": R(c, 0.92), "d": 0.3, "amp": 22},
       {"type": "flash", "t": R(c, 0.92), "d": 0.14, "a": 0.45, "color": "#fff3c4"}]
se(R(c, 0.34), "syn:whoosh", -12)
se(R(c, 0.92), "【キラッ✨,長い】ピラリーーン.wav", -9)
se(R(c, 0.94), "【汎用,太鼓】太鼓(ドドン).wav", -6)

# 問いの札（答えは出さない）
Q = "じゃあ、どう守ればいい？"
T_Q = end(c) + 0.14                       # 声が止まって 0.14秒後。ここで BGM も止める。背景はこのコマで止める（bg_frames）
txt(Q, T_Q, T_TITLE, 960, 935, 100, align="c", anim="rise", say=(T_Q, T_Q + 0.42), colors=colors_of(Q, {"どう守れば": YEL}),
    box={"color": "rgba(0,0,0,0.65)", "px": 0.35, "py": 0.22})
fx.append({"type": "dim", "t0": T_Q, "t1": T_TITLE, "a": 0.25, "fi": 0.15})
se(T_Q, "syn:whoosh", -12)

# ホワイトアウト → タイトルコール（シャーン → 指鳴らしで切り替え・BGM なし・2.6秒）
fx.append({"type": "whiteout", "t0": T_WO, "t1": T_TITLE, "t2": T_TITLE + 0.28})
se(T_WO - 0.05, "【汎用,鈴】シャーン.wav", -8)
se(T_TITLE, "パチンっ指鳴らし.wav", -2)
fxp, fyp = FACE["TT"]
shots.append({"t0": T_TITLE, "t1": None, "z0": 1.14, "z1": 1.24, "cx0": fxp - (1300 - 960) / 1.14, "cy0": fyp - (470 - 540) / 1.14,
              "cx1": fxp - (1300 - 960) / 1.24, "cy1": fyp - (470 - 540) / 1.24, "tint": "#1d5cff", "tintA": 0.45, "cid": "TT",
              "shade": "none", "filter": "contrast(1.15) saturate(0.6) brightness(0.8)"})
fx.append({"type": "dim", "t0": T_TITLE, "t1": TOTAL, "a": 0.5})
# 本編へのホワイトアウト（タイトルの終わり 0.8秒で白く飛び、挨拶の頭 0.83秒で白から戻る）。前半はここで描き、後半は Premiere に白の素材を置く
WO_OUT = 0.80
fx.append({"type": "whiteout", "t0": TOTAL - WO_OUT, "t1": TOTAL - 0.5 / FPS, "t2": TOTAL + 5})
els.append({"type": "particles", "t0": T_TITLE, "t1": TOTAL})
tt0 = T_TITLE
TT1 = "年商25億AI社長が語る"
txt(TT1, tt0 + 0.08, TOTAL, 960, 290, 84, align="c", say=(tt0 + 0.08, tt0 + 0.40))
TT2 = "AI時代のセキュリティ"
txt(TT2, tt0 + 0.46, TOTAL, 960, 545, 150, font=HV, color=BLUE, anim="slam", align="c",
    glow="rgba(77,163,255,.9)", echo=3, drift=0.02, colors=colors_of(TT2, {"AI": ORANGE}))
txt("本当の守り方", tt0 + 1.10, TOTAL, 960, 820, 200, font=HV, color=YEL, anim="slam", from_=2.6, align="c", glow="rgba(255,210,63,.65)",
    echo=2, drift=0.02)
els.append({"type": "sweep", "t0": tt0 + 1.45, "t1": tt0 + 1.95, "y0": 420, "y1": 960, "a": 0.6})
fx += [{"type": "punch", "t": tt0 + 0.46, "d": 0.4, "amt": 0.06}, {"type": "flash", "t": tt0 + 0.46, "d": 0.12, "a": 0.4, "color": "#bfe0ff"},
       {"type": "punch", "t": tt0 + 1.10, "d": 0.4, "amt": 0.05}, {"type": "shake", "t": tt0 + 1.10, "d": 0.2, "amp": 10}]
se(tt0 + 0.46, "syn:hit", -5)
se(tt0 + 0.50, "【キラッ✨,短い】キランッッ!!.wav", -9)
se(tt0 + 1.10, "【汎用,太鼓】太鼓(ドン).wav", -5)

# 文字は声より少し（LEAD 秒）先に出す（カットの頭が文字なしの映像だけにならないように。場面の頭より前には出さない）
LEAD = 0.05
shots.sort(key=lambda s: s["t0"])
_starts = [s_["t0"] for s_ in shots]


def _lead(t0):
    st = max([x for x in _starts if x <= t0 + 1e-6] or [0.0])
    return max(st, t0 - LEAD)


for e in els:
    if e["type"] == "txt":
        if "ct" in e:
            e["ct"] = [_lead(x) for x in e["ct"]]
        e["t0"] = _lead(e["t0"])
    elif e["type"] in ("quote", "memo"):
        e["ct"] = [_lead(x) for x in e["ct"]]
        e["t0"] = _lead(e["t0"])
    elif e["type"] == "chat":
        for L in e["lines"]:
            L["ct"] = [_lead(x) for x in L["ct"]]
# 場面の終わり＝次の場面の始め。カットが変わるたびに、一瞬寄った所から戻る
for s_ in shots[1:]:
    fx.append({"type": "settle", "t": s_["t0"], "d": 0.28, "amt": 0.055})
for i, s in enumerate(shots):
    s["t1"] = shots[i + 1]["t0"] if i + 1 < len(shots) else TOTAL
for e in els:
    if "from_" in e:
        e["from"] = e.pop("from_")
    if "colors" in e:
        e["colors"] = {int(k): v for k, v in e["colors"].items()}
        e["colors"] = [e["colors"].get(i) for i in range(len(e["text"]))]

# BGM：最後のセリフが終わった所で止める（声が止まった所で音楽も止まり、問いの札→白→タイトルコールは BGM なし。04 の bgm：指鳴らし→タイトルコールは BGM なし）
BGM_END = end("H9") + 0.03
VOICE_ACTIVE = -27.0       # 声の話している所の大きさ（astra v007・環境設定と同じ）
BGM_DB, SE_TRIM = -15.0, -4.0
BGM_START = 0.365          # ダイジェスト用 BGM の拍（0.415 秒・1拍 0.5224 秒）が 0.05 秒に来るように（astra v007・環境設定と同じ）
# 声が 0.5秒しかない「勝った」は、BGM の山と重なって声との差が 4.7dB に縮まる（他は 9〜13dB）ので、その間だけ BGM をなめらかに下げる（前後 0.05秒で上下）
# セキュリティ：H9「もう世界のルールは変わりました」は声が小さく（+14dB で頭打ち）、BGM が盛り上がる所と重なって声との差が 4.9dB に縮む（他は 9.6〜13.8dB）ので、その間だけ BGM を 6dB 下げる
BGM_DIPS = [(T["H9"] - 0.05, end("H9") + 0.10, -6.0)]


def run(cmd, **kw):
    subprocess.run([str(x) for x in cmd], check=True, **kw)


def write_page():
    css = "".join(f"@font-face {{ font-family: '{k}'; src: url('file://{quote(str(v))}'); }}\n" for k, v in FONT_FILES.items())
    (HERE / "fonts.css").write_text(css, encoding="utf-8")
    bounds = {s_["t0"] for s_ in shots}
    bounds |= {e["t0"] for e in els if e["type"] == "card"} | {e["t1"] for e in els if e["type"] == "card"}
    bounds |= {e["t1"] for e in els if e["type"] == "txt" and e.get("exit", "cut") == "cut"}
    hl = {"fps": FPS, "N": NFR, "bgDir": "file://" + quote(str(W / "bg")), "shots": shots, "els": els, "fx": fx, "bounds": sorted(bounds),
          "fontsToLoad": ["400 100px 'Toppan'", "400 100px 'SHSHeavy'", "800 100px 'Avenir Next Condensed'",
                          "800 100px 'Hiragino Sans'", "700 100px 'Hiragino Sans'"]}
    (HERE / "hl.js").write_text("window.HL = " + json.dumps(hl, ensure_ascii=False) + ";\n", encoding="utf-8")


def bg_frames():
    """背景：場面ごとにカメラの1コマずつを書き出す（ハイライトのコマ番号で）。間はクリップの続きの映像"""
    d = W / "bg"
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    starts = [(T[cid], cid) for cid, _ in ORDER] + [(T_TITLE, "TT")]
    for i, (t0, cid) in enumerate(starts):
        t1 = starts[i + 1][0] if i + 1 < len(starts) else TOTAL
        f0, f1 = round(t0 * FPS), round(t1 * FPS)
        a = TITLE_SRC if cid == "TT" else CL[cid][0]
        run(["nice", "-n", "10", "ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{a:.4f}", "-i", CAM, "-frames:v", f1 - f0, "-q:v", "3",
             "-start_number", f0, str(d / "%05d.jpg")])
    # 問いの札（T_Q）から白く飛ぶまでは、背景を止める。続きの映像だと、声が止まっているのに口が動いて見える（三上さんは次の言葉を話し続けている）
    fq = round(T_Q * FPS)
    for f in range(fq + 1, round(T_TITLE * FPS)):
        shutil.copyfile(d / f"{fq:05d}.jpg", d / f"{f:05d}.jpg")


# ---------- 音 ----------
def synth():
    """効果音を ffmpeg で作る（素材/SE に無い、ドン・シュッ・グリッチ・ピッ・ポン・ブー・上がっていく音。astra v007・環境設定と同じ）"""
    s = W / "sfx"
    s.mkdir(exist_ok=True)
    defs = {
        "hit": "aevalsrc='0.95*sin(2*PI*(70*t-55*t*t))*exp(-9*t)+0.35*(random(0)*2-1)*exp(-55*t)':s=48000:d=0.55,lowpass=f=6000",
        "boom": "aevalsrc='1.0*sin(2*PI*(52*t-30*t*t))*exp(-4.5*t)+0.5*(random(0)*2-1)*exp(-14*t)':s=48000:d=1.1,lowpass=f=3500",
        "whoosh": "anoisesrc=d=0.42:c=pink:a=0.9:r=48000,highpass=f=350,lowpass=f=6500,afade=t=in:st=0:d=0.30:curve=exp,afade=t=out:st=0.30:d=0.12",
        "glitch": "aevalsrc='0.45*sgn(sin(2*PI*(220+660*mod(floor(t*28),4))*t))*lt(mod(t,0.07),0.045)':s=48000:d=0.28,acrusher=bits=6:samples=6:mix=1",
        "tick": "aevalsrc='0.6*sin(2*PI*2400*t)*exp(-60*t)':s=48000:d=0.07",
        "pop": "aevalsrc='0.7*sin(2*PI*(700*t+2600*t*t))*exp(-26*t)':s=48000:d=0.16",
        "error": "aevalsrc='0.35*sgn(sin(2*PI*140*t))*lt(mod(t,0.13),0.09)':s=48000:d=0.4,lowpass=f=2600",
        "riser": "anoisesrc=d=0.62:c=white:a=0.7:r=48000,highpass=f=1200,afade=t=in:st=0:d=0.6:curve=exp",
    }
    for k, f in defs.items():
        run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", f, "-ac", "2", "-ar", "48000", s / f"{k}.wav"])


def active_db(path):
    """話している所（50ミリ秒ごとの大きさが、そのクリップの一番大きい所から 20dB 以内）の平均の大きさ（dBFS）"""
    import array
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-ac", "1", "-ar", "48000", "-f", "s16le", "-"], capture_output=True).stdout
    a = array.array("h")
    a.frombytes(raw)
    n = 2400
    pw = [sum(v * v for v in a[i:i + n]) / n / 32768 ** 2 for i in range(0, len(a) - n, n)]
    db = [10 * math.log10(p + 1e-12) for p in pw]
    top = max(db)
    act = [p for p, d in zip(pw, db) if d > top - 20]
    return 10 * math.log10(sum(act) / len(act))


def audio():
    synth()
    ins, filt, vl, sl = [], [], [], []
    ins += ["-ss", f"{BGM_START:.3f}", "-i", BGM]
    dips = "".join(f"volume=eval=frame:volume='1+({10 ** (g / 20):.4f}-1)*clip((t-{a0:.3f})/0.05,0,1)*clip(({a1:.3f}-t)/0.05,0,1)'," for a0, a1, g in BGM_DIPS)
    filt.append(f"[0:a]atrim=0:{BGM_END:.3f},asetpts=PTS-STARTPTS,aformat=channel_layouts=stereo,aresample=48000,volume={BGM_DB}dB,{dips}"
                f"afade=t=out:st={BGM_END - 0.10:.3f}:d=0.10,apad=whole_dur={TOTAL:.3f}[bgm]")
    k = 1
    gains = {}
    for cid, _ in ORDER:
        a, b, _ = CL[cid]
        clip = W / f"voice_{cid}.wav"
        run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", CAM, "-vn", "-ac", "2", "-ar", "48000",
             "-af", f"afade=t=in:d=0.008,afade=t=out:st={b - a - 0.012:.3f}:d=0.012", clip])
        g = max(-3.0, min(14.0, VOICE_ACTIVE - active_db(clip)))   # 話している所の大きさをそろえる
        gains[cid] = round(g, 1)
        d = int(round(T[cid] * 1000))
        ins += ["-i", clip]
        filt.append(f"[{k}:a]volume={g:.1f}dB,adelay={d}|{d},apad=whole_dur={TOTAL:.3f}[v{k}]")
        vl.append(f"[v{k}]")
        k += 1
    for t0, name, db in ses:
        src = W / "sfx" / f"{name[4:]}.wav" if name.startswith("syn:") else SE_DIR / name
        ins += ["-i", src]
        d = int(round(max(0, t0) * 1000))
        filt.append(f"[{k}:a]aformat=channel_layouts=stereo,aresample=48000,volume={db + SE_TRIM:.1f}dB,adelay={d}|{d}[s{k}]")
        sl.append(f"[s{k}]")
        k += 1
    filt.append(f"{''.join(vl)}amix=inputs={len(vl)}:normalize=0:duration=longest,asplit=3[vox][key][vst]")
    filt.append("[bgm][key]sidechaincompress=threshold=0.01:ratio=6:attack=8:release=240:makeup=1[duck]")
    filt.append(f"{''.join(sl)}amix=inputs={len(sl)}:normalize=0:duration=longest,asplit=2[sfx][sst]")
    filt.append("[duck]asplit=2[bg1][bst]")
    filt.append("[bg1][vox][sfx]amix=inputs=3:normalize=0:duration=first,alimiter=limit=0.93:level=false[mix]")
    run(["ffmpeg", "-nostdin", "-v", "error", "-y", *ins, "-filter_complex", ";".join(filt),
         "-map", "[mix]", "-t", f"{TOTAL:.3f}", W / "mix.wav",
         "-map", "[vst]", "-t", f"{TOTAL:.3f}", W / "stem_voice.wav",
         "-map", "[bst]", "-t", f"{TOTAL:.3f}", W / "stem_bgm.wav",
         "-map", "[sst]", "-t", f"{TOTAL:.3f}", W / "stem_se.wav"])
    return gains


def main():
    W.mkdir(exist_ok=True)
    write_page()
    plan = {"total": TOTAL, "frames": NFR, "t_wo": T_WO, "t_title": T_TITLE, "t_q": T_Q,
            "clips": [{"id": cid, "src": CL[cid][:2], "at": round(T[cid], 3), "text": CL[cid][2]} for cid, _ in ORDER],
            "se": ses, "bgm_end": BGM_END}
    print("尺", round(TOTAL, 3), "秒", NFR, "コマ（問いの札", round(T_Q, 2), "・白く飛ぶ", round(T_WO, 2), "・タイトル", round(T_TITLE, 2), "）")
    for cid, _ in ORDER:
        print(f"  {cid:4s} {T[cid]:6.2f}–{end(cid):6.2f}  {CL[cid][2]}")
    if "--plan" in sys.argv:
        json.dump(plan, open(W / "plan.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        return
    if "--no-bg" not in sys.argv:
        bg_frames()
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    if "--no-render" not in sys.argv:
        frames = W / ("check_frames" if only else "frames")
        if not only and frames.exists():
            shutil.rmtree(frames)
        cmd = ["nice", "-n", "10", "node", HERE / "render.mjs", HERE / "page.html", frames, NFR, JOBS]
        if only:
            cmd += ["--only", only]
        run(cmd)
        if only:
            return
    plan["voice_gain_db"] = audio()
    json.dump(plan, open(W / "plan.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    run(["nice", "-n", "10", "ffmpeg", "-nostdin", "-v", "error", "-y", "-framerate", f"{FPS_N}/{FPS_D}", "-i", W / "frames" / "%05d.jpg", "-i", W / "mix.wav",
         "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-crf", "15", "-preset", "slow", "-pix_fmt", "yuv420p", "-r", f"{FPS_N}/{FPS_D}",
         "-c:a", "aac", "-b:a", "320k", "-frames:v", NFR, "-t", f"{TOTAL:.4f}", OUT])
    print("→", OUT)
    # Premiere 用：映像だけ（音は声・BGM・効果音を別々に置く）と、挨拶の頭に重ねる「白から戻る」素材（透明つき）
    vid = HERE / f"{NAME}_{NFR}f_映像.mp4"
    run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", OUT, "-an", "-c:v", "copy", "-frames:v", NFR, vid])
    stems = {}
    for k, jp in (("voice", "声"), ("bgm", "BGM"), ("se", "効果音")):           # ハイライトの長さ（TOTAL）ちょうどにそろえる
        stems[k] = HERE / f"{NAME}_{NFR}f_{jp}.wav"
        run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", W / f"stem_{k}.wav", "-af", f"apad=whole_dur={TOTAL:.4f}", "-t", f"{TOTAL:.4f}",
             "-c:a", "pcm_s16le", stems[k]])
    n_in = round(0.83 * FPS)
    wo = HERE / "ホワイトアウト_白から戻る_0.83秒.mov"
    run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=white:s=1920x1080:r={FPS_N}/{FPS_D}", "-frames:v", n_in,
         "-vf", f"format=rgba,fade=t=out:st=0:n={n_in}:alpha=1", "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le", wo])
    # 本編の組み立て（cuts_plan_v001.py・build_v001.py）が読む目録。frames だけ本編を後ろへずらし、映像・音3本を 0 から、白から戻る素材を挨拶の頭に置く
    man = {"frames": NFR, "fps": f"{FPS_N}/{FPS_D}", "seconds": round(TOTAL, 4), "video": str(vid), "voice": str(stems["voice"]),
           "bgm": str(stems["bgm"]), "se": str(stems["se"]), "whiteout": str(wo), "whiteout_frames": n_in, "check_mp4": str(OUT),
           "made": datetime.datetime.now().isoformat(timespec="seconds"), "note": "冒頭ハイライト（P15）。hl/README.md"}
    json.dump(man, open(HERE / "hl_manifest.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("→ Premiere 用の映像・音3本・白から戻る素材・hl_manifest.json")


if __name__ == "__main__":
    main()
