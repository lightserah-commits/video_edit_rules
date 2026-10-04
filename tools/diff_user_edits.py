#!/usr/bin/env python3
"""ユーザー（小川さん）が Premiere で直した所を読む道具（どの案件でも使える。読むだけ）。
(a) 基準＝AI が最後に組み立てた .prproj と、(b) ユーザーが保存した .prproj（か --live で Premiere で開いているシーケンス）を比べ、表にする：
  - リップルで詰めた・広げた区間（カメラのトラックの素材の位置から見つける。ずれの量）
  - トラックごとのクリップの出入り：消えた・増えた・動いた・切った（一部を消した）
  - V1・V2 のスケールと位置（キーフレーム）・無効にした／有効にした・テロップの文字の違い・素材の位置の違い
  - 穴（基準ではクリップがあったのに今は無い区間）と、増えた区間
使い道：AI が作り直す前に、ユーザーの直しを言葉にして確かめる（記憶「ユーザーの直しの意図を言葉に」）。直しを次の版の組み立てに入れる時の材料。
元：環境設定 v004 で小川さんの 20:16 の保存を調べた scratchpad の run_base.py・dump_live.py・cmp.py・cmp3.py・cmp4.py（9:48 と 16:36 の直し）。

  python3 tools/diff_user_edits.py --base <AI の .prproj> --saved <ユーザーが保存した .prproj> --seq <シーケンス名> [--md 表.md] [--json 結果.json]
  python3 tools/diff_user_edits.py --base <AI の .prproj> --live <Premiere で開いている .prproj のパス> --seq <シーケンス名>
      … Premiere で開いているシーケンスを MCP Bridge で読むだけ（保存しない・前面を切り替えない・開かない）。テロップの文字は比べない
  基準（AI が最後に組み立てたもの）が上書きされている時は、組み立てのスクリプトの出力先を一時的な場所に替えて作り直す（環境設定 v004 の run_base.py）
  --main V1（リップルを見つけるトラック）・--motion V1,V2（スケールと位置を見るトラック）・--show 40（トラックごとに出す行数）
"""
import argparse
import bisect
import json
import os
import re
import sys

ROOT = os.path.expanduser("~/Desktop/video_edit_rules")
sys.path.insert(0, os.path.join(ROOT, "tools"))
from native_prproj import Prproj, TPS  # noqa: E402
from prproj_motion import motion_of, is_muted  # noqa: E402


def tc(t):
    s = t / TPS
    return f"{int(s // 60)}:{s % 60:05.2f}"


def named(r, name):
    """クリップの名前：n＝表に出す形（改行は空白に）、nk＝比べる形（空白・改行を除く。Premiere は保存の時に名前の改行を落とす）"""
    name = name or ""
    r["n"] = re.sub(r"[\r\n]+", " ", name).strip()
    r["nk"] = re.sub(r"\s+", "", name)
    return r


# ---------- 読む ----------
def from_prproj(path, seq_name, motion_tracks):
    pj = Prproj.load(path)
    seq = pj.sequence(seq_name)
    ft = pj.frame_ticks(seq)
    out = {}
    for n, tr in pj.tracks(seq):
        rows = []
        for it in pj.items(tr):
            s, e = pj.span(it)
            sc = pj.ref(it.find("ClipTrackItem/SubClip"))
            clip = pj.ref(sc.find("Clip")) if sc is not None and sc.find("Clip") is not None else None
            h = pj.range_holder(clip)
            r = named({"s": s, "e": e, "i": int(h.findtext("InPoint")) if h is not None else None, "mu": is_muted(it)},
                      sc.findtext("Name") if sc is not None else "")
            if n in motion_tracks:
                r["sc"], r["pos"], r["keyed"] = motion_of(pj, it)
            try:
                tx = pj.item_texts(it)
            except Exception:
                tx = []
            if tx:
                r["text"] = "／".join("".join(runs) for runs in tx).replace("\r", "／")
            rows.append(r)
        out[n] = sorted(rows, key=lambda r: r["s"])
    return out, ft


