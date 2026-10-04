#!/usr/bin/env python3
"""テロップ見本集を、Premiereで元の完成版と見比べて確認する（画像の書き出し）。

  1. 見本集プロジェクトを Premiere で開く（開いていなければ）
  2. 見本集シーケンスと、元の完成版の本編シーケンスから、同じ相対時刻の画像を書き出す
  3. 見本ごとに「元／見本」を並べた画像と、全体の一覧画像を作る
  4. 場面見本（全トラック複製）は、元との画素の差を数値で出す
Premiere の操作は小分けにして、1回ごとにユーザーが見ていたシーケンスへ戻す。

使い方:
  python3 verify_library.py --library 見本/テロップ見本集.prproj --reference 完成.prproj --ref-sequence 本編 --out 見本/確認
  python3 verify_library.py ... --compare-only     （書き出し済みの画像で比較だけやり直す）

出力（--out の下）:
  frames/      … 書き出した画像（<ID>_<相対フレーム>_元.png / _見本.png）
  並べ/<ID>.jpg … 相対フレームごとに「元｜見本｜差（4倍に強調）」を並べた画像
  一覧_<区画>_<番号>.jpg … 差の大きい順に「元｜見本」の縮小を並べた一覧
  差分.json    … 見本ごとの差（平均の差、差が30を超える画素の割合%）
テロップ型・画面効果の見本は、元の場面にあった他のテロップや画像を持たないので、その分の差は出る。
場面見本（D）は全トラックの複製なので、差はほぼ0になるはず。
"""
import argparse
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from premiere_bridge import run, timecode, seconds_to_frame, preflight  # noqa: E402

EXPORT_JS = r'''
(function(){
  try {
    function __byPath(pp){ for (var z=0;z<app.projects.numProjects;z++){ if (String(app.projects[z].path)===pp) return app.projects[z]; } return null; }
    var prevPath = String(app.project.path), prevSeq = null; try { prevSeq = app.project.activeSequence; } catch (e0) {}
    var prevId = prevSeq ? String(prevSeq.sequenceID) : null;
    var target = null;
    for (var i = 0; i < app.projects.numProjects; i++) { try { if (String(app.projects[i].name) === __PROJECT__) target = app.projects[i]; } catch (e1) {} }
    if (!target) return JSON.stringify({error: "project not open: " + __PROJECT__});
    var seq = null;
    for (var j = 0; j < target.sequences.numSequences; j++) {
      var sq = target.sequences[j];
      if (String(sq.name) === __SEQUENCE__ && (!seq || sq.videoTracks.numTracks > seq.videoTracks.numTracks)) seq = sq;
    }
    if (!seq) return JSON.stringify({error: "sequence not found"});
    target.openSequence(seq.sequenceID);
    app.enableQE();
    var qs = qe.project.getActiveSequence();
    var jobs = __JOBS__, n = 0, errs = [];
    for (var k = 0; k < jobs.length; k++) { try { qs.exportFramePNG(jobs[k][0], jobs[k][1]); n++; } catch (e2) { errs.push(String(e2)); } }
    // 元のプロジェクトの中で戻す（コピーした版どうしはシーケンスの ID が同じなので、全プロジェクトから探すと別の版へ戻る）
    if (prevId) { var pj0 = __byPath(prevPath); try { if (pj0) pj0.openSequence(prevId); } catch (e3) {} }
    return JSON.stringify({exported: n, errs: errs.slice(0, 3)});
  } catch (e) { return JSON.stringify({err: String(e), line: e.line}); }
})();
'''


def open_name(name):
    """Premiere が持っているプロジェクト名（濁点が分かれた形 NFD のことがある）に合わせる。開いていなければ元の名前のまま。"""
    import unicodedata
    names = run('(function(){ var a=[]; for (var i=0;i<app.projects.numProjects;i++) a.push(String(app.projects[i].name)); return JSON.stringify(a); })();')
    for n in names if isinstance(names, list) else []:
        if unicodedata.normalize("NFC", n) == unicodedata.normalize("NFC", name):
            return n
    return name


