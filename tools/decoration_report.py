#!/usr/bin/env python3
"""完成済み Premiere プロジェクト（.prproj）から「装飾の使い方」を逆算するツール。

何が分かるか:
  - どのテロップ（保存スタイル名）のときに、どのSEを、どの音量で鳴らしたか
  - どのテロップのときに寄り／引きのズームを入れたか（カメラ直接・調整レイヤーの両方）
  - どこでBGMを止めたか
  - 演出の間隔（テンポ）

使い方:
  python3 decoration_report.py 完成.prproj --out 出力フォルダ [--sequence シーケンス名]

出力:
  events.csv   … 演出イベント1行ずつ（時刻・話者トラック・本文・スタイル・SE・ズーム・BGM停止・前後の字幕）
  summary.md   … 集計（スタイル×SE、SE×スタイル、スタイル×ズーム、SE系統ごとのBGM停止率、テンポ）
  summary.json … 同じ集計の機械用

注意:
  - 「無効化」したクリップ（Premiereで有効のチェックを外したもの）は除外する。
  - 読むのはプロジェクトの保存値。実際の書き出し映像・音は確認していない。
  - Python 3.9 標準ライブラリのみで動く。
"""
import argparse
import base64
import csv
import gzip
import json
import math
import os
import re
import statistics
import struct
import sys
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict

TPS = 254016000000  # Premiere の1秒あたりの ticks
VIDEO_EXT = re.compile(r"\.(mov|mp4|mxf|avi|m4v)$", re.I)
IMAGE_EXT = re.compile(r"\.(png|jpe?g|psd|gif|tiff?|ai)$", re.I)
AUDIO_EXT = re.compile(r"\.(wav|mp3|aiff?|m4a|aac|ogg|flac)$", re.I)
FONT_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]*(-[A-Za-z0-9]+)+$|^[A-Z][A-Za-z0-9]{5,}$")
NEAR = 0.12  # 「同時」とみなす秒数（約3〜4フレーム）


def nfc(s):
    return unicodedata.normalize("NFC", s) if s else s


def fmt(t):
    return f"{int(t // 60):02d}:{t % 60:05.2f}"


def fb_strings(raw):
    """FlatBuffer の長さ付き文字列（uint32長 + UTF-8 + NUL）を順に取り出す。"""
    out, i, n = [], 0, len(raw)
    while i + 4 < n:
        ln = struct.unpack_from("<I", raw, i)[0]
        if 1 <= ln <= 4000 and i + 4 + ln < n and raw[i + 4 + ln] == 0:
            try:
                s = raw[i + 4:i + 4 + ln].decode("utf-8")
                if all(ord(c) >= 0x20 or c in "\r\n\t" for c in s):
                    out.append(s)
                    i += 5 + ln
                    continue
            except UnicodeDecodeError:
                pass
        i += 1
    return out


