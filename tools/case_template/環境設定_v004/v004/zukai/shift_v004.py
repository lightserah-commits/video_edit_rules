#!/usr/bin/env python3
"""v003：カットが変わって字幕が動いた分だけ、描いた図解（Z1〜Z7）をずらす（描き直さない）。
make_zukai.py を回すと overlay を作り直す（Z2・Z4・Z5 は overlay_r2.mov）ので、manifest と diagram.json の時刻だけを直す。
  - ずらす量＝diagram.json の anchor の字幕の、今のタイムラインの開始 − anchor.f（make_zukai.py と同じ）
  - 図解の区間の素材のコマ（src_ranges）が前と同じことを確かめる（ワイプ・確かめの画像のカメラが同じ絵のままか）。違えば止める
  - manifest の tl_start_f・tl_end_f・se_events・区間に重なる字幕（hide_caption_ids が auto のもの）と、diagram.json の start_f・end_f・anchor.f を直す
  python3 zukai/shift_v004.py [--dry]
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tl import TL, ts  # noqa: E402
from make_zukai import src_ranges  # noqa: E402

HERE = Path(__file__).resolve().parent
dry = "--dry" in sys.argv
tl = TL()
# v004（2026-10-04 小川さんが 551 を切った後）：画像（I*）・ロゴの札（L*）も、目印の字幕の動いた分だけずらす（描き直さない）
for ddir in sorted(p for p in HERE.iterdir() if p.is_dir() and p.name[:1] in "ZIL" and (p / "diagram.json").exists() and (HERE / "out" / p.name / "manifest.json").exists()):
    k = ddir.name
    d = json.load(open(ddir / "diagram.json", encoding="utf-8"))
    mp = HERE / "out" / k / "manifest.json"
    m = json.load(open(mp, encoding="utf-8"))
    now = tl.caps[d["anchor"]["cap"]]["s"]
    sh = now - d["anchor"]["f"]
    S, E = d["start_f"] + sh, d["end_f"] + sh
    assert m["tl_start_f"] == d["start_f"] + m.get("shift", 0) or m["tl_start_f"] == d["start_f"], (k, m["tl_start_f"], d["start_f"])
    old = [list(x) for x in m["src_ranges"]]

    def try_src(S_, E_):
        try:
            return [list(x) for x in src_ranges(tl, S_, E_)]
        except AssertionError:
            return None
    src = try_src(S, E)
    if src != old:
        # v004：目印の字幕が G4（字幕をカットのコマから出す）で動くと、字幕の動きと図解の区間の動きがずれる → 素材のコマが同じになるずらしを探す
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
    if dry:
        continue
    for ev in m.get("se_events", []):
        ev["tl_f"] = ev["tl_f"] - m["tl_start_f"] + S
        ev["tl"] = ts(ev["tl_f"])
    m.update({"tl_start_f": S, "tl_end_f": E, "tl_start": ts(S), "tl_end": ts(E), "hide_caption_ids": hide,
              "shift_v004": {"frames": sh, "anchor": d["anchor"]["cap"], "how": "zukai/shift_v004.py（描き直さず時刻だけ）"}})
    json.dump(m, open(mp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    d["start_f"], d["end_f"] = S, E
    d["anchor"]["f"] = now                       # 次に回した時のずらしは 0（start_f は素材で合わせた S）
    json.dump(d, open(ddir / "diagram.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
