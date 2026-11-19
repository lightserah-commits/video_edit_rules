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
終了コード：語尾か頭が聞こえない所が1つでもあれば 1。比べたつなぎ目が 0 の時は 2（書き起こしを渡していない・カットが古いなど。--out は書かない）。

2026-11-19 から（1116 v001 の手のカットの突き合わせ。小川さん「推奨のまま go」）:
  ・比べたつなぎ目が 0 なのに合格（終了コード 0）にしない。1116 v001 は書き起こしを渡さずに流して 484 のつなぎ目を全部飛ばし、「0件」で通っていた
  ・字幕の最初の語も見る（「頭が聞こえない」）。つなぎ目のすぐ後に始まる字幕の頭の3字が、つなぎ目の後の書き起こしに無く、字幕の4字目より後ろからしか合わない時に出す
    （1116 v001 の「面倒くさい耐性とかは」は「面倒くさい」が丸ごと切れていた）。頭の1〜2字だけの違いは書き起こしの揺れとして数えない。合う所が無い物は「頭を比べられない」（数だけ）。
    数コマだけ頭が欠けた所（「自動販売機」の「じ」）は文字では出ない
  ・一覧に「切った物」の列を足す（中身＝中身・相づち・言い直し・フィラー・笑いを切ったつなぎ目／間＝間を詰めただけ）。カットの一覧（<版>/カット一覧_vNNN.csv。--cut-list で場所を変えられる）から決める。
    小川さんが戻した語尾・語頭は中身を切ったつなぎ目に集まる（1116：中身 47 のうち 9・間 175 のうち 1。1115：128 のうち 12・525 のうち 4）ので、読むのは「中身」の行。--only-content で「間」のつなぎ目を書き起こさない
  ・--cache の書き起こしは、つなぎ目の番号ではなく前後の素材の範囲で名前を付ける（カットを直しても、変わっていないつなぎ目は書き起こし直さない）。案件の join_sounds.py の j0001.json… は、カットより新しい時だけ使う
