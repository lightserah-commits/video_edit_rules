"""Air v001 のカットを決める（整理後の 08 の cut：2段階・pauses・no_chop・no_slivers）。ワークの完全解説 v001 の cuts_plan を元に、
  入り（HEAD）を「声が上がり始める 2〜3フレーム前」＝0.08秒にし、つなぎ目ごとに声の途中で切れていないか（tools/check_chops.py と同じ見方）を
  組み立て前に確かめて、近くの静かな所へずらす（④）。
  ① 中身で切る：台本（script_v004.txt）の「x」。切る位置は声の出だしと終わりに合わせる（続けて話している所は大きさの谷）
  ② 無音を詰める：残す区間の中で、声の無い間が MIN_PAUSE 秒以上ある所を、前の声の後ろ TAIL 秒＋次の声の前 HEAD 秒まで詰める
       溜め（plan_v004.TAME の字幕の前）は TAME_HEAD 秒、画面で黙って操作している長い間（SCREEN_MIN 秒以上）は SCREEN_HEAD 秒残す
       小さい声（境目−10dB 以上が 0.1秒以上続く所）が文字起こしの語と重なっていれば、そこは声として残す（聞き手の小さい声など）
  ②' 切れ端をなくす（v001）：カットの間に 0.2秒未満しか残らない所は、その部分ごと切る（字幕の頭が入っていれば隣の間を縮めて残す）
  ③ 冒頭のハイライト：台本の「h」の区間を、この順に一番前へ置く
  出力 _work/cuts_v004.json（素材のフレーム［開始, 終了）の残す区間・ハイライト・字幕ごとのタイムラインのフレーム）と カット一覧_v004.csv
  ~/Desktop/video_edit_rules/env/bin/python v004/cuts_plan_v004.py
"""
import bisect
import csv
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from common import FPS, SYNC_OFFSET, Aligner, Script, Voice, load_units, norm  # noqa: E402
import plan_v004 as plan  # noqa: E402

MIN_PAUSE = 0.20                 # v001 小川さん「もっとジャンプカット」：0.30→0.20秒以上の間を詰める
TAIL = 0.06
HEAD = 0.06                       # 08 no_chop.sound：入りは声が上がり始める 2〜3フレーム前
TAME_HEAD = 0.35
SCREEN_MIN = 1.5
SCREEN_HEAD = 0.30
MIN_CUT_FRAMES = 3
MIN_KEEP_F = 6                    # 08 の no_slivers：残す区間は 0.2秒（6フレーム）以上
MAX_FRAG_F = 20                   # これ未満で、字幕の頭も残す言葉も無い所は切った言葉の頭として切る（v001）
HL_HEAD, HL_TAIL = 0.05, 0.15     # ハイライトの前後に残す
BIG_SEC = 10.0
HL_MANIFEST = os.path.join(HERE, "hl", "hl_manifest.json")   # 冒頭ハイライトの動画（frames・映像・声・BGM・効果音・白から戻る素材）
REORDER = {"Y": 811, "X": 1032, "Z": 1623}   # 並べ替え（区切りの番号。⑤）
# v003（2026-10-04 小川さん）：⑤の並べ替えの後に、区切り u0〜u1 のまとまりを、区切り after の後ろへ移す（同じ具体の話を1か所にまとめる）
MOVES = [{"u0": 132, "u1": 134, "after": 60,
          "why": "サッカーのたとえ（132〜134）を 60「皿のこだわりとかどうでもいいんだ」の後ろへ（小川さん「同じ具体の話をしてる…こっち側に持ってくるべき」）"}]
