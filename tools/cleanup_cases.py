#!/usr/bin/env python3
"""案件の作業場の片付け。作業場は、小川さんが指定した案件フォルダ（素材入り）の中の edit/（場所は
.claude/addness/goals.json の cases[].edit）。古い案件は ~/Movies/video_edit_cases/（video_edit_rules/work のリンク）の下。
消してよいものを種類ごとに一覧にし、容量を出す。--trash を付けた時だけ、その種類を macOS のゴミ箱に移す
（完全には消さない。ゴミ箱を空にするのは人がやる）。2026-09-28 小川さん指示。

種類（どれも元素材とスクリプトから作り直せる。決まったこと・分かったことは Addness とルールにある）:
  途中       焼き込みの途中ファイル（_blur_chunks*）、検査・文字認識の画像（leak*・dense）、Premiere・Media Encoder のキャッシュ
             （Audio Previews・Auto-Save・*Masks。最新の版の分は Premiere で開いて使うので --done の時だけ）、前の出力の控え（v*/_from_*）
  前の書き出し 最新の版より前の版の書き出し（v*/*.mp4）
  使っていない media/ の作業用コピーのうち、最新の版の .prproj が使っていないもの（途中の版の焼き込みなど）。
             素材を固定フレームにした元のコピー（*_CFR*）は次の版の元なので入れない
  終わった案件 --done を付けた案件だけ：最新の版が使っている作業用コピー・書き出し・分析の画像や音声（.prproj・台本・plan・
             スクリプト・報告・JSON は小さいので残す）
  元素材     --done と --materials パス を付けた時だけ（素材は小川さんのもの。ふつうは消さない）

使い方:
  python3 tools/cleanup_cases.py                         全案件の一覧（何も動かさない）
  python3 tools/cleanup_cases.py 案件名 --trash 途中 前の書き出し 使っていない
  python3 tools/cleanup_cases.py 案件名 --done --trash 終わった案件
タイミング（編集の依頼文.md の「片付け」）：版ができたら「途中」、次の版ができたら「前の書き出し」「使っていない」、
案件が終わったら「終わった案件」（最終の書き出しを人が別の場所に保存してから）。
"""
import argparse
import gzip
import os
import re
import shutil
import sys

RULES = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES = os.path.realpath(os.path.join(RULES, "work"))        # 前のやり方の置き場
GOALS = os.path.join(RULES, ".claude", "addness", "goals.json")


def case_paths():
    """案件名 → 作業場（edit/）。goals.json に書いたものと、work/ の下の古い案件"""
    import json
    out, skip = {}, set()
    try:
        g = json.load(open(GOALS, encoding="utf-8"))
        skip = set(g.get("not_cases", []))                 # 道具の試し（案件ではない）
        cases = dict(g.get("cases", {}))
        try:                                               # その Mac で足した案件（Git に入れない）
            loc = json.load(open(os.path.join(os.path.dirname(GOALS), "cases_local.json"), encoding="utf-8"))
            cases.update(loc.get("cases") or loc)
        except (OSError, ValueError):
            pass
        for n, c in cases.items():
            e = os.path.expanduser(c.get("edit", "")) if isinstance(c, dict) else ""
            if e and os.path.isdir(e):
                out[n] = e
    except (OSError, ValueError):
        pass
    if os.path.isdir(CASES):
        for d in sorted(os.listdir(CASES)):
            if not d.startswith((".", "_")) and os.path.isdir(os.path.join(CASES, d)) and d not in out and d not in skip:
                out[d] = os.path.join(CASES, d)
    return out
TRASH = os.path.expanduser("~/.Trash")
CACHE_DIRS = ("Adobe Premiere Pro Audio Previews", "Adobe Premiere Pro Auto-Save", "Adobe Adobe Media Encoder Audio Previews")
HEAVY_EXT = (".mov", ".mp4", ".m4a", ".wav", ".mxf", ".npy", ".f32", ".png", ".jpg", ".m4v")


def size(p):
    if os.path.isfile(p) or os.path.islink(p):
        return os.path.getsize(p) if os.path.isfile(p) else 0
    t = 0
    for r, _, fs in os.walk(p):
        for f in fs:
            fp = os.path.join(r, f)
            if os.path.isfile(fp) and not os.path.islink(fp):
                t += os.path.getsize(fp)
    return t


def human(n):
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024 or u == "GB":
            return f"{n:.1f}{u}" if u != "B" else f"{n}B"
        n /= 1024


def versions(case):
    vs = []
    for d in os.listdir(case):
        if re.fullmatch(r"v\d{3}", d) and any(f.endswith(".prproj") for f in os.listdir(os.path.join(case, d))):
            vs.append(d)
    return sorted(vs)