LIVE_JS = r"""
(function () {
  var p = __projectByPath(__PROJ__);
  if (!p) return JSON.stringify({error: "not open", front: String(app.project.name)});
  var seq = null;
  for (var i = 0; i < p.sequences.numSequences; i++) if (__nfc(p.sequences[i].name) === __nfc(__SEQ__)) seq = p.sequences[i];
  if (!seq) return JSON.stringify({error: "no seq"});
  var MOTION = __MOTION__;
  function val(pr) {
    var o = {};
    try { o.tv = pr.isTimeVarying(); } catch (e) {}
    try { var v = pr.getValue(); o.v = (v instanceof Array) ? [v[0], v[1]] : v; } catch (e) { o.v = null; }
    return o;
  }
  var out = {front: String(app.project.name), video: [], audio: []};
  for (var t = 0; t < seq.videoTracks.numTracks; t++) {
    var tr = seq.videoTracks[t], rows = [];
    for (var c = 0; c < tr.clips.numItems; c++) {
      var cl = tr.clips[c];
      var r = {s: cl.start.ticks, e: cl.end.ticks, i: cl.inPoint.ticks, n: String(cl.name), dis: false};
      try { r.dis = cl.disabled; } catch (e) {}
      var want = false;
      for (var w = 0; w < MOTION.length; w++) if (MOTION[w] === t) want = true;
      if (want) {
        for (var m = 0; m < cl.components.numItems; m++) {
          var cp = cl.components[m];
          if (String(cp.matchName) !== "AE.ADBE Motion") continue;
          var pos = val(cp.properties[0]), sc = val(cp.properties[1]);
          r.pos = pos.v; r.sc = sc.v; r.keyed = !!(pos.tv || sc.tv);
          break;
        }
      }
      rows.push(r);
    }
    out.video.push(rows);
  }
  for (var t2 = 0; t2 < seq.audioTracks.numTracks; t2++) {
    var at = seq.audioTracks[t2], ar = [];
    for (var c2 = 0; c2 < at.clips.numItems; c2++) { var ac = at.clips[c2]; ar.push({s: ac.start.ticks, e: ac.end.ticks, i: ac.inPoint.ticks, n: String(ac.name)}); }
    out.audio.push(ar);
  }
  return JSON.stringify(out);
})();
"""


def from_live(proj, seq_name, motion_tracks):
    """Premiere で開いているシーケンスを読むだけ（保存・前面の切り替え・開くことはしない）"""
    import premiere_bridge
    helpers = open(os.path.join(ROOT, "tools", "premiere_helpers.jsx"), encoding="utf-8").read()
    js = helpers + LIVE_JS.replace("__PROJ__", json.dumps(os.path.abspath(proj), ensure_ascii=False)) \
        .replace("__SEQ__", json.dumps(seq_name, ensure_ascii=False)) \
        .replace("__MOTION__", json.dumps([int(t[1:]) - 1 for t in motion_tracks if t.startswith("V")]))
    res = premiere_bridge.run(js, timeout=600)
    if isinstance(res, str):
        res = json.loads(res)
    if res.get("error"):
        raise SystemExit(f"読めない：{res}")
    out = {}
    for kind, tag in (("video", "V"), ("audio", "A")):
        for k, rows in enumerate(res[kind]):
            n = f"{tag}{k + 1}"
            rs = []
            for r in rows:
                d = named({"s": int(r["s"]), "e": int(r["e"]), "i": int(r["i"]), "mu": bool(r.get("dis"))}, r.get("n", ""))
                if "sc" in r and r["sc"] is not None:
                    d["sc"], d["pos"], d["keyed"] = float(r["sc"]), [float(v) for v in r["pos"]], bool(r.get("keyed"))
                elif n in motion_tracks:
                    d["sc"], d["pos"], d["keyed"] = 100.0, [0.5, 0.5], False
                rs.append(d)
            out[n] = sorted(rs, key=lambda r: r["s"])
    return out


# ---------- リップル（カメラのトラックの素材の位置から） ----------
def find_shifts(base, saved):
    """保存のクリップごとに「基準の時刻 − 保存の時刻」（ずれ）を求め、同じずれの続きをまとめる。
    返す：[(保存の開始, 保存の終わり, ずれ)]（ずれ＝基準の時刻 − 保存の時刻。ticks）"""
    by = {}
    for r in base:
        if r["i"] is not None:
            by.setdefault(r["nk"], []).append(r)
    for v in by.values():
        v.sort(key=lambda r: r["i"])
    groups, prev = [], 0
    for u in saved:
        if u["i"] is None or u["nk"] not in by:
            continue
        cands = by[u["nk"]]
        k = bisect.bisect_right([r["i"] for r in cands], u["i"])
        best = None
        for r in cands[:k][::-1][:50]:
            if r["i"] <= u["i"] < r["i"] + (r["e"] - r["s"]):
                d = r["s"] + (u["i"] - r["i"]) - u["s"]
                if best is None or abs(d - prev) < abs(best - prev):
                    best = d
        if best is None:
            continue
        if groups and groups[-1][2] == best:
            groups[-1][1] = u["e"]
        else:
            groups.append([u["s"], u["e"], best])
        prev = best
    return groups


