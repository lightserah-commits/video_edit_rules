#!/usr/bin/env python3
"""版のタイムライン（冒頭ハイライト＋本編。29.97fps）と、字幕・話した言葉の時刻をつなぐ道具（図解を作る人が使う。どの案件でも使える）。
元：環境設定 v004 の zukai/tl.py。

  python3 tools/zukai/tl.py --ver <edit/vNNN> caps 275 316     … 字幕 275〜316 を、タイムラインの順に（開始・終わりのコマ、時刻、話者、文字、画面かカメラか）
  python3 tools/zukai/tl.py --ver <edit/vNNN> words 275 316    … 上に加えて、話した言葉ごとの聞こえ始めのコマ（文字起こしの語の時刻。カットで切った所の語は出ない）
  python3 tools/zukai/tl.py --ver <edit/vNNN> at 5:20.0        … この版の時刻 → コマ・その時の字幕
  python3 tools/zukai/tl.py --ver <edit/vNNN> prev <前の版の cuts_vMMM.json> 5:19.9   … 前の版の時刻 → この版の時刻（素材のコマでつなぐ）
  （--ver は環境変数 ZUKAI_VER でもよい。ほかの置き場所は case.py）

コマはタイムラインの絶対のコマ（0＝動画の頭）。図解のページの中のコマは「図解の頭からのコマ」＝絶対のコマ − 図解の開始のコマ。
語の時刻は whisper の語の時刻。聞こえ始めより 0.05〜0.15秒ずれることがあるので、大事な所は波形（tools/audible_onset.py）で確かめる。
"""
import argparse
import bisect
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from case import Case, add_args  # noqa: E402

FPS = 30000 / 1001


def ts(f):
    t = f / FPS
    return f"{int(t // 60)}:{t % 60:05.2f}"


def parse_t(s):
    if ":" in s:
        m, x = s.split(":")
        return int(m) * 60 + float(x)
    return float(s)


class TL:
    def __init__(self, cuts, captions=None, asr=None, map_=None):
        cj = json.load(open(cuts, encoding="utf-8"))
        self.hl = cj.get("highlight_external_frames", 0)
        self.total = cj["total_frames"]
        self.segs = []                       # (タイムラインの開始, 終わり, 素材の開始)
        t = self.hl
        for a, b in cj.get("highlight_frames", []) + cj["keep_frames"]:
            self.segs.append((t, t + b - a, a))
            t += b - a
        assert t == self.total, f"カットの表の長さが合わない {t} / {self.total}"
        self.by_src = sorted((a, a + (e - s), s) for s, e, a in self.segs)
        self.src_starts = [x[0] for x in self.by_src]
        self.cap_tl = cj.get("caption_tl", {})          # 字幕の頭のコマはカットの表のもの（環境設定 v004 と同じ）
        self.caps, self.ids = {}, []
        if captions:
            capj = json.load(open(captions, encoding="utf-8"))
            caps = [c for c in capj["captions"] if c.get("mode") != "drop" and "src" in c and c["id"] in self.cap_tl]
            order = sorted(caps, key=lambda c: self.cap_tl[c["id"]])
            for k, c in enumerate(order):
                s = self.cap_tl[c["id"]]
                e = self.cap_tl[order[k + 1]["id"]] if k + 1 < len(order) else self.total
                self.caps[c["id"]] = {"id": c["id"], "s": s, "e": e, "text": c["text"].replace("\r", "／"), "who": c.get("who", ""), "src": c["src"]}
                self.ids.append(c["id"])
        self.pos = {i: k for k, i in enumerate(self.ids)}
        self._starts = [self.caps[x]["s"] for x in self.ids]
        self.screen = []
        if map_ and os.path.exists(map_):
            mp = json.load(open(map_, encoding="utf-8"))
            if mp.get("total_frames") == self.total:
                self.screen = mp.get("screen_spans", [])
        self.asr = asr
        self._words = None

    @classmethod
    def of(cls, case):
        return cls(case.cuts, case.captions, case.asr, case.map)

    def src_to_tl(self, f):
        """素材（カメラ）のコマ → タイムラインのコマ（切った所なら None）"""
        i = bisect.bisect_right(self.src_starts, f) - 1
        if i < 0:
            return None
        a, b, s = self.by_src[i]
        return s + (f - a) if a <= f < b else None

    def tl_to_src(self, f):
        for s, e, a in self.segs:
            if s <= f < e:
                return a + (f - s)
        return None

    def on_screen(self, f):
        return any(a <= f < b for a, b in self.screen)

    def words(self):
        if self._words is None:
            self._words = []
            if not self.asr or not os.path.exists(self.asr):
                raise SystemExit(f"文字起こし（語の時刻）が無い：{self.asr}（--asr で渡す）")
            for seg in json.load(open(self.asr, encoding="utf-8")):
                for w in seg.get("words", []):
                    f = int(round(w["start"] * FPS))
                    t = self.src_to_tl(f)
                    if t is not None:
                        self._words.append({"tl": t, "src": w["start"], "word": w["word"].strip(), "p": w.get("probability", 0)})
            self._words.sort(key=lambda x: x["tl"])
        return self._words

    def span(self, a, b):
        return self.ids[self.pos[a]:self.pos[b] + 1]

    def at(self, f):
        i = bisect.bisect_right(self._starts, f) - 1
        return self.ids[max(0, i)]


def main():
    ap = argparse.ArgumentParser(description="タイムラインのコマと字幕・言葉の時刻（図解を作る人の道具）", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    add_args(ap)
    ap.add_argument("cmd", choices=["caps", "words", "at", "prev"])
    ap.add_argument("args", nargs="+")
    a = ap.parse_args()
    tl = TL.of(Case(a))
    if a.cmd in ("caps", "words"):
        x, y = a.args[0], a.args[1] if len(a.args) > 1 else a.args[0]
        ws = tl.words() if a.cmd == "words" else []
        for i in tl.span(x, y):
            c = tl.caps[i]
            scr = "画面" if tl.on_screen(c["s"]) else "カメラ"
            print(f"[{i}] f{c['s']}〜f{c['e']}（{ts(c['s'])}〜{ts(c['e'])}・{(c['e'] - c['s']) / FPS:.2f}秒）{c['who']} {scr}｜{c['text']}")
            if a.cmd == "words":
                for w in ws:
                    if c["s"] - 3 <= w["tl"] < c["e"]:
                        print(f"      f{w['tl']}（{ts(w['tl'])}） {w['word']}")
    elif a.cmd == "at":
        f = int(round(parse_t(a.args[0]) * FPS))
        i = tl.at(f)
        print(f"f{f}（{ts(f)}）字幕 [{i}] {tl.caps[i]['text']}  {'画面' if tl.on_screen(f) else 'カメラ'}")
    elif a.cmd == "prev":
        old = TL(a.args[0])
        f = int(round(parse_t(a.args[1]) * FPS))
        src = old.tl_to_src(f)
        g = tl.src_to_tl(src) if src is not None else None
        print(f"前の版 {a.args[1]}（f{f}）→ 素材のコマ {src} → この版 f{g}（{ts(g) if g is not None else '切った所'}）")


if __name__ == "__main__":
    main()
