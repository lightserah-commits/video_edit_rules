#!/usr/bin/env python3
"""MTZ（安藤さんの道具。声の頭にカットとテロップを合わせる）の結果を、こちらの工程の下書きの形にする（2026-11-05）。

MTZ は ~/Downloads/MTZ（入口は mtz）。動画の横に「〈名前〉_MTZ/」を出す（完成.mp4・テロップ.srt・Premiere.xml・カット表.csv・作業/）。
この道具は、その結果を読んで、工程3（カット）と工程4（字幕）の下書きをこちらの形で書く。MTZ のファイルは書き換えない。

使い方（video_edit_rules の一番上で）:
  python3 tools/mtz_bridge.py run <作業用コピー> [--辞書=<tsv>]… [--テンション=1〜5] [--間を詰めない]
      … mtz <動画> --開かない を流す（素材ではなく edit/media/ の作業用コピーに流す。出力は動画の横の 〈名前〉_MTZ/）。
        終わったら続けて convert と check も流す
  python3 tools/mtz_bridge.py convert <動画 か 〈名前〉_MTZ/>
      … 〈名前〉_MTZ/こちらの形/ に書く：
        mtz_cuts.json        … cuts_vNNN.json と同じ keep_frames（素材のコマ。[開始, 終了)。コマは動画の fps で数える）
        mtz_captions.json    … captions_vNNN.json と同じ並び（id・text（2行は \\r で区切る）・who・src（素材の秒）・end_src・how）
        カット候補_MTZ.csv   … 完成の時刻・素材の開始・終了・切った秒・切った中身（文字）・理由（削除した文字.csv から）
        字幕候補_MTZ.csv     … id・素材の秒・文字（行）
  python3 tools/mtz_bridge.py check <動画 か 〈名前〉_MTZ/>
      … こちらの決まりで数える：0.2秒未満の残し区間（08 no_slivers）・字の途中で切れている切れ目（08 no_chop）・1行17字を超える字幕（08 captions.layout）。
        結果は 〈名前〉_MTZ/こちらの形/checks_mtz.json

注意
  - MTZ の時刻は 30fps のコマで丸めてある（素材の fps が 60 なら 2倍で割り切れる。29.97 なら 1コマ未満のずれが出る）
  - MTZ の話者分けはこの版（0.8.1）に入っていない。who は MTZ が付けた時だけ入り、ふつうは空。話者は工程4 でこちらで付ける
  - 下書きはそのまま使わず、工程3・4 の決まり（08）で読んで決める。ルールの食い違いは 記録/判断待ち.md の 18
"""
from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

MTZ_HOME = Path(os.environ.get("MTZ_HOME", os.path.expanduser("~/Downloads/MTZ")))
SLIVER_SEC = 0.2      # 08 no_slivers
LINE_MAX = 17         # 08 captions.layout（横は1行17字まで）


def stop(msg: str, code: int = 1):
    print(f"✖ {msg}")
    sys.exit(code)


def find_mtz() -> Path | None:
    for c in (shutil.which("mtz"), os.path.expanduser("~/.local/bin/mtz"), MTZ_HOME / "mtz"):
        if c and Path(c).exists():
            return Path(c)
    return None


def mtz_dir_of(p: str) -> Path:
    q = Path(p).expanduser()
    if q.is_dir() and q.name.endswith("_MTZ"):
        return q.resolve()
    if q.is_file():
        d = q.parent / f"{q.stem}_MTZ"
        if d.is_dir():
            return d.resolve()
        stop(f"MTZ の出力が無い：{d}（先に run を流す）")
    stop(f"動画か 〈名前〉_MTZ/ を渡す：{p}")


def video_of(mtz_dir: Path) -> Path | None:
    """〈名前〉_MTZ/ の隣の動画（作業/記録.log の1行目や、同じ名前のファイルから）"""
    stem = mtz_dir.name[: -len("_MTZ")]
    for ext in ("mov", "MOV", "mp4", "MP4", "m4v", "mkv", "avi"):
        c = mtz_dir.parent / f"{stem}.{ext}"
        if c.exists():
            return c
    return None


def fps_of(video: Path) -> Fraction:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate",
                          "-of", "default=nokey=1:noprint_wrappers=1", str(video)], capture_output=True, text=True).stdout.strip()
    return Fraction(out) if out else Fraction(30)


