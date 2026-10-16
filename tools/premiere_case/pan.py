#!/usr/bin/env python3
"""本編の締めのつなぎ目（「ということで今回は」の頭）に、Premiere Composer の「Pan [Left]」を付ける（02 の transitions.closing_pan。毎回付ける）。
どの案件でも使える道具。元：1015claude project開設 v007 の _work/apply_pan.py（2026-10-16 小川さん「『ということで今回は』に Premiere Composer の中の
『パン』でトランジション（左右どちらでも）」「これは毎回」）。

  python3 tools/premiere_case/pan.py --proj "<版>/<案件>_vNNN.prproj" --seq <シーケンス名> --at <つなぎ目の秒> [--dry]

- --at はタイムラインの秒（「ということで今回は」の字幕の頭を含む残す区間の頭＝カットの切れ目）。29.97fps のコマにそろえて送る
- 前に：Premiere で Composer のパネルを一度開く（関数が読み込まれる）。このプロジェクトは閉じておく（開いていたら何もしない。close.py で閉じる）
- 開いて付けて保存し、閉じて、前面をユーザーが見ていたものに戻す。組み立て（make）をやり直したら、もう一度。make の後・検査の前に
- Composer の元のファイル（.mhpctransition）を <版>/_work/composer/Pan Left.prproj に写して使う（Composer のファイルには触らない）
- Premiere を使う前と後にチャットで知らせる（CLAUDE.md）。Composer の無い Mac では止まるので、付けずに報告で知らせる
"""
import argparse
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

COMPOSER = os.path.expanduser("~/Library/Application Support/MisterHorse/ProductManager/Products/3283/Items/Starter Pack/(3) Transitions")
PAN_LEFT = "(1) Pan [$Left].mhpctransition"
FPS = 30000 / 1001
TICKS_PER_FRAME = 8475667200      # 254016000000 × 1001 / 30000


def main():
    ap = argparse.ArgumentParser(description="締めのつなぎ目に Premiere Composer の Pan [Left] を付ける", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--proj", required=True)
    ap.add_argument("--seq", required=True)
    ap.add_argument("--at", type=float, required=True, help="つなぎ目（タイムラインの秒）")
    ap.add_argument("--dry", action="store_true", help="送らない（埋めた ExtendScript の頭を出す）")
    ap.add_argument("--skip-font-check", action="store_true")
    a = ap.parse_args()
    proj = C.need_file(a.proj)
    src = os.path.join(COMPOSER, PAN_LEFT)
    if not os.path.exists(src):
        raise SystemExit(f"Composer の Pan [Left] が無い（この Mac に Composer が無い？）：{src}")
    dst_dir = os.path.join(os.path.dirname(proj), "_work", "composer")
    dst = os.path.join(dst_dir, "Pan Left.prproj")
    frame = round(a.at * FPS)
    sec = frame / FPS
    print(f"つなぎ目 {frame}コマ＝{sec:.3f}秒（{int(sec // 60)}:{sec % 60:06.3f}）")
    js = C.script("pan.jsx", {"__PROJ__": proj, "__SEQ__": a.seq, "__FILE__": dst,
                              "__TICKS__": str(frame * TICKS_PER_FRAME), "__SEC__": round(sec, 3)})
    if a.dry:
        print(js[-1200:])
        print("（--dry：送らない・写さない）")
        return
    if not os.path.exists(dst):
        os.makedirs(dst_dir, exist_ok=True)
        shutil.copyfile(src, dst)
    if not a.skip_font_check:
        C.font_check(proj)
    b = C.bridge()
    print(b.preflight())
    print(b.run(js, timeout=600))


if __name__ == "__main__":
    main()