def export(project, sequence, jobs, batch=120):
    project = open_name(project)
    done = 0
    for i in range(0, len(jobs), batch):
        chunk = jobs[i:i + batch]
        js = (EXPORT_JS.replace("__PROJECT__", json.dumps(project, ensure_ascii=False))
              .replace("__SEQUENCE__", json.dumps(sequence, ensure_ascii=False))
              .replace("__JOBS__", json.dumps(chunk, ensure_ascii=False)))
        r = run(js, timeout=900)
        if not isinstance(r, dict) or "exported" not in r:
            raise RuntimeError(f"書き出し失敗: {r}")
        done += r["exported"]
        print(f"  {project} {done}/{len(jobs)}", flush=True)
    return done


def compare(out_dir, idx, jobs, threshold=30):
    """書き出した画像の組を比べ、並べ画像・一覧・差分.json を作る。"""
    from PIL import Image, ImageChops, ImageDraw, ImageStat
    section = {s["id"]: s["section"] for s in idx["samples"]}
    pairs = defaultdict(list)
    for (_, lib_png), (_, ref_png) in zip(jobs["lib_jobs"], jobs["ref_jobs"]):
        sid, off = os.path.basename(lib_png)[:-len("_見本")].rsplit("_", 1)
        pairs[sid].append((int(off), ref_png + ".png", lib_png + ".png"))
    sheets = os.path.join(out_dir, "並べ")
    os.makedirs(sheets, exist_ok=True)
    W, H = 640, 360
    result, thumbs = {}, {}
    for sid, rows in pairs.items():
        stats, strips = [], []
        for off, rp, lp in sorted(rows):
            if not (os.path.exists(rp) and os.path.exists(lp)):
                stats.append({"offset": off, "missing": True})
                continue
            ref, lib = Image.open(rp).convert("RGB"), Image.open(lp).convert("RGB")
            d = ImageChops.difference(ref, lib).convert("L")
            over = sum(d.histogram()[threshold:]) / (d.size[0] * d.size[1]) * 100
            stats.append({"offset": off, "mean_diff": round(ImageStat.Stat(d).mean[0], 3), f"pixels_over_{threshold}_pct": round(over, 3)})
            strip = Image.new("RGB", (W * 3, H + 24), (24, 24, 24))
            strip.paste(ref.resize((W, H)), (0, 24))
            strip.paste(lib.resize((W, H)), (W, 24))
            strip.paste(d.point(lambda v: min(255, v * 4)).convert("RGB").resize((W, H)), (W * 2, 24))
            ImageDraw.Draw(strip).text((8, 6), f"{sid} +{off}f   original | sample | diff x4   over{threshold}: {over:.2f}%", fill=(230, 230, 230))
            strips.append(strip)
            thumbs.setdefault(sid, (ref.resize((320, 180)), lib.resize((320, 180))))
        if strips:
            sheet = Image.new("RGB", (W * 3, sum(s.size[1] for s in strips)))
            y = 0
            for s in strips:
                sheet.paste(s, (0, y))
                y += s.size[1]
            sheet.save(os.path.join(sheets, f"{sid}.jpg"), quality=82)
        vals = [x[f"pixels_over_{threshold}_pct"] for x in stats if "missing" not in x]
        result[sid] = {"section": section.get(sid), "max_pct": max(vals) if vals else None, "offsets": stats}
    # 一覧（区画ごと、差の大きい順）
    for sec in sorted({v["section"] for v in result.values()}):
        ids = sorted([k for k, v in result.items() if v["section"] == sec and k in thumbs], key=lambda k: -(result[k]["max_pct"] or 0))
        for page in range(0, len(ids), 32):
            chunk = ids[page:page + 32]
            img = Image.new("RGB", (4 * 650, ((len(chunk) + 3) // 4) * 206), (16, 16, 16))
            for i, sid in enumerate(chunk):
                x, y = (i % 4) * 650, (i // 4) * 206
                img.paste(thumbs[sid][0], (x, y + 22))
                img.paste(thumbs[sid][1], (x + 322, y + 22))
                ImageDraw.Draw(img).text((x + 4, y + 5), f"{sid}  max over{threshold}: {result[sid]['max_pct']:.2f}%", fill=(230, 230, 230))
            img.save(os.path.join(out_dir, f"一覧_{sec}_{page // 32 + 1:02d}.jpg"), quality=80)
    summary = {}
    for sec in sorted({v["section"] for v in result.values()}):
        vs = [v["max_pct"] for v in result.values() if v["section"] == sec and v["max_pct"] is not None]
        summary[sec] = {"samples": len(vs), "zero": sum(1 for v in vs if v == 0), "under_1pct": sum(1 for v in vs if 0 < v < 1),
                        "1_to_5pct": sum(1 for v in vs if 1 <= v < 5), "over_5pct": sum(1 for v in vs if v >= 5)}
    json.dump({"threshold": threshold, "summary": summary, "samples": result},
              open(os.path.join(out_dir, "差分.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for sec, s in summary.items():
        print(f"  {sec}: {s['samples']}件  差なし {s['zero']} / 1%未満 {s['under_1pct']} / 1〜5% {s['1_to_5pct']} / 5%以上 {s['over_5pct']}")
    return summary


def structure(lib_path, idx, ref_path, ref_sequence, out_dir):
    """Premiereなしで、見本ごとに元の同じ場所とクリップ単位で突き合わせる（reproduce.py check と同じ比べ方）。
    見本の区間（見本集の開始〜終了）と、元の同じ長さの区間（元の開始から）を比べる。
      違い            … 長さ・文字・見た目と動きの指紋・音量・素材の頭の位置のどれかが違う（直すべきもの）
      見本にだけある   … 元の同じ場所にないクリップ（直すべきもの）
      元にだけある     … 見本に入れていない周りの要素（他のテロップ・画像など）。場面見本（D）では直すべきもの
      フォント置き換え … HiraKakuStdN-W8 → HiraginoSans-W8 だけの違い（想定内）"""
    from native_prproj import Prproj
    from reproduce import Timeline, compare_clips

    def fr(sec):
        return int(round(sec * 30000 / 1001))
    lpj, rpj = Prproj.load(lib_path), Prproj.load(ref_path)
    lt = Timeline(lpj, lpj.sequence(idx["sequence"]), False)
    rt = Timeline(rpj, rpj.sequence(ref_sequence), True)
    result, summary = {}, defaultdict(lambda: {"samples": 0, "ok": 0, "problems": 0})
    for s in idx["samples"]:
        l0, l1 = fr(s["start"]), fr(s["end"])
        r0 = fr(s["source"]["start"])
        rows = compare_clips(rt.window(r0, r0 + (l1 - l0)), lt.window(l0, l1))
        problems = [r for r in rows if r["diff"] or r.get("only") == "比較先" or (s["section"] == "D" and r.get("only") == "元")]
        result[s["id"]] = {"section": s["section"], "clips": len(rows),
                           "same": sum(1 for r in rows if not r["diff"] and "only" not in r),
                           "font_swap_only": sum(1 for r in rows if r.get("note") and not r["diff"]),
                           "only_in_original": sum(1 for r in rows if r.get("only") == "元"),
                           "problems": problems}
        sm = summary[s["section"]]
        sm["samples"] += 1
        sm["ok" if not problems else "problems"] += 1
    out = {"library": os.path.basename(lib_path), "reference": os.path.basename(ref_path), "summary": summary, "samples": result}
    os.makedirs(out_dir, exist_ok=True)
    json.dump(out, open(os.path.join(out_dir, "構造チェック.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for sec in sorted(summary):
        print(f"  {sec}: {summary[sec]['samples']}件  問題なし {summary[sec]['ok']} / 問題あり {summary[sec]['problems']}")
    for sid, r in result.items():
        for p in r["problems"][:3]:
            print(f"    {sid} {p['track']} +{p['sec']}秒 {p['name']}: {' / '.join(p['diff']) or ('見本にだけある' if p.get('only') == '比較先' else '元にだけある')}")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--library", required=True)
    ap.add_argument("--reference", required=True)
    ap.add_argument("--ref-sequence", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--offsets", default="2,6,14")
    ap.add_argument("--compare-only", action="store_true", help="書き出さず、既にある画像で比較だけする")
    ap.add_argument("--structure", action="store_true",
                    help="Premiereを使わず、.prproj の中身をクリップ単位で元と突き合わせる（--reference は .prproj のパス）")
    a = ap.parse_args()
    if a.structure:
        lib_path = os.path.abspath(a.library)
        idx = json.load(open(os.path.splitext(lib_path)[0] + "_目次.json", encoding="utf-8"))
        structure(lib_path, idx, a.reference, a.ref_sequence, os.path.abspath(a.out))
        return
    lib_path = os.path.abspath(a.library)
    lib_name = os.path.basename(lib_path)
    ref_name = os.path.basename(a.reference)
    idx = json.load(open(os.path.splitext(lib_path)[0] + "_目次.json", encoding="utf-8"))
    frames_dir = os.path.join(os.path.abspath(a.out), "frames")  # 書き出し先は絶対パス（相対パスだと Premiere は何も書かずに書き出したと返す）
    os.makedirs(frames_dir, exist_ok=True)
    offs = [int(x) for x in a.offsets.split(",")]
    if a.compare_only:
        jobs = json.load(open(os.path.join(a.out, "jobs.json"), encoding="utf-8"))
        compare(os.path.abspath(a.out), idx, jobs)
        return
    print("Premiere:", preflight())

    # 見本集を開く（開いていなければ）
    r = run('(function(){ for (var i=0;i<app.projects.numProjects;i++){ if (String(app.projects[i].name)===' + json.dumps(open_name(lib_name), ensure_ascii=False)
            + ') return "open"; } var prev=null; var pp=String(app.project.path); try{prev=app.project.activeSequence;}catch(e){} app.openDocument(' + json.dumps(lib_path, ensure_ascii=False)
            + ', true, true, true, true); try{ if(prev){ for (var z=0;z<app.projects.numProjects;z++){ if (String(app.projects[z].path)===pp) app.projects[z].openSequence(String(prev.sequenceID)); } } }catch(e2){} return "opened"; })();', timeout=600)
    print("見本集:", r)

    lib_jobs, ref_jobs = [], []
    for s in idx["samples"]:
        if s["section"] == "C":
            continue
        length = s["end"] - s["start"]
        rel = [o for o in offs if o / 29.97 < length] + [int(length * 29.97 / 2)]
        for o in sorted(set(rel)):
            name = f"{s['id']}_{o:03d}"
            lib_jobs.append([timecode(seconds_to_frame(s["start"]) + o), os.path.join(frames_dir, name + "_見本")])
            ref_jobs.append([timecode(seconds_to_frame(s["source"]["start"]) + o), os.path.join(frames_dir, name + "_元")])
    print("書き出し", len(lib_jobs), "×2")
    export(lib_name, idx["sequence"], lib_jobs)
    export(ref_name, a.ref_sequence, ref_jobs)
    jobs = {"lib_jobs": lib_jobs, "ref_jobs": ref_jobs}
    json.dump(jobs, open(os.path.join(a.out, "jobs.json"), "w", encoding="utf-8"), ensure_ascii=False)
    print("比較")
    compare(os.path.abspath(a.out), idx, jobs)
    print("完了")


if __name__ == "__main__":
    main()
