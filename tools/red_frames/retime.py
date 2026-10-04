#!/usr/bin/env python3
"""赤枠の時刻だけを今の版の土台に合わせ直す（枠の場所は決め直さない・文字認識も流さない。どの案件でも使える道具）。
カットが変わって字幕が動いた時に、前の red_frames.json をそのまま使う。place.py を流し直せるなら（batch_NN_out.json があるなら）そちらが確か。
元：環境設定 v004 の _work/retime_red_frames.py。

  python3 tools/red_frames/retime.py --frames <前の版の _work/red_frames.json> --ver <edit/vNNN> [--png-dir <PNG を置き直した所>] [--out <書き先>]
  - 枠は id_from の字幕の頭から、id_to の次の字幕の頭まで。画面を映している間だけ（place.py と同じ決め方）
  - --png-dir：PNG を写した先（省くと PNG の場所はそのまま）。PNG が無ければ止まる
  - --out を省くと <版>/_work/red_frames.json（--frames と同じファイルなら、元を red_frames_前.json に残してから書く）
"""
import argparse
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="赤枠の時刻を今の版に合わせ直す")
    ap.add_argument("--frames", required=True, help="red_frames.json（place.py の出力）")
    C.add_case_args(ap, cuts=False)
    ap.add_argument("--png-dir", help="PNG の置き場所を替える時のフォルダ")
    ap.add_argument("--out", help="書き先（省くと <版>/_work/red_frames.json）")
    a = ap.parse_args()
    C.resolve(a, need=("map", "captions"))
    mp, capj = C.load(a.map), C.load(a.captions)
    ctl = mp["caption_tl"]
    _, nxt = C.caption_order(mp, capj)
    d = C.load(a.frames)
    keep = []
    for f in d["frames"]:
        if f["id_from"] not in ctl or f["id_to"] not in nxt:
            print(f"！ 今の版に無い字幕 {f['id_from']}〜{f['id_to']}（枠を捨てた）")
            continue
        s, e = C.clip_to_screen(mp, ctl[f["id_from"]], nxt[f["id_to"]], keep=True)
        old = (f["start"] / C.FT, f["end"] / C.FT)
        f["start"], f["end"] = s * C.FT, e * C.FT
        if a.png_dir:
            f["png"] = os.path.join(a.png_dir, os.path.basename(f["png"]))
        if not os.path.exists(f["png"]):
            raise SystemExit(f"PNG が無い {f['png']}")
        keep.append(f)
        print(f"{f['id_from']}-{f['id_to']}: {C.ts(old[0])}〜{C.ts(old[1])} → {C.ts(s)}〜{C.ts(e)}  {f.get('read', '')[:24]}")
    d["frames"] = keep
    dst = a.out or (os.path.join(a.ver, "_work", "red_frames.json") if a.ver else None)
    if not dst:
        raise SystemExit("--out か --ver を渡す")
    if os.path.exists(dst) and os.path.samefile(dst, a.frames):
        shutil.copy(dst, os.path.join(os.path.dirname(dst), "red_frames_前.json"))
    json.dump(d, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"赤枠 {len(keep)} → {dst}")


if __name__ == "__main__":
    main()
