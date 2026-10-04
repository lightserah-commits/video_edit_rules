#!/usr/bin/env python3
"""テロップの開始を「聞こえる音」に合わせるための道具（音の立ち上がりを波形から測る）。

上司の方法セット 20_間 の TIMING_ACOUSTIC_REQUIRED（字幕の開始＝本文の先頭の語の発音開始。ASRの時刻は候補）を
実際の音で確かめるためのもの。

  - 字幕の開始候補（ASR の時刻など）の前後を見て、小さい音（間）から声が立ち上がる瞬間を探す
  - 子音（サ行・ハ行などの息の音）も拾えるよう、高い音を強めてから、5ミリ秒ごとの音の大きさを測る
  - 直前に間が無い（続けて話している）所は、立ち上がりを決めつけず「要確認」（no_pause）にする
  - 編集済みの音で、声の途中にカット点がある場合は、カット点が聞こえ始め
フレームは「聞こえ始めの瞬間を含むフレーム」（切り捨て）。一律に数フレームずらす補正はしない。

使い方:
  python3 audible_onset.py extract 素材.MOV 出力.wav
      … 声を 16kHz・モノラルの WAV で取り出す（作業用。案件フォルダか作業用フォルダに置く）
  python3 audible_onset.py measure 出力.wav 12.34 56.78 ...
      … 候補の秒（素材の時刻）ごとに、聞こえ始めの秒を出す
  python3 audible_onset.py check-prproj 完成.prproj --sequence 本編 --tracks V8,V9 --audio-track A1 --media IMG_1063.MOV --wav 出力.wav [--asr 認識.json]
      … 置かれている字幕の開始フレームと、聞こえ始めのフレームの差を出す（編集済みのタイムラインで）。
        --asr を渡すと、本番と同じく音声認識の語の時刻を候補にして聞こえ始めを決める
  python3 audible_onset.py transcribe 出力.wav 認識.json [--model ggml-small.bin]
      … 音声認識（語の時刻つき）。3分ずつ whisper-cli -dtw にかけてつなぐ（長い声を一度に -dtw で渡すと止まる）。
        --asr に渡すと、DTW の語の時刻を 0.10秒前にして候補にする（DTW_LEAD）
"""
import argparse
import json
import math
import os
import re
import subprocess
import sys
import unicodedata
import wave
from array import array
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

RATE = 16000
HOP = 80                  # 5ミリ秒
# 下の値は、1本目の完成版の字幕956本で調整した（測れた592本のうち、編集者の字幕の開始と±1フレーム以内73%・±2以内88%）
SEARCH = 0.15             # 候補の前後 何秒を探すか（候補がずれていると外れる。候補は語ごとの時刻を使う）
PAUSE_HOPS = 4            # 立ち上がりの直前に必要な小さい音の区間（20ミリ秒）
RISE_DB = 14.0            # 間の大きさより何dB大きくなったら声とみなすか
KEEP_DB = 16.0            # 立ち上がりの後 40ミリ秒の平均がこれ以上なら声が続いている
QUIET_DB = 12.0           # 間とみなす大きさ（底から何dB以内）
FPS = 30000 / 1001
# whisper の DTW の語の時刻は、聞こえ始めより中央で3〜4フレーム遅い。候補（探す中心）にする時だけ 0.10秒前にする
# （字幕の時刻は波形で決めるので、一律にずらす補正ではない）。かかるのは load_whisper_tokens を通した時だけ。
# 1本目の声の途中から始まる字幕 330本の ±1フレーム以内が small 28%→39%（前半・後半とも同じ向き）。0.08〜0.15秒はほぼ同じ、
# 0.20秒は下がる。2本目は声の途中の字幕が27本しかなく確かめになっていない。カットの頭の字幕では差が無い（実例/根拠と実例.md）
DTW_LEAD = 0.10
CHUNK_SEC, CHUNK_OVERLAP = 180.0, 10.0    # transcribe：長い声を一度に -dtw で渡すと止まる（92分で2時間進まなかった）ので3分ずつ


