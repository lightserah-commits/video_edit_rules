#!/usr/bin/env python3
"""確認の画像を、直した所だけに絞って選ぶ（全部の確認の画像の代わりに、最後の直しの後に。どの案件でも使える道具）。
組み立ての記録（<版>/vNNN_記録.json）から、画像・動く図解・ズーム（理由に --zoom-why の言葉があるもの）・画面の頭を前に出した所・
置かなかった右上タイトル・赤枠（--frames-every つに1つ）の時刻を拾い、finish.py の jobs にする。
元：環境設定 v004 の _work/review_jobs_last.py（小川さんの顔まね・9:48 のつなぎ・画像 15か所・図解 7つ・赤枠の3つに1つ）。

  python3 tools/premiere_case/review_jobs_fixed.py --record <版>/vNNN_記録.json --out <版>/_work/review_jobs_fixed.json \\
      [--zoom-why 顔まね] [--frames-every 3] [--only images,diagrams,zooms,screen_lead,titles_dropped,frames]
  python3 tools/premiere_case/finish.py --proj … --seq … --jobs <版>/_work/review_jobs_fixed.json
  記録の形（環境設定 v004 の make が書くもの）：images・anim_diagrams [{key, start, end}]（秒）・zooms [{start, end, why}]・
  screen_lead [{at, was}]・titles_dropped [{start, end}]・frames [{start, from}]。無いものは飛ばす
  画像の名前：<分2桁><秒2桁>_<種類>（例 1636_小川さん顔まね_寄り）。タイムコードは 30 で数える（Premiere の exportFramePNG に渡す形）
"""
import argparse
import json
import os

FPS = 30000 / 1001
KINDS = ["images", "diagrams", "zooms", "screen_lead", "titles_dropped", "frames"]


def main():
    ap = argparse.ArgumentParser(description="直した所だけの確認の画像の一覧（finish.py の jobs）を作る")
    ap.add_argument("--record", required=True, help="組み立ての記録 vNNN_記録.json")
    ap.add_argument("--out", required=True, help="書き出す jobs の JSON")
    ap.add_argument("--zoom-why", action="append", default=None, help="拾うズームの理由の言葉（何回でも。既定 顔まね）")
    ap.add_argument("--frames-every", type=int, default=3, help="赤枠をいくつに1つ見るか（既定 3。0 で見ない）")
    ap.add_argument("--only", help=f"拾う種類（既定 全部：{','.join(KINDS)}）")
    a = ap.parse_args()
    rec = json.load(open(a.record, encoding="utf-8"))
    only = set(a.only.split(",")) if a.only else set(KINDS)
    whys = a.zoom_why or ["顔まね"]
    jobs = []

    def add(sec, name):
        f = int(round(sec * FPS))
        m, s = int(sec // 60), sec % 60
        jobs.append([f"{f // 108000:02d}:{f // 1800 % 60:02d}:{f // 30 % 60:02d}:{f % 30:02d}", f"{m:02d}{int(s):02d}_{name}", round(sec, 2)])

    if "images" in only:
        for im in rec.get("images", []):                          # 画像（I*・L*）：出だし・真ん中・終わり
            x, y = im["start"], im["end"]
            for t, w in ((x + 0.4, "出だし"), ((x + y) / 2, "途中"), (y - 0.2, "終わり")):
                add(t, f"画像{im['key']}_{w}")
    if "diagrams" in only:
        for d in rec.get("anim_diagrams", []):                    # 動く図解：直前・頭・直後
            add(d["start"] - 0.15, f"図解{d['key']}_直前")
            add(d["start"] + 0.1, f"図解{d['key']}_頭")
            add(d["end"] + 0.1, f"図解{d['key']}_直後")
    if "zooms" in only:
        for z in rec.get("zooms", []):                            # 理由に言葉のあるズーム：前・寄り・終わり・後
            hit = next((w for w in whys if w in str(z.get("why", ""))), None)
            if hit:
                add(z["start"] - 0.3, f"{hit}_前")
                add(z["start"] + 0.3, f"{hit}_寄り")
                add(z["end"] - 0.1, f"{hit}_終わり")
                add(z["end"] + 0.3, f"{hit}_後")
    if "screen_lead" in only:
        for x in rec.get("screen_lead", []):                      # 画面をカットから出した所
            add(x["at"] + 0.05, "画面の頭を前へ_頭")
            add(x["was"] + 0.1, "画面の頭を前へ_元の頭")
    if "titles_dropped" in only:
        for t in rec.get("titles_dropped", []):                   # 置かなかった右上タイトル
            add((t["start"] + t["end"]) / 2, "右上タイトルを置かない")
    if "frames" in only and a.frames_every > 0:
        for fr in rec.get("frames", [])[::a.frames_every]:        # 赤枠
            add(fr["start"] + 0.3, f"赤枠_{str(fr.get('from', '')).replace('+', 'p')}")
    seen, out = set(), []
    for j in sorted(jobs, key=lambda x: x[2]):
        if j[0] not in seen:
            seen.add(j[0])
            out.append(j)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print("確認の画像", len(out), "→", a.out)


if __name__ == "__main__":
    main()
