#!/usr/bin/env python3
"""冒頭のハイライト（環境設定について v001。02 の P15）を作る。astra v007 の下書きB（v007/hl/make_hl.py）を写して、中身をこの動画用に作り直した。
2026-10-03。切り抜きのように本人のセリフを細かく切ってつなぎ、激しい文字グラフィックを乗せる。文字はセリフの書き起こしにせず、
要約とつなぎの言葉で1本の流れにする（小川さん「文字起こししすぎ。引きを作るように要約、前後が繋がる形に」）。

流れ：AI好きほどムダだらけ → 流行りの Orca・Obsidian → ガチでいらない
      → じゃあ年商25億の社長は？ AIのスキルはほぼナシ → 返信が来たら AIが勝手にまた動き出す
      （v003：中身はただのメモ・しかも毎日腐っていく・やってるのは環境構築だけ を外した。小川さん「答えまで見せるとネタバレ」）
      → ヤバくない？ → しかも社長と同じ環境がワンタップ → 「じゃあ、一番大事な環境設定とは？」→ ホワイトアウト
      → タイトルコール「年商25億AI社長の AI環境設定 全公開」（BGM なし・指鳴らし・2.6秒）→ 白く飛んで本編へ（後半は Premiere に白から戻る素材）

  1. clips.tsv のセリフ（カメラの秒。入り・出は波形の谷で決め、asr_clips.py でクリップだけを文字起こしして確かめた）を ORDER の順に詰めて並べる
  2. 場面ごとの寄り（顔の位置は Mac の顔検出 _work/facedet）・文字（声の区間に合わせて1字ずつ）・図形・光を決めて hl.js に書く
  3. 背景のカメラの1コマずつを _work/bg/ に書き出し、page.html を Chrome で1コマずつ描く（render.mjs、4本並行）
  4. 声（話している所の大きさを -27dBFS にそろえる）・BGM（ダイジェスト用。声の間は下げ、「ヤバくない？」は止める）・効果音を混ぜる
  5. 確認用の音つき mp4、Premiere 用の映像だけの mp4（コマ数をそろえる）・声・BGM・効果音の WAV（同じ長さ）・白から戻る素材・hl_manifest.json
  python3 make_hl.py [--plan] [--no-bg] [--no-render] [--only 10,200,...]
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
NAME = "kankyo_hl_v004"
OUT = HERE / f"{NAME}.mp4"
FPS_N, FPS_D = 30000, 1001
FPS = FPS_N / FPS_D

# ---------- 書体（Adobe Fonts は PostScript 名で探したファイル。astra v007 と同じ） ----------
FONT_FILES = {
    "Toppan": LIVETYPE / ".42307.otf",      # 凸版文久見出しゴシック EB（地の文字）
    "SHSHeavy": LIVETYPE / ".41309.otf",    # 源ノ角ゴシック Heavy（叩きつける言葉）
    "SHSerifH": LIVETYPE / ".33854.otf",    # 源ノ明朝 Heavy
}
JP, HV, MIN, LAT, HIRA = "'Toppan'", "'SHSHeavy'", "'SHSerifH'", "'Avenir Next Condensed'", "'Hiragino Sans'"
WHITE, YEL, RED, BLUE, GREEN = "#FFFFFF", "#FFD23F", "#FF2D46", "#4DA3FF", "#A8D84E"

# ---------- セリフの並び（id, この後の間（秒）） ----------
# v002（2026-10-04 小川さん、dots のハイライト「間を思いっきり詰めて」を当てはめる）：声と声の間を 0.14〜0.33秒 → 0.10〜0.21秒に詰めた。
#   v001 の間：H1 0.06・H3 0.10・H4 0.10・H5 0.12・H7 0.10・H8 0.04・H9 0.08（クリップの頭と終わりの無音 0.02〜0.15秒は波形の谷なのでそのまま）
# v003（2026-10-04 小川さん、画面収録の指示）：ネタバレを見せない。H4「ただのメモ」・H5「どんどん毎日毎日腐るのよ」（Obsidian がいらない答え）と
#   H7「環境構築だけ終わりだ」（「俺スキルほぼない」だけで十分引きになる）を外し、ガチでいらない → 俺スキル ほぼない → AIがまた動き始める とつなぐ。
#   H6b の後の間は、外した H7 の後と同じ 0.04秒
ORDER = [("H1", 0.0), ("H2", 0), ("H3", 0.04), ("H6a", 0), ("H6b", 0.04), ("H8", 0.0), ("H9", 0.02), ("H10", 0)]
HOLD = 1.00                                    # 最後の言葉の後、「じゃあ、一番大事な環境設定とは？」を見せる秒
WO = 0.30                                      # 白く飛ぶまでの秒
TITLE_SRC, TITLE_SEC = 577.0, 2.6              # タイトルコールの映像（カメラの秒。顎に手を当てて画面を見て考えている・声なし 575.4〜582.7）と長さ
# 顔の中心（カメラの画素。各クリップの真ん中のコマを Mac の顔検出 _work/facedet で測った 2026-10-03）
FACE = {"TT": (1183, 363), "H1": (1093, 375), "H2": (1170, 372), "H3": (1131, 358), "H4": (1142, 400), "H5": (1106, 399),
        "H6a": (1029, 365), "H6b": (1041, 363), "H7": (1202, 377), "H8": (1202, 388), "H9": (1225, 392), "H10": (1148, 389)}
# 寄り（z の始め・終わり、顔を置く画面の位置）
FRAMING = {"wide": (1.08, 1.12, 1270, 440), "med": (1.30, 1.36, 1300, 450), "close": (1.62, 1.70, 1320, 470),
           "xclose": (2.20, 2.36, 1150, 470), "cen": (1.22, 1.28, 960, 430)}


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


# =================== 構成（文字は書き起こさず、要約とつなぎの言葉で1本の流れにする） ===================
# 1. 主張：AI好きほどムダだらけ
c = "H1"   # 声：AI好きなやつほど無駄なことしてるよ
shot(c, 0, "med")
txt("AI好きな人ほど", R(c, 0.06), nxt(c), 110, 400, 124, say=(R(c, 0.06), R(c, 1.20)), colors={"0": YEL, "1": YEL})
txt("ムダだらけ", R(c, 1.62), nxt(c), 110, 660, 250, font=HV, anim="slam", colors={"0": RED, "1": RED}, echo=2, jolt=26,
    glow="rgba(255,45,70,.55)")
els.append({"type": "speed", "t0": R(c, 1.62), "t1": nxt(c), "x": 1300, "y": 470, "a": 0.35})
fx += [{"type": "flash", "t": R(c, 0), "d": 0.16, "a": 0.75}, {"type": "settle", "t": R(c, 0), "d": 0.35, "amt": 0.08},
       {"type": "punch", "t": R(c, 1.62), "d": 0.35, "amt": 0.07}, {"type": "shake", "t": R(c, 1.62), "d": 0.25, "amp": 18}]
se(R(c, 0.0), "syn:hit", -4)
se(R(c, 1.62), "【汎用,太鼓】太鼓(ドン).wav", -6)

# 2. 流行りの Orca・Obsidian → ガチでいらない（カードに赤い×）
c = "H2"   # 声：オルカとかオブシディアンとかって
shot(c, 0, "wide")
txt("流行りの", R(c, 0.0), nxt(c), 110, 200, 100, say=(R(c, 0.0), R(c, 0.20)))
X_AT = R("H3", 0.60)
els.append({"type": "tools", "t0": R(c, 0.06), "t1": nxt("H3"), "xAt": X_AT,
            # v004（2026-10-04 小川さん、質問4「A で」）：2枚とも公式のロゴを入れる（本編 1:03.7 のロゴの札と同じ画像）。カードを縦に 60px 伸ばした
            "items": [{"t": R(c, 0.06), "name": "Orca", "sub": "AIを動かすアプリ", "c1": "#0b1a3a", "c2": "#1f6feb", "x": 110, "y": 260,
                       "w": 440, "h": 320, "rot": -4, "logo": "../zukai/assets/orca_icon.png", "ls": 130},
                      {"t": R(c, 0.72), "name": "Obsidian", "sub": "メモアプリ", "c1": "#24104d", "c2": "#7c3aed", "x": 600, "y": 275,
                       "w": 440, "h": 320, "rot": 3, "logo": "../zukai/assets/obsidian_logo_gradient.svg", "ls": 120}]})
for tt in (R(c, 0.06), R(c, 0.72)):
    se(tt, "syn:pop", -7)
    se(tt - 0.05, "syn:whoosh", -15)
fx.append({"type": "punch", "t": R(c, 0.72), "d": 0.25, "amt": 0.03})

c = "H3"   # 声：ガチでいらない
shot(c, 0, "close")
txt("ガチで", R(c, 0.02), nxt(c), 110, 700, 120, say=(R(c, 0.02), R(c, 0.30)))
txt("いらない", R(c, 0.60), nxt(c), 150, 885, 230, font=HV, anim="stamp", say=(R(c, 0.60), R(c, 0.92)), jolt=30, rot=-4,
    box={"color": RED, "skew": -12, "px": 0.2, "py": 0.12, "d": 0.08})
fx += [{"type": "punch", "t": X_AT, "d": 0.4, "amt": 0.10}, {"type": "shake", "t": X_AT, "d": 0.35, "amp": 30},
       {"type": "flash", "t": X_AT, "d": 0.14, "a": 0.45, "color": "#ff2d46"}]
se(X_AT, "【ツッコミ】ドスッ.wav", -2)
se(X_AT, "syn:boom", -9)

# 3.（v003 で外した：中身はただのメモ → しかも毎日腐っていく。H4・H5）

# 4. じゃあ年商25億の社長は？ → AIのスキルはほぼナシ（ゲージが落ちる）
c = "H6a"  # 声：俺スキル
shot(c, 0, "med")
txt("じゃあ年商25億の社長は？", R(c, 0.0), nxt("H6b"), 110, 180, 84, say=(R(c, 0.0), R(c, 0.40)),
    box={"color": "rgba(0,0,0,0.6)", "px": 0.3, "py": 0.2})
els.append({"type": "gauge", "t0": R(c, 0.55), "t1": nxt("H6b"), "x": 110, "y": 300, "w": 780, "h": 58, "label": "AIの「スキル」",
            "from": 1.0, "to": 0.04, "drainAt": R("H6b", 0.08), "drainD": 0.35})
se(R(c, 0.0), "syn:whoosh", -10)
se(R(c, 0.55), "syn:pop", -9)
c = "H6b"  # 声：ほぼない
shot(c, 0, "close")
txt("ほぼナシ", R(c, 0.10), nxt(c), 110, 700, 280, font=HV, color=RED, anim="slam", echo=2, jolt=24, glow="rgba(255,45,70,.6)")
fx += [{"type": "punch", "t": R(c, 0.10), "d": 0.35, "amt": 0.08}, {"type": "shake", "t": R(c, 0.10), "d": 0.25, "amp": 20}]
se(R(c, 0.08), "syn:error", -12)
se(R(c, 0.10), "【汎用,太鼓】太鼓(カカッ).wav", -6)

# 5.（v003 で外した：やってるのは環境構築だけ。H7）

# 6. 返信が来たら AIが勝手にまた動き出す（コメントの札 → 再開の札）
c = "H8"   # 声：その相手の返信コメントで勝手にAIがまた動き始める
shot(c, 0, "med")
els.append({"type": "chat", "t0": R(c, 0.04), "t1": nxt(c), "x": 90, "y": 200, "w": 980, "h": 300, "name": "Addness", "tag": "コメント",
            "tagFont": HIRA,
            "lines": [{"text": "AI「この内容で進めていい？」", "size": 50, "weight": 700, "color": "#cfe3ff",
                       "ct": span("AI「この内容で進めていい？」", R(c, 0.04), R(c, 0.50))},
                      {"text": "人「OK！進めて」", "size": 78, "weight": 800,
                       "ct": span("人「OK！進めて」", R(c, 0.94), R(c, 1.60))}]})
els.append({"type": "pill", "t0": R(c, 2.46), "t1": nxt(c), "x": 110, "y": 600, "size": 44, "text": "AIが作業を再開"})
txt("AIが勝手に", R(c, 2.46), nxt(c), 110, 760, 150, say=(R(c, 2.46), R(c, 2.95)), colors={"2": YEL, "3": YEL, "4": YEL})
txt("また動き出す", R(c, 3.30), nxt(c), 110, 935, 190, font=HV, anim="slam", from_=2.0, jolt=18, echo=2)
fx += [{"type": "punch", "t": R(c, 2.46), "d": 0.3, "amt": 0.05}, {"type": "punch", "t": R(c, 3.30), "d": 0.3, "amt": 0.05}]
se(R(c, 0.04), "syn:pop", -9)
se(R(c, 0.94), "ピピ.mp3", -9)
se(R(c, 1.84), "syn:riser", -15)
se(R(c, 2.46), "syn:hit", -7)
se(R(c, 3.30), "syn:whoosh", -10)

# 7. ヤバくない？（BGM を止める）
c = "H9"   # 声：やばくない？
shot(c, 0, "xclose", tint="#7a0f1c", tintA=0.45)
txt("ヤバくない？", R(c, 0.08), nxt(c), 960, 560, 250, font=HV, color=WHITE, stroke=14, strokeColor=RED, anim="slam", from_=3.0, align="c",
    jolt=36, glow="rgba(255,45,70,.85)", echo=3, echoColor=WHITE)
els.append({"type": "burst", "t0": R(c, 0.08), "t1": R(c, 0.60), "x": 960, "y": 560, "r": 330, "color": RED, "color2": WHITE})
fx += [{"type": "punch", "t": R(c, 0.08), "d": 0.4, "amt": 0.12}, {"type": "shake", "t": R(c, 0.08), "d": 0.4, "amp": 38},
       {"type": "flash", "t": R(c, 0.06), "d": 0.14, "a": 0.55, "color": "#ff2d46"}]
se(R(c, 0.06), "syn:boom", -5)
se(R(c, 0.08), "【汎用,太鼓】太鼓(ドドン).wav", -6)

# 8. しかも社長と同じ環境がワンタップ → 問い
c = "H10"  # 声：俺と同じ環境設定をするためには ワンタップなの
shot(c, 0, "med")
TAP = R(c, 1.40)
txt("しかも社長と同じ環境が", R(c, 0.02), end(c) + 0.10, 110, 190, 96, say=(R(c, 0.02), R(c, 1.10)), exit="fade", ed=0.15)
els.append({"type": "tapbtn", "t0": R(c, 0.35), "t1": end(c) + 0.10, "ed": 0.15, "x": 110, "y": 300, "w": 700, "h": 150, "size": 60,
            "label": "社長の環境をコピー", "label2": "✓ コピー完了", "handAt": R(c, 0.85), "tapAt": TAP})
txt("ワンタップ", TAP, T_TITLE, 110, 730, 240, font=HV, color=YEL, anim="slam", from_=2.4, echo=2, jolt=22, glow="rgba(255,210,63,.6)")
fx += [{"type": "punch", "t": TAP, "d": 0.35, "amt": 0.07}, {"type": "shake", "t": TAP, "d": 0.2, "amp": 14},
       {"type": "flash", "t": TAP, "d": 0.12, "a": 0.35, "color": "#fff3c4"}]
se(R(c, 0.35), "syn:pop", -10)
se(TAP, "決定、ボタン押下22.wav", -6)
se(TAP + 0.03, "syn:hit", -8)
se(TAP + 0.06, "【キラッ✨,短い】キラ.wav", -12)
Q = "じゃあ、一番大事な環境設定とは？"
txt(Q, end(c) + 0.02, T_TITLE, 960, 935, 90, align="c", anim="rise", say=(end(c) + 0.02, end(c) + 0.40),
    box={"color": "rgba(0,0,0,0.65)", "px": 0.35, "py": 0.22})
fx.append({"type": "dim", "t0": end(c) + 0.02, "t1": T_TITLE, "a": 0.25, "fi": 0.15})
se(end(c) + 0.02, "syn:whoosh", -12)

# ホワイトアウト → タイトルコール（お手本1本目・astra v007：シャーン → 指鳴らしで切り替え・BGM なし・2.6秒）
fx.append({"type": "whiteout", "t0": T_WO, "t1": T_TITLE, "t2": T_TITLE + 0.28})
se(T_WO - 0.05, "【汎用,鈴】シャーン.wav", -8)
se(T_TITLE, "パチンっ指鳴らし.wav", -2)
fxp, fyp = FACE["TT"]
shots.append({"t0": T_TITLE, "t1": None, "z0": 1.14, "z1": 1.24, "cx0": fxp - (1300 - 960) / 1.14, "cy0": fyp - (470 - 540) / 1.14,
              "cx1": fxp - (1300 - 960) / 1.24, "cy1": fyp - (470 - 540) / 1.24, "tint": "#1d5cff", "tintA": 0.45, "cid": "TT",
              "shade": "none", "filter": "contrast(1.15) saturate(0.6) brightness(0.8)"})
fx.append({"type": "dim", "t0": T_TITLE, "t1": TOTAL, "a": 0.5})
# 本編へのホワイトアウト（お手本1本目：タイトルの終わり 0.8秒で白く飛び、挨拶の頭 0.83秒で白から戻る）。前半はここで描き、後半は Premiere に白の素材を置く
WO_OUT = 0.80
fx.append({"type": "whiteout", "t0": TOTAL - WO_OUT, "t1": TOTAL - 0.5 / FPS, "t2": TOTAL + 5})
els.append({"type": "particles", "t0": T_TITLE, "t1": TOTAL})
tt0 = T_TITLE
txt("年商25億AI社長の", tt0 + 0.08, TOTAL, 960, 300, 96, align="c", say=(tt0 + 0.08, tt0 + 0.40))
txt("AI環境設定", tt0 + 0.46, TOTAL, 960, 545, 250, font=HV, colors={"0": BLUE, "1": BLUE}, anim="slam", align="c",
    glow="rgba(77,163,255,.9)", echo=3, drift=0.02)
txt("全公開", tt0 + 1.10, TOTAL, 960, 830, 220, font=HV, color=YEL, anim="slam", from_=2.6, align="c", glow="rgba(255,210,63,.65)",
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

# BGM：「ヤバくない？」の間は止める（H8 の終わり〜H10 の始め）
BGM_OFF = (end("H8"), T["H10"])
VOICE_ACTIVE = -27.0       # 声の話している所の大きさ（astra v007 と同じ）
BGM_DB, SE_TRIM = -15.0, -4.0
BGM_START = 0.365          # ダイジェスト用 BGM の拍（0.415 秒・1拍 0.5224 秒）が 0.05 秒に来るように（astra v007 と同じ）


def run(cmd, **kw):
    subprocess.run([str(x) for x in cmd], check=True, **kw)


def write_page():
    css = "".join(f"@font-face {{ font-family: '{k}'; src: url('file://{quote(str(v))}'); }}\n" for k, v in FONT_FILES.items())
    (HERE / "fonts.css").write_text(css, encoding="utf-8")
    bounds = {s_["t0"] for s_ in shots}
    bounds |= {e["t0"] for e in els if e["type"] == "card"} | {e["t1"] for e in els if e["type"] == "card"}
    bounds |= {e["t1"] for e in els if e["type"] == "txt" and e.get("exit", "cut") == "cut"}
    hl = {"fps": FPS, "N": NFR, "bgDir": "file://" + quote(str(W / "bg")), "shots": shots, "els": els, "fx": fx, "bounds": sorted(bounds),
          "fontsToLoad": ["400 100px 'Toppan'", "400 100px 'SHSHeavy'", "400 100px 'SHSerifH'", "800 100px 'Avenir Next Condensed'",
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
        run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a:.4f}", "-i", CAM, "-frames:v", f1 - f0, "-q:v", "3", "-start_number", f0,
             str(d / "%05d.jpg")])


# ---------- 音 ----------
def synth():
    """効果音を ffmpeg で作る（素材/SE に無い、ドン・シュッ・グリッチ・ピッ・ポン・ブー・上がっていく音。astra v007 と同じ）"""
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
        run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f, "-ac", "2", "-ar", "48000", s / f"{k}.wav"])


def active_db(path):
    """話している所（50ミリ秒ごとの大きさが、そのクリップの一番大きい所から 20dB 以内）の平均の大きさ（dBFS）"""
    import array
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", "48000", "-f", "s16le", "-"], capture_output=True).stdout
    a = array.array("h"); a.frombytes(raw)
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
    a0, a1 = BGM_OFF
    filt.append(f"[0:a]atrim=0:{T_TITLE:.3f},asetpts=PTS-STARTPTS,aformat=channel_layouts=stereo,aresample=48000,volume={BGM_DB}dB,"
                f"volume=enable='between(t,{a0:.3f},{a1:.3f})':volume=0,afade=t=out:st={T_TITLE - 0.06:.3f}:d=0.06,apad=whole_dur={TOTAL:.3f}[bgm]")
    k = 1
    gains = {}
    for cid, _ in ORDER:
        a, b, _ = CL[cid]
        clip = W / f"voice_{cid}.wav"
        run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", CAM, "-vn", "-ac", "2", "-ar", "48000",
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
    filt.append(f"[bg1][vox][sfx]amix=inputs=3:normalize=0:duration=first,alimiter=limit=0.93:level=false[mix]")
    run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", ";".join(filt),
         "-map", "[mix]", "-t", f"{TOTAL:.3f}", W / "mix.wav",
         "-map", "[vst]", "-t", f"{TOTAL:.3f}", W / "stem_voice.wav",
         "-map", "[bst]", "-t", f"{TOTAL:.3f}", W / "stem_bgm.wav",
         "-map", "[sst]", "-t", f"{TOTAL:.3f}", W / "stem_se.wav"])
    return gains


def main():
    W.mkdir(exist_ok=True)
    write_page()
    plan = {"total": TOTAL, "frames": NFR, "t_wo": T_WO, "t_title": T_TITLE,
            "clips": [{"id": cid, "src": CL[cid][:2], "at": round(T[cid], 3), "text": CL[cid][2]} for cid, _ in ORDER],
            "se": ses, "bgm_off": BGM_OFF}
    print("尺", round(TOTAL, 3), "秒", NFR, "コマ（白く飛ぶ", round(T_WO, 2), "・タイトル", round(T_TITLE, 2), "）")
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
        cmd = ["node", HERE / "render.mjs", HERE / "page.html", frames, NFR, 4]
        if only:
            cmd += ["--only", only]
        run(cmd)
        if only:
            return
    plan["voice_gain_db"] = audio()
    json.dump(plan, open(W / "plan.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    run(["ffmpeg", "-v", "error", "-y", "-framerate", f"{FPS_N}/{FPS_D}", "-i", W / "frames" / "%05d.jpg", "-i", W / "mix.wav",
         "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-crf", "15", "-preset", "slow", "-pix_fmt", "yuv420p", "-r", f"{FPS_N}/{FPS_D}",
         "-c:a", "aac", "-b:a", "320k", "-frames:v", NFR, "-t", f"{TOTAL:.4f}", OUT])
    print("→", OUT)
    # Premiere 用：映像だけ（音は声・BGM・効果音を別々に置く）と、挨拶の頭に重ねる「白から戻る」素材（透明つき）
    vid = HERE / f"{NAME}_{NFR}f_映像.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-i", OUT, "-an", "-c:v", "copy", "-frames:v", NFR, vid])
    stems = {}
    for k, jp in (("voice", "声"), ("bgm", "BGM"), ("se", "効果音")):           # ハイライトの長さ（TOTAL）ちょうどにそろえる
        stems[k] = HERE / f"{NAME}_{NFR}f_{jp}.wav"
        run(["ffmpeg", "-v", "error", "-y", "-i", W / f"stem_{k}.wav", "-af", f"apad=whole_dur={TOTAL:.4f}", "-t", f"{TOTAL:.4f}",
             "-c:a", "pcm_s16le", stems[k]])
    n_in = round(0.83 * FPS)
    wo = HERE / "ホワイトアウト_白から戻る_0.83秒.mov"
    run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=white:s=1920x1080:r={FPS_N}/{FPS_D}", "-frames:v", n_in,
         "-vf", f"format=rgba,fade=t=out:st=0:n={n_in}:alpha=1", "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le", wo])
    # 本編の組み立て（cuts_plan_v004.py・build_v004.py）が読む目録。frames だけ本編を後ろへずらし、映像・音3本を 0 から、白から戻る素材を挨拶の頭に置く
    man = {"frames": NFR, "fps": f"{FPS_N}/{FPS_D}", "seconds": round(TOTAL, 4), "video": str(vid), "voice": str(stems["voice"]),
           "bgm": str(stems["bgm"]), "se": str(stems["se"]), "whiteout": str(wo), "whiteout_frames": n_in, "check_mp4": str(OUT),
           "made": datetime.datetime.now().isoformat(timespec="seconds"), "note": "冒頭ハイライト（P15）。hl/README.md"}
    json.dump(man, open(HERE / "hl_manifest.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("→ Premiere 用の映像・音3本・白から戻る素材・hl_manifest.json")


if __name__ == "__main__":
    main()
