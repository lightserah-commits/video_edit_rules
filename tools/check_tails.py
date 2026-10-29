#!/usr/bin/env python3
"""字幕の最後の語が、つないだ声で聞こえているかを、全部のつなぎ目で確かめる（08 の cut.no_chop.flow「欠けた語尾」。2026-10-28 から）。

1025 v002・1026 v004 で小川さんが手で戻した語尾（「思って｜て」「あっ｜て」「っていう」「言われて｜て」など）は、
小さい「っ」の無音や小さい語尾を AI が言い終わりと見誤って切った物だった。波形では見分けにくいので、文字で比べる:
  つなぎ目の左で終わる字幕の最後の文字（（ ）の補いと記号は除く）が、つないだ声をフィラーも書く設定で書き起こし直した
  「つなぎ目の手前の語」の終わりに無ければ、「語尾が聞こえない」として一覧に出す。
  字幕の最後が漢字・数字・英字で、書き起こしと字の種類が違う時は「比べられない」に分ける（耳で決める）。
字幕と書き起こしで語尾が違うだけの所もあるので、出た所は自動で延ばさず、素材の前後を見て決める（1025 の 1:15.74 は戻していない）。

使い方:
  python3 tools/check_tails.py --cuts <版>/_work/cuts_vNNN.json --captions <版>/_work/captions_vNNN.json \\
      --wav <edit>/analysis/asr/_work/camera.wav [--cache <版>/_work/_join_sounds] [--from 秒 --to 秒] [--out 一覧.tsv]
  --cache：つなぎ目ごとの書き起こし（j0001.json…。案件の join_sounds.py と同じ形）。あれば使い、無い所だけ書き起こす
  書き起こしは models/ の whisper（HF_HUB_OFFLINE=1。名前で呼ぶと無断ダウンロードになる）。env/ の python で動かす。
終了コード：語尾が聞こえない所が1つでもあれば 1。
"""
import argparse
import bisect
import json
import os
import re
import sys
import unicodedata

FPS = 30000 / 1001
SR = 16000
W = 3.0
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MODEL = os.path.join(ROOT, "models", "whisper-large-v3-turbo")
PROMPT = "えー、あの、えっと、ど、どこに、その、まあ、なんか、はい。えっとですね、あのー、こ、こういう。"
DROP = re.compile(r"[（(][^）)]*[）)]|[\s、。，．,.！？!?「」『』…・〜ー―\-]")


def norm(s):
    """比べる形：（ ）の補い・記号・のばし棒を除き、カタカナをひらがなに"""
    s = DROP.sub("", unicodedata.normalize("NFKC", s))
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)


def kind(c):
    if "ぁ" <= c <= "ゖ":
        return "kana"
    return "other"


def transcribe(ver, t, cache_path):
    if cache_path and os.path.exists(cache_path):
        return json.load(open(cache_path))["words"]
    os.environ["HF_HUB_OFFLINE"] = "1"
    import mlx_whisper
    a0, a1 = max(0.0, t - W), min(len(ver) / SR, t + W)
    r = mlx_whisper.transcribe(ver[int(a0 * SR):int(a1 * SR)], path_or_hf_repo=MODEL, language="ja", word_timestamps=True,
                               condition_on_previous_text=False, initial_prompt=PROMPT, verbose=None)
    words = [[w["start"] + a0, w["end"] + a0, w["word"]] for s in r["segments"] for w in s.get("words", [])]
    if cache_path:
        json.dump({"words": words}, open(cache_path, "w"), ensure_ascii=False)
    return words


