#!/usr/bin/env python3
"""フィラーの候補を探す（08 の cut.remove「フィラー（言いよどみ）」）。どの案件でも使える道具。2026-10-20 小川さん OK。

今の文字起こし（1回目・2回目）にはフィラーがほとんど出ない（1017 の35分で「えー」8回・「あのー」0回）。そこで、フィラーも書き起こすように
促す文字起こし（mlx_whisper・large-v3-turbo。AI動画編集 r2 の確かめで使った言葉の並び）をもう1回作り、残している所のフィラーを
「声も切る／声は残す」に分けて一覧にする。文字起こしは2分ずつで、終わった所は残す（止まっても続きから。次の版でも使い回す）。

  ① 版のカットに残っているフィラー（工程3。カットを組んだ後に毎回）
     ~/Desktop/video_edit_rules/env/bin/python tools/find_fillers.py --ver "<edit/vNNN>" [--wav 声.wav] [--all]
       読む物：<edit/vNNN>/_work/cuts_vNNN.json、<edit>/analysis/asr/_work/camera.wav（素材の声。--wav で変える）、<edit>/analysis/camera_env.npy
       作る物：<edit>/analysis/asr/_work/filler_NNNNN.json（2分ずつの文字起こし。残している所にかかる2分だけ作る）
       出す物：<edit/vNNN>/_work/fillers_vNNN.md・.tsv（--out で変える）
  ② 書き出した mp4 に残っているフィラー（工程9。書き出した後）
     ~/Desktop/video_edit_rules/env/bin/python tools/find_fillers.py --mp4 "<書き出し.mp4>" [--out 出す場所]
       出す物：<mp4 の名前>_fillers.md・.tsv（mp4 の隣）。文字起こしは <mp4 の名前>_filler_asr.json。声も切る種類が残っていれば終了コード1

分け方（08 の cut.remove「フィラー（言いよどみ）」）
  声も切る … えー・えっと・えーと・あのー・うーん・あー／文の頭とつなぎ目の「あの」（三上さんの決まり。ほかの人の時は読んで決める）／
             カットのつなぎ目に接する「やっぱ」「まあ」／同じ語の重なりの前の方（「まあまあ」「なんか なんか」）
  声は残す … 文の中の「あの」・なんか・やっぱ・まあ・ですね・ちなみに・その・はい（一覧の終わりに数だけ。--all で全部並べる）
  つなぎ目＝前か後ろの言葉を切っている所（間を詰めただけの所は入らない）。②の mp4 ではつなぎ目が分からないので、つなぎ目の決まりは見ない
  言いかけ・言い直しの一部かどうかは道具では決めない（前後を読んで AI が決める。08 の remove「言い直し」）
① の「声も切る」には、切る区間（10ms ごとの声の大きさの谷から谷まで。素材の秒）と、EXTRA_CUTS の形の行を付ける。谷が無く前後の語と
続いている所は「谷なし」（字幕から抜くだけ。no_chop）。決めるのは AI：一覧を全部読み、切る物を cuts_plan の EXTRA_CUTS に理由つきで写して
組み直す。文字起こしの時刻は ±0.1秒ほど粗いので、組み直したら check_chops・check_slivers・check_stray_words で確かめる。耳では確かめていない（未聴取）。
"""
import argparse
import bisect
import json
import os
import re
import subprocess
import sys
import tempfile
import wave

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL = os.path.join(ROOT, "models", "whisper-large-v3-turbo")
PROMPT = "えー、あの、えっと、ど、どこに、その、まあ、なんか、はい。えっとですね、あのー、こ、こういう。"   # フィラーを書き起こすように促す
CHUNK = 120
FPS = 30000 / 1001
B = r"(?<![ぁ-んァ-ヶ一-龥ー])"     # 前が語の途中でない（「たとえ」「伝えと」「じゃあ」を外す）
KINDS = [   # （種類, 形）。上から順に探し、先に当たった所は後の形で数えない
    ("言いよどみ", B + r"(えー+っと|えーと|えっと|えと(?=[、 ])|えー+|うー+ん|んー+|あー+(?=[、 ]))"),
    ("あのー", B + r"(あのー+|あのう)"),
    ("あの", r"(?<![こそどか])あの(?=[、 。]|$)"),
    ("やっぱ", r"やっぱり?"),
    ("まあ", r"(?<!じゃ)(まあ|まぁ|まー)"),
    ("なんか", r"(?<!なん)(?<!何)なんか"),          # 「何なんかっていうと」を外す
    ("ですね", r"(?<=[^ 、。])ですね(?=[、 ])"),
    ("ちなみに", r"ちなみに"),
    ("その", B + r"その(?=[、 ]|$)"),
    ("はい", B + r"はい(?=[、。 ]|$)"),
]
SEP = " 、。,.？?！!"


