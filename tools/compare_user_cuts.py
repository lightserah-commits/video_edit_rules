#!/usr/bin/env python3
"""小川さんがカットを手で直した所と、AI の版の差を1か所ずつ測って表にする（どの案件でも使える。読むだけ）。
目的：「なぜ AI の版に残ったか」を、勘ではなく数字で見る（2026-10-19 小川さん「絶妙にカットが毎回惜しい」「差を測る道具を作って」）。
小川さんの直しも完璧ではないので、小川さんの切り口が声の途中に入っている所も出す（小川さん「俺の手直しも完璧ではない」）。

測ること（小川さんが切った所ごと）:
  - どこか：小川さんのシーケンスの位置・AI の版の位置・素材の秒・長さ
  - 何が消えたか：文字起こしの語（区切りの番号つき）・話者（台本の @＝聞き手）・声のある秒・中の一番長い無音
  - 小川さんの切り口：前の声の途中で切っていないか・次の声の途中から入っていないか（語の途中なら、その語と近くの静かな所）
  - AI の版ではどうだったか：AI のつなぎ目のすぐ横か（＝切り残し）・そこで AI が切った物と理由（カット一覧）・
    中の無音に文字起こしの語がかかっていないか・中の無音が「声」の大きさ（AI のしきい値）を超えていないか・
    中や直後に字幕の頭が無いか（AI は字幕の聞こえ始めを越えて切らない）・台本の行（AI が残す／切ると決めた行と理由）・
    判断シートの候補のどれに入るか（と小川さんの選び）
  - 種類（自動の目安）：間だけ／切り残し（AI のつなぎ目の横）／聞き手の一言／一言・言いかけ／一文／話の塊

使い方（例：1017 で、小川さんが AI の書き出し mp4 を別のシーケンスで切った時）:
  ~/Desktop/video_edit_rules/env/bin/python tools/compare_user_cuts.py \\
    --ai-map  analysis/シーケンス01_20261019/segs_r2.json \\
    --user-seq analysis/シーケンス01_20261019/seq01.json --user-media ai_export \\
    --ai-cuts v008/_work/cuts_v008.json --ai-cut-list v008/カット一覧_v008.csv \\
    --units analysis/units.json --voice media/camera_voice_comp.wav --script v008/script_v008.txt \\
    --sheet 尺の短縮_判断シート/候補.json --sheet-cut 3,7,11,12,16,17,18,20 \\
    --out 出す場所/差_v008_シーケンス01
  （パスは案件の edit/ から。--out の後ろに .md と .json を付けて書く）

入れる物:
  --ai-map   AI の版のタイムライン → 素材の対応 [[タイムラインの開始, 終了, 素材の開始, 終了], …]（フレーム）。
             無ければ --ai-cuts の keep_frames を highlight_external_frames から並べて作る
  --user-seq 小川さんのシーケンス。premiere_bridge で読んだ形（v[0].clips の s・e・i・o、秒）か、tools/dump_timeline.py の出力（--user-track）
  --user-media ai_export … 小川さんが切った素材が AI の書き出し（クリップの in/out＝AI の版のタイムラインの秒）
               source    … 素材そのもので切り直した（in/out＝素材の秒。AI の版に無い所を足していれば「戻した」として出す）
  --voice    声の WAV（素材の秒）。声の大きさは 10ms ごと。しきい値は --ai-cuts の params.voice_thr_db（無ければ -45dB）
  Premiere の同じシーケンスをその場で直した時は tools/diff_user_edits.py（リップル・クリップの出入り）を使う
"""
import argparse
import bisect
import csv
import json
import os
import re
import subprocess
import sys
from fractions import Fraction

import numpy as np

TPS = 254016000000          # Premiere の ticks / 秒
SR = 8000                   # 声を読む時のサンプルの数（秒あたり）
HOP = 0.01                  # 声の大きさを測る幅（秒）
VOICE_DB = -38.0            # 切り口の「声」（tools/check_chops.py と同じ）
QUIET_DB = -45.0            # 「声が無い」（08 の no_chop.sound：無音・息・部屋の音は -45dB より小さい）


