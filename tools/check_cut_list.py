#!/usr/bin/env python3
"""カットの検査を1つの一覧にして、未処理が残っていたら止める（08 の cut.before_handing。2026-11-04 小川さん「残っていたら渡さない」）。

見る物と、未処理の決め方（素材の秒は全部 <edit/vNNN>/_work/cuts_vNNN.json の今のカットに対して）：
  声の無い所       find_silence.py を動かす。1.0秒以上の切る候補
  言葉の無い音     find_laugh_gaps.py を動かす。候補の全部
  字幕に無い言葉   check_stray_words.py を動かす。⑥⑦の全部
  平らな所         wave_shape.py を動かす。目立って長い平らな所の詰める案（線は1回目の値を _work/cut_list_state.json に残して使う。毎回測ると線が下がって0にならない）
  語尾の坂         同じ。tail（語尾の坂の途中で切れている）
  言い出しの坂     同じ。head（坂の始まりから2コマ以上後ろから入っている）
  フィラー         fillers_vNNN.tsv の「声も切る」で切る区間がある物。谷なしは切れないので止めない（08 の remove「フィラー」）
  語尾             tails*.tsv の一番新しい物の「語尾が聞こえない」
  音のブツッ       checks_chops.json（--before-build の時は見ない）
  切れ端           checks_slivers.json（--before-build の時は見ない）
  fillers・tails・checks_* は文字起こしか .prproj が要るので、ここでは動かさない。無いか、カットより古い時は「動かしていない」として止める（動かすコマンドは ルール/工程/09_検査.md）。
  wave_shape の shaky・chop は耳で決める所なので止めず、「聴いてもらう」に分けて一覧に出す（工程11 の聴いてほしい時刻に入れる）。

未処理を0にするには、切るか、残す理由を <edit/vNNN>/_work/cut_keep.tsv に書く（検査の名前<TAB>秒<TAB>理由。±0.5秒で合う物が「残す」になる。秒は一覧の「素材の秒」の列をそのまま写す。音のブツッは版の秒が入る）。
入りの間（声が線を超えるまでの秒・入りの点の高さ）は報告のために出すだけで、止めない。

  ~/Desktop/video_edit_rules/env/bin/python tools/check_cut_list.py --ver "<edit/vNNN>" [--before-build]

出す物：<版>/_work/cut_list_vNNN.md・.tsv・.json（.json は premiere_case/export.py が見る）。未処理が1つでもあれば終了コード 1。
音は聴いていない（波形と文字起こしだけ）。
"""
import argparse
import csv
import glob
import json
import os
import re
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from wave_shape import FPS  # noqa: E402

MATCH_SEC = 0.5
REF_HEAD = "完成版2本：声まで中央 0.03〜0.04秒・入りの高さ 部屋の音より +10〜11dB"   # 2026-11-04 元の素材で測った（実例/根拠と実例.md の「つなぎ目の実測」）
OK_CODES = (0, 1)                 # どの検査も、出た物があれば 1 で終わる


def mmss(t):
    return f"{int(t // 60)}:{t % 60:05.2f}"


def fnum(s):
    m = re.search(r"\d+(?:\.\d+)?", str(s))
    return float(m.group()) if m else None


def tsec(s):
    """1:29.10 → 89.10"""
    a, _, b = str(s).partition(":")
    return float(a) * 60 + float(b) if b else fnum(a)


def run_tool(args, out, cuts_mtime):
    """道具を動かす。動かなかった時は理由の文を返す"""
    r = subprocess.run([sys.executable] + args, capture_output=True, text=True)
    if r.returncode not in OK_CODES or not os.path.exists(out) or os.path.getmtime(out) < cuts_mtime:
        return f"{os.path.basename(args[0])} が動かなかった（終了コード {r.returncode}）：{(r.stderr or r.stdout).strip()[-300:]}"
    return None


def tsv_rows(path):
    with open(path, encoding="utf-8", newline="") as f:
        rows = [x for x in csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE) if x and not x[0].startswith("#")]
    if not rows:
        return []
    head = rows[0]
    return [dict(zip(head, x)) for x in rows[1:]]


