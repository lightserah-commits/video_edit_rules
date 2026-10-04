#!/usr/bin/env python3
"""v002 のタイムライン（冒頭ハイライト＋本編。29.97fps）と、字幕・話した言葉の時刻をつなぐ道具（図解を作る人が使う）。

  python3 zukai/tl.py caps 275 316        … 字幕 275〜316 を、タイムラインの順に（開始・終わりのコマ、時刻、話者、文字、画面かカメラか）
  python3 zukai/tl.py words 275 316       … 上に加えて、話した言葉ごとの聞こえ始めのコマ（文字起こしの語の時刻。カットで切った所の語は出ない）
  python3 zukai/tl.py at 5:20.0           … v002 の時刻 → コマ・その時の字幕
  python3 zukai/tl.py v001 5:19.9         … v001 の時刻 → v002 の時刻（本編はハイライトが 10コマ短くなった分だけ前）

コマはタイムラインの絶対のコマ（0＝動画の頭）。図解のページの中のコマは「図解の頭からのコマ」＝絶対のコマ − 図解の開始のコマ。
語の時刻は whisper（large-v3-turbo）の語の時刻。聞こえ始めより 0.05〜0.15秒ずれることがあるので、大事な所は make_zukai.py の
onset で波形の立ち上がりに合わせ直す（--onset 字幕ID 言葉）。
"""
import bisect
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
V = os.path.dirname(HERE)                       # edit/v004
EDIT = os.path.dirname(V)
FPS = 30000 / 1001
CUTS = os.path.join(V, "_work", "cuts_v004.json")
CAPJ = os.path.join(V, "_work", "captions_v004.json")
ASR = os.path.join(EDIT, "analysis", "asr", "asr_camera.json")
MAP = os.path.join(V, "_work", "base_v004_map.json")
V001_CUTS = os.path.join(EDIT, "v001", "_work", "cuts_v001.json")


def ts(f):
    t = f / FPS
    return f"{int(t // 60)}:{t % 60:05.2f}"


def parse_t(s):
    if ":" in s:
        m, x = s.split(":")
        return int(m) * 60 + float(x)
    return float(s)


class TL:
    def __init__(self, cuts=CUTS):
        cj = json.load(open(cuts, encoding="utf-8"))
        self.hl = cj.get("highlight_external_frames", 0)
        self.total = cj["total_frames"]
        self.segs = []                       # (タイムラインの開始, 終わり, 素材の開始)
        t = self.hl
        for a, b in cj["keep_frames"]:
            self.segs.append((t, t + b - a, a))
            t += b - a
        assert t == self.total
        self.by_src = sorted((a, a + (e - s), s) for s, e, a in self.segs)
        self.src_starts = [x[0] for x in self.by_src]
        self.cap_tl = cj["caption_tl"]
        capj = json.load(open(CAPJ, encoding="utf-8"))
        caps = [c for c in capj["captions"] if c["mode"] != "drop" and "src" in c]
        order = sorted(caps, key=lambda c: self.cap_tl[c["id"]])
        self.caps, self.ids = {}, []
        for k, c in enumerate(order):
            s = self.cap_tl[c["id"]]
            e = self.cap_tl[order[k + 1]["id"]] if k + 1 < len(order) else self.total
            self.caps[c["id"]] = {"id": c["id"], "s": s, "e": e, "text": c["text"].replace("\r", "／"), "who": c["who"], "src": c["src"]}
            self.ids.append(c["id"])
        self.pos = {i: k for k, i in enumerate(self.ids)}
        self.screen = []
        if os.path.exists(MAP):
            mp = json.load(open(MAP, encoding="utf-8"))
            if mp.get("total_frames") == self.total:
                self.screen = mp["screen_spans"]
        self._words = None

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
            for seg in json.load(open(ASR, encoding="utf-8")):
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
        i = bisect.bisect_right([self.caps[x]["s"] for x in self.ids], f) - 1
        return self.ids[max(0, i)]


def main():
    tl = TL()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd in ("caps", "words"):
        a, b = sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else sys.argv[2]
        ws = tl.words() if cmd == "words" else []
        for i in tl.span(a, b):
            c = tl.caps[i]
            scr = "画面" if tl.on_screen(c["s"]) else "カメラ"
            print(f"[{i}] f{c['s']}〜f{c['e']}（{ts(c['s'])}〜{ts(c['e'])}・{(c['e'] - c['s']) / FPS:.2f}秒）{c['who']} {scr}｜{c['text']}")
            if cmd == "words":
                for w in ws:
                    if c["s"] - 3 <= w["tl"] < c["e"]:
                        print(f"      f{w['tl']}（{ts(w['tl'])}） {w['word']}")
    elif cmd == "at":
        f = int(round(parse_t(sys.argv[2]) * FPS))
        i = tl.at(f)
        print(f"f{f}（{ts(f)}）字幕 [{i}] {tl.caps[i]['text']}  {'画面' if tl.on_screen(f) else 'カメラ'}")
    elif cmd == "v001":
        old = TL(V001_CUTS) if os.path.exists(V001_CUTS) else None
        f = int(round(parse_t(sys.argv[2]) * FPS))
        src = old.tl_to_src(f) if old else None
        g = tl.src_to_tl(src) if src is not None else None
        print(f"v001 {sys.argv[2]}（f{f}）→ 素材のコマ {src} → v002 f{g}（{ts(g) if g is not None else '-'}）")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
