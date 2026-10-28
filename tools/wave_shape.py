#!/usr/bin/env python3
"""間と語尾を、秒数や決まった音量の線ではなく「波形の形」で決める道具（08 の cut.no_chop.sound・cut.pauses。2026-10-28 から）。

小川さん（2026-10-28）「秒数で定義するのが良くない…俺は波形を見て、耳で聞いて切っている」→ 波形の形で決める案に「合ってる」。
決まりは 08 が正。この道具は、その決まりを波形の数字に置き換えるだけ（数字はこの中だけで使い、ルールには書かない）。

見ること（どれも、その録音の「部屋の音の高さ」を基準にする。決まった dB の線は使わない）:
  部屋の音の高さ … 録音全体の声の大きさ（10ms ごと）の低い方から1割の値。1025 は約 −81dB、1026 は約 −70dB で、録音ごとに違う。
  平らな所       … 声の無い所。まわりの一番低い所（その場の底）から少しの幅に収まり、部屋の音に近いまま続く所。
  坂             … 語尾が下がって平らな所に着くまで（下がりきる坂）と、平らな所から次の声が上がる所（言い出しの坂）。残す。
  揺れている所   … その場の底が部屋の音よりずっと高い所（笑い・相手の声・息が重なっている）。平らな所と見なさず、聴いてもらう一覧に出す。

平らな所（残す区間をつないだ時に聞こえる物。つなぎ目をまたぐ物は1つに数える）:
  --mode で詰める物を選ぶ（plan_flats）。詰める時は、語尾の坂の後に少し・言い出しの坂の前に少しを残す（小川さんは声の際から 0.02〜0.06秒）。
  long＝その録音の中で「目立って長い」平らな所（長さの長い方から5%）だけ（既定。08 の pauses.rule。1025・1026 の手の直しでは、小川さんは
       つなぎ目の長い平らな所をほぼ全部詰め、短い所は2〜8%・文の途中はほぼ詰めていなかった）
  rule＝つなぎ目と字幕の境の平らな所は全部・文の途中は目立って長い物だけ　　all＝全部
つなぎ目ごとに出すもの（--cuts の keep_frames の、となり合う2つの残す区間の間）:
  tail    … 左の区間の終わりが、語尾の坂の途中で切れている。素材を後ろへ見て、下がりきる所まで戻す案（次の語が上がり始める前に着く時だけ）
  head    … 右の区間の頭が、言い出しの坂の途中から始まっている。素材を前へ見て、上がり始める手前まで戻す案
  shaky   … つなぎ目のまわりに部屋の音に近い所が無い（笑い・相手の声・息が重なっている）。切らずに一覧に出す
            （1026 v004 の 4:47：三上さんの笑いが重なって詰めすぎ、小川さんが戻した）
  chop    … 坂の途中で切れているが、すぐ次の語の声につながっていて、戻すと切った言葉が入る所。耳で決める
  「思って｜て」の「て」のように、小さい「っ」の無音の後の語尾は波形では見分けられない。tools/check_tails.py が字幕と書き起こしで見る。

使い方:
  python3 tools/wave_shape.py --env <edit>/analysis/camera_env.npy --cuts <版>/_work/cuts_vNNN.json \\
      [--captions <版>/_work/captions_vNNN.json] [--mode long|rule|all] [--keep-ranges 詰めない所.json] [--from 秒 --to 秒] [--out 一覧.tsv] [--json 結果.json]
  （--json の cuts が詰める素材の範囲。案件の cuts_plan の EXTRA_CUTS などに入れて組み直す。joins の tail・head は戻す案、shaky・chop は耳で決める）
  （--from・--to は素材の秒。小川さんが手で直した範囲を外す時などに使う）
  ほかの道具から使う時は import して plan_flats()・join_shape()・room_floor() を呼ぶ。

声の大きさ（camera_env.npy）は 10ms ごとの dB（素材の秒×100 が添え字）。無い時は --wav で素材の声（16kHz mono）から作る。
AI は音を出さないので、これは波形で見た案。揺れている所・chop は小川さんの耳で決める（08 の no_chop.sound の listen）。
"""
import argparse
import bisect
import json
import os
import sys