class Project:
    def __init__(self, path):
        data = open(path, "rb").read()
        if data[:2] == b"\x1f\x8b":
            data = gzip.decompress(data)
        self.root = ET.fromstring(data)
        self.ids, self.uids = {}, {}
        for e in self.root:
            if "ObjectID" in e.attrib:
                self.ids[e.attrib["ObjectID"]] = e
            if "ObjectUID" in e.attrib:
                self.uids[e.attrib["ObjectUID"]] = e
        self.blobs = {}
        for e in self.root.iter("StartKeyframeValue"):
            h = e.attrib.get("BinaryHash")
            if h and e.text and e.text.strip():
                self.blobs[h] = e.text.strip()
        self.style_names = {}
        for s in self.root.findall("StyleProjectItem"):
            self.style_names[s.get("ObjectUID")] = s.findtext("ProjectItem/Name")

    def ref(self, e):
        if e is None:
            return None
        if "ObjectRef" in e.attrib:
            return self.ids.get(e.attrib["ObjectRef"])
        if "ObjectURef" in e.attrib:
            return self.uids.get(e.attrib["ObjectURef"])
        return None

    def sequences(self):
        return [e for e in self.root if e.tag == "Sequence"]

    def tracks(self, seq):
        out = []
        for tg in seq.findall("TrackGroups/TrackGroup"):
            g = self.ref(tg.find("Second"))
            if g is None or g.tag not in ("VideoTrackGroup", "AudioTrackGroup"):
                continue
            prefix = "V" if g.tag == "VideoTrackGroup" else "A"
            for i, t in enumerate(g.findall("TrackGroup/Tracks/Track")):
                tr = self.ref(t)
                if tr is not None:
                    out.append((prefix + str(i + 1), tr))
        return out

    def items(self, track):
        res = []
        for ti in track.findall("ClipTrack/ClipItems/TrackItems/TrackItem"):
            it = self.ref(ti)
            if it is not None:
                res.append(it)
        return res

    def param_value(self, pe):
        v = pe.findtext("StartKeyframe") or ""
        parts = v.split(",")
        return parts[1] if len(parts) > 1 else v

    def text_of(self, pe):
        sk = pe.find("StartKeyframeValue")
        if sk is None:
            return [], []
        b = (sk.text or "").strip() or self.blobs.get(sk.attrib.get("BinaryHash"), "")
        if not b:
            return [], []
        ss = fb_strings(base64.b64decode(b))
        fonts = [s for s in ss if FONT_RE.match(s)]
        texts = [s for s in ss if s not in fonts]
        return texts, fonts

    def clip(self, track_name, it):
        cti = it.find("ClipTrackItem")
        ti = cti.find("TrackItem")
        start = int(ti.findtext("Start") or 0) / TPS
        end = int(ti.findtext("End") or 0) / TPS
        row = {"track": track_name, "start": round(start, 3), "end": round(end, 3),
               "disabled": cti.findtext("IsMuted") == "true"}
        props = ti.find("Node/Properties")
        if props is not None and props.findtext("ESP.Tag"):
            row["esp"] = props.findtext("ESP.Tag")
        sc = self.ref(cti.find("SubClip"))
        name = media = None
        if sc is not None:
            name = sc.findtext("Name")
            cl = self.ref(sc.find("Clip"))
            if cl is not None:
                if cl.tag == "AudioClip" and cl.findtext("Gain"):
                    g = float(cl.findtext("Gain"))
                    row["gain_db"] = round(20 * math.log10(g), 2) if g > 0 else -99.0
                c = cl.find("Clip")
                if c is not None:
                    src = self.ref(c.find("Source"))
                    if src is not None:
                        m = self.ref(src.find("MediaSource/Media"))
                        if m is not None:
                            p = m.findtext("FilePath") or m.findtext("ActualMediaFilePath") or m.findtext("Title")
                            media = os.path.basename(p) if p else None
        row["name"] = nfc(name)
        row["media"] = nfc(media or name or "")
        layers, fx = [], []
        chain = self.ref(cti.find("ComponentOwner/Components"))
        if chain is not None:
            for c in chain.findall("ComponentChain/Components/Component"):
                ce = self.ref(c)
                if ce is None:
                    continue
                mn = ce.findtext("MatchName") or ce.findtext("Component/MatchName") or ""
                dn = ce.findtext("Component/DisplayName") or mn
                params = [self.ref(p) for p in ce.findall("Component/Params/Param")]
                params = [p for p in params if p is not None]
                if mn == "AE.ADBE Text":
                    ps = ce.find("Component/ParentStyle")
                    style = self.style_names.get(ps.get("ObjectURef")) if ps is not None else None
                    for pe in params:
                        if pe.tag == "ArbVideoComponentParam":
                            t, f = self.text_of(pe)
                            if t or f:
                                layers.append({"text": "".join(t).replace("\r", " ").strip(),
                                               "fonts": sorted(set(f)), "style": nfc(style)})
                            break
                elif mn == "AE.ADBE Motion":
                    for pe in params:
                        if (pe.findtext("Name") or "").strip() in ("スケール", "Scale"):
                            try:
                                row["scale"] = float(self.param_value(pe))
                            except ValueError:
                                pass
                            if (pe.findtext("Keyframes") or "").strip():
                                row["scale_keyframed"] = True
                elif mn == "AE.ADBE Geometry2":  # トランスフォーム（調整レイヤーでのズーム）
                    fx.append("トランスフォーム")
                    for pe in params:
                        nm = (pe.findtext("Name") or "").strip()
                        if ("スケール" in nm or "Scale" in nm) and "幅" not in nm and "Width" not in nm:
                            try:
                                row["transform_scale"] = float(self.param_value(pe))
                            except ValueError:
                                pass
                elif mn == "AE.ADBE AECrop":
                    fx.append("クロップ")
                    for pe in params:
                        nm = (pe.findtext("Name") or "").strip()
                        if nm in ("上", "Top", "下", "Bottom"):
                            row["crop_" + nm] = self.param_value(pe)
                elif mn == "AE.ADBE Horizontal Flip":
                    fx.append("水平反転")
                elif dn and mn not in ("AE.ADBE Opacity",) and not mn.startswith("Internal") and mn not in (
                        "AE.ADBE Graphic Group", "AE.ADBE Shape", "AE.ADBE Graphic SubGroup"):
                    fx.append(dn)
        if layers:
            row["layers"] = layers
        if fx:
            row["fx"] = fx
        return row


