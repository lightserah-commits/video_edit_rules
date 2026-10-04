#!/usr/bin/env python3
"""黙って演じている所の候補を探す（どの案件でも使える道具。読むだけ。音は鳴らさない）。
話し手が言葉の途中で黙って、顔・身ぶりで演じている所（例：環境設定 v004 の 16:36「多分Obsidianの開発者は」……（開発者の顔まね）……「ってなると思う」。
小川さんが Premiere で 151% の寄り＋ポカン＋BGM 停止＋文字なしにした）は、声が無いのでカットで詰められやすく、字幕も出ない。
カット（工程3）と演出（工程5）の前に、そういう所を一覧と画像で見つける。

  - 字幕（captions_vNNN.json。src＝素材の秒）を素材の順に並べ、字幕と次の字幕の間で、文字起こしの語（asr_camera.json）が無い時間が
    --min-gap 秒（既定 2）以上ある所を拾う。両方の字幕が残す区間（cuts の keep_frames。省くと drop 以外の全部）にある所だけ
  - 言葉が途中で抜けている所（前の字幕が「〜は」「〜って」「〜が」などで終わる・次の字幕が「って」「みたいな」「と思う」などで始まる）を上に並べる。
    同じ点なら声の無い時間が長い順
  - その間の音を ffmpeg で読み（その区間だけ）、50ミリ秒ごとの大きさが −45dBFS 未満の続く一番長い時間（声の無い長さ）と、−45dB 以上の割合を出す
  - 上から --sheets 件（既定 12）、カメラの 0.5秒ごとのコマを並べた画像を作る（前後 0.5秒。今のカットで切っているコマには「カット」と書く）

  python3 tools/find_silent_acts.py --ver <edit/vNNN> --cam <カメラ> [--asr <edit>/analysis/asr/asr_camera.json] [--out <edit>/analysis/silent_acts]
  python3 tools/find_silent_acts.py --captions <captions.json> --asr <asr_camera.json> --cam <カメラ> --out <出力> [--cuts <cuts.json>]
  カメラは作業用コピー（<edit>/media/camera_CFR2997.mov）。無ければ案件フォルダの元の素材（読むだけ）。字幕の src と同じ時計の動画を渡す
  （違う時は --offset 秒）。音は --audio で別の物を渡せる（省くとカメラの音）
出力：<out>/silent_acts.md（表）・silent_acts.json・sheets/NN_<字幕ID>.jpg
"""
import argparse
import array
import json
import math
import os
import re
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

FPS = 30000 / 1001
FONT = "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"
# 前の字幕がこれで終わる＝言葉が続くはず（「〜は」の後に黙るなど）
PREV_OPEN = ["って", "けども", "けど", "から", "ので", "のに", "たら", "ても", "は", "が", "を", "に", "で", "と", "も", "の", "へ", "て", "ば", "、"]
# 次の字幕がこれで始まる＝前の言葉を受けている（「って」で受けるなど）
NEXT_TAKE = ["っていう", "ってなる", "ってこと", "って", "っつって", "みたいな", "と思", "とか", "的な", "とな", "と言"]


def ts(sec):
    return f"{int(sec // 60)}:{sec % 60:05.2f}"


def clean(t):
    t = re.sub(r"（[^）]*）", "", t.replace("\r", "").replace("\n", ""))
    return t.strip(" 　。．.!！?？…・")


def score_of(prev, nxt):
    p, n = clean(prev), clean(nxt)
    sc, why = 0, []
    for w in PREV_OPEN:
        if p.endswith(w):
            sc += 3 if w in ("は", "って") else 2
            why.append(f"前が「〜{w}」で終わる")
            break
    for w in NEXT_TAKE:
        if n.startswith(w):
            sc += 3
            why.append(f"次が「{w}…」で始まる")
            break
    return sc, why


def load_words(path):
    words = []
    for seg in json.load(open(path, encoding="utf-8")):
        for w in seg.get("words", []):
            if w.get("start") is not None and w.get("end") is not None:
                words.append((float(w["start"]), float(w["end"]), w.get("word", "").strip()))
    words.sort()
    return words


def overlap(a, b, ranges):
    return sum(max(0.0, min(b, y) - max(a, x)) for x, y in ranges)


