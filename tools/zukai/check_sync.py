#!/usr/bin/env python3
"""図解・画像（Z*・I*・L*）の部品が、今の版の声と合っているかを測る検査（工程9。どの案件でも使える道具）。
元：1026 AI未来予測 v003（2026-10-27 小川さん「図解のタイミングとか発声と会ってない」）。v003 は最後のカットの直しの後、
shift.py が I06 で止まったのを rebuild_all.sh の `grep -c … || true` が隠し、図解・画像が1つ前のカットの時刻のまま組み上がった
（部品が声より 0.3〜7秒遅い）。確認の画像（静止画）と確かめ係では見つからなかったので、数字で見る。

  python3 tools/zukai/check_sync.py --ver <edit/vNNN> [--json <出す.json>] [KEY …]

見ること（1つでも当たれば終了コード 1）：
  ① 描いた時のカットと今のカットの差：図解の動画（overlay）は描いた時のカットの声に合わせて部品を置いている。
     overlay と同じフォルダの manifest.json の src_ranges（描いた時の素材のコマ）と、今の版で同じ区間に流れる素材のコマを
     1コマずつ比べる。いちばん多い差＝全体の遅れ（±9コマ＝0.3秒を超えたら落第）。その分ずらしても 3コマ以上・±9コマを超えて
     違う所が残れば、区間の中のカットが変わった＝「描き直し」（残らなければ shift.py でずらすだけで合う）
  ② SE の目印と声：manifest の se_events の why に「字幕ID「言葉」」があれば、その言葉の聞こえ始め（文字起こしの語の時刻を
     今のカットでつないだもの）と SE のコマの差。-0.15〜+0.30秒の外は「早い／遅い」
  ③ 部品の表（<図解のフォルダ>/<KEY>/beats.json があれば。retime.py と同じ形）：[{"part", "cap_id", "word"}]。部品のコマは page.html の
     const F の値（"f" があればそれ）。②と同じ物差し。物差しは retime.py が置いた所と同じ：
     "at": "cap" の行は字幕の頭、"pad" の行は言葉の聞こえ始め＋pad（文字起こしの語の頭が声とずれる所を、声の大きさで測って直した分）。
     ②の SE が beats.json の部品と同じコマなら、その部品の行（asr・pad・at）で測る（2026-10-27 1026 v004 Z6：SE の行は
     文字起こしの書き方〈ChatGPT→チャット〉を使えず、句の別の語と比べて落第に出た）
語の時刻は whisper の語の時刻（聞こえ始めより 0.05〜0.15秒ずれることがある）。言葉が見つからない行は「測れない」に出す（落第にしない）。
"""
import argparse
import difflib
import glob
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from case import Case, add_args  # noqa: E402
from tl import TL, ts, FPS  # noqa: E402
from make_zukai import src_ranges  # noqa: E402

LATE, EARLY, DRIFT = 9, -4, 9          # コマ（+0.30秒・-0.15秒・±0.30秒）


def flat(rs):
    out = []
    for a, b in rs:
        out.extend(range(a, b))
    return out


class Words:
    def __init__(self, tl):
        self.tl, self.ws = tl, tl.words()

    def onset(self, cid, quote, hint=None):
        """字幕 cid の中で quote（字幕の書き方）が始まる語の、タイムラインのコマ。
        hint＝文字起こしでの書き方（Addness → アドネス など。字幕と書き方が違う言葉）。字幕の頭の 15コマ前から探す
        （言葉が字幕の頭より少し前から聞こえることがある。1026 v004 の 717+1「Addness」）"""
        c = self.tl.caps.get(cid)
        if not c:
            return None, f"字幕 {cid} が今の版に無い"
        ws = [x for x in self.ws if c["s"] - 15 <= x["tl"] < c["e"]]
        if not ws:
            return None, f"字幕 {cid} の語が無い"
        asr = "".join(x["word"] for x in ws)
        starts, acc = [], 0
        for x in ws:
            starts.append(acc)
            acc += len(x["word"])

        def word_at(pos):
            i = max(j for j, s0 in enumerate(starts) if s0 <= max(0, pos))
            return ws[i]["tl"], ws[i]["word"]
        text, q = c["text"].replace("／", ""), quote.replace("／", "")
        k = next((text.find(q[:n]) for n in (6, 4, 3, 2) if q[:n] and text.find(q[:n]) >= 0), -1)
        if k < 0:
            return None, f"「{quote}」が字幕 {cid}（{text}）に無い"
        # 字幕の中の位置から、文字起こしの中のおおよその位置を出す
        guess = None
        for a_, b_, n in difflib.SequenceMatcher(None, text, asr, autojunk=False).get_matching_blocks():
            if a_ <= k < a_ + n:
                guess = b_ + (k - a_)
                break
            if a_ > k:
                guess = max(0, b_ - (a_ - k))
                break
        if guess is None:
            guess = int(len(asr) * k / max(1, len(text)))
        # 言葉そのもの（か hint）が文字起こしにあれば、おおよその位置にいちばん近い所
        for cand in [h for h in (hint, q[:6], q[:4], q[:3]) if h and len(h) >= 2]:
            hits = [m.start() for m in re.finditer(re.escape(cand), asr)]
            if hits:
                return word_at(min(hits, key=lambda h: abs(h - guess)))
        # 字幕の頭より前の語（15コマ前から入れた分）は、言葉が字幕の頭から始まる時は拾わない
        head = next((j for j, x in enumerate(ws) if x["tl"] >= c["s"] - 3), 0)
        return word_at(max(guess, starts[head] if k == 0 and guess < starts[head] and hint is None else guess))