"""
import argparse
import bisect
import csv
import difflib
import hashlib
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


CONTENT_WORDS = ("区切り", "フィラー", "相づち", "言葉の端", "言いかけ", "言い直し", "くり返し")
SOUND_WORDS = ("笑い", "言葉の無い")      # 笑い・言葉の無い音を切った所は中身に数える。ただし「平らな所」（波形で詰めただけ）は間


def default_cut_list(cuts_path):
    """<版>/_work/cuts_vNNN.json → <版>/カット一覧_vNNN.csv"""
    w = os.path.dirname(os.path.abspath(cuts_path))
    m = re.match(r"cuts_(.+)\.json$", os.path.basename(cuts_path))
    p = os.path.join(os.path.dirname(w), f"カット一覧_{m.group(1)}.csv") if m else None
    return p if p and os.path.exists(p) else None


def load_cut_kinds(path):
    """カットの一覧から、つなぎ目（左の終わり b1 → 右の頭 a2）で切った物を返す関数を作る。
    中身＝種類に「中身」がある・理由に区切り／フィラー／笑い／言葉の無い音 などがある。間＝間を詰めただけ。一覧が無い・合う行が無い時は ""（読む側に入れる）"""
    cuts = []
    if path and os.path.exists(path):
        def sec(x):
            a, _, b = str(x).partition(":")
            return float(a) * 60 + float(b) if b else float(a)
        with open(path, encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                try:
                    c0, c1 = sec(r["素材の開始"]), sec(r["素材の終了"])
                except (KeyError, ValueError):
                    continue
                txt = (r.get("種類") or "") + " " + (r.get("理由") or "")
                content = "中身" in (r.get("種類") or "") or any(w in txt for w in CONTENT_WORDS) or (any(w in txt for w in SOUND_WORDS) and "平らな所" not in txt)
                cuts.append((c0, c1, "中身" if content else "間"))
    cuts.sort()
    starts = [c[0] for c in cuts]

    def kind(b1, a2):
        best, ov_best = "", 0.0
        i = bisect.bisect_left(starts, b1 - 1.0)
        while i < len(cuts) and cuts[i][0] < a2 + 0.06:
            c0, c1, kd = cuts[i]
            ov = min(c1, a2) - max(c0, b1)
            if ov > ov_best:
                best, ov_best = kd, ov
            i += 1
        return best if ov_best >= 0.5 * max(a2 - b1, 0.03) else ""
    return kind


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
    ap.add_argument("--cut-list", help="カットの一覧（素材の開始・素材の終了・種類・理由の列がある CSV）。既定：--cuts が <版>/_work/cuts_vNNN.json なら <版>/カット一覧_vNNN.csv")
    ap.add_argument("--only-content", action="store_true", help="中身・相づち・言い直し・フィラー・笑いを切ったつなぎ目だけを見る（間を詰めただけのつなぎ目は書き起こさない）")
    a = ap.parse_args()
    keep = [(x / a.fps, y / a.fps) for x, y in json.load(open(a.cuts))["keep_frames"]]
    kind_of = load_cut_kinds(a.cut_list or default_cut_list(a.cuts))
    cuts_mtime = os.path.getmtime(a.cuts)
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
    def cache_path(k, tj):
        """つなぎ目の前後 W 秒に入る素材の範囲から名前を作る（カットを直しても、ここが変わっていなければ同じ名前）"""
        if not a.cache:
            return None
        old = os.path.join(a.cache, f"j{k:04d}.json")          # 案件の join_sounds.py の形。カットより新しい時だけ使う
        if os.path.exists(old) and os.path.getmtime(old) >= cuts_mtime:
            return old
        parts = []
        for (x, y), t0 in zip(keep, tls):
            t1 = t0 + (y - x)
            if t1 <= tj - W or t0 >= tj + W:
                continue
            c0, c1 = max(t0, tj - W), min(t1, tj + W)
            parts.append(f"{x + (c0 - t0):.2f}-{x + (c1 - t0):.2f}")
        return os.path.join(a.cache, "w" + hashlib.md5("|".join(parts).encode()).hexdigest()[:16] + ".json")

    rows, n_ok, n_cmp, n_mid, n_skip = [], 0, 0, 0, 0
    h_ok, h_cmp = 0, 0
    for k in range(1, len(keep)):
        b1, a2 = keep[k - 1][1], keep[k][0]
        if b1 < a.lo or a2 > a.hi:
            continue
        tj = tls[k]
        what = kind_of(b1, a2)
        if a.only_content and what == "間":
            n_skip += 1
            continue
        cid_h = None
        if tl_caps:                      # 字幕の頭が版の上でつなぎ目のすぐ後にある＝前の字幕がここで終わる
            j = bisect.bisect_left(tl_starts, tj - 0.15)
            if not (j < len(tl_starts) and tl_starts[j] <= tj + 0.4) or j == 0:
                n_mid += 1
                continue
            cid = tl_caps[j - 1][1]
            text = text_of[cid]
            cid_h = tl_caps[j][1]
        else:
            i = bisect.bisect_left(cap_src, b1 - 0.3) - 1
            nxt = cap_src[i + 1] if 0 <= i and i + 1 < len(caps) else None
            if nxt is None or not (a2 - 0.3 <= nxt <= a2 + 0.8):
                n_mid += 1
                continue
            cid, text = caps[i][1], caps[i][2]
            cid_h = caps[i + 1][1]
        tgt = norm(text)
        if not tgt:
            continue
        if all_words is not None:
            q0, q1 = bisect.bisect_left(aw_start, tj - W), bisect.bisect_left(aw_start, tj + W)
            words = all_words[q0:q1]
        else:
            cp = cache_path(k, tj)
            if (cp is None or not os.path.exists(cp)) and ver is None:
                print(f"つなぎ目 {k} の書き起こしが無い（--wav か --words を渡す）", file=sys.stderr)
                continue
            words = transcribe(ver, tj, cp)
        # 書き起こしの語の時刻は 0.1〜0.3秒ずれるので、字幕の終わりの数字を、つなぎ目の前後（−2.5〜＋0.6秒）の書き起こしの文字の中で探す：
        #   終わりの4字が見つかる → 聞こえる
        #   終わりの1〜4字を除いた4字は見つかるのに、その後に残りが続かない → 語尾が聞こえない（「思って｜て」の「て」・「叩き込む｜っていう」）
        #   どちらも見つからない → 比べられない（字の書き方の違い・言い直しなど。耳で決める）
        chars, ends, starts = [], [], []
        for w0, w1, s in words:
            for c in norm(s):
                chars.append(c)
                ends.append(w1)
                starts.append(w0)
        heard = "".join(chars)
        # ── 字幕の最初の語（つなぎ目のすぐ後に始まる字幕）──
        #   頭の3字がつなぎ目の後の書き起こしにあれば「聞こえる」。無い時は、字幕と書き起こしで一番長く合う所を探す：
        #   合う所が字幕の4字目より後ろから始まり、その手前の字が書き起こしに（書き方違いでも）無ければ「頭が聞こえない」。
        #   頭の1〜2字だけの違い・手前の字が似ている時は、書き起こしの揺れとして「聞こえる」に数える。合う所が無ければ「頭を比べられない」
        tgt_h = norm(text_of.get(cid_h, "")) if cid_h else ""
        if len(tgt_h) >= 4:
            part_h = "".join(c for c, x in zip(chars, starts) if tj - 0.30 <= x <= tj + 3.0)
            if tgt_h[:3] in part_h[:12]:
                h_ok += 1
            else:
                ta, pb = tgt_h[:20], part_h[:26]
                m = difflib.SequenceMatcher(None, ta, pb, autojunk=False).find_longest_match(0, len(ta), 0, len(pb))
                if m.size >= 3 and m.a < 3:
                    h_ok += 1
                elif m.size >= 3 and m.b <= 10 and ta[:m.a].isascii():          # 英字・数字の頭（Grok・ChatGPT）は、書き起こしがかな書きで合わないだけ
                    h_ok += 1
                elif m.size >= 3 and m.b <= 10 and difflib.SequenceMatcher(None, ta[:m.a], pb[:m.b], autojunk=False).ratio() < 0.34:
                    rows.append([mmss(tj), "頭が聞こえない", cid_h, text_of[cid_h], "", part_h[:12], f"{a2:.2f}←{b1:.2f}", f"欠けた「{ta[:m.a]}」", what])
                elif m.size >= 3 and m.b <= 10:
                    h_ok += 1
                else:
                    h_cmp += 1
                    rows.append([mmss(tj), "頭を比べられない", cid_h, text_of[cid_h], "", part_h[:12], f"{a2:.2f}←{b1:.2f}", "", what])
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
            rows.append([mmss(tj), "比べられない", cid, text, part[-10:], "", f"{b1:.2f}→{a2:.2f}", "", what])
            continue
        rows.append([mmss(tj), "語尾が聞こえない", cid, text, missing[2], missing[3], f"{b1:.2f}→{a2:.2f}", f"欠けた「{missing[1]}」", what])
    bad = [r for r in rows if r[1] == "語尾が聞こえない"]
    bad_h = [r for r in rows if r[1] == "頭が聞こえない"]
    n_tail = n_ok + n_cmp + len(bad)
    n_head = h_ok + h_cmp + len(bad_h)

    def by_kind(rs):
        return f"中身を切ったつなぎ目 {sum(1 for r in rs if r[8] != '間')}・間を詰めただけ {sum(1 for r in rs if r[8] == '間')}"
    print(f"字幕の終わりのつなぎ目 {n_tail}：聞こえる {n_ok}・語尾が聞こえない {len(bad)}（{by_kind(bad)}）・比べられない {n_cmp}"
          f"（字幕の途中のつなぎ目 {n_mid} は見ていない" + (f"・間を詰めただけのつなぎ目 {n_skip} は --only-content で見ていない" if n_skip else "") + "）")
    print(f"字幕の頭のつなぎ目 {n_head}：聞こえる {h_ok}・頭が聞こえない {len(bad_h)}（{by_kind(bad_h)}）・比べられない {h_cmp}")
    if n_tail + n_head == 0:
        print("比べたつなぎ目が 0。検査になっていない（--wav か --words を渡したか・--cuts と --captions が同じ版か・--from と --to を確かめる）。一覧は書かない", file=sys.stderr)
        return 2
    for r in sorted(bad + bad_h, key=lambda r: (r[8] == "間", r[0]))[:60]:
        print("  " + " | ".join(str(x) for x in r))
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write("版の時刻（ハイライト無し）\t見立て\t字幕\t字幕の文\t聞こえた手前の語\tその後の語\t素材の秒（語尾：左の終わり→右の頭／頭：右の頭←左の終わり）\t欠けた字\t切った物\n")
            for r in rows:                 # 2行の字幕の改行が入ると行が割れる（2026-11-19 まで割れていた）ので、空白にする
                f.write("\t".join(re.sub(r"[\t\r\n]+", " ", str(x)) for x in r) + "\n")
        print("一覧 →", a.out)
    return 1 if bad or bad_h else 0


if __name__ == "__main__":
    sys.exit(main())