def edits_from(groups):
    """ずれの変わり目 → リップルで詰めた（deleted）・広げた（inserted）区間"""
    out = []
    for g0, g1 in zip(groups, groups[1:]):
        d0, d1 = g0[2], g1[2]
        if d0 == d1:
            continue
        bs, be = g0[1] + d0, g1[0] + d1          # 基準の時刻の、前の続きの終わり・次の続きの始まり
        if d1 > d0:
            out.append({"kind": "詰めた", "saved_at": g1[0], "base_from": g1[0] + d0, "base_to": g1[0] + d1, "amount": d1 - d0})
        else:
            out.append({"kind": "広げた", "saved_at": g0[1], "base_at": bs, "amount": d0 - d1, "base_next": be})
    return out


class Mapper:
    """基準の時刻 → 保存の時刻（リップルの分だけずらす）。詰めた区間に入る所は None"""

    def __init__(self, groups, edits):
        self.groups = groups
        self.cuts = [(e["base_from"], e["base_to"]) for e in edits if e["kind"] == "詰めた"]
        # 基準の時刻での区切り：(基準の開始, ずれ)
        self.marks = sorted((g[0] + g[2], g[2]) for g in groups) or [(0, 0)]
        self.keys = [m[0] for m in self.marks]

    def shift_at(self, b):
        i = bisect.bisect_right(self.keys, b) - 1
        return self.marks[max(0, i)][1]

    def deleted(self, b):
        return any(x <= b < y for x, y in self.cuts)

    def pieces(self, r):
        """基準のクリップ r が、保存ではどうなるはずか（詰めた区間で切って、ずらす）。[(s, e, i)]"""
        segs = [(r["s"], r["e"])]
        for x, y in self.cuts:
            nxt = []
            for s, e in segs:
                if e <= x or s >= y:
                    nxt.append((s, e))
                    continue
                if s < x:
                    nxt.append((s, x))
                if e > y:
                    nxt.append((y, e))
            segs = nxt
        out = []
        for s, e in segs:
            d = self.shift_at(s)
            i = None if r["i"] is None else r["i"] + (s - r["s"])
            out.append((s - d, e - d, i))
        return out


# ---------- 比べる ----------
def cover(rows):
    out = []
    for s, e in sorted((r["s"], r["e"]) for r in rows):
        if out and s <= out[-1][1]:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return out


def minus(a, b):
    """区間の集まり a から b を引く"""
    out = []
    for s, e in a:
        cur = s
        for x, y in b:
            if y <= cur or x >= e:
                continue
            if x > cur:
                out.append([cur, x])
            cur = max(cur, y)
        if cur < e:
            out.append([cur, e])
    return out


def compare_values(n, b, u, motion_tracks, live):
    dif = []
    if n in motion_tracks and "sc" in b and "sc" in u:
        if abs(b["sc"] - u["sc"]) > 0.01:
            dif.append(f"スケール {b['sc']:g}→{u['sc']:.4g}")
        if any(abs(x - y) > 1e-4 for x, y in zip(b["pos"], u["pos"])):
            dif.append(f"位置 {b['pos'][0]:.3f}:{b['pos'][1]:.3f}→{u['pos'][0]:.3f}:{u['pos'][1]:.3f}")
        if u.get("keyed") and not b.get("keyed"):
            dif.append("キーフレームを付けた")
    if b.get("mu") != u.get("mu"):
        dif.append("無効にした" if u.get("mu") else "有効にした")
    if not live and b.get("text", "") != u.get("text", ""):
        dif.append(f"文字「{b.get('text', '')[:30]}」→「{u.get('text', '')[:30]}」")
    return dif