def silence_items(path):
    items = []
    for line in open(path, encoding="utf-8"):
        m = re.match(r"\|\s*(\d+:[\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*(.*?)\s*\|$", line.rstrip())
        if m and "残してよい見込み" not in m.group(4) and "溜めか読む" not in m.group(4) and "（allow）" not in m.group(4):
            items.append(dict(tl=m.group(1), src=float(m.group(3)), text=f"{m.group(2)}秒 {m.group(4)}"))
    return items


def laugh_items(path):
    return [dict(tl=r["版の時刻"], src=fnum(r["素材の秒"]), text=f"{r['長さ']}秒 字幕{r.get('字幕', '')} {r.get('字幕の文字', '')}") for r in tsv_rows(path)]


def stray_items(path):
    return [dict(tl=r["版の時刻"], src=fnum(r["素材の秒"]), text=f"{r['種類']} {r['語']} {r.get('字幕か切る行', '')}") for r in tsv_rows(path)]


def filler_items(path):
    do, cannot = [], []
    for r in tsv_rows(path):
        if r.get("分け方") != "声も切る":
            continue
        it = dict(tl=r["版の時刻"], src=fnum(r["素材の秒"]), text=f"{r['語']}（{r['種類']}）{r.get('前', '')}｜{r.get('後', '')}")
        (cannot if r.get("切る区間") == "谷なし" else do).append(it)
    return do, cannot


def tail_items(path):
    items = []
    for r in tsv_rows(path):
        if r.get("見立て") == "語尾が聞こえない":
            sec = next((v for k, v in r.items() if k.startswith("素材の秒")), "")      # 列の名前は「素材の秒（左の終わり→…」。値の左の数が語尾の所
            items.append(dict(tl=r["版の時刻（ハイライト無し）"], src=fnum(sec), text=f"字幕{r['字幕']} {r['字幕の文']} {r.get('欠けた字', '')}"))
    return items


def head_stats(env, keep):
    """入りの間（報告だけ）：声が線（85パーセンタイル−12dB）を超えるまでの秒と、入りの点の高さ（部屋の音より）"""
    floor, thr = float(np.percentile(env, 10)), float(np.percentile(env, 85)) - 12
    to_voice, height = [], []
    for (_, b0), (a1, _) in zip(keep, keep[1:]):
        if (a1 - b0) / FPS < 0.1:
            continue
        i = int(round(a1 / FPS * 100))
        if not 0 <= i < len(env) - 5:
            continue
        nz = np.nonzero(env[i:i + 300] > thr)[0]
        if len(nz):
            to_voice.append(nz[0] * 0.01)
        height.append(float(env[i]) - floor)
    if not to_voice:
        return None
    return dict(joins=len(height), to_voice=round(float(np.median(to_voice)), 2), height=round(float(np.median(height)), 1))