def read_csv(p: Path) -> list[dict]:
    with open(p, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load(mtz_dir: Path):
    w = mtz_dir / "作業"
    ear = w / "02_全データ_耳.json"
    if not ear.exists():
        stop(f"作業/02_全データ_耳.json が無い：{mtz_dir}")
    chars = json.load(open(ear, encoding="utf-8"))["chars"]
    cuts = read_csv(mtz_dir / "カット表.csv")
    telops = json.load(open(mtz_dir / "テロップの時刻.json", encoding="utf-8"))
    deleted = read_csv(mtz_dir / "削除した文字.csv") if (mtz_dir / "削除した文字.csv").exists() else []
    return chars, cuts, telops, deleted


def convert(arg: str):
    d = mtz_dir_of(arg)
    video = video_of(d)
    fps = fps_of(video) if video else Fraction(30)
    chars, cuts, telops, deleted = load(d)
    out = d / "こちらの形"
    out.mkdir(exist_ok=True)
    ver = (MTZ_HOME / "VERSION").read_text().strip() if (MTZ_HOME / "VERSION").exists() else "?"

    # ---- カット：カット表.csv（素材の秒）→ keep_frames（素材のコマ [開始, 終了)）
    keep = []
    rows = []
    prev_end = 0.0
    for r in cuts:
        s, e = float(r["素材の始まり(秒)"]), float(r["素材の終わり(秒)"])
        a, b = int(round(s * fps)), int(round(e * fps))
        if b <= a:
            continue
        keep.append([a, b])
        gap_chars = "".join(c["c"] for c in chars if c["s"] >= prev_end - 0.005 and c["e"] <= s + 0.005) if s > prev_end else ""
        why = " ／ ".join(f"{x['削除した文字']}（{x['理由']}）" for x in deleted
                           if prev_end - 0.005 <= float(x["素材の時刻(秒)"]) <= s + 0.005) if s > prev_end else ""
        rows.append({"完成の時刻": r["完成の時刻(秒)"], "素材の開始": f"{s:.3f}", "素材の終了": f"{e:.3f}",
                     "切った秒": f"{s - prev_end:.3f}" if s > prev_end else "0.000",
                     "切った中身（文字）": gap_chars, "理由": why, "残した中身": r["残した中身"]})
        prev_end = e
    total = sum(b - a for a, b in keep)
    src_dur = chars[-1]["e"] if chars else 0.0
    json.dump({"params": {"fps": f"{fps.numerator}/{fps.denominator}", "source": f"MTZ {ver}", "video": str(video) if video else None,
                          "mtz_dir": str(d), "note": "MTZ のカット表.csv を素材のコマにした下書き。工程3 の決まり（08 cut・pauses・no_chop）で読んで決める"},
               "keep_frames": keep, "total_frames": total, "total_sec": round(float(total / fps), 3),
               "total_cut_sec": round(sum(float(x["切った秒"]) for x in rows), 3), "counts": {"keep": len(keep)}},
              open(out / "mtz_cuts.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    with open(out / "カット候補_MTZ.csv", "w", encoding="utf-8-sig", newline="") as fo:
        w = csv.DictWriter(fo, fieldnames=["完成の時刻", "素材の開始", "素材の終了", "切った秒", "切った中身（文字）", "理由", "残した中身"])
        w.writeheader()
        w.writerows(rows)

    # ---- 字幕：テロップの時刻.json（文字の番号 → 02_全データ_耳.json の chars の素材の秒）
    caps = []
    crow = []
    for t in telops:
        c0, c1 = t["文字の番号"]
        c1 = min(c1, len(chars))
        if c0 >= len(chars) or c1 <= c0:
            continue
        src = chars[c0]["s"]
        end = chars[c1 - 1]["e"]
        lines = t.get("行") or [t["文字"]]
        caps.append({"id": str(t["番号"]), "text": "\r".join(lines), "who": t.get("話者"), "src": round(src, 3), "end_src": round(end, 3),
                     "c0": c0, "c1": c1, "lines": lines, "mtz_frames": [t["出るコマ"], t["終わるコマ"]],
                     "how": "MTZ 耳（" + (t.get("切り替えた理由") or "") + ("／" + t["改行した理由"] if t.get("改行した理由") else "") + "）"})
        crow.append({"id": t["番号"], "素材の秒": f"{src:.3f}", "終わり": f"{end:.3f}", "文字": " ｜ ".join(lines), "話者": t.get("話者") or ""})
    json.dump({"captions": caps, "source": f"MTZ {ver}", "mtz_dir": str(d),
               "note": "MTZ のテロップの時刻.json を素材の秒にした下書き。who は MTZ が付けた時だけ。工程4 の決まり（08 captions）で読んで決める"},
              open(out / "mtz_captions.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    with open(out / "字幕候補_MTZ.csv", "w", encoding="utf-8-sig", newline="") as fo:
        w = csv.DictWriter(fo, fieldnames=["id", "素材の秒", "終わり", "文字", "話者"])
        w.writeheader()
        w.writerows(crow)
    print(f"✔ こちらの形に書いた：{out}")
    print(f"  カット：残す区間 {len(keep)}・残す {float(total / fps):.1f}秒／素材 {src_dur:.1f}秒（fps {fps}）・切った {sum(float(x['切った秒']) for x in rows):.1f}秒 → mtz_cuts.json・カット候補_MTZ.csv")
    print(f"  字幕：{len(caps)}枚 → mtz_captions.json・字幕候補_MTZ.csv")
    return out


def check(arg: str):
    d = mtz_dir_of(arg)
    out = convert(arg)      # いつも作り直す（途中で止まった古い物を読まない）
    video = video_of(d)
    fps = fps_of(video) if video else Fraction(30)
    chars, _, _, _ = load(d)
    cuts = json.load(open(out / "mtz_cuts.json", encoding="utf-8"))
    caps = json.load(open(out / "mtz_captions.json", encoding="utf-8"))["captions"]
    keep = cuts["keep_frames"]
    # 08 no_slivers：0.2秒未満の残し区間
    slivers = [{"frames": k, "sec": round(float((k[1] - k[0]) / fps), 3)} for k in keep if (k[1] - k[0]) / fps < SLIVER_SEC]
    # 08 no_chop：切れ目（残し区間の終わりと次の始まり）が、字（耳の s〜e）の途中にある
    chops = []
    for i, k in enumerate(keep):
        for name, f in (("終わり", k[1]), ("始まり", k[0])):
            t = f / fps
            for j, c in enumerate(chars):
                if c["s"] < t < c["e"]:
                    chops.append({"区間": i, "どこ": name, "秒": round(float(t), 3), "字": c["c"], "前後": "".join(x["c"] for x in chars[max(0, j - 4): j + 5])})
    # 08 captions.layout：1行17字を超える
    long_lines = [{"id": c["id"], "行": ln, "字数": len(ln)} for c in caps for ln in c["lines"] if len(ln) > LINE_MAX]
    # 字幕の頭が声の頭（耳）と同じか（MTZ は作りとして同じになる。違えば道具の穴）
    off = [{"id": c["id"], "src": c["src"], "耳": chars[c["c0"]]["s"]} for c in caps if abs(c["src"] - chars[c["c0"]]["s"]) > 0.001]
    res = {"fps": f"{fps}", "残す区間": len(keep), "字幕": len(caps),
           "0.2秒未満の残し区間": slivers, "字の途中の切れ目": chops, "17字を超える行": long_lines, "字幕の頭が耳と違う": off,
           "note": "こちらの検査（check_chops・check_slivers）は .prproj にしか効かないので、ここでは MTZ の表と耳の時刻だけで数えた。音の波形では見ていない"}
    json.dump(res, open(out / "checks_mtz.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"✔ 検査（MTZ の表と耳の時刻だけ。波形は見ていない）→ {out / 'checks_mtz.json'}")
    print(f"  0.2秒未満の残し区間：{len(slivers)}件　字の途中の切れ目：{len(chops)}件　17字を超える行：{len(long_lines)}件　字幕の頭が耳と違う：{len(off)}件")
    for x in chops[:10]:
        print(f"    - 切れ目 {x['秒']}秒（区間{x['区間']}の{x['どこ']}）が「{x['字']}」の途中：{x['前後']}")
    return res


def run(args: list[str]):
    video = None
    extra = []
    for a in args:
        if a.startswith("--"):
            extra.append(a)
        elif video is None:
            video = a
        else:
            stop(f"動画は1つだけ：{a}")
    if not video:
        stop("動画（edit/media/ の作業用コピー）を渡す")
    v = Path(video).expanduser().resolve()
    if not v.is_file():
        stop(f"動画が無い：{v}")
    if "edit/media" not in str(v) and "edit\\media" not in str(v):
        print(f"⚠ 作業用コピー（edit/media/）ではない動画に流そうとしている：{v}\n  MTZ は動画の横に 〈名前〉_MTZ/ を作るので、素材のフォルダに物が増える。続けるなら --素材でもよい を付ける")
        if "--素材でもよい" not in extra:
            sys.exit(2)
        extra.remove("--素材でもよい")
    mtz = find_mtz()
    if not mtz:
        stop("mtz が無い（~/Downloads/MTZ にセットアップしてあるか。bash ~/Downloads/MTZ/セットアップ.sh）")
    cmd = [str(mtz), str(v), "--開かない", *extra]
    print("■ MTZ を流す：", " ".join(cmd))
    r = subprocess.run(cmd)
    if r.returncode != 0:
        stop(f"MTZ が止まった（終了 {r.returncode}）。記録：{v.parent / (v.stem + '_MTZ') / '作業' / '記録.log'}", r.returncode)
    convert(str(v))
    check(str(v))


def main():
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(64)
    if a[0] == "run":
        run(a[1:])
    elif a[0] == "convert" and len(a) >= 2:
        convert(a[1])
    elif a[0] == "check" and len(a) >= 2:
        check(a[1])
    else:
        print(__doc__)
        sys.exit(64)


if __name__ == "__main__":
    main()
