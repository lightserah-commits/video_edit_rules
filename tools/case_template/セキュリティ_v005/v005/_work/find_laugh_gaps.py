"""v005（2026-10-17 小川さんの G1「カットが全体的に浅い」・G3「笑い声の間に画面が変わらない」）：
残している区間の中で、文字起こし2つ（asr_camera_p・asr_img1320）のどちらにも言葉が無い 0.5秒以上の所を探し、
切る候補（EXTRA_CUTS の形）にして _work/laugh_gaps_v005.tsv に書く。切る点は、言葉の終わり＋0.04秒・次の言葉の頭−0.06秒の近くの
大きさの谷（10ms の camera_env の一番小さい所）。音がある（声の境目より大きい所が半分以上）＝笑い声などの見込み。
  ~/Desktop/video_edit_rules/env/bin/python v005/_work/find_laugh_gaps.py
決めるのは人（メインの AI）：溜め（08 の cut.pauses keep_as_tame）・顔や手で演じている所（keep_face）・オチの後（after_punchline）は残すか短く残す。
"""
import json, os
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
V = os.path.dirname(HERE)
A = os.path.join(os.path.dirname(V), "analysis")
FPS = 30000 / 1001
MIN_GAP = 0.5


def words(fn):
    a = json.load(open(os.path.join(A, "asr", fn)))
    segs = a["segments"] if isinstance(a, dict) else a
    return [(w["start"], w["end"]) for s in segs for w in s.get("words", []) if w.get("end", 0) > w.get("start", 0) - 1]


def main():
    d = json.load(open(os.path.join(HERE, "cuts_v005.json")))
    caps = json.load(open(os.path.join(HERE, "captions_v005.json")))["captions"]
    env = np.load(os.path.join(A, "camera_env.npy"))
    thr = d["params"]["voice_thr_db"]
    spoken = np.zeros(len(env) + 200, bool)
    for fn in ("asr_camera_p.json", "asr_img1320.json"):
        for s, e in words(fn):
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
        a, b = int(max(lo, t - 0.1) * 100), int(min(hi, t + 0.1) * 100)
        if b <= a:
            return t
        k = a + int(np.argmin(env[a:b]))
        return k / 100

    tl = d["highlight_external_frames"] / FPS
    rows = []
    for a_, b_ in d["keep_frames"]:
        s, e = a_ / FPS, b_ / FPS
        A0, B0 = int(s * 100), int(e * 100)
        m = ~spoken[A0:B0]
        i = 0
        while i < len(m):
            if not m[i]:
                i += 1
                continue
            j = i
            while j < len(m) and m[j]:
                j += 1
            g0, g1 = s + i / 100, s + j / 100
            if g1 - g0 >= MIN_GAP:
                loud = float(np.mean(env[A0 + i:A0 + j] >= thr))
                c0 = valley(g0 + 0.04, g0, g1)
                c1 = valley(g1 - 0.06, c0 + 0.2, g1)
                edge = "区間の頭" if i == 0 else ("区間の終わり" if j == len(m) else "")
                cap = cap_at(g0)
                rows.append((tl + i / 100, g1 - g0, g0, g1, c0, c1, loud, edge, cap["id"] if cap else "", (cap["text"] if cap else "").replace("\r", "／")))
            i = j
        tl += e - s

    def mmss(t):
        return f"{int(t // 60)}:{t % 60:04.1f}"

    out = os.path.join(HERE, "laugh_gaps_v005.tsv")
    with open(out, "w", encoding="utf-8") as f:
        f.write("v005の時刻\t長さ\t素材の秒\t切る候補(素材)\t音がある割合\t区間の端\t字幕\t字幕の文字\n")
        for r in rows:
            f.write(f"{mmss(r[0])}\t{r[1]:.2f}\t{r[2]:.2f}-{r[3]:.2f}\t({r[4]:.2f}, {r[5]:.2f})\t{int(r[6] * 100)}%\t{r[7]}\t{r[8]}\t{r[9]}\n")
    tot = sum(r[1] for r in rows)
    loud = [r for r in rows if r[6] >= 0.5]
    print(f"候補 {len(rows)}（計 {tot:.1f}秒）・うち音がある {len(loud)}（計 {sum(r[1] for r in loud):.1f}秒）→ {out}")


if __name__ == "__main__":
    main()