def diff_track(n, base_rows, saved_rows, mapper, motion_tracks, live, ft):
    rows = []                                     # (保存の時刻, 種類, 内容)
    exp, gone_by_ripple = [], []
    for r in base_rows:
        ps = mapper.pieces(r)
        if not ps:
            gone_by_ripple.append(r)
        for s, e, i in ps:
            exp.append(dict(r, s=s, e=e, i=i, base_s=r["s"]))
    ue = list(saved_rows)
    used_u, used_e = set(), set()
    by_se = {}
    for k, u in enumerate(ue):
        by_se.setdefault((u["s"], u["e"]), []).append(k)
    pairs = []
    for j, x in enumerate(exp):                    # 1. 同じ所にある
        for k in by_se.get((x["s"], x["e"]), []):
            if k not in used_u and ue[k]["nk"] == x["nk"]:
                used_u.add(k)
                used_e.add(j)
                pairs.append((x, ue[k], None))
                if x["i"] is not None and ue[k]["i"] is not None and x["i"] != ue[k]["i"]:
                    rows.append((x["s"], "素材の位置", f"{x['n'][:24]} 素材の頭が {(ue[k]['i'] - x['i']) / ft:+.0f}コマ"))
                break
    for j, x in enumerate(exp):                    # 2. 動いた（同じ名前・長さ・素材の位置・文字）
        if j in used_e:
            continue
        for k, u in enumerate(ue):
            if k in used_u or u["nk"] != x["nk"] or (u["e"] - u["s"]) != (x["e"] - x["s"]) or u["i"] != x["i"]:
                continue
            if not live and u.get("text", "") != x.get("text", ""):
                continue
            used_u.add(k)
            used_e.add(j)
            pairs.append((x, u, None))
            rows.append((u["s"], "動いた", f"{x['n'][:24]}{('「' + x['text'][:20] + '」') if x.get('text') else ''} {tc(x['s'])}→{tc(u['s'])}"
                                            f"（{(u['s'] - x['s']) / ft:+.0f}コマ）"))
            break
    for j, x in enumerate(exp):                    # 3. 切った・詰めた（中に入っていて、素材の位置がそろう）
        if j in used_e:
            continue
        inside = [k for k, u in enumerate(ue) if k not in used_u and u["nk"] == x["nk"] and x["s"] <= u["s"] and u["e"] <= x["e"]
                  and (x["i"] is None or u["i"] is None or u["i"] - x["i"] == u["s"] - x["s"])
                  and (live or not x.get("text") or u.get("text", "") == x.get("text", ""))]
        if not inside:
            continue
        used_e.add(j)
        for k in inside:
            used_u.add(k)
            pairs.append((x, ue[k], "piece"))
        got = sum(ue[k]["e"] - ue[k]["s"] for k in inside)
        what = f"{x['n'][:24]}{('「' + x['text'][:20] + '」') if x.get('text') else ''} {tc(x['s'])}〜{tc(x['e'])}"
        cuts = sorted(ue[k]["s"] for k in inside)[1:]
        if got == x["e"] - x["s"]:
            rows.append((x["s"], "切った", f"{what} を {len(inside)}個に（切れ目 " + "、".join(tc(c) for c in cuts) + "）"))
        else:
            holes = minus([[x["s"], x["e"]]], [[ue[k]["s"], ue[k]["e"]] for k in inside])
            rows.append((x["s"], "一部を消した", f"{what} → 残り {len(inside)}個・消した " + "、".join(f"{tc(a)}〜{tc(b)}" for a, b in holes)))
    for j, x in enumerate(exp):                    # 4. 消えた
        if j not in used_e:
            rows.append((x["s"], "消えた", f"{x['n'][:30]}{('「' + x['text'][:24] + '」') if x.get('text') else ''} {tc(x['s'])}〜{tc(x['e'])}"
                                            f"（{(x['e'] - x['s']) / ft:.0f}コマ）"))
    for k, u in enumerate(ue):                     # 5. 増えた
        if k not in used_u:
            rows.append((u["s"], "増えた", f"{u['n'][:30]}{('「' + u['text'][:24] + '」') if u.get('text') else ''} {tc(u['s'])}〜{tc(u['e'])}"
                                            f"（{(u['e'] - u['s']) / ft:.0f}コマ）"))
    for x, u, kind in pairs:                       # 値の違い
        dif = compare_values(n, x, u, motion_tracks, live)
        if dif:
            rows.append((u["s"], "値", f"{tc(u['s'])}〜{tc(u['e'])}（{(u['e'] - u['s']) / ft:.0f}コマ）" + "；".join(dif)))
    holes = minus(cover(exp), cover(ue))
    added = minus(cover(ue), cover(exp))
    return sorted(rows, key=lambda r: (r[0], r[1])), holes, added, gone_by_ripple, len(exp)