def ff(t):
    if t is None:
        return "-"
    m = int(t // 60)
    return f"{m}:{t - 60 * m:05.2f}"


def read_wav(path):
    with wave.open(path) as f:
        if f.getframerate() != 16000 or f.getnchannels() != 1:
            raise SystemExit(f"{path} は 16kHz・1ch ではない（ffmpeg -ac 1 -ar 16000 で作る）")
        return np.frombuffer(f.readframes(f.getnframes()), dtype=np.int16).astype(np.float32) / 32768


def transcribe(audio, starts, cache_dir):
    """audio の starts（2分ずつの頭の秒）だけを文字起こしする。終わった所は cache_dir/filler_NNNNN.json を使う"""
    os.environ["HF_HUB_OFFLINE"] = "1"      # モデルは models/ の物だけ使う（名前で呼ぶと無断でダウンロードになる）
    import mlx_whisper
    os.makedirs(cache_dir, exist_ok=True)
    segs, todo = [], [s for s in starts if not os.path.exists(os.path.join(cache_dir, f"filler_{s:05d}.json"))]
    if todo:
        print(f"文字起こし：2分ずつ {len(todo)}個（使い回し {len(starts) - len(todo)}個）", flush=True)
    for st in starts:
        p = os.path.join(cache_dir, f"filler_{st:05d}.json")
        if not os.path.exists(p):
            r = mlx_whisper.transcribe(audio[st * 16000:(st + CHUNK) * 16000], path_or_hf_repo=MODEL, language="ja",
                                       word_timestamps=True, condition_on_previous_text=False, initial_prompt=PROMPT, verbose=None)
            part = [{"start": round(s["start"] + st, 2), "end": round(s["end"] + st, 2), "text": s["text"],
                     "words": [[round(w["start"] + st, 2), round(w["end"] + st, 2), w["word"]] for w in s.get("words", [])]}
                    for s in r["segments"]]
            json.dump(part, open(p + ".tmp", "w", encoding="utf-8"), ensure_ascii=False)
            os.replace(p + ".tmp", p)
            print(f"  {st}秒〜 済み", flush=True)
        segs += json.load(open(p, encoding="utf-8"))
    return segs


def chars(segs):
    """文字ごとの (始め, 終わり, 文字)。区切りの終わりに空白を入れる"""
    out = []
    for s in segs:
        for a, b, w in s["words"]:
            w = w.strip()
            for i, ch in enumerate(w):
                out.append((a + (b - a) * i / len(w), a + (b - a) * (i + 1) / len(w), ch))
        out.append((s["end"], s["end"], " "))
    return out


def find(cs):
    text = "".join(c[2] for c in cs)
    used, hits = set(), []
    for kind, pat in KINDS:
        for m in re.finditer(pat, text):
            i, j = m.start(), m.end()
            if any(k in used for k in range(i, j)):
                continue
            used.update(range(i, j))
            a, b = cs[i][0], cs[j - 1][1]
            if b - a < 0.05:
                b = a + 0.1
            pi = i - 1
            while pi >= 0 and cs[pi][2] in SEP:
                pi -= 1
            ni = j
            while ni < len(cs) and cs[ni][2] in SEP:
                ni += 1
            between = text[pi + 1:i] if pi >= 0 else ""
            head = pi < 0 or any(ch in between for ch in "。？?！!") or (a - cs[pi][1] > 0.3)
            hits.append(dict(kind=kind, word=m.group(0), s=round(a, 2), e=round(b, 2), i=i, j=j, head=head,
                             prev=cs[pi] if pi >= 0 else None, next=cs[ni] if ni < len(cs) else None,
                             before=text[max(0, i - 16):i].replace(" ", "／"), after=text[j:j + 16].replace(" ", "／")))
    hits.sort(key=lambda h: h["s"])
    for h, g in zip(hits, hits[1:]):         # 同じ語の重なり：前の方を切る候補に
        if g["word"] == h["word"] and g["s"] - h["e"] < 0.6 and not text[h["j"]:g["i"]].strip(SEP):
            h["repeat"] = True
    return hits


def valley(env, t0, t1, quiet):
    """env（10ms ごとの dB）の [t0, t1] でいちばん小さい所の秒。quiet より大きければ None（谷なし）"""
    i0, i1 = max(0, int(t0 * 100)), min(len(env), int(t1 * 100) + 1)
    if i1 <= i0:
        return None
    k = int(np.argmin(env[i0:i1]))
    return round((i0 + k) / 100, 2) if env[i0 + k] <= quiet else None


def write(out, title, lines_md, rows_tsv):
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    open(out + ".md", "w", encoding="utf-8").write("\n".join([title, ""] + lines_md) + "\n")
    with open(out + ".tsv", "w", encoding="utf-8") as f:
        f.write("分け方\t版の時刻\t素材の秒\t種類\t語\t前\t後\t切る区間\t理由\n")
        for r in rows_tsv:
            f.write("\t".join(str(x) for x in r) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ver", help="版のフォルダ edit/vNNN（①）")
    ap.add_argument("--mp4", help="書き出した mp4（②）")
    ap.add_argument("--wav", help="①：素材の声（16kHz・1ch。省略で <edit>/analysis/asr/_work/camera.wav）")
    ap.add_argument("--env", help="①：10ms ごとの声の大きさ（省略で <edit>/analysis/camera_env.npy）")
    ap.add_argument("--cuts", help="①：cuts_vNNN.json（省略で <版>/_work/cuts_vNNN.json）")
    ap.add_argument("--over", type=float, default=6.0, help="①：谷とみなす大きさ＝声のしきい値（cuts の voice_thr_db）＋この dB（既定 6）")
    ap.add_argument("--all", action="store_true", help="声は残すフィラーも全部並べる")
    ap.add_argument("--out", help="出す場所（拡張子なし）")
    a = ap.parse_args()
    if bool(a.ver) == bool(a.mp4):
        ap.error("--ver か --mp4 のどちらか1つ")

    if a.mp4:
        mp4 = os.path.abspath(os.path.expanduser(a.mp4))
        base = os.path.splitext(mp4)[0]
        asr_path = base + "_filler_asr.json"
        if os.path.exists(asr_path):
            segs = json.load(open(asr_path, encoding="utf-8"))
        else:
            with tempfile.TemporaryDirectory() as td:
                wav = os.path.join(td, "voice.wav")
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", mp4, "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", wav], check=True)
                audio = read_wav(wav)
                segs = transcribe(audio, list(range(0, len(audio) // 16000 + 1, CHUNK)), os.path.join(td, "chunks"))
            json.dump(segs, open(asr_path, "w", encoding="utf-8"), ensure_ascii=False)
        hits = find(chars(segs))
        cut, keep = [], []
        for h in hits:
            if h["kind"] in ("言いよどみ", "あのー") or h.get("repeat") or (h["kind"] == "あの" and h["head"]):
                why = "重なりの前の方" if h.get("repeat") and h["kind"] not in ("言いよどみ", "あのー") else \
                      ("文の頭の「あの」（三上さんの時）" if h["kind"] == "あの" else "言いよどみ")
                cut.append((h, why))
            else:
                keep.append(h)
        out = a.out or base + "_fillers"
        L = [f"文字起こし：{os.path.basename(asr_path)}（フィラーも書き起こす設定。時刻は ±0.1秒ほど粗い）。**全部未聴取**",
             "つなぎ目は mp4 からは分からないので、つなぎ目の「あの」「やっぱ」「まあ」は見ていない（①で見る）", "",
             f"- 声も切る種類が残っている：{len(cut)}件", f"- 声は残すフィラー：{len(keep)}件", "",
             "| mp4 の時刻 | 種類 | 前【語】後 | 理由 |", "|---|---|---|---|"]
        L += [f"| {ff(h['s'])} | {h['kind']} | {h['before']}【{h['word']}】{h['after']} | {why} |" for h, why in cut]
        if a.all:
            L += ["", "## 声は残す", "", "| mp4 の時刻 | 種類 | 前【語】後 |", "|---|---|---|"]
            L += [f"| {ff(h['s'])} | {h['kind']} | {h['before']}【{h['word']}】{h['after']} |" for h in keep]
        rows = [("声も切る", ff(h["s"]), "", h["kind"], h["word"], h["before"], h["after"], "", why) for h, why in cut] + \
               [("声は残す", ff(h["s"]), "", h["kind"], h["word"], h["before"], h["after"], "", "") for h in keep]
        write(out, f"# 書き出しに残っているフィラー（{os.path.basename(mp4)}）", L, rows)
        print(f"声も切る種類 {len(cut)}件・声は残す {len(keep)}件 → {out}.md")
        sys.exit(1 if cut else 0)

    V = os.path.abspath(os.path.expanduser(a.ver))
    tag = os.path.basename(V)
    E = os.path.dirname(V)
    cuts = json.load(open(a.cuts or os.path.join(V, "_work", f"cuts_{tag}.json"), encoding="utf-8"))
    env = np.load(a.env or os.path.join(E, "analysis", "camera_env.npy"))
    quiet = cuts["params"]["voice_thr_db"] + a.over
    wav = a.wav or os.path.join(E, "analysis", "asr", "_work", "camera.wav")
    keep, tl0 = [], cuts.get("highlight_external_frames", 0)
    for f0, f1 in cuts["keep_frames"]:
        keep.append((f0 / FPS, f1 / FPS, tl0 / FPS))
        tl0 += f1 - f0
    ks = sorted(keep)
    kstart = [k[0] for k in ks]

    def kept(s, e):
        """素材の [s, e) のうち残している割合と、頭のタイムラインの秒"""
        if e <= s:
            return 0.0, None
        i = max(0, bisect.bisect_right(kstart, s) - 1)
        tot, first = 0.0, None
        for k0, k1, t in ks[i:]:
            if k0 >= e:
                break
            lo, hi = max(s, k0), min(e, k1)
            if hi > lo:
                tot += hi - lo
                if first is None:
                    first = t + (lo - k0)
        return tot / (e - s), first

    audio = read_wav(wav)
    starts = sorted({st for k0, k1, _ in ks for st in range((int(k0) // CHUNK) * CHUNK, int(k1) + 1, CHUNK)
                     if st * 16000 < len(audio)})
    segs = transcribe(audio, starts, os.path.join(E, "analysis", "asr", "_work"))
    hits = find(chars(segs))
    cut, keep_h = [], []
    for h in hits:
        r, tl = kept(h["s"], h["e"])
        if r < 0.5:
            continue                          # もう切ってある
        h["tl"] = tl
        pk = kept(h["prev"][0], h["prev"][1] + 0.02)[0] >= 0.5 if h["prev"] else False
        nk = kept(h["next"][0] - 0.02, h["next"][1])[0] >= 0.5 if h["next"] else False
        h["edge"] = not (pk and nk)
        why = None
        if h["kind"] in ("言いよどみ", "あのー"):
            why = "言いよどみ"
        elif h["kind"] == "あの" and (h["head"] or h["edge"]):
            why = "「あの」（文の頭）" if h["head"] else "「あの」（つなぎ目）"
            why += "：三上さんの時は切る"
        elif h["kind"] in ("やっぱ", "まあ") and h["edge"]:
            why = f"つなぎ目に接する「{h['word']}」"
        elif h.get("repeat"):
            why = f"重なりの前の方（{h['word']} {h['word']}）"
        if why:
            # 切る区間：前の声の終わりの谷 → 次の声の頭の谷（素材の秒）
            v0 = valley(env, h["s"] - 0.12, h["s"] + 0.04, quiet)
            v1 = valley(env, h["e"] - 0.04, h["e"] + 0.15, quiet)
            h["cut"] = (v0, v1) if (v0 is not None and v1 is not None and v1 - v0 >= 0.06) else None
            cut.append((h, why))
        else:
            keep_h.append(h)

    out = a.out or os.path.join(V, "_work", f"fillers_{tag}")
    counts = {}
    for h in keep_h:
        counts[h["kind"]] = counts.get(h["kind"], 0) + 1
    ok = [x for x in cut if x[0]["cut"]]
    L = [f"文字起こし：{E}/analysis/asr/_work/filler_*.json（フィラーも書き起こす設定。残している所にかかる2分ずつ。時刻は ±0.1秒ほど粗い）。"
         f"谷＝{os.path.basename(a.env or 'camera_env.npy')} が {quiet:.1f}dB（声のしきい値＋{a.over:.0f}dB）以下。**全部未聴取**", "",
         f"- 声も切る候補：{len(cut)}件（谷あり {len(ok)}・谷なし {len(cut) - len(ok)}）",
         "- 声は残す：" + ("・".join(f"{k} {v}" for k, v in sorted(counts.items(), key=lambda x: -x[1])) or "0件"), "",
         "決めること：一覧を全部読み、切る物を cuts_plan の EXTRA_CUTS に理由つきで写す。言いかけ・言い直しの一部なら、言い直しとして前ごと切る（08 の remove）。"
         "「あの」は三上さんの時だけ（ほかの人は読んで決める）。谷なしは声を切らない（字幕から抜くだけ）", "",
         "## 声も切る候補", "", "| 版の時刻 | 素材の秒 | 種類 | 前【語】後 | 切る区間（素材の秒） | 理由 |", "|---|---|---|---|---|---|"]
    def span(h):
        return f"{h['cut'][0]:.2f}〜{h['cut'][1]:.2f}" if h["cut"] else "谷なし"
    L += [f"| {ff(h['tl'])} | {h['s']:.2f} | {h['kind']} | {h['before']}【{h['word']}】{h['after']} | {span(h)} | {why} |"
          for h, why in cut]
    L += ["", "## EXTRA_CUTS に写す行（谷ありだけ。読んで決めた物だけ写す）", "", "```"]
    L += [f'    ({h["cut"][0]:.2f}, {h["cut"][1]:.2f}, "フィラー（{why}）：…{h["before"][-8:]}【{h["word"]}】{h["after"][:8]}…"),' for h, why in ok]
    L += ["```"]
    if a.all:
        L += ["", "## 声は残す", "", "| 版の時刻 | 素材の秒 | 種類 | 前【語】後 | 文の頭 | つなぎ目 |", "|---|---|---|---|---|---|"]
        L += [f"| {ff(h['tl'])} | {h['s']:.2f} | {h['kind']} | {h['before']}【{h['word']}】{h['after']} | {'頭' if h['head'] else ''} | {'つなぎ目' if h['edge'] else ''} |"
              for h in keep_h]
    rows = [("声も切る", ff(h["tl"]), h["s"], h["kind"], h["word"], h["before"], h["after"],
             f"{h['cut'][0]:.2f}-{h['cut'][1]:.2f}" if h["cut"] else "谷なし", why) for h, why in cut] + \
           [("声は残す", ff(h["tl"]), h["s"], h["kind"], h["word"], h["before"], h["after"], "", "") for h in keep_h]
    write(out, f"# 残している所のフィラー（{tag}）", L, rows)
    print(f"声も切る候補 {len(cut)}件（谷あり {len(ok)}・谷なし {len(cut) - len(ok)}）・声は残す {len(keep_h)}件 → {out}.md")


if __name__ == "__main__":
    main()