def used_names(case, v):
    """最新の版の .prproj が参照しているファイル名（中身の文字列に出てくる名前）"""
    text = ""
    for f in os.listdir(os.path.join(case, v)):
        if f.endswith(".prproj"):
            p = os.path.join(case, v, f)
            try:
                text += gzip.open(p).read().decode("utf-8", "ignore")
            except OSError:
                text += open(p, encoding="utf-8", errors="ignore").read()
    return text


def plan(case, done):
    out = {"途中": [], "前の書き出し": [], "使っていない": [], "終わった案件": []}
    vs = versions(case)
    latest = vs[-1] if vs else None
    text = used_names(case, latest) if latest else ""
    for r, ds, fs in os.walk(case):
        rel = os.path.relpath(r, case)
        for d in list(ds):
            p = os.path.join(r, d)
            in_latest = latest is not None and rel.split(os.sep)[0] == latest
            if (d in CACHE_DIRS or d.endswith(" Masks")) and in_latest and not done:
                continue                                   # 最新の版のキャッシュは Premiere で開いている間使うので、終わるまで残す
            if d.startswith("_blur_chunks") or d.startswith("leak") or d == "dense" or d in CACHE_DIRS or d.endswith(" Masks") \
                    or (d.startswith("_from_") and re.match(r"v\d{3}$", os.path.basename(r))):
                out["途中"].append(p)
                ds.remove(d)
        for f in fs:
            p = os.path.join(r, f)
            top = rel.split(os.sep)[0]
            if top == "media" and f.lower().endswith(HEAVY_EXT):
                base_copy = "_CFR" in f                   # 素材を固定フレームにした作業用コピー（次の版の元）は、案件が終わるまで残す
                (out["終わった案件"] if (f in text or base_copy) else out["使っていない"]).append(p)
            elif re.fullmatch(r"v\d{3}", top) and f.endswith(".mp4") and os.sep not in rel:
                (out["終わった案件"] if top == latest else out["前の書き出し"]).append(p)
            elif top == "analysis" and f.lower().endswith(HEAVY_EXT):
                out["終わった案件"].append(p)
    if not done:
        out["終わった案件"] = []
    return out, latest


def to_trash(p, name, case):
    """ゴミ箱での名前は「案件_版_名前」（同じ名前のキャッシュが版ごとにあるので、ぶつからないように）"""
    base = (name + os.sep + os.path.relpath(p, case)).replace(os.sep, "_")
    dst, k = os.path.join(TRASH, base), 1
    while os.path.exists(dst):
        k += 1
        dst = os.path.join(TRASH, f"{base} {k}")
    shutil.move(p, dst)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cases", nargs="*", help="案件フォルダ名（省略で全部）")
    ap.add_argument("--done", action="store_true", help="案件が終わった（「終わった案件」も候補にする）")
    ap.add_argument("--materials", nargs="*", default=[], help="--done の時、ゴミ箱に移す元素材（_materials の下の名前）")
    ap.add_argument("--trash", nargs="*", default=[], help="ゴミ箱に移す種類（途中・前の書き出し・使っていない・終わった案件・元素材）")
    a = ap.parse_args()
    paths = case_paths()
    names = a.cases or sorted(paths)
    total_moved = 0
    for n in names:
        if n not in paths:
            print(f"== {n}：見つからない（.claude/addness/goals.json の cases に edit を書く）")
            continue
        case = paths[n]
        out, latest = plan(case, a.done)
        if a.done and a.materials:
            out["元素材"] = [m if os.path.isabs(m) else os.path.join(CASES, "_materials", m) for m in a.materials]
        print(f"== {n}（{case}。全体 {human(size(case))}・最新の版 {latest}）")
        for k, ps in out.items():
            if not ps:
                continue
            s = sum(size(p) for p in ps)
            mark = "  → ゴミ箱へ" if k in a.trash else ""
            print(f"  {k}: {len(ps)}件 {human(s)}{mark}")
            for p in sorted(ps, key=size, reverse=True)[:6]:
                print(f"     {human(size(p)):>8}  {os.path.relpath(p, case)}")
            if len(ps) > 6:
                print(f"     …ほか {len(ps) - 6}件")
            if k in a.trash:
                for p in ps:
                    if os.path.exists(p):
                        to_trash(p, n, case)
                total_moved += s
    if a.trash:
        print(f"ゴミ箱に移した：{human(total_moved)}（Finder のゴミ箱から戻せる。空にするまではディスクは空かない）")


if __name__ == "__main__":
    main()