def main():
    ap = argparse.ArgumentParser(description="AI の組み立てと、ユーザーが Premiere で直したものを比べて表にする（読むだけ）", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", required=True, help="AI が最後に組み立てた .prproj")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--saved", help="ユーザーが保存した .prproj")
    g.add_argument("--live", help="Premiere で開いている .prproj のパス（開いているシーケンスを読むだけ）")
    ap.add_argument("--seq", required=True, help="シーケンス名")
    ap.add_argument("--main", default="V1", help="リップルを見つけるトラック（既定 V1＝カメラ）")
    ap.add_argument("--motion", default="V1,V2", help="スケールと位置を見るトラック（既定 V1,V2）")
    ap.add_argument("--min-frames", type=int, default=1, help="穴・増えた区間をこれより短いと出さない（既定 1コマ）")
    ap.add_argument("--show", type=int, default=40, help="トラックごとに出す行数")
    ap.add_argument("--md", help="表を Markdown で書く所")
    ap.add_argument("--json", help="結果を JSON で書く所")
    a = ap.parse_args()
    motion = [t.strip() for t in a.motion.split(",") if t.strip()]
    base, ft = from_prproj(a.base, a.seq, motion)
    live = bool(a.live)
    if live:
        saved = from_live(a.live, a.seq, motion)
        src = f"Premiere で開いている {a.live}"
    else:
        saved, _ = from_prproj(a.saved, a.seq, motion)
        src = a.saved
    groups = find_shifts(base.get(a.main, []), saved.get(a.main, []))
    edits = edits_from(groups)
    mapper = Mapper(groups, edits)
    lines = [f"# ユーザーの直し（{a.seq}）", "", f"- 基準（AI の組み立て）：{a.base}", f"- 比べたもの：{src}",
             f"- {'テロップの文字は比べていない（--live）' if live else 'テロップの文字も比べた'}", ""]
    lines += ["## リップル（" + a.main + " の素材の位置から）", ""]
    if not edits:
        lines.append("- なし")
    for e in edits:
        if e["kind"] == "詰めた":
            lines.append(f"- **{tc(e['saved_at'])} で {e['amount'] / ft:.0f}コマ詰めた**（基準の {tc(e['base_from'])}〜{tc(e['base_to'])} を消して、後ろを前へ）")
        else:
            lines.append(f"- **{tc(e['saved_at'])} で {e['amount'] / ft:.0f}コマ広げた**（基準の {tc(e['base_at'])} の後に足した・同じ所を繰り返した）")
    lines += ["", "## トラックごと", "", "| トラック | 基準 | 保存 | リップルで消えるはず | 違い |", "|---|---|---|---|---|"]
    detail, out_json = [], {"base": a.base, "saved": src, "seq": a.seq, "ripple": edits, "tracks": {}}
    names = [n for n in base if n in saved] + [n for n in saved if n not in base]
    for n in names:
        rows, holes, added, gone, n_exp = diff_track(n, base.get(n, []), saved.get(n, []), mapper, motion, live, ft)
        holes = [h for h in holes if h[1] - h[0] >= a.min_frames * ft]
        added = [h for h in added if h[1] - h[0] >= a.min_frames * ft]
        lines.append(f"| {n} | {len(base.get(n, []))} | {len(saved.get(n, []))} | {len(gone)} | {len(rows)}・穴 {len(holes)}・増えた区間 {len(added)} |")
        out_json["tracks"][n] = {"rows": [{"at": tc(t), "kind": k, "what": w} for t, k, w in rows],
                                 "holes": [[tc(x), tc(y), round((y - x) / ft)] for x, y in holes],
                                 "added": [[tc(x), tc(y), round((y - x) / ft)] for x, y in added],
                                 "gone_by_ripple": [{"n": r["n"], "text": r.get("text", ""), "at": tc(r["s"])} for r in gone]}
        if rows or holes or added or gone:
            detail += ["", f"### {n}", ""]
            for t, k, w in rows[:a.show]:
                detail.append(f"- {tc(t)} **{k}** {w}")
            if len(rows) > a.show:
                detail.append(f"- …ほか {len(rows) - a.show}")
            if holes:
                detail.append("- **穴**（基準ではあったのに今は無い）：" + "、".join(f"{tc(x)}〜{tc(y)}（{(y - x) / ft:.0f}コマ）" for x, y in holes[:a.show]))
            if added:
                detail.append("- **増えた区間**：" + "、".join(f"{tc(x)}〜{tc(y)}（{(y - x) / ft:.0f}コマ）" for x, y in added[:a.show]))
            if gone:
                detail.append("- リップルで詰めた区間に入っていて消えたもの：" + "、".join(
                    f"{r['n'][:20]}{('「' + r['text'][:16] + '」') if r.get('text') else ''}" for r in gone[:10]))
    lines += detail
    text = "\n".join(lines)
    print(text)
    if a.md:
        open(a.md, "w", encoding="utf-8").write(text + "\n")
    if a.json:
        json.dump(out_json, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