def ff(t):
    if t is None:
        return "-"
    m = int(t // 60)
    return f"{m}:{t - 60 * m:05.2f}"


def parse_mmss(s):
    s = (s or "").strip()
    if not s:
        return None
    if ":" in s:
        m, x = s.split(":", 1)
        return int(m) * 60 + float(x)
    return float(s)


# ---------- AI の版のタイムライン ----------
class AiTimeline:
    def __init__(self, segs, fps):
        self.fps = fps
        self.segs = sorted([list(map(float, s)) for s in segs])          # [a0, a1, s0, s1]（フレーム）
        self.starts = [s[0] for s in self.segs]
        self.end = self.segs[-1][1] / fps if self.segs else 0.0
        self.first = self.segs[0][0] / fps if self.segs else 0.0
        # つなぎ目（素材が続いていない所）のタイムラインの秒と、そこで素材をどれだけ飛ばしたか
        self.joins = []
        for p, q in zip(self.segs, self.segs[1:]):
            if abs(q[2] - p[3]) > 0.5:
                self.joins.append((q[0] / fps, p[3] / fps, q[2] / fps))   # (タイムライン, 前の素材の終わり, 次の素材の頭)
        self.join_t = [j[0] for j in self.joins]

    def to_src(self, t):
        f = t * self.fps
        i = bisect.bisect_right(self.starts, f + 1e-6) - 1
        if i < 0:
            return None
        a0, a1, s0, s1 = self.segs[i]
        if f > a1 + 1e-6:
            return None
        return (s0 + (f - a0)) / self.fps

    def pieces(self, A, B):
        """タイムラインの [A, B) に入る素材の区間 [(素材の開始, 終わり, タイムラインの開始, 終わり)]（秒）"""
        fa, fb = A * self.fps, B * self.fps
        out = []
        for a0, a1, s0, s1 in self.segs:
            lo, hi = max(a0, fa), min(a1, fb)
            if hi - lo > 0.5:
                out.append(((s0 + lo - a0) / self.fps, (s0 + hi - a0) / self.fps, lo / self.fps, hi / self.fps))
        return out

    def src_to_tl(self, s):
        f = s * self.fps
        for a0, a1, s0, s1 in self.segs:
            if s0 - 1e-6 <= f <= s1 + 1e-6:
                return (a0 + f - s0) / self.fps
        return None

    def near_join(self, t):
        if not self.join_t:
            return None, None
        i = bisect.bisect_left(self.join_t, t)
        best = None
        for k in (i - 1, i):
            if 0 <= k < len(self.joins):
                d = abs(self.joins[k][0] - t)
                if best is None or d < best[0]:
                    best = (d, self.joins[k])
        return best


def load_ai_map(args, fps):
    if args.ai_map:
        return json.load(open(args.ai_map, encoding="utf-8"))
    cuts = json.load(open(args.ai_cuts, encoding="utf-8"))
    tl = cuts.get("highlight_external_frames") or 0
    segs = []
    for s0, s1 in cuts["keep_frames"]:
        segs.append([tl, tl + (s1 - s0), s0, s1])
        tl += s1 - s0
    return segs


# ---------- 小川さんのシーケンス ----------
def load_user_clips(path, track):
    d = json.load(open(path, encoding="utf-8"))
    if "v" in d:                                       # premiere_bridge の形（秒）
        clips = [dict(s=c["s"], e=c["e"], i=c["i"], o=c["o"], n=c.get("n")) for c in d["v"][0]["clips"]]
        fps = d.get("fps")
    elif "tracks" in d:                                # tools/dump_timeline.py の形（ticks）
        rows = d["tracks"].get(track) or next(iter(d["tracks"].values()))
        clips = [dict(s=r["start_ticks"] / TPS, e=r["end_ticks"] / TPS, i=r["in_ticks"] / TPS, o=r["out_ticks"] / TPS,
                      n=r.get("name")) for r in rows if not r.get("muted")]
        fps = d.get("fps")
    else:
        sys.exit("--user-seq の形が分からない（premiere_bridge の v か、dump_timeline.py の tracks）")
    clips.sort(key=lambda c: c["s"])
    return clips, fps


def subtract(base, holes):
    """区間の引き算：base から holes を除く"""
    out = []
    for a, b in base:
        cur = [(a, b)]
        for h0, h1 in holes:
            nxt = []
            for x, y in cur:
                if h1 <= x or h0 >= y:
                    nxt.append((x, y))
                    continue
                if h0 > x:
                    nxt.append((x, h0))
                if h1 < y:
                    nxt.append((h1, y))
            cur = nxt
        out += cur
    return out


def merge(iv, tol):
    iv = sorted(iv)
    out = []
    for a, b in iv:
        if out and a <= out[-1][1] + tol:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


# ---------- 声・語・台本 ----------
class Voice:
    def __init__(self, wav, cache):
        if cache and os.path.exists(cache):
            x = np.load(cache)
        else:
            raw = subprocess.run(["ffmpeg", "-v", "error", "-i", wav, "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
                                 check=True, capture_output=True).stdout
            x = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
            n = int(SR * HOP)
            k = len(x) // n
            r = np.sqrt(np.mean(x[:k * n].reshape(k, n) ** 2, axis=1)) / 32768.0
            x = 20 * np.log10(r + 1e-9)
            if cache:
                np.save(cache, x)
        self.db = x

    def idx(self, t):
        return max(0, min(len(self.db) - 1, int(round(t / HOP))))

    def span(self, a, b):
        i0, i1 = self.idx(a), max(self.idx(a) + 1, self.idx(b))
        return self.db[i0:i1]


def load_words(path):
    units = json.load(open(path, encoding="utf-8"))
    words = []
    for u in units:
        for w in u.get("words", []):
            words.append((float(w[0]), float(w[1]), w[2], u["u"]))
    words.sort()
    return words, {u["u"]: u for u in units}


def load_script(path):
    """台本（common.py の Script の形）：区切り u → (話者, 字幕の行)・カットの行 [(u0, u1, 行)]"""
    lines, cuts = {}, []
    if not path:
        return lines, cuts
    for raw in open(path, encoding="utf-8"):
        line = raw.rstrip("\n")
        if not line or line.startswith("#"):
            continue
        body = line.split("  #", 1)[0]
        if body.startswith("x "):
            m = re.match(r"x\s+(\d+)\S*\.\.(\d+)\S*\|(.*)", body)
            if m:
                cuts.append((int(m.group(1)), int(m.group(2)), line.strip()))
            continue
        if body.startswith("h "):
            continue
        m = re.match(r"(\d+)\S*\|(.*)", body)
        if m:
            u = int(m.group(1))
            who = "聞き手" if m.group(2).startswith("@") else "話し手"
            lines.setdefault(u, []).append((who, line.strip()))
    return lines, cuts


def load_asr_spoken(paths, n):
    """文字起こし（語の時刻つき。2つ以上あるとよい）のどれかに言葉がある 10ms の印（tools/find_laugh_gaps.py と同じ見方）"""
    spoken = np.zeros(n + 200, bool)
    used = []
    for fn in paths or []:
        a = json.load(open(fn, encoding="utf-8"))
        segs = a["segments"] if isinstance(a, dict) and "segments" in a else a
        ws = []
        if isinstance(segs, list):
            for s in segs:
                for w in (s.get("words") or []) if isinstance(s, dict) else []:
                    if "start" in w and "end" in w:
                        ws.append((float(w["start"]), float(w["end"])))
        if not ws:
            continue
        used.append(os.path.basename(fn))
        for s, e in ws:
            spoken[int(s * 100):int(e * 100) + 1] = True
    return (spoken if used else None), used


def load_ai_cut_list(path):
    rows = []
    if not path:
        return rows
    for r in csv.DictReader(open(path, encoding="utf-8-sig")):
        a, b = parse_mmss(r.get("素材の開始")), parse_mmss(r.get("素材の終了"))
        if a is None or b is None:
            continue
        rows.append(dict(a=a, b=b, kind=r.get("種類", ""), why=r.get("理由", ""), text=r.get("切った中身（文字起こし）", "")))
    return rows


def load_sheet(path, cut_nos):
    if not path:
        return []
    d = json.load(open(path, encoding="utf-8"))
    cands = d["cands"] if isinstance(d, dict) else d
    out = []
    for c in cands:
        rng = []
        for a, b in c["ids"]:
            ia, ib = int(re.match(r"\d+", str(a)).group()), int(re.match(r"\d+", str(b)).group())
            if ib < ia or ib - ia > 150:
                # ids は字幕の並び順の [頭, 次に残す字幕)。並べ替えをまたぐと番号では範囲にならないので、頭の近くだけで見る
                ib = ia + 6
            rng.append((ia, ib))
        choice = None
        if cut_nos is not None:
            choice = "切る" if c["no"] in cut_nos else "残す"
        out.append(dict(no=c["no"], tier=c.get("tier"), title=c.get("title"), rng=rng, keep=c.get("keep"), choice=choice))
    return out


# ---------- 1か所を測る ----------
def silent_runs(db, a, thr, min_len):
    """db（10ms ごと）の中の、thr 以下が min_len 秒以上続く所 [(開始の秒, 長さ, 中の一番大きい dB)]"""
    q = db <= thr
    d = np.diff(np.concatenate([[0], q.astype(np.int8), [0]]))
    out = []
    for x, y in zip(np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]):
        if (y - x) * HOP >= min_len:
            out.append((a + x * HOP, (y - x) * HOP))
    return out


def straddle(words, t, pad=0.02):
    i = bisect.bisect_left(words, (t - 3.0,))
    for w in words[i:]:
        if w[0] > t:
            break
        if w[0] < t - pad and w[1] > t + pad:
            return w
    return None


def quiet_near(voice, t, thr, side, reach=0.4):
    """t の近くで、声が thr 以下になる所（30ms 続く）。side='back' は t より前へ、'fwd' は後ろへ探す"""
    steps = int(reach / HOP)
    for k in range(steps):
        x = t - k * HOP if side == "back" else t + k * HOP
        seg = voice.span(x - 0.015, x + 0.015)
        if len(seg) and seg.max() <= thr:
            return x
    return None


def measure(item, tl, voice, ai_thr, words, units, script_lines, script_cuts, ai_cuts, sheet, cap_tl, spoken):
    A, B = item["A"], item["B"]
    pcs = tl.pieces(A, B)
    item["src"] = [(round(p[0], 2), round(p[1], 2)) for p in pcs]
    # 消えた語
    ws = []
    for s0, s1, _, _ in pcs:
        i = bisect.bisect_left(words, (s0 - 3.0,))
        for w in words[i:]:
            if w[0] >= s1:
                break
            mid = (w[0] + w[1]) / 2
            if s0 <= mid < s1:
                ws.append(w)
    item["text"] = "".join(w[2] for w in ws)
    us = sorted({w[3] for w in ws})
    item["units"] = us
    whos = {who for u in us for who, _ in script_lines.get(u, [])}
    item["who"] = "・".join(sorted(whos)) if whos else "-"
    # 声：-45dB を超える秒（08 の「声が無い」の外）・AI のしきい値〜-45dB の秒（AI は声と見なすが、08 では声でない音）・中の無音
    voiced, faint, longest, max_db, sil, noword, noword_loud = 0.0, 0.0, 0.0, -120.0, [], 0.0, 0.0
    for s0, s1, _, _ in pcs:
        db = voice.span(s0, s1)
        if not len(db):
            continue
        voiced += float((db > QUIET_DB).sum()) * HOP
        faint += float(((db > ai_thr) & (db <= QUIET_DB)).sum()) * HOP
        max_db = max(max_db, float(db.max()))
        for st, ln in silent_runs(db, s0, QUIET_DB, 0.3):
            sil.append((round(st, 2), round(ln, 2)))
            longest = max(longest, ln)
        if spoken is not None:
            i0 = voice.idx(s0)
            m = ~spoken[i0:i0 + len(db)]
            # 言葉の無い所（どの文字起こしにも語が無い）が 0.5秒以上続く所
            d = np.diff(np.concatenate([[0], m.astype(np.int8), [0]]))
            for x, y in zip(np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]):
                if (y - x) * HOP >= 0.5:
                    noword += (y - x) * HOP
                    noword_loud += float((db[x:y] > ai_thr).sum()) * HOP
    item["voiced_sec"] = round(voiced, 2)
    item["faint_sec"] = round(faint, 2)
    item["longest_silence"] = round(longest, 2)
    item["max_db"] = round(max_db, 1)
    item["noword_sec"] = round(noword, 2)
    item["noword_sound_sec"] = round(noword_loud, 2)
    gaps = []
    for st, ln in sil:
        over = [w for w in words[bisect.bisect_left(words, (st - 3.0,)):] if w[0] < st + ln and w[1] > st][:3]
        over = [w for w in over if w[0] < st + ln - 0.05 and w[1] > st + 0.05]
        gaps.append(dict(at=st, len=ln, words_over=[f"{w[2]}[{w[3]}] {w[0]:.2f}-{w[1]:.2f}" for w in over]))
    item["gaps"] = gaps
    # 小川さんの切り口（tools/check_chops.py と同じ見方：残す側の端2フレームが声で、消した側の0.1秒も声）
    fps = tl.fps
    s_out = tl.to_src(A - 1e-4) if A > tl.first + 1e-3 else None
    s_in = tl.to_src(B + 1e-4) if B < tl.end - 1e-3 else None
    cut_q = []
    if s_out is not None and voice.span(s_out - 2 / fps, s_out).max() > VOICE_DB and voice.span(s_out, s_out + 0.1).max() > VOICE_DB:
        w = straddle(words, s_out)
        q = quiet_near(voice, s_out, QUIET_DB, "back")
        cut_q.append(f"前の声の途中で切っている{'（語「' + w[2] + '」）' if w else ''}"
                     + (f"→ {s_out - q:.2f}秒前の静かな所で切る候補" if q is not None else ""))
    if s_in is not None and voice.span(s_in, s_in + 2 / fps).max() > VOICE_DB and voice.span(s_in - 0.1, s_in).max() > VOICE_DB:
        w = straddle(words, s_in)
        q = quiet_near(voice, s_in, QUIET_DB, "back")
        cut_q.append(f"次の声の途中から入っている{'（語「' + w[2] + '」）' if w else ''}"
                     + (f"→ {s_in - q:.2f}秒前の静かな所から入る候補" if q is not None else ""))
    item["user_cut"] = cut_q or ["声の切れ目"]
    item["src_out"], item["src_in"] = s_out, s_in
    # AI のつなぎ目
    near = []
    for side, t in (("頭", A), ("終わり", B)):
        d = tl.near_join(t)
        if d and d[0] is not None and d[0] <= 0.15:
            near.append(f"小川さんのカットの{side}が AI のつなぎ目から {d[0]:.2f}秒")
    item["ai_join"] = near
    rel = []
    for c in ai_cuts:
        for s in (s_out, s_in):
            if s is not None and (abs(c["b"] - s) <= 0.15 or abs(c["a"] - s) <= 0.15):
                rel.append(f"AI のカット 素材 {ff(c['a'])}-{ff(c['b'])}（{c['kind']}）{c['why'][:70]}")
    item["ai_cut_here"] = sorted(set(rel))
    caps = [(cid, t) for cid, t in cap_tl if A - 0.05 <= t <= B + 0.4]
    item["captions"] = [f"字幕{cid} の頭 {ff(t)}（{'カットの中' if t < B - 0.05 else 'カットの直後'}）" for cid, t in caps]
    sl = []
    if us:
        lo, hi = min(us) - 1, max(us) + 1
        for u in range(lo, hi + 1):
            for _, ln in script_lines.get(u, []):
                sl.append(ln)
        for u0, u1, ln in script_cuts:
            if u1 >= lo and u0 <= hi:
                sl.append(ln)
    item["script"] = sl
    sh = []
    for c in sheet:
        if us and any(a <= u < b for a, b in c["rng"] for u in us):
            sh.append(f"No.{c['no']}（{c['tier']}）{c['title']}" + (f" → 小川さんの選び：{c['choice']}" if c["choice"] else "")
                      + (f"／AI の残す案：{c['keep'][:60]}" if c.get("keep") else ""))
    item["sheet"] = sh
    # 種類（目安）
    dur = B - A
    if len(item["text"]) <= 1 or (item["noword_sec"] >= 0.5 * dur and len(item["text"]) <= 4):
        kind = "言葉の無い音・間"
    elif dur >= 8:
        kind = "話の塊"
    elif near and dur < 1.5:
        kind = "切り残し（AI のつなぎ目の横）"
    elif item["who"] == "聞き手" and dur < 3:
        kind = "聞き手の一言"
    elif len(item["text"]) <= 8:
        kind = "一言・言いかけ"
    else:
        kind = "一文"
    item["kind"] = kind
    return item


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ai-map")
    ap.add_argument("--ai-cuts")
    ap.add_argument("--ai-cut-list")
    ap.add_argument("--user-seq", required=True)
    ap.add_argument("--user-track", default="V1")
    ap.add_argument("--user-media", choices=["ai_export", "source"], default="ai_export")
    ap.add_argument("--units", required=True)
    ap.add_argument("--voice", required=True)
    ap.add_argument("--voice-cache")
    ap.add_argument("--thr", type=float)
    ap.add_argument("--script")
    ap.add_argument("--asr", nargs="*", help="語の時刻つきの文字起こし（2つ以上あるとよい。言葉の無い所を見る。tools/find_laugh_gaps.py と同じ）")
    ap.add_argument("--sheet")
    ap.add_argument("--sheet-cut", help="判断シートで小川さんが「切る」を選んだ No（カンマ区切り）")
    ap.add_argument("--fps", default="30000/1001")
    ap.add_argument("--min-cut", type=float, default=0.05, help="これより短い差は数えない（秒）")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    if not a.ai_map and not a.ai_cuts:
        sys.exit("--ai-map か --ai-cuts が要る")
    fps = float(Fraction(a.fps))
    tl = AiTimeline(load_ai_map(a, fps), fps)
    cutsj = json.load(open(a.ai_cuts, encoding="utf-8")) if a.ai_cuts else {}
    thr = a.thr if a.thr is not None else (cutsj.get("params", {}).get("voice_thr_db") or QUIET_DB)   # AI が「声」と見なしたしきい値
    cap_tl = sorted(((cid, f / fps) for cid, f in (cutsj.get("caption_tl") or {}).items()), key=lambda x: x[1])
    if a.ai_map and cutsj.get("caption_tl"):
        # 字幕の位置は cuts の時刻（書き出しの版と少しずれることがある）。素材の秒を通して、この対応の位置に置き直す
        base = AiTimeline(load_ai_map(argparse.Namespace(ai_map=None, ai_cuts=a.ai_cuts), fps), fps)
        cap_tl = sorted(((cid, tl.src_to_tl(base.to_src(t) or -1) or t) for cid, t in cap_tl), key=lambda x: x[1])
    clips, _ = load_user_clips(a.user_seq, a.user_track)
    words, units = load_words(a.units)
    script_lines, script_cuts = load_script(a.script)
    ai_cuts = load_ai_cut_list(a.ai_cut_list)
    sheet = load_sheet(a.sheet, {int(x) for x in a.sheet_cut.split(",")} if a.sheet_cut else None)
    voice = Voice(a.voice, a.voice_cache)
    spoken, asr_used = load_asr_spoken(a.asr, len(voice.db))

    items, added = [], []
    notes = []
    if a.user_media == "ai_export":
        kept = merge([(c["i"], c["o"]) for c in clips], 1.0 / fps)
        removed = subtract([(0.0, tl.end)], [tuple(k) for k in kept])
        back = [k for k, (p, q) in enumerate(zip(clips, clips[1:])) if q["i"] < p["o"] - 0.5 / fps]
        if back:
            notes.append(f"順番を入れ替えた・同じ所を2回使ったクリップ：{len(back)}か所（クリップ番号 {back}）")
    else:
        ai_src = merge([(s[2] / fps, s[3] / fps) for s in tl.segs], 1.0 / fps)
        user_src = merge([(c["i"], c["o"]) for c in clips], 1.0 / fps)
        rem_src = subtract([tuple(x) for x in ai_src], [tuple(x) for x in user_src])
        add_src = subtract([tuple(x) for x in user_src], [tuple(x) for x in ai_src])
        removed = []
        for s0, s1 in rem_src:
            t0, t1 = tl.src_to_tl(s0 + 1e-3), tl.src_to_tl(s1 - 1e-3)
            if t0 is not None and t1 is not None:
                removed.append((t0, t1))
        removed = [tuple(x) for x in merge(removed, 1.0 / fps)]
        for s0, s1 in add_src:
            if s1 - s0 >= a.min_cut:
                txt = "".join(w[2] for w in words if s0 <= (w[0] + w[1]) / 2 < s1)
                added.append(dict(src=(round(s0, 2), round(s1, 2)), dur=round(s1 - s0, 2), text=txt))
    for A, B in removed:
        if B - A < a.min_cut:
            continue
        it = dict(n=len(items) + 1, A=A, B=B, dur=round(B - A, 2))
        if A < tl.first - 1e-3:
            it["note"] = "AI の版の頭（ハイライトなど、対応の外）"
        # 小川さんのシーケンスの位置（カットの直後）
        pos = None
        if a.user_media == "ai_export":
            for c in clips:
                if abs(c["i"] - B) <= 1.0 / fps:
                    pos = c["s"]
                    break
        it["user_pos"] = pos
        measure(it, tl, voice, thr, words, units, script_lines, script_cuts, ai_cuts, sheet, cap_tl, spoken)
        items.append(it)

    out = dict(params=dict(ai_thr=thr, quiet_db=QUIET_DB, voice_db=VOICE_DB, fps=a.fps, user_media=a.user_media, asr=asr_used), notes=notes,
               total_removed=round(sum(i["dur"] for i in items), 2), items=items, added=added)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump(out, open(a.out + ".json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)

    kinds = {}
    for i in items:
        kinds.setdefault(i["kind"], []).append(i)
    L = [f"# 小川さんの直しと AI の版の差（{len(items)}か所・合わせて {out['total_removed']:.1f}秒）", "",
         f"声：{QUIET_DB:.0f}dB を超える所（08 の「声が無い」の外）。AI が声と見なしたしきい値は {thr:.1f}dB。切り口の声は {VOICE_DB:.0f}dB（check_chops と同じ）。"
         f"言葉の無い所は文字起こし {len(asr_used)}本（{'・'.join(asr_used) or '無し'}）のどれにも語が無い 0.5秒以上。種類は道具の目安。**全部未聴取**（波形と文字起こしで見ただけ）", ""]
    L += [f"- {n}" for n in notes]
    L += ["", "| 種類 | か所 | 秒 |", "|---|---|---|"]
    for k, v in sorted(kinds.items(), key=lambda kv: -sum(x["dur"] for x in kv[1])):
        L.append(f"| {k} | {len(v)} | {sum(x['dur'] for x in v):.1f} |")
    L += ["", "| # | 小川さんの位置 | AI の版 | 長さ | 種類 | 話者 | 消えた言葉 | 小川さんの切り口 |", "|---|---|---|---|---|---|---|---|"]
    for i in items:
        L.append(f"| {i['n']} | {ff(i['user_pos'])} | {ff(i['A'])} | {i['dur']:.2f} | {i['kind']} | {i['who']} | "
                 f"{i['text'][:40]}{'…' if len(i['text']) > 40 else ''} | {'／'.join(i['user_cut'])} |")
    L += ["", "## 1か所ずつ（AI の版でどうだったか）", ""]
    for i in items:
        L.append(f"### {i['n']}. {ff(i['user_pos'])}（AI の版 {ff(i['A'])}〜{ff(i['B'])}・{i['dur']:.2f}秒・{i['kind']}）")
        L.append(f"- 消えた言葉：{i['text'] or '（無し）'}（区切り {i['units'][:1]}〜{i['units'][-1:]}）")
        L.append(f"- 声（{QUIET_DB:.0f}dB 超）{i['voiced_sec']}秒・AI だけが声と見なす小さい音 {i['faint_sec']}秒・言葉の無い所 {i['noword_sec']}秒（うち音がある {i['noword_sound_sec']}秒）・"
                 f"中の一番長い無音 {i['longest_silence']}秒・最大 {i['max_db']}dB・素材 {i['src']}")
        for g in i["gaps"]:
            L.append(f"- 無音 {g['at']:.2f}秒から {g['len']:.2f}秒" + (f"：語の時刻がかかっている {g['words_over']}" if g["words_over"] else ""))
        for x in i["ai_join"] + i["ai_cut_here"] + i["captions"] + i["sheet"]:
            L.append(f"- {x}")
        L.append(f"- 小川さんの切り口：{'／'.join(i['user_cut'])}")
        if i["script"]:
            L.append("- 台本の行（AI の決め）：")
            L += [f"  - `{s[:140]}`" for s in i["script"][:12]]
        L.append("")
    if added:
        L += ["## 小川さんが戻した（AI の版に無い素材を使った）所", ""]
        L += [f"- 素材 {ff(x['src'][0])}〜{ff(x['src'][1])}（{x['dur']}秒）{x['text'][:60]}" for x in added]
    open(a.out + ".md", "w", encoding="utf-8").write("\n".join(L) + "\n")
    print(f"{a.out}.md：{len(items)}か所・{out['total_removed']:.1f}秒" + (f"・戻した {len(added)}か所" if added else ""))
    for k, v in kinds.items():
        print(f"  {k}: {len(v)}か所 {sum(x['dur'] for x in v):.1f}秒")


if __name__ == "__main__":
    main()
