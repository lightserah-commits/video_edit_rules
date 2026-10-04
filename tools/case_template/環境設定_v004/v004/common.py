"""Air v001 の共通部品：区切り（units）・台本（script_v004.txt）の読み込み、声の大きさ（Voice）、語の位置と聞こえ始め。
ワークの完全解説 v001（~/Desktop/みかみ案件依頼書/0927 claude cowork/edit/v004/common.py）と同じもの。
"""
import json
import os
import re
import sys
import unicodedata

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
CASE = os.path.dirname(HERE)
ROOT = os.path.expanduser("~/Desktop/video_edit_rules")   # ルールと道具の場所（案件フォルダはどこにあってもよい。2026-09-28）
sys.path.insert(0, os.path.join(ROOT, "tools"))
import audible_onset  # noqa: E402

A = os.path.join(CASE, "analysis")
WAV = os.path.join(A, "asr", "_work", "camera.wav")          # カメラの音（16kHz・モノラル）。素材の秒＝作業用コピーの秒
ENV = os.path.join(A, "camera_env.npy")                       # 10ms ごとの大きさ（dB）
SCRIPT = os.path.join(HERE, "script_v004.txt")
FPS = 30000 / 1001
TPS = 254016000000
FT = 8475667200                                               # 29.97fps の1フレーム（ticks）
SYNC_OFFSET = json.load(open(os.path.join(A, "sync", "sync.json")))["offset"]   # カメラの秒 ＝ 画面コピーの秒 ＋ これ（analysis/sync/sync.json）


def norm(s):
    s = unicodedata.normalize("NFKC", s).lower()
    return re.sub(r"[\s、。・,.!?！？「」『』（）()\[\]【】:：;；\"'`~〜ー\-–—→…／/%＠@〇]", "", s)


def width(line):
    return sum(0.5 if ord(ch) < 128 else 1.0 for ch in line)


def load_units():
    return {u["u"]: u for u in json.load(open(os.path.join(A, "units.json")))}


class Voice:
    """10ms ごとの大きさ。声の区間は、境目（85パーセンタイル−12dB）を超えた所を芯にして、小さい音（境目−6dB）が続く所まで
    前後に 0.10秒まで広げる。0.08秒未満で前後 0.2秒に声が無い音（キーボード・クリック）は声と数えない（v008 と同じ）"""
    def __init__(self):
        db = np.load(ENV)
        self.db = db
        self.thr = float(np.percentile(db, 85)) - 12
        core = db > self.thr
        v = core.copy()
        for i in range(1, 4):
            v[:-i] |= core[i:]
            v[i:] |= core[:-i]
        d = np.diff(np.concatenate([[0], v.astype(np.int8), [0]]))
        st, en = np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]
        for j, (a, b) in enumerate(zip(st, en)):
            if b - a < 8:
                pg = a - en[j - 1] if j > 0 else 999
                ng = st[j + 1] - b if j + 1 < len(st) else 999
                if pg >= 20 and ng >= 20:
                    v[a:b] = False
        low = db > self.thr - 6
        ext = v.copy()
        for i in range(1, 11):
            ext[:-i] |= v[i:] & low[:-i]
            ext[i:] |= v[:-i] & low[i:]
        self.v = ext

    def idx(self, t):
        return max(0, min(len(self.v) - 1, int(round(t * 100))))

    def voiced(self, t):
        return bool(self.v[self.idx(t)])

    def runs(self, s, e):
        a, b = self.idx(s), self.idx(e)
        seg = self.v[a:b].astype(np.int8)
        d = np.diff(np.concatenate([[0], seg, [0]]))
        st, en = np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]
        return [((a + x) / 100, (a + y) / 100) for x, y in zip(st, en)]

    def end_before(self, t, limit=2.0):
        """t の前で声が終わった所。t の直前まで声が続いていれば None"""
        if self.voiced(t - 0.02):
            return None
        rs = [(x, y) for x, y in self.runs(max(0, t - limit), t) if y < t - 0.005]
        return rs[-1][1] if rs else None

    def dip(self, t, before=0.08, after=0.05):
        """続けて話している所の切れ目：t の近くで一番小さい所（10ms）"""
        a, b = self.idx(t - before), self.idx(t + after)
        k = int(np.argmin(self.db[a:b + 1]))
        return (a + k) / 100


