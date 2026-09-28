#!/usr/bin/env python3
"""見本集から、型ID（T＝テロップ型／E＝画面効果／S＝SE）で実物を複製して、新しい場面に置く（再現ツール）。

見本集プロジェクト（見本/テロップ見本集.prproj）のコピーの中で使う。共有物（元クリップ・素材・保存スタイル）が
見本集の中にあるため、編集するシーケンスも同じプロジェクトの中に置く。

使い方（Pythonから）:
  lib = Library("案件/v001/edit.prproj")                 # 見本集のコピー（編集用）
  seq = lib.pj.sequence("編集シーケンス")
  lib.add_telop(seq, "T001", "通常の字幕", start=12.3, duration=1.8, track="V6")
  lib.add_telop(seq, "T015", [["AIを使いこなす習慣⑧"], ["8つの習慣"]], start=20.0)
  lib.add_effect(seq, "E001", start=20.0, duration=3.9, track="V5")
  lib.add_se(seq, "S001", start=20.0, track="A4")
  lib.save("案件/v002/edit.prproj")

デモ（完成版 01:51〜02:30 を、映像・声・BGMだけ元から持ち、装飾はすべて型IDから置き直す）:
  python3 reproduce.py demo --library 見本/テロップ見本集.prproj --out work/reproduce_demo/demo_v001.prproj
  python3 reproduce.py check --project work/reproduce_demo/demo_v001.prproj --reference 見本/_base.prproj --ref-sequence AI使いこなす習慣7選
      … Premiereなしで、元とクリップ単位で突き合わせる（長さ・文字・見た目と動きの指紋・音量・素材の頭の位置）
  python3 reproduce.py verify --project work/reproduce_demo/demo_v001.prproj --out work/reproduce_demo/確認
      … Premiereで画像を書き出して、元（場面見本）と画素で比べる
"""
import argparse
import json
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from native_prproj import Prproj, TPS  # noqa: E402

FRAME_T = 8475667200
FONT_SWAP = [("HiraKakuStdN-W8", "HiraginoSans-W8")]   # build_library.py と同じ（見本集で置き換えたフォント）
HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_TYPES = os.path.join(HERE, "..", "見本", "分類", "types.json")
DEFAULT_INDEX = os.path.join(HERE, "..", "見本", "テロップ見本集_目次.json")


def snap(sec, frame_t=FRAME_T):
    """秒 → フレームの区切りに揃えた ticks（既定は 29.97fps。30fps のシーケンスには frame_t=8467200000）"""
    return int(round(sec * TPS / frame_t)) * frame_t


