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
- 2026-10-17（grok bots v002）：Composer の元のファイルは、中の音（Transition Complex 14.wav）の場所が「___MH_PATH___Audio/…」という仮の書き方で、
  そのまま読み込むと Premiere が「メディアをリンク」の画面を出して止まる（人が押すまでスクリプトが返らない）。写す時に ___MH_PATH___ を
  Composer の Assets のフォルダ（Products/3283/Assets/）へ書き換える（Composer のパネルが入れる時と同じ）。毎回写し直す
- 2026-10-18（1017 v003）：--sound-gain-db -3 で、部品の音（Transition Complex 14.wav）を下げた写しを <版>/_work/composer/Audio/ に作り、
  写した部品の音の場所をそこへ向ける（1017 v002 は Pan の音だけ真のピーク −0.1 dBFS。04 の真のピーク −1 dBFS 以下）。Composer の元の音には触らない
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


def write_resolved(src, dst, gain_db=0.0):
    """Composer の .mhpctransition（gzip の prproj）を、中の仮の場所 ___MH_PATH___ を Assets のフォルダに書き換えて dst に写す"""
    import gzip
    import re
    assets = os.path.join(COMPOSER.split("/Items/")[0], "Assets") + "/"
    x = gzip.open(src).read().decode("utf-8")
    y = x.replace("___MH_PATH___", assets)
    lost = sorted({p for p in re.findall(re.escape(assets) + r'[^<>"]+', y) if not os.path.exists(p)})
    if lost:
        raise SystemExit(f"Composer の部品の音が見つからない（このまま入れると「メディアをリンク」で止まる）：{lost}")
    if gain_db:                                   # 部品の音を下げた写しへ向ける（同じ形式・同じ長さ。場所の文字だけ替える）
        import subprocess
        for p in sorted({p for p in re.findall(re.escape(assets) + r'[^<>"]+\.wav', y)}):
            q = os.path.join(os.path.dirname(dst), os.path.relpath(p, assets))
            os.makedirs(os.path.dirname(q), exist_ok=True)
            codec = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=codec_name", "-of", "csv=p=0", p],
                                   capture_output=True, text=True, check=True).stdout.strip()
            subprocess.run(["ffmpeg", "-nostats", "-loglevel", "error", "-y", "-i", p, "-af", f"volume={gain_db}dB", "-c:a", codec, "-map_metadata", "0", q], check=True)
            y = y.replace(p, q)
            print(f"部品の音を {gain_db:+.1f}dB にした写しへ向けた：{q}")
    tmp = dst + ".tmp"
    with gzip.open(tmp, "wb") as g:
        g.write(y.encode("utf-8"))
    os.replace(tmp, dst)
    print(f"Composer の部品の仮の場所を書き換えた {x.count('___MH_PATH___')}か所 → {assets}")


def main():
    ap = argparse.ArgumentParser(description="締めのつなぎ目に Premiere Composer の Pan [Left] を付ける", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--proj", required=True)
    ap.add_argument("--seq", required=True)
    ap.add_argument("--at", type=float, required=True, help="つなぎ目（タイムラインの秒）")
    ap.add_argument("--dry", action="store_true", help="送らない（埋めた ExtendScript の頭を出す）")
    ap.add_argument("--skip-font-check", action="store_true")
    ap.add_argument("--sound-gain-db", type=float, default=0.0, help="部品の音を下げる dB（例 -3。真のピークが −1 dBFS を超える時）")
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
    os.makedirs(dst_dir, exist_ok=True)
    write_resolved(src, dst, a.sound_gain_db)
    if not a.skip_font_check:
        C.font_check(proj)
    b = C.bridge()
    print(b.preflight())
    print(b.run(js, timeout=600))


if __name__ == "__main__":
    main()
