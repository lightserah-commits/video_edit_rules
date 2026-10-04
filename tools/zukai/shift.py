#!/usr/bin/env python3
"""カットが変わって字幕が動いた分だけ、描いた図解・画像・ロゴの札（Z*・I*・L*）の時刻をずらす（描き直さない。どの案件でも使える道具）。
元：環境設定 v004 の zukai/shift_v004.py（I・L も）。make_zukai.py を回すと overlay を作り直すので、時刻だけ直したい時にこれを使う。
  - ずらす量＝diagram.json の anchor の字幕の、今のタイムラインの開始 − anchor.f（make_zukai.py と同じ）
  - 図解の区間の素材のコマ（src_ranges）が前と同じことを確かめる（ワイプ・確かめの画像のカメラが同じ絵のままか）。
    目印の字幕の動きと区間の動きがずれる時（字幕をカットのコマから出す直しなど）は、±30コマの中で素材のコマが同じになるずらしを探す。無ければ止める（描き直しが要る）
  - manifest の tl_start_f・tl_end_f・se_events・区間に重なる字幕（hide_caption_ids が auto のもの）と、diagram.json の start_f・end_f・anchor.f を直す
  python3 tools/zukai/shift.py --ver <edit/vNNN> [--dry] [--prefixes ZIL] [KEY …]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from case import Case, add_args  # noqa: E402
from tl import TL, ts  # noqa: E402
from make_zukai import src_ranges  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="字幕が動いた分だけ図解の時刻をずらす（描き直さない）")
    add_args(ap)
    ap.add_argument("--dry", action="store_true", help="書き換えずに見るだけ")
    ap.add_argument("--prefixes", default="ZIL", help="対象のキーの頭の文字（既定 ZIL＝図解・画像・ロゴの札）")
    ap.add_argument("keys", nargs="*", help="キー（省くと全部）")
    a = ap.parse_args()
    K = Case(a)
    tl = TL.of(K)
    dirs = sorted(p for p in K.zukai.iterdir() if p.is_dir() and p.name[:1] in a.prefixes and (p / "diagram.json").exists()
                  and (K.out / p.name / "manifest.json").exists())
    if a.keys:
        dirs = [p for p in dirs if p.name in a.keys]
    for ddir in dirs:
        k = ddir.name
        d = json.load(open(ddir / "diagram.json", encoding="utf-8"))
        mp = K.out / k / "manifest.json"
        m = json.load(open(mp, encoding="utf-8"))
        now = tl.caps[d["anchor"]["cap"]]["s"]
        sh = now - d["anchor"]["f"]
        S, E = d["start_f"] + sh, d["end_f"] + sh
        assert m["tl_start_f"] in (d["start_f"] + m.get("shift", 0), d["start_f"]), (k, m["tl_start_f"], d["start_f"])
        old = [list(x) for x in m["src_ranges"]]

        def try_src(S_, E_):
            try:
                return [list(x) for x in src_ranges(tl, S_, E_)]
            except AssertionError:
                return None
        src = try_src(S, E)
        if src != old:
            for d_ in sorted(range(-30, 31), key=abs):
                if try_src(S + d_, E + d_) == old:
                    print(f"  {k}：目印の字幕の動きと {d_:+d}コマ違う（素材のコマで合わせた）")
                    S, E, sh = S + d_, E + d_, sh + d_
                    src = old
                    break
        assert src == old, f"{k}：図解の区間の素材のコマが変わった（描き直しが要る）{old} → {src}"
        hide = d.get("hide_caption_ids", "auto")
        if hide == "auto":
            hide = [i for i in tl.ids if tl.caps[i]["s"] < E and S < tl.caps[i]["e"]]
        print(f"{k}: {m['tl_start']}〜{m['tl_end']} → {ts(S)}〜{ts(E)}（{sh:+d}コマ）字幕を外す {len(m['hide_caption_ids'])}→{len(hide)}"
              + ("" if hide == m["hide_caption_ids"] else f"  !! 外す字幕が変わった {m['hide_caption_ids']} → {hide}"))
        if a.dry:
            continue
        for ev in m.get("se_events", []):
            ev["tl_f"] = ev["tl_f"] - m["tl_start_f"] + S
            ev["tl"] = ts(ev["tl_f"])
        m.update({"tl_start_f": S, "tl_end_f": E, "tl_start": ts(S), "tl_end": ts(E), "hide_caption_ids": hide,
                  "shifted": {"frames": sh, "anchor": d["anchor"]["cap"], "ver": K.ver.name, "how": "tools/zukai/shift.py（描き直さず時刻だけ）"}})
        json.dump(m, open(mp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        d["start_f"], d["end_f"] = S, E
        d["anchor"]["f"] = now                       # 次に回した時のずらしは 0（start_f は素材で合わせた S）
        json.dump(d, open(ddir / "diagram.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
