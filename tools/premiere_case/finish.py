#!/usr/bin/env python3
"""確認の画像を Premiere で書き出す（工程10。どの案件でも使える道具）。案件のプロジェクトを開き（開いていなければ）、jobs の時刻の画像を書き出し、
前面はユーザーが見ていたプロジェクト・シーケンスに戻す。案件のプロジェクトは開いたまま。
--dissolve を付けた時だけ、右上のタイトル（V8・V9）の最初のクリップの頭にクロスディゾルブを付けて**保存する**（AI の案件のプロジェクトだけに使う）。
元：環境設定 v004 の _work/finish.py ＋ finish_v004.jsx。

  python3 tools/premiere_case/finish.py --proj <版>/<案件>_vNNN.prproj --seq <シーケンス名> --jobs <jobs.json> [--out-dir <版>/確認]
      [--dissolve 15 --title-tracks V8,V9] [--wait 20000] [--dry]
  jobs.json：[[タイムコード, 名前, 秒（省いてよい）], …]（review_jobs_fixed.py の出力と同じ形）。画像は <out-dir>/<名前>.png
  Premiere を使う前と後にチャットで知らせる。開く前に無いフォントが0件か確かめる（--skip-font-check で飛ばす）
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="確認の画像を Premiere で書き出す")
    ap.add_argument("--proj", required=True)
    ap.add_argument("--seq", required=True)
    ap.add_argument("--jobs", required=True, help="[[タイムコード, 名前, 秒], …] の JSON")
    ap.add_argument("--out-dir", help="画像の置き場所（既定 .prproj と同じフォルダの 確認/）")
    ap.add_argument("--dissolve", type=int, default=0, help="右上タイトルの頭に付けるディゾルブのコマ数（0＝付けない・保存しない。既定 0）")
    ap.add_argument("--title-tracks", default="V8,V9", help="ディゾルブを付けるトラック（既定 V8,V9）")
    ap.add_argument("--wait", type=int, default=20000, help="書き出しの前に待つミリ秒（画像・動画の読み込み待ち。既定 20000）")
    ap.add_argument("--timeout", type=int, default=1500)
    ap.add_argument("--skip-font-check", action="store_true")
    ap.add_argument("--dry", action="store_true", help="Premiere に送らず、送る中身の要約だけ出す")
    a = ap.parse_args()
    proj = C.need_file(a.proj)
    out_dir = os.path.abspath(a.out_dir or os.path.join(os.path.dirname(proj), "確認"))
    os.makedirs(out_dir, exist_ok=True)
    rows = json.load(open(a.jobs, encoding="utf-8"))
    jobs = [[r[0], os.path.join(out_dir, r[1] if r[1].endswith(".png") else r[1] + ".png")] for r in rows]
    tracks = [int(t.strip().lstrip("Vv")) - 1 for t in a.title_tracks.split(",") if t.strip()]
    js = C.script("finish.jsx", {"__PROJ__": proj, "__SEQ__": a.seq, "__JOBS__": jobs, "__WAIT__": a.wait,
                                 "__DISSOLVE__": a.dissolve, "__TITLE_TRACKS__": tracks})
    print(f"確認の画像 {len(jobs)} 枚 → {out_dir}。ディゾルブ {a.dissolve}コマ{'（保存する）' if a.dissolve else '（付けない・保存しない）'}")
    if a.dry:
        print(f"（--dry：送らない。スクリプト {len(js)} 字）")
        return
    if not a.skip_font_check:
        C.font_check(proj)
    b = C.bridge()
    print(b.preflight())
    print(b.run(js, timeout=a.timeout))


if __name__ == "__main__":
    main()
