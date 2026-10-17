"""笑い声・言葉の途中の間の候補を探す（08 の cut.pauses.laugh_gaps）。どの案件でも使える道具。
元：セキュリティについて v004 の _work/find_laugh_gaps.py（2026-10-17 小川さん「カットが全体的に浅い」「笑い声のとき画面変化がないのが冗長」）。

残している区間（<版>/_work/cuts_vNNN.json の keep_frames）の中で、文字起こし（analysis/asr/ の語の時刻。2つ以上あるとよい）の
どれにも言葉が無い 0.5秒以上の所を探し、切る候補（EXTRA_CUTS の形＝素材の秒）にして一覧にする。
切る点は、言葉の終わり＋0.04秒・次の言葉の頭−0.06秒の近くの大きさの谷（10ms ごとの声の大きさ analysis/camera_env.npy）。
音がある（声の境目より大きい所が半分以上）＝笑い声・息・相づちの見込み。

  ~/Desktop/video_edit_rules/env/bin/python tools/find_laugh_gaps.py --ver "<edit/vNNN>" [--asr asr_a.json asr_b.json] [--min 0.5]

決めるのは人（AI）：溜め（keep_as_tame）・顔や手で演じている所（keep_face。コマを見る）・オチの後（after_punchline）・問いの札を読む間・
図解の区間の中（図解の動きは声に合わせてあるので切らない）は残すか短く残す。谷が無く音が次の言葉までつながる所は切らない（no_chop）。
決めた物は cuts_plan の EXTRA_CUTS に理由つきで書き、元から組み直す。
"""
import argparse, glob, json, os
import numpy as np

FPS = 30000 / 1001


def words(path):
    a = json.load(open(path))
    segs = a["segments"] if isinstance(a, dict) and "segments" in a else a
    if not isinstance(segs, list):
        return []
    return [(w["start"], w["end"]) for s in segs if isinstance(s, dict) for w in s.get("words", []) or []
            if "start" in w and "end" in w]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ver", required=True, help="版のフォルダ edit/vNNN")
    ap.add_argument("--asr", nargs="*", help="analysis/asr/ の中の語の時刻つきの文字起こし（省略で asr_*.json の全部）")
    ap.add_argument("--env", help="10ms ごとの声の大きさ（省略で analysis/camera_env.npy）")
    ap.add_argument("--min", type=float, default=0.5, help="この秒以上の言葉の無い所を出す（既定 0.5）")
    a = ap.parse_args()
    V = os.path.abspath(os.path.expanduser(a.ver))
    tag = os.path.basename(V)
    A = os.path.join(os.path.dirname(V), "analysis")
    cuts = json.load(open(os.path.join(V, "_work", f"cuts_{tag}.json")))
    caps = json.load(open(os.path.join(V, "_work", f"captions_{tag}.json")))["captions"]
    env = np.load(a.env or os.path.join(A, "camera_env.npy"))
    thr = cuts["params"]["voice_thr_db"]
    asr_files = [os.path.join(A, "asr", f) for f in a.asr] if a.asr else sorted(glob.glob(os.path.join(A, "asr", "asr_*.json")))
    spoken = np.zeros(len(env) + 200, bool)
    used = []
    for fn in asr_files:
        ws = words(fn)
        if not ws:
            continue
        used.append(os.path.basename(fn))
        for s, e in ws:
            spoken[int(s * 100):int(e * 100) + 1] = True
    shown = sorted([c for c in caps if "src" in c], key=lambda c: c["src"])

    def cap_at(t):
        cur = None
        for c in shown:
            if c["src"] <= t:
                cur = c
            else:
                break
        return cur

    def valley(t, lo, hi):
        i0, i1 = int(max(lo, t - 0.1) * 100), int(min(hi, t + 0.1) * 100)
        return t if i1 <= i0 else (i0 + int(np.argmin(env[i0:i1]))) / 100

    tl = cuts.get("highlight_external_frames", 0) / FPS
    rows = []
    for f0, f1 in cuts["keep_frames"]:
        s, e = f0 / FPS, f1 / FPS
        i0, i1 = int(s * 100), int(e * 100)
        m = ~spoken[i0:i1]
        i = 0
        while i < len(m):
            if not m[i]:
                i += 1
                continue
            j = i
            while j < len(m) and m[j]:
                j += 1
            g0, g1 = s + i / 100, s + j / 100
            if g1 - g0 >= a.min:
                loud = float(np.mean(env[i0 + i:i0 + j] >= thr))
                c0 = valley(g0 + 0.04, g0, g1)
                c1 = valley(g1 - 0.06, c0 + 0.2, g1)
                edge = "区間の頭" if i == 0 else ("区間の終わり" if j == len(m) else "")
                cap = cap_at(g0)
                rows.append((tl + i / 100, g1 - g0, g0, g1, c0, c1, loud, edge, cap["id"] if cap else "",
                             (cap["text"] if cap else "").replace("\r", "／")))
            i = j
        tl += e - s

    def mmss(t):
        return f"{int(t // 60)}:{t % 60:04.1f}"

    out = os.path.join(V, "_work", f"laugh_gaps_{tag}.tsv")
    with open(out, "w", encoding="utf-8") as f:
        f.write(f"# 文字起こし：{'・'.join(used)}\n")
        f.write("版の時刻\t長さ\t素材の秒\t切る候補(素材)\t音がある割合\t区間の端\t字幕\t字幕の文字\n")
        for r in rows:
            f.write(f"{mmss(r[0])}\t{r[1]:.2f}\t{r[2]:.2f}-{r[3]:.2f}\t({r[4]:.2f}, {r[5]:.2f})\t{int(r[6] * 100)}%\t{r[7]}\t{r[8]}\t{r[9]}\n")
    loud = [r for r in rows if r[6] >= 0.5]
    print(f"候補 {len(rows)}（計 {sum(r[1] for r in rows):.1f}秒）・うち音がある {len(loud)}（計 {sum(r[1] for r in loud):.1f}秒）"
          f"・文字起こし {len(used)}本 → {out}")


if __name__ == "__main__":
    main()
