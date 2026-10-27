#!/usr/bin/env python3
"""図解（Z*）の部品の出るコマ（page.html の const F の表）を、今の版の声（言葉の聞こえ始め）から付け直す（どの案件でも使える道具）。
元：1026 AI未来予測 v004（2026-10-27 小川さん「図解のタイミングとか発声と会ってない」）。v003 は v001 で数えた F の表のまま、
カットが何度も変わった区間に描いていて、部品が声より 0.3〜3秒遅かった。カットが変わるたびに、ここから F を付け直して描き直す。

  python3 tools/zukai/retime.py --ver <edit/vNNN> [--dry] [KEY …]
    → <図解のフォルダ>/<KEY>/beats.json を読み、page.html の const F・window.ZUKAI.frames と diagram.json（start_f・end_f・anchor・se）を書き換える
    → そのあと make_zukai.py（run_zukai.py）で描く。確かめは check_sync.py（beats.json の部品を声と比べる）

beats.json（部品ごとに、合わせる字幕IDと言葉。言葉は字幕の書き方の頭 2〜6字）：
  [{"part": "ima", "cap_id": "96", "word": "今"}, {"part": "ad", "cap_id": "717+1", "word": "Addness", "asr": "アドネス"}, …,
   {"part": "END", "cap_id": "132", "at": "cap"}]          ← at: "cap"＝字幕の頭のコマ（終わりは次の字幕の頭）
  - F の値が 0 の部品が図解の頭（start_f）。"pad": 数字 で言葉の頭から何コマ後に出すかを足せる（既定 0）
  - "asr"＝文字起こしでの書き方（字幕と書き方が違う言葉。Addness → アドネス、OpenAI → オープンAI など。無くても探すが外れやすい）
  - beats.json に無い F の部品は、表の上で前にある部品と同じだけずらす（言葉に結びつかない飾り）
  - 言葉が今の版で見つからない（切った）部品は止まる（beats.json を直すか、部品を外す）
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from case import Case, add_args  # noqa: E402
from tl import TL, ts  # noqa: E402
from check_sync import Words  # noqa: E402

F_RE = re.compile(r"const F = \{(.*?)\};", re.S)
ITEM = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(-?\d+)")


def main():
    ap = argparse.ArgumentParser(description="図解の部品の時刻を声から付け直す", epilog=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_args(ap)
    ap.add_argument("--dry", action="store_true", help="書き換えずに見るだけ")
    ap.add_argument("keys", nargs="*")
    a = ap.parse_args()
    K = Case(a)
    tl = TL.of(K)
    W = Words(tl)
    keys = a.keys or sorted(p.name for p in K.zukai.iterdir() if p.is_dir() and p.name.startswith("Z") and (p / "beats.json").exists())
    bad = 0
    for k in keys:
        d = K.zukai / k
        page = (d / "page.html").read_text(encoding="utf-8")
        m = F_RE.search(page)
        if not m:
            print(f"!! {k}：page.html に const F の表が無い"); bad += 1
            continue
        old = {n: int(v) for n, v in ITEM.findall(m.group(1))}
        order = sorted(old, key=lambda n: (old[n], list(old).index(n)))
        beats = {b["part"]: b for b in json.load(open(d / "beats.json", encoding="utf-8"))}
        miss = [n for n in beats if n not in old]
        if miss:
            print(f"!! {k}：beats.json の部品が F の表に無い {miss}"); bad += 1
            continue
        on = {}
        for n, b in beats.items():
            if b.get("at") == "cap":
                c = tl.caps.get(str(b["cap_id"]))
                f = c["s"] if c else None
                why = f"字幕 {b['cap_id']} が今の版に無い"
            else:
                f, why = W.onset(str(b["cap_id"]), b["word"], b.get("asr"))
            if f is None:
                print(f"!! {k}：{n} の言葉が見つからない（{why}）"); bad += 1
                continue
            on[n] = f + int(b.get("pad", 0))
        if len(on) != len(beats):
            continue
        zero = [n for n in old if old[n] == 0 and n in on]
        if not zero:
            print(f"!! {k}：F の値が 0 の部品（図解の頭）が beats.json に無い"); bad += 1
            continue
        S = on[zero[0]]
        new, last_old, last_new = {}, 0, 0
        for n in order:
            if n in on:
                new[n] = on[n] - S
            else:                                    # 言葉に結びつかない部品：前の部品と同じだけずらす
                new[n] = last_new + (old[n] - last_old)
            last_old, last_new = old[n], new[n]
        if "END" not in beats and "END" in old:
            new["END"] = max(new.values()) + (old["END"] - max(v for n, v in old.items() if n != "END"))
        neg = [n for n in new if new[n] < 0]
        if neg:
            print(f"!! {k}：図解の頭より前に出る部品 {neg}（beats.json の頭の部品を見直す）"); bad += 1
            continue
        N = new.get("END", max(new.values()))
        moved = [(n, old[n], new[n]) for n in order if old[n] != new[n]]
        print(f"{k}：頭 {ts(S)}（f{S}・字幕 {beats[zero[0]]['cap_id']}）・長さ {old.get('END')}→{N}コマ・付け直した部品 {len(moved)}/{len(old)}")
        for n, x, y in moved:
            print(f"   {n}: {x} → {y}（{(y - x) / 29.97:+.2f}秒）")
        if a.dry:
            continue
        body = m.group(1)
        body2 = ITEM.sub(lambda mm: f"{mm.group(1)}: {new.get(mm.group(1), int(mm.group(2)))}", body)
        page = page[:m.start(1)] + body2 + page[m.end(1):]
        page = re.sub(r"window\.ZUKAI = \{ frames: \d+ \}", f"window.ZUKAI = {{ frames: {N} }}", page)
        page = re.sub(r"(const F = \{)", f"// retime.py {K.ver.name}：F を今の版の声（beats.json）から付け直した\n\\1", page, count=1) \
            if f"retime.py {K.ver.name}" not in page else page
        (d / "page.html").write_text(page, encoding="utf-8")
        dj = json.load(open(d / "diagram.json", encoding="utf-8"))
        val2name = {}
        for n in order:
            val2name.setdefault(old[n], n)

        def remap(f):
            if f in val2name:
                return new[val2name[f]]
            base = max((n for n in order if old[n] <= f), key=lambda n: old[n], default=order[0])
            return new[base] + (f - old[base])
        for ev in dj.get("se", []):
            ev["f"] = remap(ev["f"])
        if isinstance(dj.get("checks"), list):
            dj["checks"] = sorted({min(N - 1, max(0, remap(c))) for c in dj["checks"]})
        cap0 = str(beats[zero[0]]["cap_id"])
        dj.update(start_f=S, end_f=S + N, anchor={"cap": cap0, "f": tl.caps[cap0]["s"] if cap0 in tl.caps else S},
                  retimed={"ver": K.ver.name, "how": "tools/zukai/retime.py（beats.json の言葉の聞こえ始め）"})
        dj["anchor_offset"] = S - dj["anchor"]["f"]
        json.dump(dj, open(d / "diagram.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