def judge(d):
    return "遅い" if d > LATE else ("早い" if d < EARLY else "○")


def main():
    ap = argparse.ArgumentParser(description="図解・画像の部品と声のずれ（工程9）", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    add_args(ap)
    ap.add_argument("--json", help="結果を書く JSON")
    ap.add_argument("keys", nargs="*")
    a = ap.parse_args()
    K = Case(a)
    tl = TL.of(K)
    W = Words(tl)
    res, bad = [], 0
    for mp in sorted(glob.glob(str(K.out / "*" / "manifest.json"))):
        m = json.load(open(mp, encoding="utf-8"))
        k = m["key"]
        if a.keys and k not in a.keys:
            continue
        S, E = m["tl_start_f"], m["tl_end_f"]
        drawn_p = Path(m.get("overlay", {}).get("file", "")).parent / "manifest.json"
        dm = json.load(open(drawn_p, encoding="utf-8")) if drawn_p.exists() else m
        r = {"key": k, "range": f"{ts(S)}〜{ts(E)}", "drawn": str(drawn_p), "beats": [], "unmeasured": []}
        drawn = flat(dm["src_ranges"])

        def cur_at(sh):
            try:
                return flat(src_ranges(tl, S + sh, E + sh))
            except AssertionError:
                return None
        cur = cur_at(0)
        if cur is None or len(cur) != len(drawn):
            r.update(offset_f=None, redraw=True, residual=None, why=f"長さが違う（今 {len(cur) if cur else '?'}／描いた時 {len(drawn)}）")
        else:
            # 全体の遅れ＝いちばん多いずれ（部品が声より何コマ遅いか）。その分ずらして描いた時と同じ素材なら「ずらすだけ」、違えば描き直し
            from collections import Counter
            off = Counter(x - y for x, y in zip(cur, drawn)).most_common(1)[0][0]
            moved = cur_at(-off)
            resid = [x - y for x, y in zip(moved, drawn)] if moved and len(moved) == len(drawn) else None
            runs, prev, n0 = [], None, 0
            for i, x in enumerate(resid or []):
                if x != prev:
                    if prev not in (None, 0):
                        runs.append((n0, i, prev))
                    prev, n0 = x, i
            if prev not in (None, 0):
                runs.append((n0, len(resid), prev))
            long_ = [(a_, b_, x) for a_, b_, x in runs if b_ - a_ >= 3 and abs(x) > DRIFT]
            r.update(offset_f=off, offset_s=round(off / FPS, 2), redraw=resid is None or bool(long_),
                     residual=[{"from": ts(S - off + a_), "frames": b_ - a_, "shift": x} for a_, b_, x in long_])
        r["drift_max"] = None if r.get("offset_f") is None else max([abs(r["offset_f"])] + [abs(x["shift"]) for x in r["residual"]])
        rows = []
        bp = K.zukai / k / "beats.json"
        by_f = {}                                        # 部品のコマ（タイムライン）→ beats.json の行（SE を同じ部品の物差しで測る）
        if bp.exists():
            fm0 = re.search(r"const F = \{(.*?)\};", (K.zukai / k / "page.html").read_text(encoding="utf-8"), re.S)
            Fv0 = {n: int(v) for n, v in re.findall(r"([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(-?\d+)", fm0.group(1))} if fm0 else {}
            dF0 = dm.get("F") or Fv0
            for b in json.load(open(bp, encoding="utf-8")):
                f0 = b.get("f", dF0.get(b["part"]))
                if f0 is not None and b["part"] != "END":
                    by_f.setdefault(S + int(f0), b)
        for ev in m.get("se_events", []):
            b = by_f.get(ev["tl_f"])
            if b:
                rows.append(("SE " + ev.get("se", ""), ev["tl_f"], str(b["cap_id"]), b.get("word", ""), b.get("asr"), b.get("pad", 0), b.get("at")))
                continue
            mm = re.search(r"([0-9]+(?:\+[0-9]+)?)「([^」]*)", ev.get("why", ""))
            if mm:
                rows.append(("SE " + ev.get("se", ""), ev["tl_f"], mm.group(1), mm.group(2), None, 0, None))
        if bp.exists():
            fm = re.search(r"const F = \{(.*?)\};", (K.zukai / k / "page.html").read_text(encoding="utf-8"), re.S)
            Fv = {n: int(v) for n, v in re.findall(r"([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(-?\d+)", fm.group(1))} if fm else {}
            # 描いた時の F（overlay の中のコマ）で比べる。page.html を retime.py で書き換えた後、まだ描いていない時は manifest の frames と合わない
            drawn_F = dm.get("F") or Fv
            for b in json.load(open(bp, encoding="utf-8")):
                if b["part"] == "END":
                    continue
                f = b.get("f", drawn_F.get(b["part"]))
                if f is None:
                    r["unmeasured"].append({"part": b["part"], "at": "", "why": "F の表に無い"})
                    continue
                rows.append((b["part"], S + int(f), str(b["cap_id"]), b.get("word", ""), b.get("asr"), b.get("pad", 0), b.get("at")))
        for part, f, cid, q, hint, pad, at in rows:
            if at == "cap":                              # 字幕の頭に付けた部品：今の版の字幕の頭と比べる（カットが変わったら分かる）
                c_ = tl.caps.get(cid)
                on, w = (c_["s"], "字幕の頭") if c_ else (None, f"字幕 {cid} が今の版に無い")
            else:
                on, w = W.onset(cid, q, hint)
                if on is not None and pad:
                    on, w = on + int(pad), f"{w}（pad {int(pad):+d}）"
            if on is None:
                r["unmeasured"].append({"part": part, "at": ts(f), "why": w})
                continue
            d = f - on
            r["beats"].append({"part": part, "at": ts(f), "cap_id": cid, "word": q, "voice": ts(on), "asr": w,
                               "delta_f": d, "delta_s": round(d / FPS, 2), "result": judge(d)})
        nb = sum(b["result"] != "○" for b in r["beats"])
        late_all = r.get("offset_f") is None or abs(r["offset_f"]) > DRIFT
        bad += nb + (1 if (r["redraw"] or late_all) else 0)
        print(f"{k} {r['range']}：" + ("描いた時と長さが違う（描き直し）" if r.get("offset_f") is None else
              f"全体の遅れ {r['offset_s']:+.2f}秒" + ("（区間の中のカットも変わった＝描き直し）" if r["redraw"] else ("（ずらすだけで合う＝shift.py）" if late_all else ""))) + "・"
              f"部品と声 {len(r['beats'])}個のうち 遅い {sum(b['result'] == '遅い' for b in r['beats'])}・早い {sum(b['result'] == '早い' for b in r['beats'])}"
              + (f"・測れない {len(r['unmeasured'])}" if r["unmeasured"] else ""))
        for b in r["beats"]:
            if b["result"] != "○":
                print(f"   {b['result']} {b['delta_s']:+.2f}秒 {b['at']} {b['part']} ／ 声 {b['voice']} 字幕{b['cap_id']}「{b['word']}」")
        res.append(r)
    if a.json:
        json.dump(res, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    nr = sum(1 for r in res if r["redraw"] or r.get("offset_f") is None or abs(r["offset_f"]) > DRIFT)
    print(f"\n図解・画像 {len(res)}個：落第 {bad}（全体が遅い・早い・描き直し {nr}〈うち描き直し {sum(bool(r['redraw']) for r in res)}〉・部品と声のずれ {bad - nr}）")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
