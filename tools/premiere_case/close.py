#!/usr/bin/env python3
"""Premiere で開いている案件のプロジェクトを、保存せずに閉じる（作り直す前に。ほかのプロジェクトには触らない。前面はユーザーが見ていたものに戻す）。
どの案件でも使える道具。元：環境設定 v004 の _work/close_v004.py。

ユーザー（小川さん）が Premiere で直して保存したものを、AI が閉じて作り直すと直しが消える（環境設定 v004 の 20:16 の保存）。そこで閉じる前に：
  1. .prproj の保存時刻と md5 が、AI の最後の組み立ての記録（--record で書いた <名前>.ai_build.json か --expect-md5）と同じか。違えば止まる
  2. Premiere で開いているシーケンスの、トラックごとのクリップの始まり・終わりが .prproj と同じか（保存していない直しが無いか）。違えば閉じない
     （--no-live-check で飛ばす。--seq が要る）
  止まった時は tools/diff_user_edits.py で違いを表にして、ユーザーの直しを言葉にして確かめる（CLAUDE.md・記憶「ユーザーの直しの意図を言葉に」）

  python3 tools/premiere_case/close.py --proj <版>/<案件>_vNNN.prproj --record          … 組み立ての直後に記録する（Premiere に触らない）
  python3 tools/premiere_case/close.py --proj <版>/<案件>_vNNN.prproj --seq <シーケンス名> … 確かめてから閉じる
  python3 tools/premiere_case/close.py --proj … --check-only                              … 1 だけ（Premiere に触らない）
"""
import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402


def stamp_path(proj):
    return os.path.splitext(proj)[0] + ".ai_build.json"


def file_state(proj):
    st = os.stat(proj)
    return {"md5": C.md5(proj), "mtime": st.st_mtime, "mtime_text": datetime.datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
            "size": st.st_size}


def expected_clips(proj, seq_name):
    from native_prproj import Prproj
    pj = Prproj.load(proj)
    seq = pj.sequence(seq_name)
    out = {"video": [], "audio": []}
    for name, tr in pj.tracks(seq):
        rows = sorted([str(s), str(e)] for s, e in (pj.span(it) for it in pj.items(tr)))
        rows.sort(key=lambda r: int(r[0]))
        out["video" if name.startswith("V") else "audio"].append(rows)
    return out


def main():
    ap = argparse.ArgumentParser(description="案件のプロジェクトを保存せずに閉じる（ユーザーの直しが無いか確かめてから）")
    ap.add_argument("--proj", required=True)
    ap.add_argument("--seq", help="シーケンス名（開いている所の確かめに使う）")
    ap.add_argument("--record", action="store_true", help="今の .prproj を「AI の最後の組み立て」として記録する（閉じない）")
    ap.add_argument("--expect-md5", help="記録の代わりに、AI の最後の組み立ての md5 を渡す（保存時刻は見ない）")
    ap.add_argument("--check-only", action="store_true", help="ファイルの確かめだけ（閉じない・Premiere に触らない）")
    ap.add_argument("--no-live-check", action="store_true", help="開いているシーケンスとの比べを飛ばす")
    a = ap.parse_args()
    proj = C.need_file(a.proj)
    sp = stamp_path(proj)
    now = file_state(proj)
    if a.record:
        rec = dict(now, proj=proj, recorded_at=datetime.datetime.now().isoformat(timespec="seconds"), how="tools/premiere_case/close.py --record")
        json.dump(rec, open(sp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"記録した → {sp}（md5 {now['md5']}・保存時刻 {now['mtime_text']}）")
        return
    if a.expect_md5:
        want = {"md5": a.expect_md5.strip().lower()}
    elif os.path.exists(sp):
        want = json.load(open(sp, encoding="utf-8"))
    else:
        raise SystemExit(f"AI の最後の組み立ての記録が無い（{os.path.basename(sp)}）。組み立ての直後に --record する（か --expect-md5）。閉じない")
    bad = []
    if now["md5"] != want["md5"]:
        bad.append(f"md5 が違う（今 {now['md5']}・組み立て {want['md5']}）")
    if "mtime" in want and abs(now["mtime"] - want["mtime"]) > 1.0:
        bad.append(f"保存時刻が違う（今 {now['mtime_text']}・組み立て {want.get('mtime_text')}）")
    if bad:
        raise SystemExit("止めた：" + "、".join(bad) + "。ユーザーが Premiere で保存した可能性がある。閉じない"
                         "（python3 tools/diff_user_edits.py で違いを見て、ユーザーに確かめる）")
    print(f"ファイルは AI の最後の組み立てと同じ（md5 {now['md5']}）")
    if a.check_only:
        return
    expect = None
    if not a.no_live_check:
        if not a.seq:
            raise SystemExit("--seq が要る（開いているシーケンスの確かめ。飛ばすなら --no-live-check）")
        expect = expected_clips(proj, a.seq)
    js = C.script("close.jsx", {"__PROJ__": proj, "__SEQ__": a.seq or "", "__EXPECT__": expect})
    b = C.bridge()
    res = b.run(js, timeout=300)
    print(res)
    if isinstance(res, dict) and res.get("closed") is False and res.get("diffs"):
        raise SystemExit("閉じなかった：開いているシーケンスが .prproj と違う（保存していない直しがあるかもしれない）。ユーザーに確かめる")


if __name__ == "__main__":
    main()
