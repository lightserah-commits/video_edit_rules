#!/usr/bin/env python3
"""視聴者が見る順に、字幕・問い・強調・図解・説明の文字と、カットで素材が飛んだ所を並べた一覧を作る（読むだけ）。
「偏差値40の人が考えずに見て分かるか」（動画の土台.md の3）・前後がつながるか・迷い／言いかけ／くり返しが残っていないかを、頭から読んで確かめる材料。

使い方:
  python3 tools/flow_table.py 版.prproj --seq シーケンス名 [--label V6=字幕 --label V7=強調 ...] [--from 0 --to 780] [--out flow.txt]
    --label   段の名前（無ければ、文字のある段を全部「V7」のように段の名前で出す。02 の output_tracks に合わせて付けると読みやすい）
    --from/--to  読む範囲（秒）。冒頭13分を先に読む時など
出力の行: 「時刻 【段の名前】文字」。字幕の段（--label で「字幕」と付けた段）は字下げする。
  カットの所は「✂ 素材を n.nn秒 飛ばした（前へ戻った）」。中身は字幕で読む（切った中身は カット一覧 で）
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dump_timeline import dump  # noqa: E402

TPS = 254016000000


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("prproj"); ap.add_argument("--seq", required=True)
    ap.add_argument("--label", action="append", default=[]); ap.add_argument("--from", dest="t0", type=float, default=0)
    ap.add_argument("--to", dest="t1", type=float, default=1e9); ap.add_argument("--out")
    a = ap.parse_args()
    tl = dump(a.prproj, a.seq); fps = tl["fps"]
    labels = dict(x.split("=", 1) for x in a.label)
    ev = []
    for tr, rows in tl["tracks"].items():
        if not tr.startswith("V") or (labels and tr not in labels):
            continue
        lab = labels.get(tr, tr)
        for r in rows:
            t = "／".join(x.replace("\r", "／") for x in (r.get("texts") or []) if x.strip())
            if r["muted"] or not t:
                continue
            s = r["start_f"] / fps
            ev.append((s, 1 if lab == "字幕" else 0, f"  {t}" if lab == "字幕" else f"【{lab}】{t}"))
    # カット：A1 の隣り合うクリップで、素材の時刻が飛んでいる所
    a1 = sorted([r for r in tl["tracks"].get("A1", []) if not r["muted"] and r["in_ticks"] is not None], key=lambda r: r["start_f"])
    for p, q in zip(a1, a1[1:]):
        if p["name"] != q["name"] or q["start_f"] != p["end_f"]:
            continue
        gap = q["in_ticks"] / TPS - (p["in_ticks"] / TPS + (p["end_f"] - p["start_f"]) / fps)
        if abs(gap) >= .2:
            ev.append((q["start_f"] / fps, 2, f"    ✂ 素材を {gap:.2f}秒 飛ばした" if gap > 0 else f"    ✂ 素材の {-gap:.2f}秒 前へ戻った"))
    ev.sort(key=lambda x: (x[0], x[1]))
    lines = [f"{int(t // 60):02d}:{t % 60:05.2f} {s}" for t, k, s in ev if a.t0 <= t <= a.t1]
    out = "\n".join(lines)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(out + "\n"); print(f"{a.out}：{len(lines)}行", file=sys.stderr)
    else:
        print(out)


if __name__ == "__main__":
    main()
