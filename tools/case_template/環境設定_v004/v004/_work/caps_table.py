"""装飾係が読む字幕の一覧（タイムラインの順）：ID|v001の時刻|長さ|カメラの時刻|話者|字幕（／は改行）|前のつなぎ目
  前のつなぎ目：この字幕の前で素材が飛んでいれば「✂切った秒」、並べ替えの頭なら「⇄並べ替え」
  出力 _work/caps_table.tsv と、塊ごとの _work/caps_chunkN.tsv（台本の塊と同じ区切りの範囲）
  python3 v004/_work/caps_table.py"""
import bisect, json, os
HERE = os.path.dirname(os.path.abspath(__file__))
FPS = 30000 / 1001
cj = json.load(open(os.path.join(HERE, "cuts_v004.json")))
capj = json.load(open(os.path.join(HERE, "captions_v004.json")))
caps = [c for c in capj["captions"] if c["mode"] != "drop" and "src" in c]
ctl = cj["caption_tl"]
order = sorted(caps, key=lambda c: ctl[c["id"]])
total = cj["total_frames"]
keep = cj["keep_frames"]
seg_tl, t = [], sum(b - a for a, b in cj["highlight_frames"]) + cj.get("highlight_external_frames", 0)
for a, b in keep:
    seg_tl.append((t, a, b))
    t += b - a
starts = [s[0] for s in seg_tl]
reorder_heads = {v[0] for v in cj.get("reorder", {}).values() if isinstance(v, list)}


def mmss(f):
    s = f / FPS
    return f"{int(s // 60)}:{s % 60:04.1f}"


def join_before(f0, f1):
    """タイムラインのフレーム f0〜f1 の間に素材の飛びがあるか"""
    out = []
    i = bisect.bisect_right(starts, f0)
    while i < len(seg_tl) and seg_tl[i][0] <= f1:
        t0, a, b = seg_tl[i]
        pa, pb = seg_tl[i - 1][1], seg_tl[i - 1][2]
        if a in reorder_heads:
            out.append("⇄並べ替え")
        elif a != pb:
            out.append(f"✂{(a - pb) / FPS:.1f}")
        i += 1
    return " ".join(out)


BOUNDS = [0, 205, 344, 509, 700, 860, 1013, 1195, 1430, 1622, 10 ** 9]
lines = []
for k, c in enumerate(order):
    s = ctl[c["id"]]
    e = ctl[order[k + 1]["id"]] if k + 1 < len(order) else total
    pj = join_before(ctl[order[k - 1]["id"]], s) if k else ""
    who = "田" if c.get("guest") else c["who"]
    lines.append((c["u"], f"{c['id']}|{mmss(s)}|{(e - s) / FPS:.1f}|{int(c['src'] // 60)}:{c['src'] % 60:04.1f}|{who}|{c['text'].replace(chr(13), '／')}|{pj}"))
hdr = "ID|v001の時刻|長さ(秒)|カメラの時刻|話者(み=三上・聞=創太くん・田=田中さん)|字幕|この字幕の前のつなぎ目（✂切った秒・⇄並べ替え）\n"
open(os.path.join(HERE, "caps_table.tsv"), "w").write(hdr + "\n".join(l for _, l in lines) + "\n")
for n in range(1, 11):
    sel = [l for u, l in lines if BOUNDS[n - 1] <= u < BOUNDS[n]]
    open(os.path.join(HERE, f"caps_chunk{n}.tsv"), "w").write(hdr + "\n".join(sel) + "\n")
    print(n, len(sel), sel[0].split("|")[1] if sel else "", sel[-1].split("|")[1] if sel else "")