class Library:
    def __init__(self, project_path, types_path=DEFAULT_TYPES, index_path=DEFAULT_INDEX):
        self.pj = Prproj.load(project_path)
        self.types = json.load(open(types_path, encoding="utf-8"))
        self.index = json.load(open(index_path, encoding="utf-8"))
        self.lib_seq = self.pj.sequence(self.index["sequence"])
        self.samples = {s["id"]: s for s in self.index["samples"]}
        self.type_by_id = {t["id"]: t for t in self.types["telop_types"]}
        self.size_log = []          # add_telop で大きさを決めた記録（06_テロップの大きさ.yaml）
        self._size_tools = None

    # --- 見本の実物を探す ---
    def sample_item(self, sample_id):
        s = self.samples[sample_id]
        track = s["source"].get("track")
        return self.pj.item_at(self.lib_seq, track, s["start"], tol=0.02), track

    def type_texts(self, type_id):
        """型の見本の文字（レイヤーごと・ランごと）。差し替えの形の確認に使う。"""
        item, _ = self.sample_item(type_id)
        return self.pj.item_texts(item)

    # --- 置く ---
    def _texts(self, type_id, texts):
        shape = self.type_texts(type_id)
        if isinstance(texts, str):
            if len(shape) != 1 or len(shape[0]) != 1:
                raise ValueError(f"{type_id} は文字レイヤー／ランが複数あります。形に合わせて渡してください: {shape}")
            return [[texts]]
        return texts

    def add_telop(self, seq, type_id, texts, start, duration=None, track=None, size="auto", pattern=None):
        """size: "auto"（06_テロップの大きさ.yaml の決まりで文字の大きさを決める。既定）／ None（見本の大きさのまま）／
        数（その大きさ。文字の大きさ×テロップ全体の拡大率）。
        pattern: パターンID。スタイルが同じでも大きさが違うとき（シュールの再現シーン＝"P16"）に渡す。"""
        item, src_track = self.sample_item(type_id)
        ft = self.pj.frame_ticks(seq)       # 置き先のシーケンスのフレーム（29.97fps・30fps など）に揃える
        dur_t = snap(duration, ft) if duration is not None else None
        new = self.pj.clone_item(item, seq, track or src_track, start_ticks=snap(start, ft), duration_ticks=dur_t,
                                 texts=self._texts(type_id, texts))
        if size is not None:
            self._size(new, type_id, size, pattern)
        return new

    def _size(self, item, type_id, size, pattern):
        import telop_size
        if self._size_tools is None:
            self._size_tools = (telop_size.load_rules(), telop_size.Fonts())
        rules, fonts = self._size_tools
        styles = self.type_by_id[type_id]["styles"] if type_id in self.type_by_id else []
        if size == "auto":
            info = telop_size.auto_size(self.pj, item, styles, pattern, rules, fonts)
        else:
            m = telop_size.measure(self.pj, item, fonts)
            self.pj.scale_font_sizes(item, float(size) / m["size"])
            info = {"rule": "指定", "size_before": round(m["size"], 1), "size_after": float(size), "notes": []}
        info["type"] = type_id
        self.size_log.append(info)
        return info

    def add_effect(self, seq, effect_id, start, duration, track=None):
        item, src_track = self.sample_item(effect_id)
        ft = self.pj.frame_ticks(seq)
        return self.pj.clone_item(item, seq, track or src_track, start_ticks=snap(start, ft), duration_ticks=snap(duration, ft))

    def add_se(self, seq, se_id, start, track=None, duration=None):
        """duration を渡すと、その長さで切る（続けて鳴らすとき、前の音を次の音の手前で切る）"""
        item, src_track = self.sample_item(se_id)
        ft = self.pj.frame_ticks(seq)
        return self.pj.clone_item(item, seq, track or src_track, start_ticks=snap(start, ft),
                                  duration_ticks=snap(duration, ft) if duration is not None else None)

    def save(self, path):
        info = self.pj.check_binaries()
        if any(info.values()):
            raise RuntimeError(f"共有バイナリの決まりに違反しています: {info}")
        self.pj.save(path)


# ---------- デモ ----------
CAMERA = re.compile(r"^(IMG_|BCVX|LCAU)|\.(mov|mp4)$", re.I)