import numpy as np

FPS = 30000 / 1001
STEP = 0.01          # 声の大きさの1コマ（10ms）

# この道具の中だけで使う数字（ルールには書かない。1025・1026 の小川さんの手の直しで当てて決めた。README・08 の pauses.measure）
SMOOTH = 3           # 3コマ（30ms）の真ん中の値でならす（一瞬の音で平らな所が切れないように）
FLAT_RANGE = 6.0     # 平らな所＝その場の底から 6dB の中に収まる所
NEAR_ROOM = 12.0     # 平らな所は、部屋の音から 12dB の中（これより上の谷は音節の間の切れ目で、平らな所ではない）
SHAKY_OVER = 20.0    # その場の底が部屋の音より 20dB 以上高い時は、揺れている所（平らな所ではない）
LOUD = 20.0          # 部屋の音よりこれだけ大きい声は、はっきりした声（次の語の始まりの判定に使う）
LOOK = 1.5           # つなぎ目の前後を見る長さ（秒）
BASE_LOOK = 0.4      # その場の底を、つなぎ目の前後この長さの中で探す
TAIL_KEEP = 0.03     # 語尾が平らな所に着いてから残す（小川さんは声の際から 0.02〜0.06秒）
HEAD_KEEP = 0.04     # 言い出しの上がり始めの前に残す（小川さんが詰めた所は声の際から 0.02〜0.06秒）
REACH = 0.5          # 語尾の坂を素材の後ろへ探す長さ（これより長く下がらない時は、語尾ではなく次の語）
RISE = 12.0          # 下がる途中でこれだけ上がり、はっきりした声になったら、次の語が始まった（語尾の中の揺れは数えない）
LONG_PCT = 95        # 「目立って長い」平らな所＝その録音の平らな所の長さの、長い方から5%（1025・1026 の手の直しに一番近かった）
MIN_CHANGE = 2 / FPS  # これより小さい直しは出さない（2コマ）


