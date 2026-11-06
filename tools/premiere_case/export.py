#!/usr/bin/env python3
"""案件のシーケンスを Media Encoder で mp4（YouTube 1080p HD）に書き出す（Premiere は固まらない。前面のプロジェクトは戻す。保存しない。
どの案件でも使える道具）。書き出しが終わったかは Media Encoder の画面か、出力のファイルの大きさが止まったかで見る。
元：環境設定 v004 の _work/export.py ＋ export_ame_v004.jsx。

  python3 tools/premiere_case/export.py --proj <版>/<案件>_vNNN.prproj --seq <シーケンス名> [--light] [--out <版>/<案件>_vNNN.mp4] [--preset <.epr>] [--dry]
  --light：途中の版の確認用（720p・平均 2Mbps・瞬間の上限 8Mbps・音 192kbps。35分で約0.5GB）。出力の名前は …_light.mp4 になり、tools/review_server.py の一覧に出る
  出力がもうあれば止まる（上書きしない）。Premiere を使う前と後にチャットで知らせる
"""
import argparse
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

PRESET_DIR = "/Applications/Adobe Premiere Pro */Adobe Premiere Pro *.app/Contents/MediaIO/systempresets/4E49434B_48323634/"
PRESET_GLOB = PRESET_DIR + "YouTube 1080p HD.epr"
LIGHT_BASE_GLOB = PRESET_DIR + "YouTube 720p HD.epr"
LIGHT_PRESET = os.path.expanduser("~/.video_edit_rules/light_720p.epr")
LIGHT_ID = "7c1f0a52-3d44-4e8b-9a61-2f6b8d10e720"
# 動きの激しい所を測って決めた値（2026-11-02 Addness bfa3aa1e-b76b-481d-a2e2-07da9739d8ca）。上限 3Mbps だと早回しで崩れる
LIGHT_PARAMS = {"ADBEVideoMinBitrate": "1.", "ADBEVideoTargetBitrate": "2.", "ADBEVideoMaxBitrate": "8.", "ADBEAudioBitrate": "192"}


def make_light_preset():
    """入っている Premiere の YouTube 720p HD の設定から、ビットレートだけ変えた設定を作る"""
    base = next(iter(sorted(glob.glob(LIGHT_BASE_GLOB), reverse=True)), None)
    if not base:
        raise SystemExit("書き出しの設定（YouTube 720p HD.epr）が見つからない。--preset で渡す")
    with open(base, encoding="utf-8", newline="") as f:
        s = f.read()
    for key, val in LIGHT_PARAMS.items():
        s, n = re.subn(rf"(<ParamIdentifier>{key}</ParamIdentifier>.*?<ParamValue>).*?(</ParamValue>)",
                       lambda m: m.group(1) + val + m.group(2), s, count=1, flags=re.S)
        if n != 1:
            raise SystemExit(f"{base} に {key} が無い（Premiere の版で変わった？）")
    s = re.sub(r"<PresetID>.*?</PresetID>", f"<PresetID>{LIGHT_ID}</PresetID>", s, count=1)
    s = re.sub(r"<PresetName>.*?</PresetName>", "<PresetName>途中の確認 720p</PresetName>", s, count=1)
    s = re.sub(r"<PresetComments>.*?</PresetComments>", "<PresetComments></PresetComments>", s, count=1)
    os.makedirs(os.path.dirname(LIGHT_PRESET), exist_ok=True)
    with open(LIGHT_PRESET, "w", encoding="utf-8", newline="") as f:
        f.write(s)
    return LIGHT_PRESET


def cut_list_gate(proj, skip):
    """渡す前の止め方（08 の cut.before_handing）：tools/check_cut_list.py の「止める」検査（切れ端・音のブツッ）が残っている版は書き出さない。
    知らせる検査の未処理は数を出して書き出す（2026-11-06）。AI のカット（_work/cuts_vNNN.json）が無い版は見ない"""
    V = os.path.dirname(proj)
    tag = os.path.basename(V)
    cuts = os.path.join(V, "_work", f"cuts_{tag}.json")
    if not os.path.exists(cuts):
        return
    if skip:
        print(f"カットの検査の一覧を見ずに書き出す：{skip}")
        return
    rec_p = os.path.join(V, "_work", f"cut_list_{tag}.json")
    rec = json.load(open(rec_p, encoding="utf-8")) if os.path.exists(rec_p) else None
    if not rec:
        why = "まだ動かしていない"
    elif rec.get("cuts_mtime", 0) < os.path.getmtime(cuts):
        why = "カットを組み直した後に動かしていない"
    elif rec.get("stage") != "all":
        why = "組み立ての前の結果しか無い（--before-build を付けずに動かす）"
    elif not rec.get("ok"):
        why = f"止める検査の未処理 {rec.get('unresolved_stop', rec.get('unresolved'))}・動かしていない止める検査 {rec.get('not_run_stop', rec.get('not_run'))}"
    else:
        n_ = rec.get("unresolved", 0) - rec.get("unresolved_stop", 0)
        if n_:
            print(f"カットの検査の一覧：知らせる未処理 {n_}（確認_{tag}.md の「不足」に書いて渡す）")
        return
    raise SystemExit(f"カットの検査の一覧が通っていないので書き出さない：{why}\n"
                     f"  ~/Desktop/video_edit_rules/env/bin/python tools/check_cut_list.py --ver \"{V}\"\n"
                     "  小川さんの手のカットの版など、この一覧が当てはまらない時だけ --skip-cut-list \"理由\"")


def main():
    ap = argparse.ArgumentParser(description="Media Encoder で mp4 に書き出す")
    ap.add_argument("--proj", required=True)
    ap.add_argument("--seq", required=True)
    ap.add_argument("--out", help="出力の mp4（既定 .prproj と同じ場所・同じ名前の .mp4）")
    ap.add_argument("--preset", help="書き出しの設定（.epr。既定 Premiere の YouTube 1080p HD）")
    ap.add_argument("--light", action="store_true", help="途中の版の確認用に軽く書き出す（720p・平均 2Mbps）")
    ap.add_argument("--skip-font-check", action="store_true")
    ap.add_argument("--skip-cut-list", metavar="理由", help="カットの検査の一覧を見ずに書き出す（小川さんの手のカットの版など。理由を書く）")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    if a.light and a.preset:
        raise SystemExit("--light と --preset は一緒に使わない")
    proj = C.need_file(a.proj)
    cut_list_gate(proj, a.skip_cut_list)
    out = os.path.abspath(a.out or os.path.splitext(proj)[0] + ".mp4")
    if a.light and not out.endswith("_light.mp4"):
        out = os.path.splitext(out)[0] + "_light.mp4"
    if os.path.exists(out):
        raise SystemExit(f"{out} がもうある（上書きしない）")
    preset = make_light_preset() if a.light else a.preset or next(iter(sorted(glob.glob(PRESET_GLOB), reverse=True)), None)
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