def classify_audio(c, dialog_tracks, media_maxlen):
    # Essential Sound のタグ（sfx/music）は付け間違いがあるので使わない。
    # 映像ファイルの音＝台詞（台詞トラック上）かその他、長く使われる音源＝BGM、それ以外＝SE。
    if VIDEO_EXT.search(c["media"]):
        return "DIALOG" if c["track"] in dialog_tracks else "OTHER"
    if not AUDIO_EXT.search(c["media"]):
        return "OTHER"  # ネストされたシーケンス等
    return "BGM" if media_maxlen.get(c["media"], 0) >= 10 else "SE"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("prproj")
    ap.add_argument("--out", required=True)
    ap.add_argument("--sequence", help="解析するシーケンス名（省略時はクリップ数が最も多いもの）")
    ap.add_argument("--base-styles", help="通常字幕として扱う保存スタイル名（カンマ区切り。省略時は使用数の多い上位2つ）")
    a = ap.parse_args()

    pj = Project(a.prproj)
    seqs = pj.sequences()
    if a.sequence:
        cands = [s for s in seqs if s.findtext("Name") == a.sequence]
        if not cands:
            sys.exit("シーケンスが見つかりません: " + a.sequence)
        seq = max(cands, key=lambda s: sum(len(pj.items(t)) for _, t in pj.tracks(s)))
    else:
        seq = max(seqs, key=lambda s: sum(len(pj.items(t)) for _, t in pj.tracks(s)))
    seq_name = seq.findtext("Name")

    allc = []
    for tn, tr in pj.tracks(seq):
        for it in pj.items(tr):
            allc.append(pj.clip(tn, it))
    clips = [c for c in allc if not c["disabled"]]
    disabled = Counter(c["track"] for c in allc if c["disabled"])

    # 音声の分類（台詞トラック＝カメラ音声が最も多いトラック）
    aud = [c for c in clips if c["track"].startswith("A")]
    cam_audio = Counter(c["track"] for c in aud if VIDEO_EXT.search(c["media"]))
    dialog_tracks = {t for t, _ in cam_audio.most_common(1)}
    media_maxlen = defaultdict(float)
    for c in aud:
        media_maxlen[c["media"]] = max(media_maxlen[c["media"]], c["end"] - c["start"])
    for c in aud:
        c["kind"] = classify_audio(c, dialog_tracks, media_maxlen)
    SE = sorted([c for c in aud if c["kind"] == "SE"], key=lambda c: c["start"])
    BGM = sorted([c for c in aud if c["kind"] == "BGM"], key=lambda c: c["start"])
    DIALOG = [c for c in aud if c["kind"] == "DIALOG"]
    end_time = max(c["end"] for c in clips)

    # テロップ
    texts = [c for c in clips if c["track"].startswith("V") and c.get("layers")]
    style_count = Counter(l["style"] or "(スタイルなし:" + ",".join(l["fonts"]) + ")" for c in texts for l in c["layers"])
    # 通常字幕＝全テロップの8%以上を占めるスタイル（話者ごとの基本字幕）。明示指定があればそちらを使う。
    total_layers = sum(style_count.values())
    base = set(a.base_styles.split(",")) if a.base_styles else {s for s, n in style_count.items() if n >= 0.08 * total_layers}

    def styles(c):
        return [l["style"] or "(スタイルなし:" + ",".join(l["fonts"]) + ")" for l in c.get("layers", [])]

    def is_deco(c):
        return any(s not in base for s in styles(c))

    def text(c):
        return " / ".join(l["text"] for l in c.get("layers", []) if l["text"])

    subs = sorted([c for c in texts if not is_deco(c)], key=lambda c: c["start"])
    deco = sorted([c for c in texts if is_deco(c)], key=lambda c: c["start"])
    sub_track = Counter(c["track"] for c in subs)

    # カメラ（映像ファイル）の表示とズーム
    cams = [c for c in clips if c["track"].startswith("V") and VIDEO_EXT.search(c["media"])]
    modal = {}
    for m in {c["media"] for c in cams}:
        cnt = Counter(round(c.get("scale", 100.0)) for c in cams if c["media"] == m)
        modal[m] = cnt.most_common(1)[0][0]
    zooms = []
    bounds = sorted({c["start"] for c in cams} | {c["end"] for c in cams})
    cams_sorted = sorted(cams, key=lambda c: c["start"])
    for s0, s1 in zip(bounds, bounds[1:]):
        mid = (s0 + s1) / 2
        top = None
        for c in cams_sorted:
            if c["start"] > mid:
                break
            if c["start"] <= mid < c["end"] and (top is None or int(c["track"][1:]) > int(top["track"][1:])):
                top = c
        if top is None:
            continue
        sc = top.get("scale", 100.0)
        base_sc = modal.get(top["media"], 100)
        if abs(sc - base_sc) > 3:
            zooms.append({"start": s0, "end": s1, "scale": round(sc / base_sc * 100), "via": "カメラ直接"})
    for c in clips:
        if "transform_scale" in c and abs(c["transform_scale"] - 100) > 1:
            zooms.append({"start": c["start"], "end": c["end"], "scale": round(c["transform_scale"]), "via": "調整レイヤー"})
    zooms.sort(key=lambda z: z["start"])
    merged = []
    for z in zooms:
        if merged and abs(merged[-1]["end"] - z["start"]) < 0.05 and merged[-1]["scale"] == z["scale"] and merged[-1]["via"] == z["via"]:
            merged[-1]["end"] = z["end"]
        else:
            merged.append(dict(z))
    zooms = merged

    def zkind(s):
        return "引き" if s < 95 else ("寄り" if s <= 145 else "強い寄り")

    # BGMの停止区間
    cov = sorted((c["start"], c["end"]) for c in BGM)
    m2 = []
    for s0, s1 in cov:
        if m2 and s0 <= m2[-1][1] + 0.02:
            m2[-1] = (m2[-1][0], max(m2[-1][1], s1))
        else:
            m2.append((s0, s1))
    bgm_gaps = [(m2[i][1], m2[i + 1][0]) for i in range(len(m2) - 1) if m2[i + 1][0] - m2[i][1] > 0.2]

    # 画面特殊（シネスコ帯・左右反転）
    specials = [c for c in clips if c.get("fx") and ("クロップ" in c["fx"] or "水平反転" in c["fx"]) and not c.get("layers")]

    def at(lst, t, tol=NEAR):
        return [x for x in lst if abs(x["start"] - t) <= tol]

    def zoom_at(t):
        # 同時に始まったズームを優先し、なければ t を含むズーム
        zs = [z for z in zooms if abs(z["start"] - t) <= NEAR]
        if not zs:
            zs = [z for z in zooms if z["start"] <= t < z["end"] - 0.02]
        return zs[0] if zs else None

    def bgm_stop_at(t):
        # BGMが止まっている区間の中（開始直前0.15秒を含む）なら停止扱い
        return any(g0 - 0.15 <= t < g1 for g0, g1 in bgm_gaps)

    def sub_around(t):
        prev = [c for c in subs if c["start"] < t - NEAR]
        nxt = [c for c in subs if c["start"] > t + NEAR]
        return (text(prev[-1]) if prev else ""), (text(nxt[0]) if nxt else "")

    # イベント行（SE・装飾テロップ・ズーム・BGM停止の開始時刻をまとめる）
    times = sorted({round(c["start"], 2) for c in SE} | {round(c["start"], 2) for c in deco}
                   | {round(z["start"], 2) for z in zooms} | {round(g0, 2) for g0, _ in bgm_gaps})
    rows, used = [], set()
    for t in times:
        if any(abs(t - u) <= NEAR for u in used):
            continue
        used.add(t)
        ses = at(SE, t)
        ds = at(deco, t)
        cur = [c for c in subs if c["start"] <= t + NEAR < c["end"]]
        z = zoom_at(t)
        prev, nxt = sub_around(t)
        rows.append({
            "時刻": fmt(t), "秒": t,
            "字幕トラック": ",".join(sorted({c["track"] for c in cur})),
            "表示中の字幕": " | ".join(text(c) for c in cur),
            "装飾テロップ": " | ".join(text(c) for c in ds),
            "装飾スタイル": " | ".join(sorted({s for c in ds for s in styles(c) if s not in base})),
            "装飾フォント": " | ".join(sorted({f for c in ds for l in c["layers"] for f in l["fonts"]})),
            "SE": " + ".join(c["media"] for c in ses),
            "SEゲインdB": " + ".join(str(c.get("gain_db", 0.0)) for c in ses),
            "ズーム": zkind(z["scale"]) if z else "",
            "倍率%": z["scale"] if z else "",
            "ズーム方式": z["via"] if z else "",
            "ズーム秒": round(z["end"] - z["start"], 2) if z else "",
            "BGM停止": "停止" if bgm_stop_at(t) else "",
            "直前の字幕": prev, "直後の字幕": nxt,
        })
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "events.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # 集計
    def fam(m):
        mm = re.match(r"【([^】]+)】", m)
        return mm.group(1) if mm else re.sub(r"(_\d{3})?\.(wav|mp3|aif+)$", "", m)

    style_se = defaultdict(Counter)
    style_zoom = defaultdict(Counter)
    style_bgm = Counter()
    style_n = Counter()
    for c in deco:
        for s in {s for s in styles(c) if s not in base}:
            style_n[s] += 1
            ses = at(SE, c["start"])
            style_se[s][" + ".join(x["media"] for x in ses) or "(SEなし)"] += 1
            z = zoom_at(c["start"])
            style_zoom[s][zkind(z["scale"]) if z else "なし"] += 1
            if bgm_stop_at(c["start"]):
                style_bgm[s] += 1
    se_ctx = defaultdict(Counter)
    for s in SE:
        ds = at(deco, s["start"])
        key = " | ".join(sorted({st for c in ds for st in styles(c) if st not in base})) or (
            "通常字幕の切替" if at(subs, s["start"]) else "(テロップ変化なし)")
        se_ctx[s["media"]][key] += 1
    se_gain = defaultdict(Counter)
    for s in SE:
        se_gain[s["media"]][s.get("gain_db", 0.0)] += 1
    fam_stop, fam_tot = Counter(), Counter()
    for s in SE:
        fam_tot[fam(s["media"])] += 1
        if bgm_stop_at(s["start"]):
            fam_stop[fam(s["media"])] += 1

    def gapstats(ts):
        ts = sorted(ts)
        gs = [b - a for a, b in zip(ts, ts[1:])]
        if len(gs) < 3:
            return None
        gs2 = sorted(gs)
        return {"件数": len(ts), "1分あたり": round(len(ts) / (end_time / 60), 1),
                "間隔中央値秒": round(statistics.median(gs), 1),
                "間隔90%秒": round(gs2[int(0.9 * len(gs2))], 1),
                "間隔95%秒": round(gs2[int(0.95 * len(gs2))], 1),
                "最大間隔秒": round(max(gs), 1)}

    any_ev = [c["start"] for c in SE] + [c["start"] for c in deco] + [z["start"] for z in zooms]
    dl = [c["end"] - c["start"] for c in DIALOG]
    sl = [c["end"] - c["start"] for c in subs]
    summary = {
        "プロジェクト": os.path.basename(a.prproj), "シーケンス": seq_name, "尺分": round(end_time / 60, 1),
        "無効化クリップ数(トラック別)": dict(disabled),
        "通常字幕スタイル": sorted(base), "通常字幕トラック": dict(sub_track),
        "件数": {"SE": len(SE), "装飾テロップ": len(deco), "通常字幕": len(subs), "ズーム": len(zooms),
               "BGM停止": len(bgm_gaps), "シネスコ帯/反転": len(specials)},
        "テンポ": {"SE": gapstats([c["start"] for c in SE]), "装飾テロップ": gapstats([c["start"] for c in deco]),
                "ズーム": gapstats([z["start"] for z in zooms]), "何かしらの演出": gapstats(any_ev)},
        "カット(台詞クリップ)秒": {"件数": len(dl), "中央値": round(statistics.median(dl), 2) if dl else None},
        "通常字幕表示秒": {"中央値": round(statistics.median(sl), 2) if sl else None},
        "ズーム内訳": dict(Counter(zkind(z["scale"]) for z in zooms)),
        "ズーム倍率": dict(Counter(z["scale"] for z in zooms).most_common()),
        "スタイル別": {s: {"件数": style_n[s], "SE": dict(style_se[s].most_common()),
                        "ズーム": dict(style_zoom[s]), "BGM停止": style_bgm[s]} for s in style_n},
        "SE別": {m: {"回数": sum(se_ctx[m].values()), "ゲインdB": dict(se_gain[m]), "一緒に出たもの": dict(se_ctx[m].most_common())}
                for m in sorted(se_ctx, key=lambda k: -sum(se_ctx[k].values()))},
        "SE系統別BGM停止": {f: f"{fam_stop[f]}/{fam_tot[f]}" for f in fam_tot},
        "BGM停止区間": [(fmt(g0), round(g1 - g0, 1)) for g0, g1 in bgm_gaps],
    }
    json.dump(summary, open(os.path.join(a.out, "summary.json"), "w"), ensure_ascii=False, indent=1)

    L = [f"# 装飾の逆算レポート：{summary['プロジェクト']} / {seq_name}", "",
         f"尺 {summary['尺分']}分。無効化クリップは除外済み（{sum(disabled.values())}個）。通常字幕スタイル＝{', '.join(sorted(base))}", "",
         "## 件数", "", "| 項目 | 件数 |", "|---|---|"]
    L += [f"| {k} | {v} |" for k, v in summary["件数"].items()]
    L += ["", "## テンポ", "", "| 対象 | 件数 | 1分あたり | 間隔中央値 | 90% | 95% | 最大 |", "|---|---|---|---|---|---|---|"]
    for k, v in summary["テンポ"].items():
        if v:
            L.append(f"| {k} | {v['件数']} | {v['1分あたり']} | {v['間隔中央値秒']}s | {v['間隔90%秒']}s | {v['間隔95%秒']}s | {v['最大間隔秒']}s |")
    L += ["", f"カット中央値 {summary['カット(台詞クリップ)秒']['中央値']}s／通常字幕の表示中央値 {summary['通常字幕表示秒']['中央値']}s", "",
          "## スタイル別（装飾テロップ）", "", "| スタイル | 件数 | 一緒に鳴ったSE | ズーム | BGM停止 |", "|---|---|---|---|---|"]
    for s, v in sorted(summary["スタイル別"].items(), key=lambda kv: -kv[1]["件数"]):
        se_s = "、".join(f"{k}×{n}" for k, n in v["SE"].items())
        L.append(f"| {s} | {v['件数']} | {se_s} | {v['ズーム']} | {v['BGM停止']} |")
    L += ["", "## SE別", "", "| SE | 回数 | ゲインdB | 一緒に出たもの |", "|---|---|---|---|"]
    for m, v in summary["SE別"].items():
        L.append(f"| {m} | {v['回数']} | {v['ゲインdB']} | {'、'.join(f'{k}×{n}' for k, n in v['一緒に出たもの'].items())} |")
    L += ["", "## SE系統ごとのBGM停止", ""] + [f"- {k}: {v}" for k, v in summary["SE系統別BGM停止"].items()]
    L += ["", "## ズーム", "", f"- 内訳: {summary['ズーム内訳']}", f"- 倍率: {summary['ズーム倍率']}"]
    open(os.path.join(a.out, "summary.md"), "w").write("\n".join(L) + "\n")
    print(f"OK: {seq_name} / events {len(rows)}行 → {a.out}")


if __name__ == "__main__":
    main()