def env_from_wav(path):
    import wave
    with wave.open(path) as f:
        sr = f.getframerate()
        x = np.frombuffer(f.readframes(f.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    n = int(sr * STEP)
    m = len(x) // n
    x = x[:m * n].reshape(m, n)
    return (20 * np.log10(np.sqrt((x ** 2).mean(axis=1)) + 1e-9)).astype(np.float32)


def smooth(env, k=SMOOTH):
    if k <= 1:
        return env
    p = k // 2
    e = np.pad(env, p, mode="edge")
    return np.median(np.lib.stride_tricks.sliding_window_view(e, k), axis=1).astype(np.float32)


def room_floor(env):
    """その録音の部屋の音の高さ（声の大きさの低い方から1割）"""
    return float(np.percentile(env, 10))


def _i(t, n):
    return int(min(max(round(t / STEP), 0), n - 1))


class Wave:
    def __init__(self, env):
        self.raw = np.asarray(env, dtype=np.float32)
        self.s = smooth(self.raw)
        self.n = len(self.s)
        self.floor = room_floor(self.raw)

    def at(self, t):
        return float(self.s[_i(t, self.n)])

    def base(self, t0, t1):
        """t0〜t1 の中の、その場の底（低い方から1割）"""
        i0, i1 = _i(t0, self.n), _i(t1, self.n) + 1
        seg = self.s[i0:i1]
        return float(np.percentile(seg, 10)) if len(seg) else self.at(t0)

    def flat(self, t, base):
        v = self.at(t)
        return v <= base + FLAT_RANGE and v <= self.floor + NEAR_ROOM

    def new_word(self, v, lo):
        return v > lo + RISE and v > self.floor + LOUD


def join_shape(w, b1, a2, left_lo=None, right_hi=None):
    """となり合う残す区間 [.., b1) と [a2, ..)（素材の秒）のつなぎ目で、坂の途中で切れていないかを見る。
    kinds：ok・tail（語尾の坂の途中で切れている→下がりきる所まで戻す案 new_b1）・head（言い出しの坂の途中から→上がり始めの手前まで戻す案 new_a2）・
    chop（坂の途中で切れていて、すぐ次の声につながる＝戻すと切った言葉が入る。耳で決める）・shaky（つなぎ目のまわりに部屋の音に近い所が無い＝笑い・声・息が重なっている。耳で決める）"""
    left_lo = b1 - LOOK if left_lo is None else max(left_lo, b1 - LOOK)
    right_hi = a2 + LOOK if right_hi is None else min(right_hi, a2 + LOOK)
    near = [x for x in (w.s[_i(max(left_lo, b1 - BASE_LOOK), w.n):_i(b1, w.n)],
                        w.s[_i(a2, w.n):_i(min(right_hi, a2 + BASE_LOOK), w.n)]) if len(x)]
    base = float(np.percentile(np.concatenate(near), 10)) if near else w.at(b1)
    r = {"b1": b1, "a2": a2, "base": round(base, 1), "floor": round(w.floor, 1), "kinds": [], "new_b1": b1, "new_a2": a2}
    if base > w.floor + NEAR_ROOM:
        lo_l, lo_r = w.at(b1 - STEP), w.at(a2)
        if lo_l < w.floor + LOUD or lo_r < w.floor + LOUD:
            r["kinds"].append("shaky")
            r["why"] = f"つなぎ目のまわりに部屋の音に近い所が無い（その場の底が部屋の音より {base - w.floor:.0f}dB 上。笑い・声・息が重なっている見込み）"
            return r
    # 語尾の坂の途中で切れているか（左の区間の終わりが平らでない）
    if not w.flat(b1 - STEP, base):
        t2, lo = b1, w.at(b1)
        while t2 < b1 + REACH:
            v = w.at(t2)
            if w.flat(t2, base):
                break
            if w.new_word(v, lo):
                t2 = None
                break
            lo = min(lo, v)
            t2 += STEP
        else:
            t2 = None
        if t2 is not None and t2 - b1 >= MIN_CHANGE:
            r["kinds"].append("tail")
            r["new_b1"] = round(t2 + TAIL_KEEP, 3)
            r["why_tail"] = f"語尾の坂の途中で切れている。素材であと {t2 - b1:.2f}秒で下がりきる"
        elif t2 is None and w.at(b1 - STEP) > w.floor + NEAR_ROOM:
            r["kinds"].append("chop")
            r["why_chop"] = "語尾が下がりきらないまま次の声につながっている（戻すと切った言葉が入る。耳で決める）"
    # 言い出しの坂の途中から始まっているか（右の区間の頭が平らでない）
    if not w.flat(a2, base):
        t3, lo = a2, w.at(a2)
        while t3 > a2 - REACH:
            v = w.at(t3 - STEP)
            if w.flat(t3 - STEP, base):
                break
            if w.new_word(v, lo):
                t3 = None
                break
            lo = min(lo, v)
            t3 -= STEP
        else:
            t3 = None
        if t3 is not None and a2 - t3 >= MIN_CHANGE:
            r["kinds"].append("head")
            r["new_a2"] = round(t3 - HEAD_KEEP, 3)
            r["why_head"] = f"言い出しの坂の途中から始まっている。素材であと {a2 - t3:.2f}秒前から上がっている"
    if not r["kinds"]:
        r["kinds"].append("ok")
    return r


def audible_flats(w, keep):
    """残す区間をつないだ時に聞こえる平らな所（つなぎ目をまたぐ物は1つに数える）。
    返す物：[{"len": 聞こえる長さ, "parts": [(素材の始め, 素材の終わり), ...]（区間ごと）, "tl": 版の秒}]"""
    idx, tl0 = [], []
    t = 0.0
    for a, b in keep:
        i0, i1 = int(round(a / STEP)), int(round(b / STEP))
        idx.extend(range(i0, i1))
        tl0.append(t)
        t += b - a
    idx = np.clip(np.array(idx, dtype=np.int64), 0, w.n - 1)
    lv = w.s[idx]
    n = len(lv)
    base = np.empty(n, dtype=np.float32)
    for k in range(0, n, 5):
        base[k:k + 5] = np.percentile(lv[max(0, k - 50):min(n, k + 50)], 10)
    flat = (lv <= base + FLAT_RANGE) & (lv <= w.floor + NEAR_ROOM)
    d = np.diff(np.concatenate([[0], flat.astype(np.int8), [0]]))
    out = []
    for s, e in zip(np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]):
        src = idx[s:e]
        parts, p0 = [], 0
        for q in range(1, len(src) + 1):
            if q == len(src) or src[q] != src[q - 1] + 1:
                parts.append((src[p0] * STEP, (src[q - 1] + 1) * STEP))
                p0 = q
        out.append({"len": round((e - s) * STEP, 2), "parts": parts, "tl": round(s * STEP, 2)})
    return out


def plan_flats(w, keep, cap_starts=(), mode="long", keep_ranges=()):
    """詰める平らな所と、詰める素材の範囲（08 の pauses.rule）。
    mode="long"（既定。08 の pauses.rule）：どこでも「目立って長い」物（その録音の平らな所の長さの長い方から5%より長い）だけ、坂まで詰める
              （1025・1026 の手の直しでは、小川さんはつなぎ目の長い平らな所をほぼ全部詰め、短い所は2〜8%しか詰めていなかった）
    mode="rule"：つなぎ目と字幕の境の平らな所は全部、文の途中は「目立って長い」物だけ
    mode="all" ：平らな所を全部
    keep_ranges（素材の秒の (a, b)）にかかる物は詰めない（溜め・問いの札を読む間・顔の演技など、中身で決めた所）"""
    fl = audible_flats(w, keep)
    ends = [b for a, b in keep]
    starts = [a for a, b in keep]
    caps = sorted(cap_starts)

    def near(x, arr, d=0.02):
        k = bisect.bisect_left(arr, x - d)
        return k < len(arr) and arr[k] <= x + d
    for f in fl:
        a0, b0 = f["parts"][0][0], f["parts"][-1][1]
        f["at_join"] = bool(len(f["parts"]) > 1 or near(b0, ends) or near(a0, starts))
        k = bisect.bisect_left(caps, a0 - 0.05)
        f["at_caption"] = bool(k < len(caps) and caps[k] <= b0 + 0.25)
    mid = [f["len"] for f in fl if not f["at_join"] and not f["at_caption"] and f["len"] >= 0.06]
    allv = [f["len"] for f in fl if f["len"] >= 0.06]
    long_mid = float(np.percentile(mid, LONG_PCT)) if mid else 1e9
    long_all = float(np.percentile(allv, LONG_PCT)) if allv else 1e9
    cuts = []
    for f in fl:
        bnd = f["at_join"] or f["at_caption"]
        if mode == "all":
            go = True
        elif mode == "long":
            go = f["len"] > long_all
        else:
            go = bnd or f["len"] > long_mid
        f["long"] = bool(f["len"] > (long_all if mode == "long" else long_mid))
        if not go:
            continue
        a0, b0 = f["parts"][0][0], f["parts"][-1][1]
        if any(a0 < kb and b0 > ka for ka, kb in keep_ranges):
            f["skip"] = "中身で残すと決めた所"
            continue
        total = f["len"]
        cut_len = total - TAIL_KEEP - HEAD_KEEP
        if cut_len < MIN_CHANGE:
            continue
        lo_v, hi_v = TAIL_KEEP, total - HEAD_KEEP
        pos = 0.0
        for a, b in f["parts"]:
            L = b - a
            s, e = max(lo_v, pos), min(hi_v, pos + L)
            if e - s > 0.005:
                cuts.append((round(a + (s - pos), 3), round(a + (e - pos), 3)))
            pos += L
        f["cut"] = round(cut_len, 2)
    return cuts, fl, {"文の途中の目立って長い": round(long_mid, 2), "全体の目立って長い": round(long_all, 2)}


def mmss(t):
    return f"{int(t // 60)}:{t % 60:05.2f}"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--env", help="analysis/camera_env.npy（10ms ごとの dB）")
    ap.add_argument("--wav", help="--env が無い時：素材の声（16kHz mono wav）")
    ap.add_argument("--cuts", required=True, help="cuts_vNNN.json（keep_frames）")
    ap.add_argument("--mode", choices=["long", "rule", "all"], default="long",
                    help="long＝08 のとおり（目立って長い平らな所だけ。2026-10-28 小川さん「それで直して」）／rule＝つなぎ目と字幕の境は全部・文の途中は目立って長い物だけ／all＝全部")
    ap.add_argument("--captions", help="captions_vNNN.json（字幕の境を見る。無いとつなぎ目だけを境とみる）")
    ap.add_argument("--keep-ranges", help="詰めない所（素材の秒の [[a, b], ...] の json。溜め・問いの札を読む間など）")
    ap.add_argument("--from", dest="lo", type=float, default=0.0, help="素材の秒（これより前は見ない）")
    ap.add_argument("--to", dest="hi", type=float, default=1e9, help="素材の秒（これより後ろは見ない）")
    ap.add_argument("--fps", type=float, default=FPS)
    ap.add_argument("--out", help="一覧（tsv）")
    ap.add_argument("--json", help="結果（json。cuts＝詰める素材の範囲、joins＝つなぎ目の坂の見立て）")
    a = ap.parse_args()
    env = np.load(a.env) if a.env else env_from_wav(a.wav)
    w = Wave(env)
    keep_all = [(x / a.fps, y / a.fps) for x, y in json.load(open(a.cuts))["keep_frames"]]
    keep = [(x, y) for x, y in keep_all if y > a.lo and x < a.hi]
    kr = [tuple(x) for x in json.load(open(a.keep_ranges))] if a.keep_ranges else []
    caps = []
    if a.captions:
        cj = json.load(open(a.captions))
        caps = [c["src"] for c in (cj["captions"] if isinstance(cj, dict) else cj) if c.get("src") is not None]
    cuts, flats, long_ = plan_flats(w, keep, caps, a.mode, kr)
    joins = []
    tl, tls = 0.0, []
    for x, y in keep:
        tls.append(tl)
        tl += y - x
    for k in range(1, len(keep)):
        r = join_shape(w, keep[k - 1][1], keep[k][0], keep[k - 1][0], keep[k][1])
        r["tl"] = round(tls[k], 2)
        joins.append(r)
    count = {}
    for r in joins:
        for kd in r["kinds"]:
            count[kd] = count.get(kd, 0) + 1
    print(f"部屋の音の高さ {w.floor:.1f}dB・聞こえる平らな所 {len(flats)}（{long_}）・"
          f"詰める案 {sum(1 for f in flats if f.get('cut'))} か所 {sum(e - s for s, e in cuts):.2f}秒（--mode {a.mode}）")
    print(f"つなぎ目 {len(joins)}：" + "・".join(f"{k} {v}" for k, v in sorted(count.items())))
    res = {"room_floor_db": round(w.floor, 1), "mode": a.mode, "long_flat_sec": long_, "cuts": cuts, "flats": flats, "joins": joins, "count": count}
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write("版の時刻\t種類\t素材の秒\t案\t理由\n")
            for fl in flats:
                if fl.get("cut") or fl.get("skip"):
                    f.write(f"{mmss(fl['tl'])}\t平らな所 {fl['len']:.2f}\t{fl['parts'][0][0]:.2f}〜{fl['parts'][-1][1]:.2f}\t"
                            f"{'詰める ' + str(fl['cut']) if fl.get('cut') else '残す'}\t{fl.get('skip', ('つなぎ目' if fl.get('at_join') else '字幕の境' if fl.get('at_caption') else '文の途中') + ('・目立って長い' if fl.get('long') else ''))}\n")
            for r in joins:
                if r["kinds"] == ["ok"]:
                    continue
                why = " / ".join(r.get(k, "") for k in ("why", "why_tail", "why_head", "why_chop") if r.get(k))
                f.write(f"{mmss(r['tl'])}\t{','.join(r['kinds'])}\t{r['b1']:.2f}→{r['a2']:.2f}\t{r['new_b1']:.2f}→{r['new_a2']:.2f}\t{why}\n")
        print("一覧 →", a.out)
    if a.json:
        json.dump(res, open(a.json, "w"), ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
