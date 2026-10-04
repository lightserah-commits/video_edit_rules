#!/usr/bin/env python3
"""案件のシーケンスを Media Encoder で mp4（YouTube 1080p HD）に書き出す（Premiere は固まらない。前面のプロジェクトは戻す。保存しない。
どの案件でも使える道具）。書き出しが終わったかは Media Encoder の画面か、出力のファイルの大きさが止まったかで見る。
元：環境設定 v004 の _work/export.py ＋ export_ame_v004.jsx。

  python3 tools/premiere_case/export.py --proj <版>/<案件>_vNNN.prproj --seq <シーケンス名> [--out <版>/<案件>_vNNN.mp4] [--preset <.epr>] [--dry]
  出力がもうあれば止まる（上書きしない）。Premiere を使う前と後にチャットで知らせる
"""
import argparse
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

PRESET_GLOB = "/Applications/Adobe Premiere Pro */Adobe Premiere Pro *.app/Contents/MediaIO/systempresets/4E49434B_48323634/YouTube 1080p HD.epr"


def main():
    ap = argparse.ArgumentParser(description="Media Encoder で mp4 に書き出す")
    ap.add_argument("--proj", required=True)
    ap.add_argument("--seq", required=True)
    ap.add_argument("--out", help="出力の mp4（既定 .prproj と同じ場所・同じ名前の .mp4）")
    ap.add_argument("--preset", help="書き出しの設定（.epr。既定 Premiere の YouTube 1080p HD）")
    ap.add_argument("--skip-font-check", action="store_true")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    proj = C.need_file(a.proj)
    out = os.path.abspath(a.out or os.path.splitext(proj)[0] + ".mp4")
    if os.path.exists(out):
        raise SystemExit(f"{out} がもうある（上書きしない）")
    preset = a.preset or next(iter(sorted(glob.glob(PRESET_GLOB), reverse=True)), None)
    if not preset or not os.path.exists(preset):
        raise SystemExit("書き出しの設定（YouTube 1080p HD.epr）が見つからない。--preset で渡す")
    js = C.script("export_ame.jsx", {"__PROJ__": proj, "__SEQ__": a.seq, "__OUT__": out, "__PRESET__": preset})
    print(f"{a.seq} → {out}（{os.path.basename(preset)}）")
    if a.dry:
        print("（--dry：送らない）")
        return
    if not a.skip_font_check:
        C.font_check(proj)
    b = C.bridge()
    print(b.preflight())
    print(b.run(js, timeout=600))


if __name__ == "__main__":
    main()