def loudness(audio, a, b, offset, thr):
    """a〜b 秒の音を読み、50ミリ秒ごとの大きさ（dBFS）から、thr 未満が続く一番長い秒・thr 以上の割合・一番大きい dB"""
    dur = max(0.05, b - a)
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(0.0, a + offset):.3f}", "-t", f"{dur:.3f}", "-i", audio, "-vn", "-ac", "1",
                        "-ar", "16000", "-f", "s16le", "-"], capture_output=True)
    if r.returncode != 0 or not r.stdout:
        return None
    x = array.array("h")
    x.frombytes(r.stdout[: len(r.stdout) // 2 * 2])
    win = 800
    dbs = []
    for i in range(0, len(x) - win + 1, win):
        ch = x[i:i + win]
        rms = math.sqrt(sum(v * v for v in ch) / win)
        dbs.append(20 * math.log10(rms / 32768) if rms > 0 else -120.0)
    if not dbs:
        return None
    run = best = 0
    for d in dbs:
        run = run + 1 if d < thr else 0
        best = max(best, run)
    return {"quiet_sec": round(best * 0.05, 2), "loud_ratio": round(sum(d >= thr for d in dbs) / len(dbs), 2), "max_db": round(max(dbs), 1)}


def sheet(cam, a, b, offset, keep, out, title):
    """a〜b（前後 0.5秒を足す）の 0.5秒ごとのコマを並べた画像"""
    t0, t1 = a - 0.5, b + 0.5
    times = [round(t0 + 0.5 * k, 2) for k in range(int((t1 - t0) / 0.5) + 1)]
    tmp = out + ".frames"
    os.makedirs(tmp, exist_ok=True)
    for f in os.listdir(tmp):
        os.remove(os.path.join(tmp, f))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0.0, t0 + offset):.3f}", "-t", f"{t1 - t0 + 0.05:.3f}", "-i", cam,
                    "-vf", "fps=2:round=down,scale=384:216", "-frames:v", str(len(times)), os.path.join(tmp, "f_%03d.jpg")], check=True)
    got = sorted(os.listdir(tmp))
    font, small = ImageFont.truetype(FONT, 24), ImageFont.truetype(FONT, 18)
    cols = 5
    rows = (len(got) + cols - 1) // cols
    W, H = 384, 216 + 28
    img = Image.new("RGB", (W * cols, H * rows + 44), (20, 20, 20))
    dr = ImageDraw.Draw(img)
    dr.text((10, 8), title[:90], fill="yellow", font=font)
    for k, fn in enumerate(got):
        t = times[k] if k < len(times) else t0 + 0.5 * k
        im = Image.open(os.path.join(tmp, fn)).convert("RGB")
        x, y = (k % cols) * W, 44 + (k // cols) * H
        img.paste(im, (x, y + 28))
        cut = keep is not None and not any(p <= t < q for p, q in keep)
        lab = f"{ts(t)}" + ("  声なし" if a <= t < b else "") + ("  カット" if cut else "")
        dr.rectangle([x, y, x + W - 1, y + 27], fill=(120, 0, 0) if cut else ((0, 70, 0) if a <= t < b else (40, 40, 40)))
        dr.text((x + 6, y + 3), lab, fill="white", font=small)
    img.save(out, quality=85)
    for f in os.listdir(tmp):
        os.remove(os.path.join(tmp, f))
    os.rmdir(tmp)


def main():
    ap = argparse.ArgumentParser(description="黙って演じている所の候補（字幕の間の声の無い時間）を探して、コマを並べた画像にする", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ver", help="版のフォルダ edit/vNNN（_work/captions_vNNN.json・cuts_vNNN.json、<edit>/analysis/asr/asr_camera.json を使う）")
    ap.add_argument("--captions", help="captions_vNNN.json（--ver より優先）")
    ap.add_argument("--cuts", help="cuts_vNNN.json（残す区間 keep_frames と字幕のタイムラインのコマ。省くと全部を残す区間に）")
    ap.add_argument("--asr", help="文字起こしの語の時刻（asr_camera.json）")
    ap.add_argument("--cam", help="カメラの動画（作業用コピーか元の素材）")
    ap.add_argument("--audio", help="音を読む物（省くと --cam）")
    ap.add_argument("--offset", type=float, default=0.0, help="字幕の src の秒に足すと --cam の秒になる値（既定 0）")
    ap.add_argument("--out", help="出力のフォルダ（省くと <edit>/analysis/silent_acts）")
    ap.add_argument("--min-gap", type=float, default=2.0, help="拾う、声の無い時間（秒。既定 2）")
    ap.add_argument("--db", type=float, default=-45.0, help="声が無いとみなす大きさ（dBFS。既定 −45）")
    ap.add_argument("--sheets", type=int, default=12, help="コマの画像を作る件数（上から。既定 12）")
    ap.add_argument("--no-audio", action="store_true", help="音を読まない")
    a = ap.parse_args()
    edit = None
    if a.ver:
        v = os.path.abspath(os.path.expanduser(a.ver))
        edit = os.path.dirname(v)
        m = re.search(r"v(\d{3})$", os.path.basename(v))
        if m:
            tag = m.group(1)
            a.captions = a.captions or os.path.join(v, "_work", f"captions_v{tag}.json")
            c = os.path.join(v, "_work", f"cuts_v{tag}.json")
            a.cuts = a.cuts or (c if os.path.exists(c) else None)
        a.asr = a.asr or os.path.join(edit, "analysis", "asr", "asr_camera.json")
        if not a.cam:
            c = os.path.join(edit, "media", "camera_CFR2997.mov")
            a.cam = c if os.path.exists(c) else None
    for k in ("captions", "asr"):
        if not getattr(a, k) or not os.path.exists(getattr(a, k)):
            raise SystemExit(f"--{k} が無い（{getattr(a, k)}）")
    out = a.out or (os.path.join(edit, "analysis", "silent_acts") if edit else None)
    if not out:
        raise SystemExit("--out を渡す")
    os.makedirs(os.path.join(out, "sheets"), exist_ok=True)
    capj = json.load(open(a.captions, encoding="utf-8"))
    caps = sorted([c for c in capj["captions"] if c.get("mode") != "drop" and c.get("src") is not None], key=lambda c: c["src"])
    keep, cap_tl, hl = None, {}, 0
    if a.cuts:
        cj = json.load(open(a.cuts, encoding="utf-8"))
        keep = [(x / FPS, y / FPS) for x, y in cj["keep_frames"]]
        cap_tl = cj.get("caption_tl", {})
    words = load_words(a.asr)
    starts = [w[0] for w in words]
    import bisect
    found = []
    for c0, c1 in zip(caps, caps[1:]):
        s0, s1 = float(c0["src"]), float(c1["src"])
        if s1 <= s0:
            continue
        if keep is not None and not (any(p <= s0 < q for p, q in keep) and any(p <= s1 < q for p, q in keep)):
            continue
        # 前の字幕の頭〜次の字幕の頭（＋0.3秒）の語を並べ、語と語の間で一番長い間（次の字幕の頭の 0.6秒前より後で終わるもの）を「声の無い時間」に。
        # 文字起こしの語の時刻は聞こえ始めより早いことがある（環境設定 v004 の 1101「って」は語 3104.30・字幕 3104.40）ので、次の字幕の語も入れて見る
        i0, i1 = bisect.bisect_left(starts, s0 - 0.1), bisect.bisect_left(starts, s1 + 0.3)
        g0 = g1 = None
        end = s0
        for w in words[i0:i1] + [(s1, s1, "")]:
            if w[0] > end and w[0] >= s1 - 0.6 and (g0 is None or w[0] - end > g1 - g0):
                g0, g1 = end, min(w[0], s1 + 0.3)
            end = max(end, w[1])
        if g0 is None or g1 - g0 < a.min_gap:
            continue
        sc, why = score_of(c0["text"], c1["text"])
        row = {"prev_id": c0["id"], "next_id": c1["id"], "prev": c0["text"].replace("\r", "／"), "next": c1["text"].replace("\r", "／"),
               "who": c0.get("who", ""), "gap_src": [round(g0, 2), round(g1, 2)], "gap_sec": round(g1 - g0, 2),
               "kept_sec": round(overlap(g0, g1, keep), 2) if keep is not None else round(g1 - g0, 2), "score": sc, "why": why}
        if c1["id"] in cap_tl:
            row["next_tl"] = ts((cap_tl[c1["id"]]) / FPS)
        found.append(row)
    found.sort(key=lambda r: (-r["score"], -r["gap_sec"]))
    audio = a.audio or a.cam
    if audio and not a.no_audio:
        for r in found:
            r["audio"] = loudness(audio, r["gap_src"][0], r["gap_src"][1], a.offset, a.db)
    for k, r in enumerate(found[:a.sheets], 1):
        if not a.cam:
            break
        p = os.path.join(out, "sheets", f"{k:02d}_{r['next_id'].replace('+', 'p')}.jpg")
        sheet(a.cam, r["gap_src"][0], r["gap_src"][1], a.offset, keep, p,
              f"{k}. [{r['prev_id']}]「{clean(r['prev'])[-16:]}」…{r['gap_sec']}秒…[{r['next_id']}]「{clean(r['next'])[:14]}」")
        r["sheet"] = p
    lines = ["# 黙って演じている所の候補", "", f"- 字幕：{a.captions}", f"- 語の時刻：{a.asr}", f"- カメラ：{a.cam or '（無し：画像は作っていない）'}",
             f"- 声の無い時間 {a.min_gap}秒以上 {len(found)}件。上ほど言葉が途中で抜けている。声の無い長さは {a.db}dBFS 未満が続く一番長い時間", "",
             "| # | 素材の時刻 | 今の版 | 声なし（今のカットで残る） | 音（声の無い長さ・大きい所の割合） | 前の字幕 → 次の字幕 | わけ |",
             "|---|---|---|---|---|---|---|"]
    for k, r in enumerate(found, 1):
        au = r.get("audio") or {}
        lines.append(f"| {k} | {ts(r['gap_src'][0])}〜{ts(r['gap_src'][1])} | {r.get('next_tl', '')} | {r['gap_sec']}秒（{r['kept_sec']}秒） | "
                     f"{(str(au.get('quiet_sec')) + '秒・' + str(int(au.get('loud_ratio', 0) * 100)) + '%') if au else ''} | "
                     f"[{r['prev_id']}] {clean(r['prev'])[-20:]} → [{r['next_id']}] {clean(r['next'])[:20]} | {'・'.join(r['why'])} |")
    open(os.path.join(out, "silent_acts.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    json.dump(found, open(os.path.join(out, "silent_acts.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n".join(lines[:min(len(lines), 9 + 15)]))
    print(f"→ {out}（画像 {min(len(found), a.sheets) if a.cam else 0}枚）")


if __name__ == "__main__":
    main()