def mmss(t):
    return f"{int(t // 60)}:{t % 60:05.2f}"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cuts", required=True)
    ap.add_argument("--captions", required=True)
    ap.add_argument("--wav", help="素材の声（16kHz mono）。--cache に無いつなぎ目を書き起こす時に要る")
    ap.add_argument("--cache", help="つなぎ目ごとの書き起こしの置き場（j0001.json…）。版を作り直したら古い物は使わない（つなぎ目の番号がずれる）")
    ap.add_argument("--words", help="書き出した mp4 の語の時刻つきの文字起こし（[{start,end,text,words:[{start,end,word}]}]。mp4 の秒）。渡すとこちらを使う")
    ap.add_argument("--words-offset", type=float, help="mp4 の秒から引く秒（既定：cuts の highlight_external_frames＝冒頭ハイライトの長さ）")
    ap.add_argument("--from", dest="lo", type=float, default=0.0)
    ap.add_argument("--to", dest="hi", type=float, default=1e9)
    ap.add_argument("--fps", type=float, default=FPS)
    ap.add_argument("--out")
    a = ap.parse_args()
    keep = [(x / a.fps, y / a.fps) for x, y in json.load(open(a.cuts))["keep_frames"]]
    cj = json.load(open(a.captions))
    caps = sorted((c["src"], c["id"], c["text"]) for c in (cj["captions"] if isinstance(cj, dict) else cj) if c.get("src") is not None)
    # 残した字幕だけ（台本で切った字幕は、src が切った所にある）
    ks = [x for x, y in keep]
    caps = [c for c in caps if (lambda j: j >= 0 and keep[j][0] - 0.3 <= c[0] <= keep[j][1])(bisect.bisect_right(ks, c[0] + 0.3) - 1)]
    cap_src = [c[0] for c in caps]
    cut_json = json.load(open(a.cuts))
    hl = cut_json.get("highlight_external_frames") or 0
    ctl = cut_json.get("caption_tl") or {}
    text_of = {c[1]: c[2] for c in caps}
    tl_caps = sorted(((f - hl) / a.fps, cid) for cid, f in ctl.items() if cid in text_of)   # 版の上（ハイライト無し）で字幕が出る時刻
    tl_starts = [x[0] for x in tl_caps]
    tls, t = [], 0.0
    for x, y in keep:
        tls.append(t)
        t += y - x
    ver = None
    if a.wav:
        import wave
        import numpy as np
        with wave.open(a.wav) as f:
            src = np.frombuffer(f.readframes(f.getnframes()), dtype=np.int16).astype(np.float32) / 32768
        ver = np.concatenate([src[int(round(x * SR)):int(round(y * SR))] for x, y in keep])
    if a.cache:
        os.makedirs(a.cache, exist_ok=True)
    all_words = None
    if a.words:
        wj = json.load(open(a.words))
        segs = wj["segments"] if isinstance(wj, dict) else wj
        off = a.words_offset if a.words_offset is not None else hl / a.fps
        # 2026-10-29 1027 v001：find_fillers.py --mp4 の文字起こし（<mp4>_filler_asr.json）は語が [始め, 終わり, 語] の並び。辞書の形と両方読む
        all_words = sorted([(w[0] if isinstance(w, list) else w["start"]) - off, (w[1] if isinstance(w, list) else w["end"]) - off,
                            w[2] if isinstance(w, list) else w["word"]] for s in segs for w in s.get("words", []))
        aw_start = [w[0] for w in all_words]
    rows, n_ok, n_cmp, n_mid = [], 0, 0, 0
    for k in range(1, len(keep)):
        b1, a2 = keep[k - 1][1], keep[k][0]
        if b1 < a.lo or a2 > a.hi:
            continue
        tj = tls[k]
        if tl_caps:                      # 字幕の頭が版の上でつなぎ目のすぐ後にある＝前の字幕がここで終わる
            j = bisect.bisect_left(tl_starts, tj - 0.15)
            if not (j < len(tl_starts) and tl_starts[j] <= tj + 0.4) or j == 0:
                n_mid += 1
                continue
            cid = tl_caps[j - 1][1]
            text = text_of[cid]
        else:
            i = bisect.bisect_left(cap_src, b1 - 0.3) - 1
            nxt = cap_src[i + 1] if 0 <= i and i + 1 < len(caps) else None
            if nxt is None or not (a2 - 0.3 <= nxt <= a2 + 0.8):
                n_mid += 1
                continue
            cid, text = caps[i][1], caps[i][2]
        tgt = norm(text)
        if not tgt:
            continue
        if all_words is not None:
            q0, q1 = bisect.bisect_left(aw_start, tj - W), bisect.bisect_left(aw_start, tj + W)
            words = all_words[q0:q1]
        else:
            cp = os.path.join(a.cache, f"j{k:04d}.json") if a.cache else None
            if (cp is None or not os.path.exists(cp)) and ver is None:
                print(f"つなぎ目 {k} の書き起こしが無い（--wav か --words を渡す）", file=sys.stderr)
                continue
            words = transcribe(ver, tj, cp)
        # 書き起こしの語の時刻は 0.1〜0.3秒ずれるので、字幕の終わりの数字を、つなぎ目の前後（−2.5〜＋0.6秒）の書き起こしの文字の中で探す：
        #   終わりの4字が見つかる → 聞こえる
        #   終わりの1〜4字を除いた4字は見つかるのに、その後に残りが続かない → 語尾が聞こえない（「思って｜て」の「て」・「叩き込む｜っていう」）
        #   どちらも見つからない → 比べられない（字の書き方の違い・言い直しなど。耳で決める）
        chars, ends = [], []
        for w0, w1, s in words:
            for c in norm(s):
                chars.append(c)
                ends.append(w1)
        heard = "".join(chars)
        win = [q for q, x in enumerate(ends) if tj - 2.5 <= x <= tj + 0.6]
        lo_q, hi_q = (win[0], win[-1] + 1) if win else (0, 0)
        part = heard[lo_q:hi_q]
        tail = tgt[-4:]
        if tail in part:
            n_ok += 1
            continue
        q_all = heard.find(tail, hi_q)
        if q_all >= 0 and ends[min(q_all + len(tail) - 1, len(ends) - 1)] <= tj + 3.0:
            n_mid += 1                   # 字幕の終わりがつなぎ目の後で聞こえる＝字幕の途中で切った所
            continue
        missing = None
        for cut in (1, 2, 3, 4):         # 欠けたのが語尾の1〜4字（「て」「のよ」「っていう」）
            stem = tgt[-4 - cut:-cut]
            if len(stem) >= 3 and stem in part:
                q = part.rfind(stem) + len(stem)
                if not part[q:q + 4].startswith(tgt[-cut:]):
                    missing = (stem, tgt[-cut:], part[max(0, q - 8):q], part[q:q + 6])
                    break
        if missing is None:
            n_cmp += 1
            rows.append([mmss(tj), "比べられない", cid, text, part[-10:], "", f"{b1:.2f}→{a2:.2f}"])
            continue
        rows.append([mmss(tj), "語尾が聞こえない", cid, text, missing[2], missing[3], f"{b1:.2f}→{a2:.2f}", f"欠けた「{missing[1]}」"])
    bad = [r for r in rows if r[1] == "語尾が聞こえない"]
    print(f"字幕の終わりのつなぎ目 {n_ok + len(rows)}：聞こえる {n_ok}・語尾が聞こえない {len(bad)}・比べられない {n_cmp}"
          f"（字幕の途中のつなぎ目 {n_mid} は見ていない）")
    for r in bad[:40]:
        print("  " + " | ".join(str(x) for x in r))
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write("版の時刻（ハイライト無し）\t見立て\t字幕\t字幕の文\t聞こえた手前の語\tその後の語\t素材の秒（左の終わり→右の頭）\t欠けた字\n")
            for r in rows:
                f.write("\t".join(str(x) for x in r) + "\n")
        print("一覧 →", a.out)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
