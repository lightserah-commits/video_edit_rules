#!/usr/bin/env python3
"""描いた図解の始まりを数コマ前へ倒す（描き直さない。どの案件でも使える道具）。
図解がカット（目印の字幕の頭）より数コマ後から始まり、その間に字幕のない素のカメラが一瞬出る時に使う。
元：環境設定 v004 の _work/z7_head_pad.py（Z7 を 8コマ前倒し。点検[32]）。
  - overlay の頭に1コマ目（板と見出しの出だし。板はもう出ている）を足し、ワイプはカメラから新しい区間で作り直す
  - どちらも新しい名前（overlay_rN.mov・wipe_rN.mp4。使われていない N）で書く（前のファイルは消さない・上書きしない）
  - 出だしの SE（図解の頭のもの）も新しい頭へ。manifest だけ直す（diagram.json・page.html は変えない。make_zukai.py を流し直すと元に戻る）
  python3 tools/zukai/head_pad.py --ver <edit/vNNN> Z7                 … 目印の字幕（anchor.cap）の頭まで前倒し
  python3 tools/zukai/head_pad.py --ver <edit/vNNN> Z7 --to-frame 46800  … 決めたコマまで
  python3 tools/zukai/head_pad.py --ver <edit/vNNN> Z7 --frames 8        … 8コマ前倒し
  （前倒しは 1〜--max コマ。既定 15。もう前倒ししてあれば止まる）
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from case import add_args  # noqa: E402
from tl import TL, ts  # noqa: E402
import make_zukai as mz  # noqa: E402


def free(odir, stem, ext):
    k = 2
    while (odir / f"{stem}_r{k}{ext}").exists():
        k += 1
    return odir / f"{stem}_r{k}{ext}"


def main():
    ap = argparse.ArgumentParser(description="描いた図解の頭を数コマ前へ倒す（描き直さない）")
    add_args(ap)
    ap.add_argument("key")
    ap.add_argument("--to-frame", type=int, help="新しい頭のコマ（タイムラインの絶対のコマ）")
    ap.add_argument("--frames", type=int, help="前倒しするコマ数")
    ap.add_argument("--max", type=int, default=15, help="前倒しの上限（既定 15コマ）")
    a = ap.parse_args()
    K = mz.setup(a)
    tl = TL.of(K)
    odir = K.out / a.key
    mp = odir / "manifest.json"
    m = json.load(open(mp, encoding="utf-8"))
    d = json.load(open(K.zukai / a.key / "diagram.json", encoding="utf-8"))
    S0, E = m["tl_start_f"], m["tl_end_f"]
    done = m.get("head_pad") or m.get("head_pad_v004")
    if done:
        raise SystemExit(f"もう前倒ししてある（{done}）")
    if a.to_frame is not None:
        S = a.to_frame
    elif a.frames:
        S = S0 - a.frames
    else:
        S = tl.caps[d["anchor"]["cap"]]["s"]               # 目印の字幕の頭（＝カットのコマ）
    pad = S0 - S
    if not 0 < pad <= a.max:
        raise SystemExit(f"前倒しが {pad}コマ（1〜{a.max} にする。今の頭 {ts(S0)}・新しい頭 {ts(S)}）")
    print(f"{a.key}: {ts(S0)} → {ts(S)}（{pad}コマ前倒し）")
    work = odir / "_work_pad"
    work.mkdir(exist_ok=True)
    n = E - S
    src = mz.src_ranges(tl, S, E)
    old_ov = Path(m["overlay"]["file"])
    ov = free(odir, "overlay", ".mov")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(old_ov), "-vf", f"tpad=start={pad}:start_mode=clone",
                    "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le", "-vendor", "apl0", str(ov)], check=True)
    assert mz.count_frames(ov) == n, (mz.count_frames(ov), n)
    m["overlay"].update({"file": str(ov), "frames": n})
    if m.get("wipe"):
        base = mz.make_base(work, S, E, src, K.cam)
        wipe = free(odir, "wipe", ".mp4")
        mz.make_wipe(base, wipe, m["wipe"]["crop_from_camera"], n)
        assert mz.count_frames(wipe) == n
        m["wipe"]["file"] = str(wipe)
    for ev in m["se_events"]:
        if ev["tl_f"] == S0:
            ev["tl_f"], ev["tl"] = S, ts(S)
    hide = d.get("hide_caption_ids", "auto")
    if hide == "auto":
        hide = [i for i in tl.ids if tl.caps[i]["s"] < E and S < tl.caps[i]["e"]]
    m.update({"tl_start_f": S, "tl_start": ts(S), "frames": n, "src_ranges": [list(x) for x in src], "hide_caption_ids": hide,
              "head_pad": {"frames": pad, "from": ts(S0), "ver": K.ver.name,
                           "how": "tools/zukai/head_pad.py（overlay の1コマ目を頭に足し、ワイプはカメラから作り直し）"}})
    json.dump(m, open(mp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"overlay {ov.name}{'・wipe ' + Path(m['wipe']['file']).name if m.get('wipe') else ''}・字幕を外す {hide}")


if __name__ == "__main__":
    main()