class Script:
    """台本を読む。captions（key・u・mode・text・who）、cuts（A・B・理由）、highlights"""
    def __init__(self, path=SCRIPT):
        self.captions, self.cuts, self.highlights = [], [], []
        mid_n = {}
        for ln, raw in enumerate(open(path, encoding="utf-8"), 1):
            line = raw.rstrip("\n")
            if not line.strip() or line.startswith("#"):
                continue
            note = ""
            if "  #" in line:                     # 行の後ろのメモ（「  # 田中さん」など）
                line, note = line.split("  #", 1)
                line = line.rstrip()
            if line.startswith("x "):
                rng, why = line[2:].split("|", 1)
                a, b = rng.split("..")
                self.cuts.append({"a": parse_pos(a), "b": parse_pos(b), "why": why, "line": ln})
                continue
            if line.startswith("h "):
                a, b = line[2:].split("..")
                self.highlights.append({"a": parse_pos(a), "b": parse_pos(b), "line": ln})
                continue
            key, text = line.split("|", 1)
            anchor = None
            if "+" in key:                       # 「u+語|」＝区切り u の中で、文字起こしのこの語から（字幕の文字が文字起こしと違う時）
                key, anchor = key.split("+", 1)
                key += "+"
                anchor = anchor or None
            mode = "mid" if key.endswith("+") else ("drop" if key.endswith("-") else "start")
            u = int(key.rstrip("+-"))
            if mode == "mid":
                mid_n[u] = mid_n.get(u, 0) + 1
                cid = f"{u}+{mid_n[u]}"
            else:
                cid = str(u) if mode == "start" else f"{u}-"
            who = "聞" if text.startswith("@") else "み"
            text = text.lstrip("@")
            self.captions.append({"id": cid, "u": u, "mode": mode, "text": text.replace("／", "\r"), "who": who, "line": ln,
                                  "anchor": anchor, "guest": "田中" in note})


def parse_pos(s):
    s = s.strip()
    if "/" in s:
        u, w = s.split("/", 1)
        return (int(u), w)
    return (int(s), None)


class Aligner:
    """語の位置 → 素材の秒（聞こえ始め）"""
    def __init__(self, units, voice):
        self.units = units
        self.voice = voice
        self.audio = audible_onset.Audio(WAV)

    def char_time(self, u, k):
        """区切り u の（正規化した）k 文字目を含む語の開始（ASR の時刻）"""
        pos = 0
        for ws, we, w in self.units[u]["words"]:
            n = norm(w)
            if pos + len(n) > k:
                return ws
            pos += len(n)
        return self.units[u]["words"][-1][0]

    def find(self, u, phrase, from_k=0):
        t = norm(self.units[u]["text"])
        p = norm(phrase)
        for L in (6, 5, 4, 3, 2, 1):
            if len(p) >= L:
                f = t.find(p[:L], from_k)
                if f >= 0:
                    return f
        return None

    def onset(self, cand, lo=None, hi=None):
        """候補の秒から聞こえ始め。戻り値 (秒, 決め方)"""
        r = audible_onset.best_onset(self.audio, cand, lo, hi)
        if r["method"] == "asr":
            return self.voice.dip(cand), "続けて話している（大きさの谷。要確認）"
        return r["onset"], {"pause": "間の後の立ち上がり", "local_rise": "続けて話している所の立ち上がり"}[r["method"]]

    def unit_onset(self, u):
        return self.onset(self.units[u]["start"])

    def phrase_onset(self, u, phrase, from_k=0):
        k = self.find(u, phrase, from_k)
        if k is None:
            return None, None, None
        t, how = self.onset(self.char_time(u, k))
        return t, how, k