def load_keep(path):
    if not os.path.exists(path):
        return []
    rows = []
    for line in open(path, encoding="utf-8"):
        x = line.rstrip("\n").split("\t")
        if len(x) >= 3 and not line.startswith("#") and x[2].strip():
            sec = fnum(x[1])
            if sec is not None:
                rows.append((x[0].strip(), sec, x[2].strip()))
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ver", required=True, help="版のフォルダ edit/vNNN")
    ap.add_argument("--before-build", action="store_true", help="組み立ての前（工程3 の終わり）：.prproj が要る検査を見ない。この結果では書き出せない")
    a = ap.parse_args()
    V = os.path.abspath(os.path.expanduser(a.ver))
    tag = os.path.basename(V)
    W = os.path.join(V, "_work")
    A = os.path.join(os.path.dirname(V), "analysis")
    cuts_p = os.path.join(W, f"cuts_{tag}.json")
    caps_p = os.path.join(W, f"captions_{tag}.json")
    env_p = os.path.join(A, "camera_env.npy")
    cuts_mtime = os.path.getmtime(cuts_p)
    checks, not_run, listen = {}, [], []          # 検査の名前 → 項目／動かしていない検査／聴いてもらう

    # ── ここで動かす検査（どれも速い）──
    p = os.path.join(W, f"silence_{tag}.md")
    err = run_tool([os.path.join(HERE, "find_silence.py"), "--ver", V, "--out", p], p, cuts_mtime)
    not_run.append(("声の無い所", err)) if err else checks.__setitem__("声の無い所", silence_items(p))
    p = os.path.join(W, f"laugh_gaps_{tag}.tsv")
    err = run_tool([os.path.join(HERE, "find_laugh_gaps.py"), "--ver", V], p, cuts_mtime)
    not_run.append(("言葉の無い音", err)) if err else checks.__setitem__("言葉の無い音", laugh_items(p))
    out = os.path.join(W, f"stray_words_{tag}")
    err = run_tool([os.path.join(HERE, "check_stray_words.py"), "--ver", V, "--out", out], out + ".tsv", cuts_mtime)
    not_run.append(("字幕に無い言葉", err)) if err else checks.__setitem__("字幕に無い言葉", stray_items(out + ".tsv"))

    state_p = os.path.join(W, "cut_list_state.json")
    state = json.load(open(state_p, encoding="utf-8")) if os.path.exists(state_p) else {}
    wj, wt = os.path.join(W, "wave_shape.json"), os.path.join(W, "wave_shape.tsv")
    wargs = [os.path.join(HERE, "wave_shape.py"), "--env", env_p, "--cuts", cuts_p, "--captions", caps_p, "--mode", "long", "--out", wt, "--json", wj]
    if state.get("long_sec"):
        wargs += ["--long-sec", str(state["long_sec"])]
    err = run_tool(wargs, wj, cuts_mtime)
    if err:
        not_run.append(("波形の形", err))
    else:
        w = json.load(open(wj, encoding="utf-8"))
        if not state.get("long_sec"):
            json.dump({"long_sec": w["long_flat_sec"]["全体の目立って長い"]}, open(state_p, "w", encoding="utf-8"), ensure_ascii=False)
        checks["平らな所"] = [dict(tl=mmss(f["tl"]), src=f["parts"][0][0], text=f"{f['len']:.2f}秒の平らな所。{f['cut']}秒詰める案") for f in w["flats"] if f.get("cut")]
        checks["語尾の坂"] = [dict(tl=mmss(r["tl"]), src=r["b1"], text=r.get("why_tail", "")) for r in w["joins"] if "tail" in r["kinds"]]
        checks["言い出しの坂"] = [dict(tl=mmss(r["tl"]), src=r["a2"], text=r.get("why_head", "")) for r in w["joins"] if "head" in r["kinds"]]
        for r in w["joins"]:
            if "shaky" in r["kinds"] or "chop" in r["kinds"]:
                listen.append(dict(check="波形", tl=mmss(r["tl"]), src=r["a2"], text=r.get("why") or r.get("why_chop", "")))

    # ── 結果を読むだけの検査（無いか、カットより古ければ止める）──
    def fresh(path, name):
        if path and os.path.exists(path) and os.path.getmtime(path) >= cuts_mtime:
            return True
        not_run.append((name, f"{os.path.basename(path) if path else 'tails*.tsv'} が{'カットより古い' if path and os.path.exists(path) else '無い'}"))
        return False
    cannot = []
    p = os.path.join(W, f"fillers_{tag}.tsv")
    if fresh(p, "フィラー"):
        checks["フィラー"], cannot = filler_items(p)
    tails = sorted(glob.glob(os.path.join(W, "tails*.tsv")), key=os.path.getmtime)
    if fresh(tails[-1] if tails else None, "語尾"):
        checks["語尾"] = tail_items(tails[-1])
    if not a.before_build:
        p = os.path.join(V, "checks_chops.json")
        if fresh(p, "音のブツッ"):
            rows = json.load(open(p, encoding="utf-8")).get("rows", [])
            checks["音のブツッ"] = [dict(tl=x["time"], src=tsec(x["time"]), text=("前が切れている " if x.get("tail_cut") else "") + ("後ろが途中から" if x.get("head_cut") else "")) for x in rows]
        p = os.path.join(V, "checks_slivers.json")
        if fresh(p, "切れ端"):
            rows = json.load(open(p, encoding="utf-8")).get("slivers", [])
            checks["切れ端"] = [dict(tl=x["time"], src=x["frame"] / FPS, text=f"{x['kind']} {x['frames']}コマ {x['name']}") for x in rows]

    # ── 残す理由を当てる ──
    keep_rows = load_keep(os.path.join(W, "cut_keep.tsv"))
    table, todo, kept = [], [], []
    for name, items in checks.items():
        for it in items:
            if it["src"] is None:                # 素材の秒が無い行（語尾の一覧の短い行）は版の秒で合わせる
                it["src"] = tsec(it["tl"])
            why = next((r[2] for r in keep_rows if r[0] == name and abs(r[1] - it["src"]) <= MATCH_SEC), None)
            it.update(check=name, why=why)
            (kept if why else todo).append(it)
        table.append((name, len(items), sum(1 for x in items if x["why"]), sum(1 for x in items if not x["why"])))

    env = np.load(env_p)
    kf = json.load(open(cuts_p, encoding="utf-8"))["keep_frames"]
    hs = head_stats(env, kf)
    ok = not todo and not not_run

    L = [f"# カットの検査の一覧（{tag}）", "", f"**{'通った：未処理 0' if ok else f'止める：未処理 {len(todo)}・動かしていない検査 {len(not_run)}'}**。音は聴いていない（全部未聴取）。", "",
         "| 検査 | 出た数 | 理由つきで残す | 未処理 |", "|---|---|---|---|"]
    L += [f"| {n} | {c} | {k} | {t} |" for n, c, k, t in table]
    L += [f"| {n} | 動かしていない | | {e} |" for n, e in not_run]
    if hs:
        L += ["", f"入りの間（報告だけ）：声まで中央 {hs['to_voice']:.2f}秒・入りの高さ 部屋の音より +{hs['height']:.1f}dB（つなぎ目 {hs['joins']}）。{REF_HEAD}"]
    if cannot:
        L += ["", f"フィラーの谷なし {len(cannot)}（声がつながっていて切れないので、字幕から抜くだけ。08 の remove「フィラー」）"]
    for title, rows in (("未処理（切るか、残す理由を _work/cut_keep.tsv に書く）", todo), ("聴いてもらう（工程11 の聴いてほしい時刻に入れる）", listen), ("理由つきで残した物", kept)):
        if rows:
            L += ["", f"## {title}", "", "| 検査 | 版の時刻 | 素材の秒 | 中身 |" + (" 理由 |" if rows is kept else ""), "|---|---|---|---|" + ("---|" if rows is kept else "")]
            L += [f"| {x['check']} | {x['tl']} | {x['src'] if x['src'] is not None else ''} | {str(x['text']).replace('|', '｜')} |" + (f" {x['why']} |" if rows is kept else "") for x in rows]
    base = os.path.join(W, f"cut_list_{tag}")
    open(base + ".md", "w", encoding="utf-8").write("\n".join(L) + "\n")
    with open(base + ".tsv", "w", encoding="utf-8") as f:
        f.write("状態\t検査\t版の時刻\t素材の秒\t中身\t理由\n")
        for state_name, rows in (("未処理", todo), ("聴いてもらう", listen), ("残す", kept)):
            for x in rows:
                f.write("\t".join([state_name, x["check"], str(x["tl"]), str(x["src"]), str(x["text"]).replace("\t", " "), x.get("why") or ""]) + "\n")
    json.dump({"ok": ok, "stage": "before_build" if a.before_build else "all", "unresolved": len(todo), "not_run": [n for n, _ in not_run],
               "cuts_mtime": cuts_mtime, "checked_at": time.strftime("%Y-%m-%d %H:%M"), "counts": {n: t for n, _, _, t in table}, "listen": len(listen), "head": hs},
              open(base + ".json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print(f"カットの検査：{'通った' if ok else '止める'}（未処理 {len(todo)}・聴いてもらう {len(listen)}・動かしていない {len(not_run)}）")
    for n, c, k, t in table:
        print(f"  {n}：出た {c}・残す {k}・未処理 {t}")
    for n, e in not_run:
        print(f"  {n}：動かしていない（{e}）")
    if hs:
        print(f"  入りの間：声まで中央 {hs['to_voice']:.2f}秒・入りの高さ +{hs['height']:.1f}dB（{REF_HEAD}）")
    print("一覧 →", base + ".md")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
