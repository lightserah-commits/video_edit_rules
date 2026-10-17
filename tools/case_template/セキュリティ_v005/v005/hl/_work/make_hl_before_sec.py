#!/usr/bin/env python3
"""冒頭のハイライト（AI動画編集 v001。02 の P15）を作る。1015claude project開設 の make_hl.py を写して、構成をこの動画用に作り直した（2026-10-16）。以下は元の説明：冒頭のハイライト（1015claude project開設 v001。02 の P15）を作る。1003 AIで稼ぐ系の hl/make_hl.py を写して、構成（セリフ・文字・図形）をこの動画用に作り直した（2026-10-15）。もとは AIで稼ぐ系 v001 の説明：環境設定の hl/make_hl.py（v001・v001）の作り方を写して、中身をこの動画用に作り直した。
2026-10-05。切り抜きのように本人（三上さん）のセリフを細かく切ってつなぎ、激しい文字グラフィックを乗せる。文字はセリフの書き起こしにせず、
要約とつなぎの言葉で1本の流れにする（小川さん「文字起こししすぎ。引きを作るように要約、前後が繋がる形に」）。答え（AI導入支援・ツルハシ・Xの
DMでクーポン・テンプレート）は言わない（小川さん「ネタバレしなくて『え？』っていう興味付け」）。聞き手（創太くん）の声は使わない。

流れ：AIは もう 金そのもの → 金は夢を叶えてくれない → でも Claude Code は仕事を終わらせてくれる → 1日5秒 → AIに「やっといて」と頼むだけ
      → 年間100万円超え → 勝った → 時代が始まる → これチート → その辺の大学生がバシバシ稼いでる
      → 「じゃあ、AIで一番稼げる方法とは？」→ ホワイトアウト → タイトルコール「年商25億AI社長の AIで稼ぐ方法 全公開」（BGM なし・指鳴らし・2.6秒）
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
NAME = "aied_hl_v001"
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
ORDER = [("H1", 0.02), ("H2", 0.02), ("H3", 0.02), ("H4", 0.02), ("H5", 0.02), ("H6", 0.02), ("H7", 0.02), ("H8", 0.02), ("H9", 0.00)]   # AI動画編集：間は check_cuts.py で確かめて直す
HOLD = 1.80                                    # 最後の言葉の後、問いの札を見せる秒
WO = 0.30                                      # 白く飛ぶまでの秒
TITLE_SRC, TITLE_SEC = 18.0, 2.6               # タイトルコールの映像（通しのカメラの秒。三上さん・「神」の後の声のない所 17.6〜20.7）と長さ
# 顔の中心（カメラの画素。各クリップの 20%・50%・80% のコマを Mac の顔検出 _work/facedet で測った平均 2026-10-05）
FACE = {"TT": (1061, 445), "H1": (1054, 423), "H2": (1073, 420), "H3": (1062, 350), "H4": (960, 540), "H5": (960, 540),
        "H6": (960, 540), "H7": (960, 540), "H8": (960, 540), "H9": (1045, 442)}   # AI動画編集：カメラの所は Mac の顔検出（20・50・80% の平均）、Loom の所（H4〜H8）は画面の真ん中

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
# AI動画編集（2026-10-16）。流れ：AI自動編集は 神 → でも世の中のは レベルが低い → 出回ってるスキルは だいたいゴミ（こういち）
#   → これ全部 AIが編集 → ヤバくない？ → 人の手なら 3〜4日 → AIなら たった数時間 → いずれ 5分でポン出し → 秘伝のタレ（三上）
#   → 「『編集して』だけで本当に完成？」→ ホワイトアウト → タイトルコール「年商25億AI社長の AI動画編集 全工程公開」（三上さんの声なしの映像）
#   答え（XML を作る仕組み・ルール・コンテキスト）は見せない。聞き手（創太くん）の声は使わない
# 言葉の時刻（クリップの頭からの秒）は units.json の語の時刻 − クリップの入り（各場面のコメント）

# 1. AI自動編集は 神
c = "H1"   # 声：神（0.25〜0.65）三上さん
shot(c, 0, "med")
txt("AI自動編集は", R(c, 0.00), nxt(c), 110, 300, 110, say=(R(c, 0.00), R(c, 0.22)), colors=colors_of("AI自動編集は", {"AI自動編集": ORANGE}))
txt("神", R(c, 0.25), nxt(c), 160, 820, 420, font=HV, grad=GOLD, anim="slam", from_=2.6, echo=3, echoColor=YEL, jolt=30, glow="rgba(255,210,63,.75)")
els.append({"type": "burst", "t0": R(c, 0.24), "t1": R(c, 0.80), "x": 380, "y": 640, "r": 300, "ringMax": 1.5, "color": YEL, "color2": WHITE})
fx += [{"type": "flash", "t": R(c, 0), "d": 0.14, "a": 0.6}, {"type": "punch", "t": R(c, 0.25), "d": 0.35, "amt": 0.09},
       {"type": "shake", "t": R(c, 0.25), "d": 0.25, "amp": 20}, {"type": "flash", "t": R(c, 0.25), "d": 0.12, "a": 0.45, "color": "#fff3c4"}]
se(R(c, 0.0), "syn:whoosh", -11)
se(R(c, 0.25), "【汎用,太鼓】太鼓(ドン).wav", -5)
se(R(c, 0.27), "【キラッ✨,短い】キランッッ!!.wav", -9)

# 2. でも世の中のは レベルが低い
c = "H2"   # 声：レベルが低い（レ 0.05・低 0.75・い 0.91）三上さん
shot(c, 0, "close", tint="#4a0a12", tintA=0.38)
txt("世の中のAI自動編集は", R(c, 0.00), nxt(c), 110, 260, 96, say=(R(c, 0.00), R(c, 0.40)))
txt("レベルが低い", R(c, 0.05), nxt(c), 110, 760, 230, font=HV, color=WHITE, stroke=12, strokeColor=RED, anim="slam", from_=2.6, jolt=26,
    glow="rgba(255,45,70,.8)", echo=2, echoColor=WHITE, say=(R(c, 0.05), R(c, 0.95)))
fx += [{"type": "punch", "t": R(c, 0.75), "d": 0.35, "amt": 0.08}, {"type": "shake", "t": R(c, 0.75), "d": 0.25, "amp": 18}]
se(R(c, 0.05), "syn:pop", -10)
se(R(c, 0.75), "【ツッコミ】ドスッ.wav", -4)

# 3. 出回ってるスキルは だいたいゴミ（こういちさん）
c = "H3"   # 声：だいたいゴミっすね（だ 0.58・ゴ 1.02・っす 1.24。入りは 425.95＝前の息から）こういちさん（IMG_1317）
shot(c, 0, "med", tint="#2a2a2a", tintA=0.35)
txt("出回ってる自動編集スキルは", R(c, 0.10), nxt(c), 110, 260, 92, say=(R(c, 0.10), R(c, 0.55)))
txt("だいたいゴミ", R(c, 0.58), nxt(c), 110, 780, 250, font=HV, color=WHITE, stroke=14, strokeColor=RED, anim="slam", from_=3.0, jolt=32,
    glow="rgba(255,45,70,.85)", echo=3, echoColor=WHITE, rgb=0.25, say=(R(c, 0.58), R(c, 1.40)))
fx += [{"type": "glitch", "t": R(c, 1.02), "d": 0.35, "amt": 0.9}, {"type": "punch", "t": R(c, 1.02), "d": 0.35, "amt": 0.09},
       {"type": "shake", "t": R(c, 1.02), "d": 0.3, "amp": 24}]
se(R(c, 0.58), "syn:glitch", -12)
se(R(c, 1.02), "【汎用,太鼓】太鼓(カカッ).wav", -5)

# 4. これ全部 AIが編集（Loom の画面）
c = "H4"   # 声：これ全てAIがやったものです（これ 0.10・全 0.24・AI 0.66・や 1.18・もの 1.40）こういちさん（Loom）
shot(c, 0, "cen", tint="#0f3d66", tintA=0.62)   # v001 直し3：見本の字幕「よくいるやん」と重ならないよう背景を暗く
txt("この編集", R(c, 0.10), nxt(c), 110, 260, 120, say=(R(c, 0.10), R(c, 0.40)))
txt("全部", R(c, 0.24), nxt(c), 110, 520, 170, font=HV, say=(R(c, 0.24), R(c, 0.50)))
txt("AIがやった", R(c, 0.66), nxt(c), 110, 820, 230, font=HV, color=BLUE, stroke=10, strokeColor=WHITE, anim="slam", from_=2.4, jolt=24,
    glow="rgba(77,163,255,.85)", echo=2, echoColor=WHITE, say=(R(c, 0.66), R(c, 1.40)))
els.append({"type": "speed", "t0": R(c, 0.66), "t1": nxt(c), "x": 1300, "y": 420, "a": 0.28})
fx += [{"type": "punch", "t": R(c, 0.66), "d": 0.35, "amt": 0.08}, {"type": "shake", "t": R(c, 0.66), "d": 0.25, "amp": 18},
       {"type": "flash", "t": R(c, 0.66), "d": 0.12, "a": 0.35, "color": "#bfe0ff"}]
se(R(c, 0.10), "syn:whoosh", -12)
se(R(c, 0.66), "syn:hit", -6)
se(R(c, 0.68), "【キラッ✨,短い】キランッッ!!.wav", -10)

# 5. ヤバくない？
c = "H5"   # 声：やばくないですか（や 0.15・ない 0.59・ですか 0.65）こういちさん（Loom）
shot(c, 0, "close", tint="#3a2a00", tintA=0.62)   # v001 直し3
txt("ヤバくない？", R(c, 0.15), nxt(c), 110, 720, 290, font=HV, color=YEL, anim="slam", from_=2.6, echo=3, echoColor=WHITE, jolt=30,
    glow="rgba(255,210,63,.75)", say=(R(c, 0.15), R(c, 0.70)))
fx += [{"type": "punch", "t": R(c, 0.15), "d": 0.4, "amt": 0.10}, {"type": "shake", "t": R(c, 0.15), "d": 0.3, "amp": 24}]
se(R(c, 0.15), "【汎用,太鼓】太鼓(ドドン).wav", -6)

# 6. 人の手なら 3〜4日
c = "H6"   # 声：3日から4日は欲しいですよね（3 0.03・日 0.21・4 0.55・日 0.67・欲 0.93）こういちさん（Loom）
shot(c, 0, "cen", tint="#2a2a2a", tintA=0.42)
txt("人の手で編集したら", R(c, 0.00), nxt(c), 110, 260, 104, say=(R(c, 0.00), R(c, 0.40)))
txt("3〜4日", R(c, 0.03), nxt(c), 110, 720, 330, font=HV, color=WHITE, anim="slam", from_=2.4, jolt=22, say=(R(c, 0.03), R(c, 0.70)))
fx += [{"type": "punch", "t": R(c, 0.55), "d": 0.3, "amt": 0.06}, {"type": "shake", "t": R(c, 0.55), "d": 0.2, "amp": 12}]
se(R(c, 0.03), "syn:tick", -8)
se(R(c, 0.55), "syn:pop", -9)

# 7. AIなら たった数時間
c = "H7"   # 声：AI使うとたった数時間で出てきてしまう（AI 0.06・た 0.94・数 1.48・時間 1.76・出 2.04）こういちさん（Loom）
shot(c, 0, "close", tint="#6b4a00", tintA=0.40)
txt("AIなら", R(c, 0.06), nxt(c), 110, 300, 150, say=(R(c, 0.06), R(c, 0.40)), colors=colors_of("AIなら", {"AI": ORANGE}))
txt("たった", R(c, 0.94), nxt(c), 110, 560, 150, font=HV, say=(R(c, 0.94), R(c, 1.30)))
txt("数時間", R(c, 1.48), nxt(c), 110, 860, 330, font=HV, grad=GOLD, anim="slam", from_=2.6, echo=3, echoColor=YEL, jolt=30, glow="rgba(255,200,40,.6)")
els.append({"type": "sparkles", "t0": R(c, 1.50), "t1": nxt(c), "x": 420, "y": 760, "rx": 380, "ry": 170, "n": 12, "speed": 3.0})
fx += [{"type": "punch", "t": R(c, 1.48), "d": 0.4, "amt": 0.10}, {"type": "shake", "t": R(c, 1.48), "d": 0.3, "amp": 24},
       {"type": "flash", "t": R(c, 1.48), "d": 0.14, "a": 0.45, "color": "#fff3c4"}]
se(R(c, 0.94), "syn:riser", -14)
se(R(c, 1.48), "【キラッ✨,長い】シャラーーン.wav", -9)
se(R(c, 1.50), "syn:hit", -7)

# 8. いずれ 5分でポン出し
c = "H8"   # 声：1回5分でポン出し（1 0.04・回 0.16・5 0.30・分 0.50・ポ 0.78・出 0.98）こういちさん（Loom）
shot(c, 0, "cen", tint="#0a2f6b", tintA=0.42)
txt("あと2回のアップデートで", R(c, 0.00), nxt(c), 110, 260, 92, say=(R(c, 0.00), R(c, 0.30)))
txt("5分で", R(c, 0.30), nxt(c), 110, 560, 200, font=HV, color=BLUE, stroke=10, strokeColor=WHITE, say=(R(c, 0.30), R(c, 0.60)))
txt("ポン出し", R(c, 0.78), nxt(c), 110, 860, 300, font=HV, color=WHITE, anim="slam", from_=2.6, echo=2, echoColor=YEL, jolt=26, glow="rgba(77,163,255,.8)")
fx += [{"type": "punch", "t": R(c, 0.78), "d": 0.35, "amt": 0.08}, {"type": "shake", "t": R(c, 0.78), "d": 0.25, "amp": 20}]
se(R(c, 0.30), "syn:pop", -10)
se(R(c, 0.78), "【汎用,太鼓】太鼓(ドン).wav", -6)

# 9. 秘伝のタレ（三上さん）
c = "H9"   # 声：編集で食ってたら上げれないんだよ これ もう秘伝のタレだから（編 0.23・食 0.65・上げ 1.05・これ 1.73・もう 2.29・秘 2.57・だから 3.19）
shot(c, 0, "med", tint="#6b4a00", tintA=0.36)
H9_OUT = end(c) + 0.02                    # 問いの札が出る前に文字を消す（1015 の H8 と同じ）
txt("編集で食ってたら", R(c, 0.23), H9_OUT, 110, 240, 104, say=(R(c, 0.23), R(c, 0.95)), exit="fade", ed=0.12)
txt("出せないレベル", R(c, 1.05), H9_OUT, 110, 460, 130, font=HV, say=(R(c, 1.05), R(c, 1.60)), exit="fade", ed=0.12)
txt("秘伝のタレ", R(c, 2.57), H9_OUT, 110, 840, 300, exit="fade", ed=0.12, font=HV, grad=GOLD, anim="slam", from_=2.6, echo=3, echoColor=YEL, jolt=30, glow="rgba(255,200,40,.65)")
els.append({"type": "burst", "t0": R(c, 2.55), "t1": R(c, 3.10), "x": 560, "y": 760, "r": 300, "ringMax": 1.4, "color": YEL, "color2": WHITE})
fx += [{"type": "punch", "t": R(c, 2.57), "d": 0.4, "amt": 0.10}, {"type": "shake", "t": R(c, 2.57), "d": 0.3, "amp": 24},
       {"type": "flash", "t": R(c, 2.57), "d": 0.14, "a": 0.45, "color": "#fff3c4"}]
se(R(c, 0.23), "syn:whoosh", -12)
se(R(c, 2.57), "【キラッ✨,長い】ピラリーーン.wav", -9)
se(R(c, 2.59), "【汎用,太鼓】太鼓(ドドン).wav", -6)

# 問いの札（答えは出さない）
Q = "「編集して」だけで本当に完成？"
T_Q = end(c) + 0.14                       # 声が止まって 0.14秒後。ここで BGM も止める。背景はこのコマで止める（bg_frames）
txt(Q, T_Q, T_TITLE, 960, 935, 88, align="c", anim="rise", say=(T_Q, T_Q + 0.42), colors=colors_of(Q, {"「編集して」": YEL}),
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
TT1 = "年商25億AI社長の"
txt(TT1, tt0 + 0.08, TOTAL, 960, 300, 84, align="c", say=(tt0 + 0.08, tt0 + 0.40))
txt("AI動画編集", tt0 + 0.46, TOTAL, 960, 545, 220, font=HV, color=BLUE, anim="slam", align="c",
    glow="rgba(77,163,255,.9)", echo=3, drift=0.02, colors=colors_of("AI動画編集", {"AI": ORANGE}))
txt("全工程公開", tt0 + 1.10, TOTAL, 960, 830, 190, font=HV, color=YEL, anim="slam", from_=2.6, align="c", glow="rgba(255,210,63,.65)",
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
BGM_DIPS = []   # 1015：声の短いクリップ（H5「数十分で」0.6秒）は音を作ってから声と BGM の差を測って決める


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