def extract(src, out_wav):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vn", "-ac", "1", "-ar", str(RATE), "-acodec", "pcm_s16le", out_wav],
                   check=True)


class Audio:
    def __init__(self, path):
        self.w = wave.open(path, "rb")
        if self.w.getframerate() != RATE or self.w.getnchannels() != 1 or self.w.getsampwidth() != 2:
            raise ValueError(f"{path} は {RATE}Hz・モノラル・16bit の WAV にしてください（extract を使う）")
        self.n = self.w.getnframes()

    def levels(self, t0, t1):
        """t0〜t1 秒の、5ミリ秒ごとの音の大きさ（dB。高い音を強めてから測る）"""
        a = max(0, int(t0 * RATE))
        b = min(self.n, int(t1 * RATE))
        if b <= a + HOP:
            return a / RATE, []
        self.w.setpos(a)
        x = array("h")
        x.frombytes(self.w.readframes(b - a))
        out, prev = [], 0
        for k in range(0, len(x) - HOP + 1, HOP):
            s = 0.0
            for v in x[k:k + HOP]:
                d = v - 0.95 * prev
                prev = v
                s += d * d
            out.append(10 * math.log10(s / HOP + 1.0))
        return a / RATE, out


def onset_near(audio, t, lo=None, hi=None):
    """素材の時刻 t（秒）の近くで、声が聞こえ始める時刻を探す。lo・hi で探す範囲を狭められる。
    戻り値: {onset, status, rise_db, floor_db}。status は ok / no_pause（続けて話していて決められない）/ no_voice"""
    s0 = t - SEARCH - PAUSE_HOPS * HOP / RATE - 0.05
    base, lv = audio.levels(max(0.0, s0), t + SEARCH + 0.06)
    if len(lv) < PAUSE_HOPS + 10:
        return {"onset": None, "status": "no_voice"}
    floor = sorted(lv)[len(lv) // 10]
    cands = []
    for k in range(PAUSE_HOPS, len(lv) - 8):
        tk = base + k * HOP / RATE
        if tk < t - SEARCH or tk > t + SEARCH or (lo is not None and tk < lo) or (hi is not None and tk > hi):
            continue
        if lv[k] < floor + RISE_DB or sum(lv[k:k + 8]) / 8 < floor + KEEP_DB:
            continue
        if max(lv[k - PAUSE_HOPS:k]) >= floor + QUIET_DB:
            continue
        j = k
        while j > k - 4 and lv[j - 1] > floor + QUIET_DB * 0.75:   # 小さく始まる息の音まで戻る
            j -= 1
        cands.append((base + j * HOP / RATE, lv[k] - floor))
    if not cands:
        loud = sum(1 for v in lv if v >= floor + KEEP_DB)
        return {"onset": None, "status": "no_pause" if loud > len(lv) // 3 else "no_voice", "floor_db": round(floor, 1)}
    on, rise = min(cands, key=lambda c: abs(c[0] - t))
    return {"onset": round(on, 4), "status": "ok", "rise_db": round(rise, 1), "floor_db": round(floor, 1)}


def local_rise(audio, cand, radius=0.10):
    """続けて話している所用。候補の近く（±radius 秒）で、音が一段大きくなる所（語の頭の子音・母音の立ち上がり）を探す。
    直前 30ミリ秒の一番小さい所から 8dB 以上大きくなる所のうち、上がり方が大きく、候補に近いものを選ぶ。"""
    base, lv = audio.levels(max(0.0, cand - radius - 0.05), cand + radius + 0.06)
    if len(lv) < 20:
        return None
    floor = sorted(lv)[len(lv) // 10]
    best = None
    for k in range(6, len(lv) - 2):
        tk = base + k * HOP / RATE
        if abs(tk - cand) > radius:
            continue
        dip = min(lv[k - 6:k])
        rise = lv[k + 2] - dip
        if rise >= 8 and lv[k + 2] >= floor + 10:
            score = rise - 40 * abs(tk - cand)          # 大きく上がる所を優先。同じくらいなら候補に近い方
            if best is None or score > best[0]:
                best = (score, tk, rise)
    return (round(best[1], 4), round(best[2], 1)) if best else None


def best_onset(audio, cand, lo=None, hi=None):
    """候補の時刻（音声認識の語の時刻）から、聞こえ始めを決める。
    1) 間の後の立ち上がり（pause） 2) 続けて話している所の一段の立ち上がり（local_rise） 3) 決まらなければ候補のまま（asr・要確認）"""
    r = onset_near(audio, cand, lo, hi)
    if r["onset"] is not None:
        return {**r, "method": "pause"}
    lr = local_rise(audio, cand)
    if lr and (lo is None or lr[0] >= lo) and (hi is None or lr[0] <= hi):
        return {"onset": lr[0], "status": "ok", "method": "local_rise", "rise_db": lr[1]}
    return {"onset": round(cand, 4), "status": "asr_only", "method": "asr"}


# ---------- 音声認識（whisper-cli）の語の時刻 ----------
def norm_text(s):
    s = unicodedata.normalize("NFKC", s)
    return "".join(ch.lower() for ch in s if ch.isalnum() or ch == "ー")


def load_whisper_tokens(path):
    """whisper-cli -ojf の出力から、トークンごとの文字と開始秒（DTW の時刻があればそれ）を取り出す"""
    d = json.loads(open(path, "rb").read().decode("utf-8", errors="replace"))
    toks = []
    for seg in d.get("transcription", []):
        for t in seg.get("tokens", []):
            text = t.get("text", "")
            if text.startswith("[_") or not norm_text(text):
                continue
            dtw = t.get("t_dtw", -1)
            t0 = (t.get("offsets") or {}).get("from", 0) / 1000
            start = max(0.0, dtw / 100 - DTW_LEAD) if isinstance(dtw, (int, float)) and dtw >= 0 else t0
            toks.append({"text": text, "start": round(start, 3)})
    toks.sort(key=lambda x: x["start"])
    return toks


MODEL_CANDIDATES = [os.path.expanduser("~/Desktop/video_edit_rules/models/ggml-small.bin"),   # tools/setup_env.sh で作る（2026-10-05 から）
                    os.path.expanduser("~/whisper-models/ggml-small.bin")]


DTW_PRESETS = {"tiny", "tiny.en", "base", "base.en", "small", "small.en", "medium", "medium.en",
               "large.v1", "large.v2", "large.v3", "large.v3.turbo"}     # whisper-cli -dtw が受け付ける名前


def dtw_preset(model):
    """モデルのファイル名から -dtw の名前（ggml-small-q5_1.bin → small、ggml-large-v3-turbo.bin → large.v3.turbo）"""
    name = re.sub(r"^ggml-|\.bin$", "", os.path.basename(model))
    name = re.sub(r"-(q\d+_\d+|q\d+|f16|f32|tdrz)$", "", name).replace("-", ".")
    return name if name in DTW_PRESETS else None


def transcribe(wav, out_json, model=None, preset=None):
    """声の WAV を3分ずつ（10秒重ねて）whisper-cli -dtw で文字起こしし、語の時刻を元の声の時刻に直してつなぐ。
    出力は whisper-cli -ojf と同じ形（transcription[].tokens[]、offsets はミリ秒・t_dtw は 1/100秒。timestamps の文字列はかけらの中の時刻のまま）。
    止まった・失敗したかけらがあれば、理由を出して止める。"""
    import signal
    import tempfile
    signal.signal(signal.SIGTERM, lambda s, f: sys.exit(143))     # 外から止められても、一時フォルダと whisper-cli を片付ける
    if model and not os.path.exists(model):
        raise SystemExit(f"モデルがありません: {model}")
    model = model or next((m for m in MODEL_CANDIDATES if os.path.exists(m)), None)
    if not model:
        raise SystemExit(f"文字起こしのモデルがありません: {MODEL_CANDIDATES}（iMacの準備.md の 3）")
    preset = preset or dtw_preset(model)
    if preset not in DTW_PRESETS:
        raise SystemExit(f"-dtw の名前をモデル名から決められません: {os.path.basename(model)}（--dtw で {sorted(DTW_PRESETS)} のどれかを渡す）")
    with wave.open(wav, "rb") as w:
        total = w.getnframes() / w.getframerate()
    tokens, log, t, i = [], [], 0.0, 0
    with tempfile.TemporaryDirectory() as tmp:
        while t < total:
            part, base = os.path.join(tmp, f"c{i:03d}.wav"), os.path.join(tmp, f"c{i:03d}")
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-t", str(CHUNK_SEC + CHUNK_OVERLAP), "-i", wav,
                            "-c", "copy", part], check=True)
            try:      # -mc 0：前の文に引きずられて同じ言葉をくり返す誤認識を防ぐ
                subprocess.run(["whisper-cli", "-m", model, "-l", "ja", "-nfa", "-mc", "0", "-dtw", preset, "-ojf", "-of", base, part],
                               stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=900, check=True)
            except subprocess.TimeoutExpired:
                raise SystemExit(f"{t:.0f}秒からのかけらの文字起こしが15分で終わらなかった（{model}）")
            except subprocess.CalledProcessError as e:
                tail = "\n".join((e.stderr or b"").decode("utf-8", errors="replace").strip().splitlines()[-5:])
                raise SystemExit(f"{t:.0f}秒からのかけらで whisper-cli が失敗した（終了コード {e.returncode}）:\n{tail}")
            d = json.loads(open(base + ".json", "rb").read().decode("utf-8", errors="replace"))
            lo, hi = t + (CHUNK_OVERLAP / 2 if i > 0 else 0.0), t + CHUNK_SEC + CHUNK_OVERLAP / 2
            n = 0
            for seg in d.get("transcription", []):
                for tok in seg.get("tokens", []):
                    off = dict(tok.get("offsets") or {})
                    f = off.get("from", 0) / 1000 + t
                    dtw = tok.get("t_dtw")
                    at = dtw / 100 + t if isinstance(dtw, (int, float)) and dtw >= 0 else f
                    if not (lo <= at < hi):
                        continue          # 重ねた所は、かけらの真ん中に近い方を使う（決めるのは DTW の時刻。offsets は文の単位で粗く、境目で語が二重・抜けになる）
                    off["from"], off["to"] = int(round(f * 1000)), int(round(off.get("to", 0) + t * 1000))
                    tok = {**tok, "offsets": off}
                    if isinstance(tok.get("t_dtw"), (int, float)) and tok["t_dtw"] >= 0:
                        tok["t_dtw"] = int(round(tok["t_dtw"] + t * 100))
                    tokens.append(tok)
                    n += 1
            log.append({"start": t, "tokens": n})
            print(f"  {t / 60:5.1f}分〜 {n}語", flush=True)
            i, t = i + 1, t + CHUNK_SEC
    json.dump({"model": model, "dtw": preset, "chunks": log, "transcription": [{"tokens": tokens}]},
              open(out_json, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"{out_json}: {len(tokens)}語（{len(log)}かけら）")


def asr_candidate(tokens, starts, text, t, window=1.5):
    """字幕の文字の先頭と、音声認識の語を突き合わせ、t の近くで一番近い一致の開始秒を返す（無ければ None）"""
    import bisect
    want = norm_text(text)
    if not want:
        return None
    i0, i1 = bisect.bisect_left(starts, t - window), bisect.bisect_right(starts, t + window)
    chars = [(ch, i) for i in range(i0, i1) for ch in norm_text(tokens[i]["text"])]
    s = "".join(c for c, _ in chars)
    for k in (4, 3, 2):
        if len(want) < k:
            continue
        best, pos = None, s.find(want[:k])
        while pos >= 0:
            st = tokens[chars[pos][1]]["start"]
            if best is None or abs(st - t) < abs(best - t):
                best = st
            pos = s.find(want[:k], pos + 1)
        if best is not None:
            return best
    return None


# ---------- 候補づくり（2026-10-03。字幕の文字と語を、ずれ・抜けを許して並べ合わせる） ----------
# 完成版1本目の声の途中から始まる字幕の前半165本で選び、後半・2本目で確かめた（scratchpad の harness。実例/根拠と実例.md）：
# ±1フレーム以内 前半 47→54%・後半 32→33%・2本目 30→44%、±2 は 53→62%・51→55%・48→74%。候補が作れない字幕が約半分になる。
# 字幕に書いていない「だから・なんか」から出す・聞こえ始めの探し方を変える案は、前半にだけ効いて後半・2本目で効かなかったので入れていない
CAP_HEAD = 10                         # 字幕の頭の何文字を並べ合わせるか
AL_MATCH, AL_MISMATCH, AL_GAP = 2.0, -1.0, -1.0
AL_MIN = 3.0                          # 並べ合わせの点がこれ未満なら一致とみなさない（ほぼ2文字以上の一致）
_KANJI_NUM = str.maketrans("〇一二三四五六七八九", "0123456789")


def _strip_paren(s):
    """（ ）の中を消す（字幕で補った言葉は話されていない）"""
    out, depth = [], 0
    for ch in s:
        if ch in "（(":
            depth += 1
            out.append(" ")
        elif ch in ")）" and depth:
            depth -= 1
        elif not depth:
            out.append(ch)
    return "".join(out) if depth == 0 else s


def cnorm(s, drop_paren=True):
    """NFKC・（ ）の中を消す・カタカナ→ひらがな・漢数字→数字・英数字と「ー」だけ残す（英字は小文字）"""
    s = unicodedata.normalize("NFKC", s)
    if drop_paren:
        s = _strip_paren(s)
    s = "".join(chr(ord(ch) - 0x60) if 0x30A1 <= ord(ch) <= 0x30F6 else ch for ch in s).translate(_KANJI_NUM)
    return "".join(ch.lower() for ch in s if ch.isalnum() or ch == "ー")


def caption_patterns(text, prev_text=None):
    """並べ合わせる字幕の文字（層ごと、長い層から）。1行目を出してから2行目を足す字幕（1つ前の字幕の文字で始まる）は、足した所だけ"""
    if prev_text:
        a, b = cnorm(prev_text), cnorm(text)
        if a and len(b) > len(a) and b.startswith(a):
            return [b[len(a):]]
    parts = [p for p in text.split(" / ") if cnorm(p)]
    parts.sort(key=lambda p: -len(cnorm(p)))
    return [cnorm(p) for p in parts] or [cnorm(text)]


def align_starts(cap, s):
    """cap（字幕の頭）を s（窓の中の語の文字）に、ずれ・抜けを許して当てる。[(点, s の何文字目から, cap の頭を何文字飛ばしたか)]"""
    n, m = len(cap), len(s)
    if n == 0 or m == 0:
        return []
    NEG = -1e9
    H = [[NEG] * (m + 1) for _ in range(n + 1)]
    S = [[None] * (m + 1) for _ in range(n + 1)]
    for j in range(m + 1):
        H[0][j] = 0.0
    for i in range(1, n + 1):
        H[i][0] = H[i - 1][0] + AL_GAP
    best = {}
    for i in range(1, n + 1):
        ci = cap[i - 1]
        Hi, Hp, Si, Sp = H[i], H[i - 1], S[i], S[i - 1]
        for j in range(1, m + 1):
            bs, bst = NEG, None
            hd = Hp[j - 1]
            if hd > NEG / 2:
                if ci == s[j - 1]:
                    bs, bst = hd + AL_MATCH, Sp[j - 1] or (j - 1, i - 1)
                elif Sp[j - 1] is not None:
                    bs, bst = hd + AL_MISMATCH, Sp[j - 1]
            if Hp[j] > NEG / 2 and Hp[j] + AL_GAP > bs:
                bs, bst = Hp[j] + AL_GAP, Sp[j]
            if Si[j - 1] is not None and Hi[j - 1] > NEG / 2 and Hi[j - 1] + AL_GAP > bs:
                bs, bst = Hi[j - 1] + AL_GAP, Si[j - 1]
            if bs <= NEG / 2:
                continue
            Hi[j], Si[j] = bs, bst
            if bst is not None and bs > best.get(bst, NEG):
                best[bst] = bs
    return [(sc, j0, i0) for (j0, i0), sc in best.items()]


def asr_candidate2(tokens, starts, text, t, prev_text=None, window=1.5):
    """字幕の文字と語を並べ合わせ、t の近く（±window 秒の語）で一番点の高い一致の開始秒を返す（同じ点なら t に近いもの。無ければ None）。
    prev_text：同じトラックで1つ前の字幕の文字（1行目→2行目の字幕の判定。無くても動く）。t は「だいたいの場所」で、窓の中心と同点の選び方だけに使う"""
    import bisect
    pats = [p for p in caption_patterns(text, prev_text) if p]
    if not pats:
        return None
    i0, i1 = bisect.bisect_left(starts, t - window), bisect.bisect_right(starts, t + window)
    chars = [(ch, i) for i in range(i0, i1) for ch in cnorm(tokens[i]["text"], drop_paren=False)]
    if not chars:
        return None
    s = "".join(c for c, _ in chars)
    ms = []
    for rank, cap in enumerate(pats):
        ms = [(sc - 0.5 * rank, chars[j][1]) for sc, j, _ in align_starts(cap[:CAP_HEAD], s)]
        if ms:
            break
    ms = [m for m in ms if m[0] >= AL_MIN]
    if not ms:
        return None
    top = max(sc for sc, _ in ms)
    return min((starts[ti] for sc, ti in ms if sc >= top), key=lambda st: abs(st - t))


def check_prproj(a):
    from native_prproj import Prproj, TPS
    pj = Prproj.load(a.project)
    seq = pj.sequence(a.sequence)
    frame_t = pj.frame_ticks(seq)              # シーケンスのフレーム（29.97fps・30fps など）
    fps = TPS / frame_t
    audio = Audio(a.wav)
    media = unicodedata.normalize("NFC", a.media)

    def name_of(it):
        sub = pj.ref(it.find("ClipTrackItem/SubClip"))
        return unicodedata.normalize("NFC", sub.findtext("Name") or "") if sub is not None else ""

    clips = []
    for tn, tr in pj.tracks(seq):
        if tn != a.audio_track:
            continue
        for it in pj.items(tr):
            if it.find("ClipTrackItem/IsMuted") is not None or name_of(it) != media:
                continue
            s, e = pj.span(it)
            sub = pj.ref(it.find("ClipTrackItem/SubClip"))
            clip = pj.ref(sub.find("Clip"))
            h = pj.range_holder(clip)
            clips.append((s, e, int(h.findtext("InPoint")) if h is not None else 0))
    clips.sort()
    tracks = set(a.tracks.split(","))
    tokens = load_whisper_tokens(a.asr) if getattr(a, "asr", None) else None
    starts = [t["start"] for t in tokens] if tokens else None
    rows = []
    for tn, tr in pj.tracks(seq):
        if tn not in tracks:
            continue
        prev_text = None                   # 同じトラックで1つ前の字幕の文字（1行目→2行目の字幕の判定）
        for it in sorted(pj.items(tr), key=lambda x: pj.span(x)[0]):
            if it.find("ClipTrackItem/IsMuted") is not None:
                continue
            s, _ = pj.span(it)
            texts = pj.item_texts(it)
            text = " / ".join("".join(r) for r in texts).replace("\r", " ")
            prev_text, prev = text, prev_text
            clip = next((c for c in clips if c[0] <= s < c[1]), None)
            if clip is None:
                rows.append({"track": tn, "frame": round(s / frame_t), "text": text[:30], "status": "no_audio_clip"})
                continue
            cs, ce, inp = clip
            src_t = (inp + (s - cs)) / TPS
            src_lo = inp / TPS          # この音のクリップの頭（カット点）より前は聞こえない
            src_hi = (inp + (ce - cs)) / TPS
            if tokens is None:
                # 置かれている字幕の時刻の近くを測る（編集者の置き方と、聞こえ始めの関係を見る）
                r = onset_near(audio, src_t, lo=src_lo - 0.2, hi=src_hi)
            else:
                # 本番と同じ：音声認識の語の時刻を候補にして聞こえ始めを決め、編集者の置き方と比べる
                cand = asr_candidate2(tokens, starts, text, src_t, prev_text=prev)
                r = best_onset(audio, cand, lo=src_lo - 0.2, hi=src_hi) if cand is not None else {"onset": None, "status": "no_asr_match"}
            row = {"track": tn, "frame": round(s / frame_t), "text": text[:30], **r}
            if r["onset"] is not None:
                on_src = max(r["onset"], src_lo)                 # カット点より前に始まった声は、カット点で聞こえ始める
                on_tl = cs / TPS + (on_src - src_lo)
                on_frame = math.floor(on_tl * fps + 1e-6)
                row["onset_frame"] = on_frame
                row["diff"] = row["frame"] - on_frame            # ＋なら字幕が遅い、−なら早い
                row["at_cut"] = r["onset"] <= src_lo
            rows.append(row)
    ok = [r for r in rows if "diff" in r]
    dist = Counter(max(-6, min(6, r["diff"])) for r in ok)
    by_method = {}
    for m in sorted({r.get("method", "") for r in ok}):
        rs = [r for r in ok if r.get("method", "") == m]
        by_method[m or "pause"] = {"n": len(rs), "within_1": sum(1 for r in rs if abs(r["diff"]) <= 1),
                                   "within_2": sum(1 for r in rs if abs(r["diff"]) <= 2)}
    summary = {"captions": len(rows), "measured": len(ok), "status": dict(Counter(r["status"] for r in rows)),
               "by_method": by_method,
               "diff_frames": {str(k): dist[k] for k in sorted(dist)},
               "within_0": sum(1 for r in ok if r["diff"] == 0), "within_1": sum(1 for r in ok if abs(r["diff"]) <= 1),
               "within_2": sum(1 for r in ok if abs(r["diff"]) <= 2)}
    if a.out:
        json.dump({"summary": summary, "rows": rows}, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    worst = sorted(ok, key=lambda r: -abs(r["diff"]))[:12]
    for r in worst:
        print(f"  {r['track']} {r['frame'] / fps // 60:02.0f}:{r['frame'] / fps % 60:05.2f} 字幕{r['frame']} 聞こえ始め{r['onset_frame']} 差{r['diff']:+d}  {r['text']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    e = sp.add_parser("extract")
    e.add_argument("src")
    e.add_argument("out")
    m = sp.add_parser("measure")
    m.add_argument("wav")
    m.add_argument("times", nargs="+", type=float)
    tr = sp.add_parser("transcribe")
    tr.add_argument("wav")
    tr.add_argument("out")
    tr.add_argument("--model", help="whisper.cpp のモデル（既定は ggml-small.bin。iMacの準備.md の 3）")
    tr.add_argument("--dtw", help="-dtw のプリセット（既定はモデルの名前から small・large.v3.turbo など）")
    c = sp.add_parser("check-prproj")
    c.add_argument("project")
    c.add_argument("--sequence", required=True)
    c.add_argument("--tracks", required=True, help="字幕のトラック（例 V8,V9）")
    c.add_argument("--audio-track", default="A1")
    c.add_argument("--media", required=True, help="声の素材の名前（例 IMG_1063.MOV）")
    c.add_argument("--wav", required=True, help="その素材から extract した WAV")
    c.add_argument("--asr", help="whisper-cli -ojf の出力。渡すと、音声認識の語の時刻を候補にして測る（本番と同じ）")
    c.add_argument("--out")
    a = ap.parse_args()
    if a.cmd == "extract":
        extract(a.src, a.out)
    elif a.cmd == "transcribe":
        transcribe(a.wav, a.out, a.model, a.dtw)
    elif a.cmd == "measure":
        audio = Audio(a.wav)
        for t in a.times:
            print(t, json.dumps(onset_near(audio, t), ensure_ascii=False))
    else:
        check_prproj(a)


if __name__ == "__main__":
    main()