def demo(library_path, out_path, scene_id="D02"):
    lib = Library(library_path)
    pj, seq = lib.pj, lib.lib_seq
    scene = lib.samples[scene_id]
    ws, we = snap(scene["source"]["start"]), snap(scene["source"]["end"])
    s0, s1 = snap(scene["start"]), snap(scene["end"])
    # 型の対応表（完成版のトラック・開始秒 → 型ID）
    t_of, e_of, s_of = {}, {}, {}
    for t in lib.types["telop_types"]:
        for m in t["members"]:
            t_of[(m["track"], snap(m["start"]))] = t["id"]
    for e in lib.types["screen_effects"]:
        for m in e["members"]:
            e_of[(m["track"], snap(m["start"]))] = e["id"]
    for s in lib.types["se"]:
        for m in s["members"]:
            s_of[(m["track"], snap(m["start"]))] = s["id"]
    # 見本集の最後の後ろにデモを置く
    end_t = max(pj.span(it)[1] for _, tr in pj.tracks(seq) for it in pj.items(tr))
    base_t = (end_t // FRAME_T + 60) * FRAME_T
    log = {"base": 0, "telop": [], "effect": [], "se": [], "unmatched": []}
    for tname, tr in pj.tracks(seq):
        for it in pj.items(tr):
            a, b = pj.span(it)
            if not (s0 <= a < s1):
                continue
            rel = a - s0
            orig_start = ws + rel
            sub = pj.ref(it.find("ClipTrackItem/SubClip"))
            name = unicodedata.normalize("NFC", sub.findtext("Name") or "") if sub is not None else ""
            key = (tname, orig_start)
            # 映像・声・BGMは場面見本から持ってくる（装飾ではないもの）
            if (tname in ("V1", "V2", "V3", "V4") and CAMERA.search(name)) or tname == "A1" or "メインテーマ" in name or "BGM" in name:
                pj.clone_item(it, seq, tname, start_ticks=base_t + rel, duration_ticks=b - a)
                log["base"] += 1
            elif key in t_of:
                texts = pj.item_texts(it)
                lib.add_telop(seq, t_of[key], texts, start=(base_t + rel) / TPS, duration=(b - a) / TPS, track=tname,
                              size=None)   # デモは完成版の再現なので、見本（＝元）の大きさのまま
                log["telop"].append(f"{tname} {orig_start / TPS:.2f} {t_of[key]} {' / '.join(''.join(r) for r in texts)[:24]}")
            elif key in e_of:
                lib.add_effect(seq, e_of[key], start=(base_t + rel) / TPS, duration=(b - a) / TPS, track=tname)
                log["effect"].append(f"{tname} {orig_start / TPS:.2f} {e_of[key]}")
            elif key in s_of:
                lib.add_se(seq, s_of[key], start=(base_t + rel) / TPS, track=tname, duration=(b - a) / TPS)
                log["se"].append(f"{tname} {orig_start / TPS:.2f} {s_of[key]}")
            else:
                log["unmatched"].append(f"{tname} {orig_start / TPS:.2f} {name[:24]}")
    lib.save(out_path)
    rec = {"scene": scene_id, "source": scene["source"], "demo_start": round(base_t / TPS, 4),
           "demo_end": round((base_t + s1 - s0) / TPS, 4), "log": log}
    json.dump(rec, open(os.path.splitext(out_path)[0] + "_記録.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"デモ {scene_id}: 映像・声・BGM {log['base']} / テロップ {len(log['telop'])} / 画面効果 {len(log['effect'])} / "
          f"SE {len(log['se'])} / 型なし {len(log['unmatched'])} → {out_path}（デモ開始 {rec['demo_start']}秒）")
    return rec


def verify_demo(project_path, record_path, out_dir, step_frames=10):
    """デモ（型IDから組み直した区間）と場面見本（元の全トラック複製）を、同じ相対時刻で書き出して画素の差を測る。
    Premiere でデモのプロジェクトを開ける状態で実行する（MCP Bridge 経由）。"""
    from premiere_bridge import run, timecode, seconds_to_frame, preflight
    from PIL import Image, ImageChops, ImageStat
    print("Premiere:", preflight())
    rec = json.load(open(record_path, encoding="utf-8"))
    idx = json.load(open(DEFAULT_INDEX, encoding="utf-8"))
    scene = {s["id"]: s for s in idx["samples"]}[rec["scene"]]
    os.makedirs(out_dir, exist_ok=True)
    length = int((rec["demo_end"] - rec["demo_start"]) * 30000 / 1001)
    jobs = []
    for o in range(0, length, step_frames):
        jobs.append([timecode(seconds_to_frame(rec["demo_start"]) + o), os.path.join(out_dir, f"{o:05d}_再現")])
        jobs.append([timecode(seconds_to_frame(scene["start"]) + o), os.path.join(out_dir, f"{o:05d}_元")])
    name = os.path.basename(project_path)
    js = r'''(function(){ try {
      var prev=null; try{prev=app.project.activeSequence;}catch(e0){}
      var target=null; for (var i=0;i<app.projects.numProjects;i++){ try{ if (String(app.projects[i].path)===__PATH__) target=app.projects[i]; }catch(e1){} }
      if (!target) { app.openDocument(__PATH__, true, true, true, true); for (var j=0;j<app.projects.numProjects;j++){ try{ if (String(app.projects[j].path)===__PATH__) target=app.projects[j]; }catch(e2){} } }
      if (!target) return JSON.stringify({error:"could not open"});
      var seq=null; for (var k=0;k<target.sequences.numSequences;k++){ var sq=target.sequences[k]; if (String(sq.name)==="テロップ見本集" && (!seq || sq.videoTracks.numTracks>seq.videoTracks.numTracks)) seq=sq; }
      target.openSequence(seq.sequenceID);
      if (String(app.project.path)!==__PATH__) return JSON.stringify({error:"active changed"});
      app.enableQE(); var qs=qe.project.getActiveSequence(); var jobs=__JOBS__, n=0;
      for (var m=0;m<jobs.length;m++){ try { qs.exportFramePNG(jobs[m][0], jobs[m][1]); n++; } catch(e3) {} }
      try{ if(prev){ for (var a=0;a<app.projects.numProjects;a++){ var pr=app.projects[a]; for (var b=0;b<pr.sequences.numSequences;b++){ if (String(pr.sequences[b].sequenceID)===String(prev.sequenceID)) pr.openSequence(String(prev.sequenceID)); } } } }catch(e4){}
      return JSON.stringify({exported:n});
    } catch(e) { return JSON.stringify({err:String(e)}); } })();'''
    js = js.replace("__PATH__", json.dumps(os.path.abspath(project_path), ensure_ascii=False)).replace("__JOBS__", json.dumps(jobs, ensure_ascii=False))
    r = run(js, timeout=1800)
    print("書き出し:", r)
    rows = []
    for o in range(0, length, step_frames):
        a = os.path.join(out_dir, f"{o:05d}_再現.png")
        b = os.path.join(out_dir, f"{o:05d}_元.png")
        if not (os.path.exists(a) and os.path.exists(b)):
            continue
        ia, ib = Image.open(a).convert("RGB"), Image.open(b).convert("RGB")
        d = ImageChops.difference(ia, ib).convert("L")
        rows.append({"frame": o, "mean_diff": round(ImageStat.Stat(d).mean[0], 3),
                     "pixels_over_30_pct": round(sum(d.histogram()[30:]) / (ia.size[0] * ia.size[1]) * 100, 3)})
    same = sum(1 for x in rows if x["pixels_over_30_pct"] == 0)
    summary = {"frames": len(rows), "identical_frames": same, "max_pixels_over_30_pct": max((x["pixels_over_30_pct"] for x in rows), default=None), "rows": rows}
    json.dump(summary, open(os.path.join(out_dir, "差分.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"比較 {len(rows)}フレーム：完全一致 {same}、差が最大の画素割合 {summary['max_pixels_over_30_pct']}%")
    return summary


class Timeline:
    """シーケンスのクリップ一覧（区間で切り出して比べるため）。見た目と動きの指紋は type_catalog の分類と同じ作り方。"""

    def __init__(self, pj, seq, enabled_only):
        from type_catalog import Catalog
        self.pj, self.cat, self._info, self._keys = pj, Catalog(pj), {}, {}
        self.clips = []
        for tn, tr in pj.tracks(seq):
            for it in pj.items(tr):
                if enabled_only and it.find("ClipTrackItem/IsMuted") is not None:
                    continue
                s, e = pj.span(it)
                self.clips.append((tn, it, int(round(s / FRAME_T)), int(round(e / FRAME_T))))

    def info(self, tn, it):
        key = id(it)
        if key not in self._info:
            pj = self.pj
            sub = pj.ref(it.find("ClipTrackItem/SubClip"))
            clip = pj.ref(sub.find("Clip")) if sub is not None and sub.find("Clip") is not None else None
            holder = pj.range_holder(clip)
            s, e = pj.span(it)
            # 素材上の長さ（OutPoint − InPoint）とタイムライン上の長さの差。完成版でも ±1フレームの揺れはふつうにある。
            # 複製で in/out を直し損ねると、ここが秒単位で食い違う
            tail = (int(holder.findtext("OutPoint")) - int(holder.findtext("InPoint"))) - (e - s) if holder is not None else 0
            self._info[key] = {
                "name": unicodedata.normalize("NFC", sub.findtext("Name") or "") if sub is not None else "",
                "texts": pj.item_texts(it) if tn.startswith("V") else [],
                "gain": clip.findtext("Gain") if clip is not None else None,
                "inpoint": int(holder.findtext("InPoint")) if holder is not None else 0,
                "tail": tail,
            }
        return self._info[key]

    def keys(self, it, head):
        """見た目と動きの指紋。キーフレームは素材の時刻で記録されているので、区間の頭で見えている素材の位置（head）
        からの時刻で比べる（途中から切り出したクリップでも、同じ動きなら同じ指紋になる）。"""
        import hashlib
        from type_catalog import GRAPHIC
        key = (id(it), head)
        if key not in self._keys:
            comps = []
            chain = self.pj.ref(it.find("ClipTrackItem/ComponentOwner/Components"))
            if chain is not None:
                for c in chain.findall("ComponentChain/Components/Component"):
                    ce = self.pj.ref(c)
                    if ce is not None:
                        comps.append(self.cat.component(ce, head))
            look = json.dumps([(c["match"], c["params"]) for c in comps if c["match"] in GRAPHIC], sort_keys=True, default=str)
            anim = json.dumps([(c["match"], c["params"]) for c in comps if c["match"] not in GRAPHIC], sort_keys=True, default=str)
            look_font = look
            for old, new in FONT_SWAP:
                look_font = look_font.replace(new, old)
            self._keys[key] = {
                "look": hashlib.sha1(look.encode()).hexdigest()[:10],
                "look_font": hashlib.sha1(look_font.encode()).hexdigest()[:10],   # フォントの置き換えを戻した指紋
                "anim": hashlib.sha1(anim.encode()).hexdigest()[:10],
                "graphic": any(c["match"] in GRAPHIC for c in comps),
            }
        return self._keys[key]

    def window(self, w0, w1):
        """区間 [w0, w1)（フレーム）に掛かるクリップを、(トラック, 区間内の開始フレーム) で引けるようにする"""
        out = {}
        for tn, it, fs, fe in self.clips:
            a0, b0 = max(fs, w0), min(fe, w1)
            if b0 - a0 < 1:
                continue
            x = dict(self.info(tn, it))
            x["len"] = b0 - a0
            x["head"] = x["inpoint"] + (a0 - fs) * FRAME_T   # 区間の頭で見えている素材の位置（ticks）
            x.update(self.keys(it, x["head"]))
            out[(tn, a0 - w0)] = x
        return out


def compare_clips(ref_items, other_items):
    """同じ (トラック, 相対フレーム) のクリップどうしを比べる。行ごとに違い（diff）を付けて返す。
    片方にしかないものは only に "元" / "比較先" を入れる。"""
    rows = []
    for key in sorted(set(ref_items) | set(other_items), key=lambda k: (k[0][0], int(k[0][1:]), k[1])):
        a, b = ref_items.get(key), other_items.get(key)
        row = {"track": key[0], "sec": round(key[1] * 1001 / 30000, 3), "name": (a or b)["name"][:30], "diff": []}
        if a is None or b is None:
            row["only"] = "比較先" if a is None else "元"
        else:
            if a["len"] != b["len"]:
                row["diff"].append(f"長さ {a['len']}→{b['len']}フレーム")
            if a["texts"] != b["texts"]:
                row["diff"].append(f"文字 {a['texts']} → {b['texts']}")
            if a["look"] != b["look"]:
                if a["look_font"] == b["look_font"]:
                    row["note"] = "フォント置き換えのみ（想定内）"
                else:
                    row["diff"].append("見た目の指紋")
            if a["anim"] != b["anim"]:
                row["diff"].append("動き・エフェクトの指紋")
            if a["gain"] != b["gain"]:
                row["diff"].append(f"音量 {a['gain']}→{b['gain']}")
            if not a["graphic"] and a["head"] != b["head"]:
                row["diff"].append(f"素材の頭 {round((b['head'] - a['head']) / TPS, 3)}秒ずれ")
            if not a["graphic"] and abs(a["tail"] - b["tail"]) > 2 * FRAME_T:
                row["diff"].append(f"素材の終わりの位置 {round((b['tail'] - a['tail']) / TPS, 3)}秒ずれ")
            if a["name"] != b["name"] and not a["graphic"]:
                row["diff"].append(f"素材名 {a['name']}→{b['name']}")
        rows.append(row)
    return rows


def check_demo(project_path, record_path, reference_path, ref_sequence, out_path=None):
    """デモの区間を、完成版の同じ区間とクリップ単位で突き合わせる（Premiereなし）。
    同じトラック・同じ相対フレームにあるクリップどうしで、長さ・名前・文字・見た目と動きの指紋（type_catalog の分類と同じ）・
    音量・素材の頭の位置を比べる。"""
    rec = json.load(open(record_path, encoding="utf-8"))
    n = int(round((rec["demo_end"] - rec["demo_start"]) * 30000 / 1001))
    d0 = int(round(rec["demo_start"] * 30000 / 1001))
    r0 = int(round(rec["source"]["start"] * 30000 / 1001))
    dpj = Prproj.load(project_path)
    demo_items = Timeline(dpj, dpj.sequence(DEMO_SEQUENCE), False).window(d0, d0 + n)
    rpj = Prproj.load(reference_path)
    ref_items = Timeline(rpj, rpj.sequence(ref_sequence), True).window(r0, r0 + n)
    rows = compare_clips(ref_items, demo_items)
    for r in rows:
        if "only" in r:
            r["diff"].append("デモにない" if r["only"] == "元" else "元にない")
    same = sum(1 for r in rows if not r["diff"])
    summary = {"project": os.path.basename(project_path), "reference": os.path.basename(reference_path),
               "window": [rec["source"]["start"], rec["source"]["end"]], "clips": len(rows), "same": same,
               "different": [r for r in rows if r["diff"]]}
    if out_path:
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        json.dump(summary, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"クリップ {len(rows)}：元と同じ {same}、違う {len(rows) - same}")
    for r in summary["different"]:
        print(f"  {r['track']} +{r['sec']}秒 {r['name']}: {' / '.join(r['diff'])}")
    return summary


DEMO_SEQUENCE = "テロップ見本集"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("demo")
    d.add_argument("--library", required=True)
    d.add_argument("--out", required=True)
    d.add_argument("--scene", default="D02")
    v = sub.add_parser("verify")
    v.add_argument("--project", required=True)
    v.add_argument("--out", required=True)
    c = sub.add_parser("check", help="デモを完成版とクリップ単位で突き合わせる（Premiereなし）")
    c.add_argument("--project", required=True)
    c.add_argument("--reference", required=True, help="完成版の .prproj（見本/_base.prproj は同じ中身のコピー）")
    c.add_argument("--ref-sequence", required=True)
    c.add_argument("--out")
    a = ap.parse_args()
    if a.cmd == "demo":
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        demo(a.library, a.out, a.scene)
    elif a.cmd == "verify":
        verify_demo(a.project, os.path.splitext(a.project)[0] + "_記録.json", a.out)
    elif a.cmd == "check":
        check_demo(a.project, os.path.splitext(a.project)[0] + "_記録.json", a.reference, a.ref_sequence, a.out)


if __name__ == "__main__":
    main()