# v003：カットの頭（残す区間の終わり）を手で決めた所。(今の頭の素材の秒の近く, 直した素材の秒, 理由)。±0.15秒の中のカットの頭を直す
CUT_START_NEAR = [(1161.36, 1161.28, "v004 413「いい動画なんじゃないかしら」の「いい」と「動画」の間（0.6秒。v003 は 0.4秒だけ詰めて 0.2秒残っていた）を全部詰める（小川さん「発話とテロップとSEがずれてる」）")]
# v004：カットの終わり（次に残す区間の頭）を手で決めた所。(今の終わりの素材の秒の近く, 直した素材の秒, 理由)
CUT_END_NEAR = [(1161.76, 1161.84, "v004 413 の「動画」の頭の 0.06秒前（上と同じ）"),
                (362.23, 362.496, "v004 142 の「なんか」を残さない（台本の x 135..142/よく どおり）。「か」と「よ」の間の谷（−46〜−48dB、約0.04秒）で切る。"
                 "声の途中で切る検査（check_chops）はここに1件出る（測り方が 0.1秒の最大のため）。意図した例外。小川さん「三上さんが発話してる瞬間に前の颯太さんのテロップが残ってる」")]
SRC_END = 4788.60                 # カメラ IMG_1305.MOV の長さ（4788.607秒）


def mmss(t):
    return f"{int(t // 60)}:{t % 60:05.2f}"


