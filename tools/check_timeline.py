#!/usr/bin/env python3
"""版のタイムラインを「変えてはいけない基準」（tools/dump_timeline.py で書き出した JSON）と突き合わせる。
元は work/gamen_kyoyu_20260926/analysis/check_cuts.py（カット尺と冒頭ハイライトを変えない案件）。

  カット：指定したトラックの（素材名で絞った）クリップが、差し込みの分だけずれた位置に、同じ素材・同じ in/out で全部あるか。
          差し込み区間の外に、基準に無いクリップが無いか。ズームのために同じ位置で切り分けたクリップは1つにまとめて比べる
  凍結区間：--frozen-until より前は、全トラックのクリップが基準と完全に同じか（装飾も含めて）
  尺：基準の尺＋差し込みの合計になっているか

使い方:
  python3 tools/check_timeline.py 版.prproj --seq シーケンス名 --base v000_source/基準_タイムライン.json \\
      --tracks V1,A1,V2 --names camera_cfr30.mov,shot_ --insert 19900:464 --frozen-until 306 --out checks_cut.json
  --insert は「基準のフレーム:足したフレーム数」。複数あればカンマで区切る（例 19900:464,30000:-120）
  --names は素材名の先頭。省略するとトラックの全クリップ
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dump_timeline import dump  # noqa: E402

KEYS = ("start_f", "end_f", "name", "in_ticks", "out_ticks", "muted", "texts")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--seq", required=True)
    ap.add_argument("--base", required=True)
    ap.add_argument("--tracks", default="V1,A1")
    ap.add_argument("--names", default="")
    ap.add_argument("--insert", default="")
    ap.add_argument("--frozen-until", type=int, default=0)
    ap.add_argument("--out")
    a = ap.parse_args()
    inserts = sorted((int(p), int(n)) for p, n in (x.split(":") for x in a.insert.split(",") if x))
    prefixes = [x for x in a.names.split(",") if x]
    base = json.load(open(a.base, encoding="utf-8"))
    cur = dump(a.project, a.seq)
    res = {"project": a.project, "inserts": inserts, "cut": {}, "frozen": {}, "ok": True}

    def is_cut_clip(r):
        return not prefixes or any((r["name"] or "").startswith(p) for p in prefixes)

    def shift(f):
        return f + sum(n for p, n in inserts if f >= p)

    def in_insert(r):
        for p, n in inserts:
            q = shift(p) - n          # 差し込みの頭（今の版のフレーム）
            if n > 0 and q <= r["start_f"] and r["end_f"] <= q + n:
                return True
        return False

    def moved(r):
        r = {k: r.get(k) for k in KEYS}
        d = shift(r["start_f"]) - r["start_f"]      # 差し込み位置で終わるクリップの終わりはずらさない
        r["start_f"], r["end_f"] = r["start_f"] + d, r["end_f"] + d
        return r

    edges = {shift(p) - n for p, n in inserts} | {shift(p) for p, n in inserts}

    def joined(rs):
        out = []
        for r in sorted(rs, key=lambda x: x["start_f"]):
            r = {k: v for k, v in r.items() if k not in ("texts", "muted")}
            if out and out[-1]["name"] == r["name"] and out[-1]["end_f"] == r["start_f"] \
                    and out[-1]["out_ticks"] == r["in_ticks"] and r["start_f"] not in edges:
                out[-1]["end_f"], out[-1]["out_ticks"] = r["end_f"], r["out_ticks"]
            else:
                out.append(r)
        return out

    for tn in a.tracks.split(","):
        want = joined([moved(r) for r in base["tracks"].get(tn, []) if is_cut_clip(r)])
        have = joined([{k: r.get(k) for k in KEYS} for r in cur["tracks"].get(tn, []) if is_cut_clip(r)])
        missing = [r for r in want if r not in have]
        extra = [r for r in have if r not in want]
        extra_outside = [r for r in extra if not in_insert(r)]
        res["cut"][tn] = {"base": len(want), "now": len(have), "n_missing": len(missing), "missing": missing[:5],
                          "added_in_insert": len(extra) - len(extra_outside), "extra_outside": extra_outside[:5]}
        if missing or extra_outside:
            res["ok"] = False

    expected = base["end_f"] + sum(n for _, n in inserts)
    res["end_f"] = {"base": base["end_f"], "now": cur["end_f"], "expected": expected}
    if cur["end_f"] != expected:
        res["ok"] = False

    F = a.frozen_until
    if F:
        for tn in sorted(set(base["tracks"]) | set(cur["tracks"])):
            want = [{k: r.get(k) for k in KEYS} for r in base["tracks"].get(tn, []) if r["start_f"] < F]
            have = [{k: r.get(k) for k in KEYS} for r in cur["tracks"].get(tn, []) if r["start_f"] < F]
            # 凍結区間の終わりをまたいで続くクリップ（BGMなど）は、終わりの位置だけ変わってよい
            same = len(want) == len(have) and all(
                {k: v for k, v in w.items() if k not in ("end_f", "out_ticks")} ==
                {k: v for k, v in h.items() if k not in ("end_f", "out_ticks")}
                and (w["end_f"] == h["end_f"] or (w["end_f"] > F and h["end_f"] > F))
                for w, h in zip(want, have))
            if want or have:
                res["frozen"][tn] = "同じ" if same else {"base": want, "now": have}
                if not same:
                    res["ok"] = False

    if a.out:
        json.dump(res, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False, indent=1)[:3000])
    sys.exit(0 if res["ok"] else 1)


if __name__ == "__main__":
    main()