def main():
    units = load_units()
    sc = Script()
    voice = Voice()
    al = Aligner(units, voice)
    capj = json.load(open(os.path.join(HERE, "_work", "captions_v004.json"), encoding="utf-8"))
    caps = [c for c in capj["captions"] if c["mode"] != "drop" and "src" in c]
    onset = {c["id"]: c["src"] for c in caps}
    starts_by_u = {}
    for c in caps:
        starts_by_u.setdefault(c["u"], []).append(c)
    tame = set(plan.TAME) | {e["id"] for e in plan.emphasis() if e["pattern"] in ("P04", "P05", "P06", "P07") and "テンポの見直し" not in e["reason"]}
    tame_sec = getattr(plan, "TAME_SEC", {})            # 字幕ごとに決めた溜めの秒（表 TAME の2列目が数なら。例 1101 の前の顔まね 1.5秒）
    screen_ids = plan.screen_caption_ids([c["id"] for c in caps])
    cap_src = [c["src"] for c in caps]
    cap_ids = [c["id"] for c in caps]

    def cap_at(t):
        i = bisect.bisect_right(cap_src, t + 0.05) - 1
        return cap_ids[i] if i >= 0 else None

    def pos(p, end=False):
        """台本の位置 → 素材の秒（声の出だし／語の頭）"""
        u, w = p
        if w is None:
            return al.unit_onset(u)[0]
        t, _, _ = al.phrase_onset(u, w)
        if t is None:
            raise ValueError(f"区切り{u}に「{w}」が見つからない")
        return t

    def next_kept_start(p):
        """カット B の後ろで、次に残る声の出だし"""
        u, w = p
        if w is not None:
            return pos(p)
        n = u + 1
        if n in starts_by_u:
            return starts_by_u[n][0]["src"]
        return al.unit_onset(n)[0] if n in units else SRC_END

    cuts = []      # (開始, 終了, 種類, 理由, 詳細)
    # ① 中身で切る
    for c in sc.cuts:
        t0 = pos(c["a"])
        if voice.voiced(t0 - 0.02):
            a = t0                                      # 続けて話している所：語の境目（大きさの谷）で切る
        else:
            pe = voice.end_before(t0, limit=15.0)      # v001：前の声の後ろの長い無音（3.6秒など）もカットに入れる（2秒までしか見ていなかった）
            a = min(pe + TAIL, t0 - 0.02) if pe is not None else t0 - 0.02
        t1 = next_kept_start(c["b"])
        nid = cap_at(t1)
        head = tame_sec.get(nid, TAME_HEAD) if nid in tame else HEAD
        b = t1 if voice.voiced(t1 - 0.02) else max(a, t1 - head)
        cuts.append((a, b, "中身", c["why"], {"from": c["a"], "to": c["b"]}))
    # 頭と終わり
    first = caps[0]["src"]
    cuts.append((0.0, first - HEAD, "中身", "撮影の頭（本編の前）", {}))
    last_u = max(u for u in units if u in starts_by_u)
    le = units[last_u]["words"][-1][1]
    rs = voice.runs(le - 0.3, le + 1.5)
    le = max([le] + [y for x, y in rs if x < le + 0.3])
    cuts.append((le + 0.4, SRC_END, "中身", "撮影の終わり（本編の後）", {}))
    # 中身のカットの区間（無音を詰める時に使う）
    content = sorted((a, b) for a, b, *_ in cuts)
    kept, cur = [], 0.0
    for a, b in content:
        if a > cur:
            kept.append((cur, a))
        cur = max(cur, b)
    if cur < SRC_END:
        kept.append((cur, SRC_END))
    # 小さい声（語と重なる所）
    db = voice.db
    lowv = db > voice.thr - 10
    LOW_SPANS = [(4471.0, 4580.0)]                     # 田中さんの区間（区切り 1643〜1687）は声が小さい → 小さい声の境目を −20dB まで下げる（検査係：語尾が「間」として切られていた）
    for a_, b_ in LOW_SPANS:
        i0_, i1_ = voice.idx(a_), voice.idx(b_)
        lowv[i0_:i1_] = db[i0_:i1_] > voice.thr - 20
    word_mask = np.zeros(len(db), dtype=bool)
    removed_units = set()
    for c in sc.cuts:
        for u in range(c["a"][0] + (1 if c["a"][1] else 0), c["b"][0] + (0 if c["b"][1] is None else 0)):
            removed_units.add(u)
    for u, U in units.items():
        if u in removed_units:
            continue
        for ws, we, w in U["words"]:
            if we - ws < 1.2:                          # 長すぎる語の時刻（間をまたいだもの）は使わない
                word_mask[voice.idx(ws):voice.idx(we) + 1] = True
    # ② 無音を詰める
    for k0, k1 in kept:
        vr = voice.runs(k0, k1)
        for (s0, e0), (s1, e1) in zip(vr, vr[1:]):
            gap = s1 - e0
            if gap < MIN_PAUSE:
                continue
            # 間の中の小さい声（語と重なる）を探す
            i0, i1 = voice.idx(e0), voice.idx(s1)
            seg = lowv[i0:i1] & word_mask[i0:i1]
            quiet = []
            d = np.diff(np.concatenate([[0], seg.astype(np.int8), [0]]))
            for x, y in zip(np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]):
                if y - x >= 10:
                    quiet.append(((i0 + x) / 100, (i0 + y) / 100))
            pieces, prev_end = [], e0
            for qa, qb in quiet:
                pieces.append((prev_end, qa))
                prev_end = qb
            pieces.append((prev_end, s1))
            for pa, pb in pieces:
                g = pb - pa
                if g < MIN_PAUSE:
                    continue
                nid = cap_at(pb)
                nid2 = cap_at(pb + 0.6)                    # 声が字幕の聞こえ始めより少し前から上がる所（1101：息・小さい音が 0.38秒前から）は、次の字幕の溜めを見る
                if nid2 != nid and nid2 in tame_sec:
                    nid = nid2
                head, why = HEAD, "間を詰める"
                if nid in tame and abs(onset.get(nid, -99) - pb) < (0.6 if nid in tame_sec else 0.3):   # 秒を決めた溜めは 0.6秒まで（1101 の顔まね）
                    head, why = tame_sec.get(nid, TAME_HEAD), f"間を詰める（字幕{nid}の前の溜めを残す）"
                elif nid in screen_ids and g >= SCREEN_MIN:
                    head, why = SCREEN_HEAD, "画面で黙って操作している間を詰める（話し出す前を残す）"
                a, b = pa + TAIL, pb - head
                if b - a >= MIN_CUT_FRAMES / FPS:
                    cuts.append((a, b, "間", why, {"gap": round(g, 2)}))
    # 残す字幕の聞こえ始めを越えて切らない（聞こえ始めは声の大きさの芯より前にあることがある：息・子音）
    fixed = []
    for c in cuts:
        a, bb = c[0], c[1]
        i = bisect.bisect_right(cap_src, a + 0.02)
        if i < len(cap_src) and cap_src[i] <= bb + 0.02:
            bb = cap_src[i] - HEAD
        if bb > a:
            fixed.append((a, bb) + tuple(c[2:]))
    cuts = fixed
    # フレームにそろえて重ねる
    frames = []
    for c in cuts:
        fa, fb = math.ceil(c[0] * FPS - 1e-6), math.floor(c[1] * FPS + 1e-6)
        if fb - fa >= (1 if c[2] != "間" else MIN_CUT_FRAMES):
            frames.append([fa, fb, [c]])
    frames.sort(key=lambda x: x[0])
    merged = []
    for fa, fb, cs in frames:
        if merged and fa <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], fb)
            merged[-1][2] += cs
        else:
            merged.append([fa, fb, cs])
    # 切れ端をなくす（08 の no_slivers、v001）：カットとカットの間に MIN_KEEP_F 未満しか残らない所
    #   v001 では「間を詰める」と「中身」のカットの間に、切った言葉の出だし 2〜5フレームが残っていた（声にも映像にも出る）
    #   字幕の聞こえ始めが入っていなければ、その部分ごと切る（前後のカットをつなぐ）。入っていれば、隣の「間」のカットを縮めて残す
    #   0.2秒以上でも、字幕の頭も残す言葉（台本で切っていない語）も入っていない短い所（MAX_FRAG_F 未満）は、切った言葉の頭・息なので切る
    cap_f = sorted(math.floor(c["src"] * FPS) for c in caps)
    cut_t = []                                          # 台本の x の時刻（語の頭。B に語があればその語の手前まで）
    for c in sc.cuts:
        (ua, wa), (ub, wb) = c["a"], c["b"]
        s = units[ua]["start"] if wa is None else al.char_time(ua, al.find(ua, wa) or 0)
        e = units[ub]["end"] if wb is None else al.char_time(ub, al.find(ub, wb) or 0)
        cut_t.append((s - 0.01, e))
    kept_words = sorted((ws, we) for U in units.values() for ws, we, _ in U["words"]
                        if not any(s <= ws < e for s, e in cut_t))
    kw_s = [w[0] for w in kept_words]

    def has_kept_word(a, b):
        t0, t1 = a / FPS, b / FPS
        i = bisect.bisect_left(kw_s, t0 - 2.0)
        return any(ws < t1 and we > t0 for ws, we in kept_words[i:bisect.bisect_left(kw_s, t1)])
    sliver_fixed = []
    k = 1
    while k < len(merged):
        a, b = merged[k - 1][1], merged[k][0]
        j = bisect.bisect_left(cap_f, a)
        has_start = j < len(cap_f) and cap_f[j] < b
        if 0 < b - a < MAX_FRAG_F and not has_start and not has_kept_word(a, b):
            sliver_fixed.append((a, b, "切った" if b - a < MIN_KEEP_F else "切った（残す言葉が無い）"))
            merged[k - 1][1] = merged[k][1]
            merged[k - 1][2] += merged[k][2]
            del merged[k]
            continue
        if 0 < b - a < MIN_KEEP_F:
            need = MIN_KEEP_F - (b - a)
            left_pause = all(c[2] == "間" for c in merged[k - 1][2])
            if left_pause and merged[k - 1][1] - merged[k - 1][0] > need + MIN_CUT_FRAMES:
                merged[k - 1][1] -= need
            else:
                merged[k][0] += need
            sliver_fixed.append((a, b, "延ばして残した"))
        k += 1
    # ④ 声の途中で切れていないか（08 no_chop.sound。tools/check_chops.py と同じ見方。v001）
    #   前が切れている：残す区間の終わりの2フレームが声（-38dB 以上）で、素材でその後ろ 0.1秒も声
    #   後ろが途中から：次に残す区間の頭の2フレームが声で、素材でその前 0.1秒も声
    #   見つかったら、カットの端を ±0.4秒（12フレーム）の中で、その形にならない一番近いフレームへずらす（まず「言い終わってから」の向き）
    LOUD = -38.0

    import check_chops                                # 組み立て後の検査と同じ測り方にする（v001）
    wav = check_chops.Wav(os.path.join(os.path.dirname(HERE), "analysis", "asr", "_work", "camera.wav"))

    def mx(t0, t1):
        return wav.db(t0, t1)

    def front_bad(f):          # f＝残す区間の終わり（カットの頭）
        return mx(f / FPS - 2 / FPS, f / FPS) >= LOUD and mx(f / FPS, f / FPS + 0.10) >= LOUD

    def back_bad(g):           # g＝次に残す区間の頭（カットの終わり）
        return mx(g / FPS, g / FPS + 2 / FPS) >= LOUD and mx(g / FPS - 0.10, g / FPS) >= LOUD
    left_after = []
    chop_fixed, chop_left = [], []
    for k, m in enumerate(merged):
        fa, fb = m[0], m[1]
        lo_a = merged[k - 1][1] + MIN_KEEP_F if k else 0
        hi_b = merged[k + 1][0] - MIN_KEEP_F if k + 1 < len(merged) else math.floor(SRC_END * FPS)
        if front_bad(fa):
            cand = [fa + d for d in list(range(1, 13)) + list(range(-1, -4, -1))]      # 言い終わってから（後ろへ）。前へは3フレームまで
            ok = [f for f in cand if lo_a <= f < fb - 1 and not front_bad(f)]
            if ok:
                chop_fixed.append((fa, ok[0], "前"))
                m[0] = ok[0]
            else:
                chop_left.append((fa, "前が切れている"))
        fa = m[0]
        if back_bad(fb):
            cand = [fb - d for d in list(range(1, 13)) + list(range(-1, -4, -1))]      # 出だしの前から（前へ）。後ろへは3フレームまで
            j = bisect.bisect_left(cap_f, fb)
            nxt_cap = cap_f[j] if j < len(cap_f) else 10 ** 9
            ok = [g for g in cand if fa + 1 < g <= hi_b and g <= nxt_cap and not back_bad(g)]
            if ok:
                chop_fixed.append((fb, ok[0], "後"))
                m[1] = ok[0]
            else:
                chop_left.append((fb, "後ろが途中から"))
    # 波形を見て手で決めたつなぎ目（組み立て後の tools/check_chops.py で残った所。素材のフレーム → 直したフレーム）
    #   CUT_START：残す区間の終わり（カットの頭）、CUT_END：次に残す区間の頭（カットの終わり）
    CUT_START = {}
    CUT_END = {}
    for m in merged:
        m[0] = CUT_START.get(m[0], m[0])
        m[1] = CUT_END.get(m[1], m[1])
    cut_start_fixed = []
    for near, to, why in CUT_START_NEAR:
        hit = [m for m in merged if abs(m[0] / FPS - near) <= 0.15]
        assert len(hit) == 1, f"CUT_START_NEAR {near}：当たるカットが {len(hit)}"
        cut_start_fixed.append((hit[0][0], round(to * FPS), why))
        hit[0][0] = round(to * FPS)
        assert not front_bad(hit[0][0]), f"CUT_START_NEAR {near}→{to} は声の途中"
    for near, to, why in CUT_END_NEAR:
        hit = [m for m in merged if abs(m[1] / FPS - near) <= 0.15]
        assert len(hit) == 1, f"CUT_END_NEAR {near}：当たるカットが {len(hit)}"
        cut_start_fixed.append((hit[0][1], round(to * FPS), "終わり：" + why))
        hit[0][1] = round(to * FPS)
    merged = [m for m in merged if m[1] > m[0]]
    # 字幕の聞こえ始めのフレームがカットに入っていないか
    warns = []
    cutset = []
    for fa, fb, _ in merged:
        cutset.append((fa, fb))
    starts_f = [x[0] for x in cutset]

    def in_cut(f):
        i = bisect.bisect_right(starts_f, f) - 1
        return i >= 0 and cutset[i][0] <= f < cutset[i][1]
    for c in caps:
        f = math.floor(c["src"] * FPS)
        bad = [g for g in range(f, f + 6) if in_cut(g) and voice.voiced(g / FPS + 0.017)]
        if in_cut(f) or bad:
            warns.append((c["id"], c["text"].replace("\r", " "), f, len(bad)))
    # 残す区間（素材のフレーム）
    total_f = math.floor(SRC_END * FPS)
    keep, cur = [], 0
    for fa, fb, _ in merged:
        if fa > cur:
            keep.append([cur, fa])
        cur = max(cur, fb)
    if cur < total_f:
        keep.append([cur, total_f])
    # ハイライト
    hls = []
    for h in sc.highlights:
        a = pos(h["a"]) - HL_HEAD
        ub = h["b"][0]
        we = units[ub]["words"][-1][1]
        rs = voice.runs(we - 0.3, we + 1.0)
        we = max([we] + [y for x, y in rs if x < we + 0.2])
        end = we + HL_TAIL
        nxt = [c["src"] for c in caps if c["u"] > ub]         # 次の区切りの字幕の聞こえ始め（語の時刻は詰まっていることがあるので区切りの順で見る）
        if nxt:
            end = min(end, min(nxt) - HEAD)                  # 次の言葉の頭を入れない
        hls.append([math.floor(a * FPS), math.floor(end * FPS)])
    hl_len = sum(b - a for a, b in hls)
    # 冒頭ハイライト（P15）は別に作った動画（hl/。astra v007 の作り方）を頭に置く。その長さだけ本編を後ろへずらす
    hl_ext = 0
    if os.path.exists(HL_MANIFEST):
        hl_ext = json.load(open(HL_MANIFEST, encoding="utf-8"))["frames"]
    hl_len += hl_ext
    # ⑤ 並べ替え（08 の reorder「撮影中の聞き手の指摘どおりに移す」。00_案件メモ.md の「AI が決めた所」）
    #   撮った順 A → Y（セットアップはワンタップ）→ X（プレゼント・比べる話）→ Z（田中さん〜）を、A → X → Y → Z にする
    #   区切りは字幕の聞こえ始めで決める：Y の頭＝区切り REORDER["Y"] 以降の最初の字幕、X の頭＝REORDER["X"]、Z の頭＝REORDER["Z"]
    #   Y と X の頭は前にカットがあるので、その残す区間の頭で分ける。Z の頭は続けて話しているので、Z の字幕の聞こえ始めの HEAD 前で残す区間を分ける
    def first_cap_f(u0):
        c = min((c for c in caps if c["u"] >= u0), key=lambda c: c["src"])
        return math.floor(c["src"] * FPS), c

    def seg_start(f):
        for a, b in keep:
            if a <= f < b:
                return a
        raise ValueError(f"フレーム {f} が残す区間に無い")
    reorder_note = {}
    if REORDER:
        fy, cy = first_cap_f(REORDER["Y"])
        fx, cx = first_cap_f(REORDER["X"])
        fz, cz = first_cap_f(REORDER["Z"])
        ya, xa = seg_start(fy), seg_start(fx)
        za = math.floor((cz["src"] - HEAD) * FPS)
        nk = []
        for a, b in keep:                                # Z の頭で残す区間を分ける
            if a < za < b:
                if za - a < MIN_KEEP_F or b - za < MIN_KEEP_F:
                    raise ValueError(f"Z の頭 {za} で分けると切れ端ができる（{a}〜{b}）")
                nk += [[a, za], [za, b]]
            else:
                nk.append([a, b])
        keep = sorted(nk)
        A_ = [s for s in keep if s[1] <= ya]
        Y_ = [s for s in keep if ya <= s[0] < xa]
        X_ = [s for s in keep if xa <= s[0] < za]
        Z_ = [s for s in keep if s[0] >= za]
        assert len(A_) + len(Y_) + len(X_) + len(Z_) == len(keep)
        keep = A_ + X_ + Y_ + Z_
        reorder_note = {"Y": [ya, cy["id"], cy["text"]], "X": [xa, cx["id"], cx["text"]], "Z": [za, cz["id"], cz["text"]],
                        "order": "A→X→Y→Z", "frames": {"A": sum(b - a for a, b in A_), "X": sum(b - a for a, b in X_),
                                                      "Y": sum(b - a for a, b in Y_), "Z": sum(b - a for a, b in Z_)}}
    # v003：まとまりを移す（MOVES）。まとまりの頭＝u0 の最初の字幕を含む残す区間の頭、終わり＝u1 の最後の語を含む残す区間の終わり。
    #   入れる所＝after の最後の語の終わりと、次の字幕の聞こえ始め − HEAD の間。そこにカットの切れ目があればそこ、無ければ一番静かなコマで分ける
    moved = []
    for mv in MOVES:
        c0 = min((c for c in caps if c["u"] >= mv["u0"]), key=lambda c: c["src"])
        f0 = seg_start(math.floor(c0["src"] * FPS))
        we = units[mv["u1"]]["words"][-1][1]
        fw = math.floor(we * FPS)
        f1 = next(b for a, b in keep if a <= fw < b)
        blk = [k_ for k_, s_ in enumerate(keep) if f0 <= s_[0] and s_[1] <= f1]
        assert blk and blk == list(range(blk[0], blk[-1] + 1)), f"移すまとまり {mv} が続いていない"
        block = [keep[k_] for k_ in blk]
        rest = [s_ for k_, s_ in enumerate(keep) if k_ not in blk]
        ea = math.ceil(units[mv["after"]]["words"][-1][1] * FPS)
        cn = min((c for c in caps if c["u"] > mv["after"]), key=lambda c: c["src"])
        eb = math.floor((cn["src"] - HEAD) * FPS)
        assert ea < eb, f"{mv['after']} の後ろに入れる間が無い"
        pos_ = None
        for k_, (a_, b_) in enumerate(rest):
            if ea <= b_ <= eb + 1 and k_ + 1 < len(rest) and rest[k_ + 1][0] >= b_:
                pos_ = k_ + 1                                  # すでにカットの切れ目がある
                break
        if pos_ is None:
            fsp = min(range(ea, eb + 1), key=lambda f_: mx(f_ / FPS - 1 / FPS, f_ / FPS + 1 / FPS))
            k_ = next(k_ for k_, (a_, b_) in enumerate(rest) if a_ < fsp < b_)
            a_, b_ = rest[k_]
            assert fsp - a_ >= MIN_KEEP_F and b_ - fsp >= MIN_KEEP_F, f"{fsp} で分けると切れ端ができる"
            rest[k_:k_ + 1] = [[a_, fsp], [fsp, b_]]
            pos_ = k_ + 1
        keep = rest[:pos_] + block + rest[pos_:]
        moved.append({"move": mv, "block_src_frames": block, "after_src_frame": rest[pos_ - 1][1], "next_caption": cn["id"]})
    # 素材のフレーム → タイムラインのフレーム（本編）。並べ替えた後なので、素材の順に並べた表から引く
    acc, offs = hl_len, []
    for a, b in keep:
        offs.append(acc)
        acc += b - a
    by_src = sorted(range(len(keep)), key=lambda i: keep[i][0])
    kstarts = [keep[i][0] for i in by_src]

    def to_tl(f):
        j = bisect.bisect_right(kstarts, f) - 1
        if j < 0:
            return offs[by_src[0]]
        i = by_src[j]
        a, b = keep[i]
        if f >= b:                                       # カットの中：素材で次に残す区間の頭
            return offs[i] + (b - a) if j + 1 >= len(by_src) else offs[by_src[j + 1]]
        return offs[i] + f - a
    cap_tl = {c["id"]: to_tl(math.floor(c["src"] * FPS)) for c in caps}
    # v004 G4（2026-10-04 小川さん「三上さんが発話してる瞬間にもかかわらず、前の颯太さんのテロップが残ってしまってるから変」→ ほかの所も OK）：
    #   話す人が替わる字幕が、残す区間の頭（カット）から 3〜20コマ後に始まり、その間に声（−38dB 以上）がある所は、字幕をカットのコマから出す
    seg_tl = sorted(offs[i] for i in range(len(keep)))
    g4 = []
    order_ = sorted(caps, key=lambda c: cap_tl[c["id"]])
    for k_ in range(1, len(order_)):
        c, pc = order_[k_], order_[k_ - 1]
        if c["who"] == pc["who"]:
            continue
        f = cap_tl[c["id"]]
        j_ = bisect.bisect_right(seg_tl, f) - 1
        s_ = seg_tl[j_]
        gap = f - s_
        if 3 <= gap <= 20 and s_ > cap_tl[pc["id"]]:
            i_ = offs.index(s_)
            a_ = keep[i_][0]
            if mx(a_ / FPS, (a_ + gap) / FPS) >= LOUD:
                cap_tl[c["id"]] = s_
                g4.append({"id": c["id"], "text": c["text"].replace("\r", " "), "from_tl": f, "to_tl": s_, "frames": gap,
                           "db": round(mx(a_ / FPS, (a_ + gap) / FPS), 1)})
    out = {"params": {"MIN_PAUSE": MIN_PAUSE, "TAIL": TAIL, "HEAD": HEAD, "TAME_HEAD": TAME_HEAD, "SCREEN_MIN": SCREEN_MIN,
                      "SCREEN_HEAD": SCREEN_HEAD, "voice_thr_db": round(voice.thr, 1), "fps": "30000/1001"},
           "keep_frames": keep, "reorder": reorder_note, "moves": moved, "cut_start_fixed": cut_start_fixed, "g4_caption_at_cut": g4, "highlight_frames": hls, "highlight_external_frames": hl_ext, "total_frames": acc, "caption_tl": cap_tl,
           "cuts_frames": [[fa, fb] for fa, fb, _ in merged], "warnings": warns,
           "counts": {"間": sum(1 for c in cuts if c[2] == "間"), "中身": sum(1 for c in cuts if c[2] == "中身")},
           "sliver_fixed": [[a, b, how] for a, b, how in sliver_fixed],
           "chop_fixed": [list(x) for x in chop_fixed], "chop_left": [list(x) for x in chop_left],
           "total_cut_sec": round(sum(fb - fa for fa, fb, _ in merged) / FPS, 1)}
    json.dump(out, open(os.path.join(HERE, "_work", "cuts_v004.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    # 一覧（v001 の時刻・素材の時刻・切った中身・理由）
    rows = []
    for fa, fb, cs in merged:
        L = (fb - fa) / FPS
        texts, whys = [], []
        for c in cs:
            if c[2] == "中身" and c[4]:
                ua, ub = c[4]["from"][0], c[4]["to"][0]
                texts.append(" / ".join(units[u]["text"] for u in range(ua, ub + 1) if u in units))
                whys.append(f"区切り{ua}" + (f"〜{ub}" if ub != ua else "") + "：" + c[3])
            elif c[2] == "中身":
                whys.append(c[3])
            else:
                whys.append(f"{c[3]}（間 {c[4]['gap']}秒）")
        kinds = sorted({c[2] for c in cs})
        rows.append([mmss(to_tl(fa) / FPS), mmss(fa / FPS), mmss(fb / FPS), f"{L:.2f}", "・".join(kinds), "大" if L >= BIG_SEC else "",
                     " ‖ ".join(texts)[:400], " ／ ".join(dict.fromkeys(whys))])
    with open(os.path.join(HERE, "カット一覧_v004.csv"), "w", encoding="utf-8-sig", newline="") as fo:
        w = csv.writer(fo)
        w.writerow(["v004の時刻", "素材の開始", "素材の終了", "切った秒", "種類", "大きなカット", "切った中身（文字起こし）", "理由"])
        w.writerows(rows)
    print(json.dumps({k: out[k] for k in ("params", "total_cut_sec", "counts")}, ensure_ascii=False))
    print(f"切れ端を直した {len(sliver_fixed)}（{dict(__import__('collections').Counter(h for *_, h in sliver_fixed))}）、残す区間の最短 {min(b - a for a, b in keep)}フレーム")
    print(f"声の途中で切れていたつなぎ目を直した {len(chop_fixed)}、直せなかった {len(chop_left)}")
    for x in chop_left[:40]:
        print("   chop", mmss(x[0] / FPS), x[1])
    print(f"G4：字幕をカットのコマから出した {len(g4)}：" + "、".join(f"{mmss(x['to_tl'] / FPS)}（{x['frames']}コマ）" for x in g4))
    print(f"残す区間 {len(keep)}、ハイライト {len(hls)}（{hl_len / FPS:.1f}秒）、尺 {mmss(acc / FPS)}、注意 {len(warns)}")
    for x in warns[:30]:
        print("  warn", x)


if __name__ == "__main__":
    main()
