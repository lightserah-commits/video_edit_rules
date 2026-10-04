"""Air v001 の土台の XML（Final Cut Pro 7 形式）を作る。ワークの完全解説 v001 の build を、整理後の 02 の output_tracks・07 の both_tracks に合わせた：
  V1 カメラ（全部・有効）／V2 画面（素材がある所は全部置き、映す所だけ有効）／V11 ワイプ（画面と同じ所に置き、画面と一緒に有効／無効）
  A1/A2 カメラの音（+3dB。plan_v004.VOICE_GAIN_DB）／A3 BGM（メイン -9dB・ダイジェスト -12dB）。V3〜V10・V12〜V14・A4・A5 は空（make_v004.py で置く）
  - 字幕の区切り（_work/cuts_v004.json の caption_tl）で映像と音に編集点を入れる（上司の AV_EDIT_POINTS）。カットの切れ目ごとに V1・V2・V11 とも分ける
  - 画面を映す字幕は plan_v004.SCREEN。07 の merge_seconds（画面→カメラ→画面の間のカメラが3秒未満なら画面のまま）
  - 画面は高さに合わせて全体を入れる（3456×2234 → 48.34%）。ワイプは右上・336×189（960×540 の 35%）、右上の角から 58px・32px
  出力 _work/base_v004.xml と _work/base_v004_map.json（字幕ごとのタイムラインのフレーム・画面の区間）
  ~/Desktop/video_edit_rules/env/bin/python v004/build_v004.py
"""
import bisect
import json
import math
import os
import sys
import urllib.parse
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
CASE = os.path.dirname(HERE)
ROOT = os.path.expanduser("~/Desktop/video_edit_rules")   # ルールと道具の場所（案件フォルダはどこにあってもよい。2026-09-28）
sys.path.insert(0, HERE)
from common import FPS, SYNC_OFFSET  # noqa: E402
import plan_v004 as plan  # noqa: E402

SEQ = "kankyo_v004"
MEDIA = os.path.join(CASE, "media")
CAMERA = os.path.join(MEDIA, "camera_CFR2997.mov")
SCREEN = os.path.join(MEDIA, "screen_CFR2997.mp4")
WEBCAM = os.path.join(MEDIA, "webcam_CFR2997.mp4")
BGM_MAIN = os.path.join(ROOT, "素材", "BGM", "0.【メインテーマ】audiostock_900412.mp3")
BGM_DIGEST = os.path.join(ROOT, "素材", "BGM", "ダイジェスト用BGM.mp3")
BGM_MAIN_DB, BGM_DIGEST_DB = plan.BGM_GAIN_DB, plan.BGM_GAIN_DB - 3.0
SCREEN_SCALE = 1080 / 2234 * 100
WIPE_SCALE = 35.0
WIPE_CENTER = ((1920 - 58 - 168 - 960) / 960, (32 + 94.5 - 540) / 540)   # Premiere は中心を「画面の半分」を1として読む（v001 の画像で確かめた）
MERGE_F = round(3 * FPS)
MIN_SCREEN_F = round(2 * FPS)
N_SCREEN = round(SYNC_OFFSET * FPS)          # カメラのフレーム − これ ＝ 画面・Webカメラのコピーのフレーム
VIDEO_TRACKS = 14
ZUKAI = os.path.join(HERE, "zukai", "out")       # v002：AI が描く動く図解（zukai/make_zukai.py。dots v002 と同じ作り方）。V15＝板と部品、V16＝図解の間のワイプ


def zukai_manifests():
    """zukai/out/Z*/manifest.json（Ztest のような試しは除く）。タイムラインの順"""
    out = []
    if os.path.isdir(ZUKAI):
        for k in sorted(os.listdir(ZUKAI)):
            p = os.path.join(ZUKAI, k, "manifest.json")
            if k.startswith("Z") and not k.lower().startswith("ztest") and os.path.exists(p):
                out.append((k, json.load(open(p, encoding="utf-8"))))
    out.sort(key=lambda x: x[1]["tl_start_f"])
    return out
SNAP_F = 5                                  # 切り替えがカットの切れ目からこのフレーム以内なら切れ目へ寄せる（08 の no_slivers）
MIN_KEEP_F = 6                              # 0.2秒。これより短い映像・声のかたまりを作らない
HL_SNAP = 5                                 # ハイライトの字幕の頭がこれより区間の頭に近ければ、区間の頭から出す
AUDIO_TRACKS = 5
HL_GAIN_DB = -2.5                           # 冒頭ハイライトの音（声・BGM・効果音）。ハイライトは −24.8 LUFS で本編（声 −32.7＋3dB）より大きいので、astra v007 と同じく −2.5dB


def ffprobe_frames(path):
    import subprocess
    d = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                             capture_output=True, text=True).stdout.strip())
    return math.floor(d * FPS), d


def nb_frames(path):
    import subprocess
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=nb_frames", "-of", "csv=p=0", path],
                       capture_output=True, text=True).stdout.strip()
    return int(r)


def url(path):
    return "file://" + urllib.parse.quote(path)


RATE = "<rate><timebase>30</timebase><ntsc>TRUE</ntsc></rate>"


def file_elem(fid, path, frames, video=None, audio_ch=0, first=True):
    if not first:
        return f'<file id="{fid}"/>'
    media = ""
    if video:
        w, h = video
        media += (f"<video><samplecharacteristics>{RATE}<width>{w}</width><height>{h}</height><anamorphic>FALSE</anamorphic>"
                  f"<pixelaspectratio>square</pixelaspectratio><fielddominance>none</fielddominance></samplecharacteristics></video>")
    if audio_ch:
        media += (f"<audio><samplecharacteristics><depth>16</depth><samplerate>48000</samplerate></samplecharacteristics>"
                  f"<channelcount>{audio_ch}</channelcount></audio>")
    return (f'<file id="{fid}"><name>{escape(os.path.basename(path))}</name><pathurl>{url(path)}</pathurl>{RATE}'
            f"<duration>{frames}</duration><media>{media}</media></file>")


def motion(scale, center=(0.0, 0.0)):
    return ("<filter><effect><name>Basic Motion</name><effectid>basic</effectid><effectcategory>motion</effectcategory>"
            "<effecttype>motion</effecttype><mediatype>video</mediatype>"
            f'<parameter authoringApp="PremierePro"><parameterid>scale</parameterid><name>Scale</name><value>{scale:.4f}</value></parameter>'
            f'<parameter authoringApp="PremierePro"><parameterid>center</parameterid><name>Center</name><value><horiz>{center[0]:.6f}</horiz>'
            f"<vert>{center[1]:.6f}</vert></value></parameter></effect></filter>")


def level(db):
    return ("<filter><effect><name>Audio Levels</name><effectid>audiolevels</effectid><effectcategory>audiolevels</effectcategory>"
            "<effecttype>audiolevels</effecttype><mediatype>audio</mediatype><parameter><parameterid>level</parameterid><name>Level</name>"
            f"<valuemin>0</valuemin><valuemax>3.98109</valuemax><value>{10 ** (db / 20):.6f}</value></parameter></effect></filter>")


def main():
    cj = json.load(open(os.path.join(HERE, "_work", "cuts_v004.json"), encoding="utf-8"))
    capj = json.load(open(os.path.join(HERE, "_work", "captions_v004.json"), encoding="utf-8"))
    caps = [c for c in capj["captions"] if c["mode"] != "drop" and "src" in c]
    order = [c["id"] for c in caps]
    scr_ids = plan.screen_caption_ids(order)
    cap_tl = cj["caption_tl"]
    total = cj["total_frames"]
    cam_frames, _ = ffprobe_frames(CAMERA)
    scr_frames, _ = ffprobe_frames(SCREEN)
    web_frames, _ = ffprobe_frames(WEBCAM)
    # タイムラインの区間（素材＝カメラのフレーム）
    hl_ext = cj.get("highlight_external_frames", 0)          # 冒頭ハイライト（P15。hl/ で別に作った動画）の長さ
    segs, t = [], hl_ext
    for a, b in cj["highlight_frames"]:
        segs.append({"tl": t, "src": a, "len": b - a, "hl": True})
        t += b - a
    hl_end = t
    for a, b in cj["keep_frames"]:
        segs.append({"tl": t, "src": a, "len": b - a, "hl": False})
        t += b - a
    assert t == total, (t, total)
    # 字幕の区切り（本編）と、字幕ごとの画面／カメラ
    bounds = sorted(set(cap_tl[i] for i in order))
    mode_at = []          # (開始フレーム, 画面か)
    for i in order:
        mode_at.append((cap_tl[i], i in scr_ids))
    mode_at.sort()
    # 画面→カメラ→画面の短いカメラを画面に
    runs = []
    for f, s in mode_at:
        if runs and runs[-1][1] == s:
            continue
        runs.append([f, s])
    notes = []
    for k in range(1, len(runs) - 1):
        if not runs[k][1] and runs[k - 1][1] and runs[k + 1][1] and runs[k + 1][0] - runs[k][0] < MERGE_F:
            notes.append(f"画面の間の短いカメラ（{runs[k][0] / FPS:.1f}秒から {(runs[k + 1][0] - runs[k][0]) / FPS:.1f}秒）を画面にした")
            runs[k][1] = True
    merged = []
    for f, s in runs:
        if merged and merged[-1][1] == s:
            continue
        merged.append([f, s])
    screen_spans = []
    for k, (f, s) in enumerate(merged):
        if s:
            e = merged[k + 1][0] if k + 1 < len(merged) else total
            screen_spans.append([f, e])
    # 画面↔カメラの切り替えを、カットの切れ目にそろえる（08 の no_slivers・07 の switching.cut_point。v001）
    #   字幕の頭で切り替えると、カットの切れ目と 1〜5フレームずれた所に切れ端が出る（v001：画面44・ワイプ22）
    joins = sorted({sg["tl"] for sg in segs if 0 < sg["tl"] < total})
    snapped = 0

    def snap(f):
        nonlocal snapped
        i = bisect.bisect_left(joins, f)
        cand = [j for j in joins[max(0, i - 1):i + 1] if abs(j - f) <= SNAP_F]
        if not cand:
            return f
        j = min(cand, key=lambda x: abs(x - f))
        snapped += j != f
        return j
    sp = []
    for a, b in screen_spans:
        a, b = snap(a), snap(b)
        if b - a < MIN_KEEP_F:
            notes.append(f"画面の区間が短すぎるのでカメラにした（{a / FPS:.1f}秒から {b - a}フレーム）")
            continue
        if sp and a - sp[-1][1] < MIN_KEEP_F:
            sp[-1][1] = b
        else:
            sp.append([a, b])
    screen_spans = sp
    for a, b in screen_spans:
        if b - a < MIN_SCREEN_F:
            notes.append(f"画面の区間が短い（{a / FPS:.1f}秒から {(b - a) / FPS:.1f}秒）")

    def is_screen(f):
        return any(a <= f < b for a, b in screen_spans)
    # ハイライトの中の字幕の区切り（頭から5フレーム以内は区間の頭にそろえる。make_v004.py と同じ）
    hl_bounds, t0 = set(), 0
    for a, b in cj["highlight_frames"]:
        for c in caps:
            f = int(c["src"] * FPS)
            if a <= f < b and f - a >= HL_SNAP:
                hl_bounds.add(t0 + f - a)
        t0 += b - a
    # 区間を字幕の区切り・画面の切り替えで分ける
    cuts_at = sorted(set(bounds) | hl_bounds | {a for a, _ in screen_spans} | {b for _, b in screen_spans})
    pieces = []
    for sg in segs:
        a, b = sg["tl"], sg["tl"] + sg["len"]
        pts = [a] + [x for x in cuts_at if a < x < b] + [b]
        for p, q in zip(pts, pts[1:]):
            scr = (not sg["hl"]) and is_screen(p)
            pieces.append({"tl": p, "end": q, "src": sg["src"] + (p - a), "screen": scr, "hl": sg["hl"]})
    # 組み立て前の切れ端の確認（組み立て後は tools/check_slivers.py）：映像（V1 カメラ／画面・V9 ワイプ）と声（A1）の
    #   素材がそのまま続くかたまりごとに長さを見る
    def runs_of(items):
        out = []
        for tl, end, media, src in items:
            if out and out[-1][1] == tl and out[-1][2] == media and out[-1][3] == src:
                out[-1][1], out[-1][3] = end, src + (end - tl)
            else:
                out.append([tl, end, media, src + (end - tl)])
        return out
    # 見えている映像（有効な V2 か V1）・有効な V11・声（A1）
    v1_items = [(p["tl"], p["end"], "screen" if p["screen"] else "camera", p["src"]) for p in pieces]
    v9_items = [(p["tl"], p["end"], "webcam", p["src"]) for p in pieces if p["screen"]]
    a1_items = [(p["tl"], p["end"], "camera", p["src"]) for p in pieces]
    slivers = []
    for name, items in (("見えている映像", v1_items), ("V11", v9_items), ("A1", a1_items)):
        for a, b, media, _ in runs_of(items):
            if b - a < MIN_KEEP_F:
                slivers.append({"track": name, "frame": a, "time": f"{int(a / FPS // 60)}:{a / FPS % 60:05.2f}", "frames": b - a, "media": media})
    # XML
    cid = [0]

    def nid():
        cid[0] += 1
        return f"clip-{cid[0]}"
    v1, v2, v9, a1, a2, a3 = [], [], [], [], [], []
    first_file = {"camera": True, "screen": True, "webcam": True, "bgm_main": True, "bgm_digest": True}

    def fe(key, path, frames, video=None, audio_ch=0):
        f = first_file[key]
        first_file[key] = False
        return file_elem(key, path, frames, video, audio_ch, f)
    for p in pieces:
        L = p["end"] - p["tl"]
        sin = p["src"] - N_SCREEN
        has_screen = (not p["hl"]) and sin >= 0 and sin + L <= min(scr_frames, web_frames)
        if p["screen"] and not has_screen:
            raise ValueError(f"画面の素材の外: {p}")
        if has_screen:                            # 07 の both_tracks：画面とワイプは素材がある所は全部置き、映す所だけ有効
            en = "TRUE" if p["screen"] else "FALSE"
            vid = nid()
            v2.append((vid, f'<clipitem id="{vid}"><name>screen_CFR2997.mp4</name><enabled>{en}</enabled><duration>{scr_frames}</duration>{RATE}'
                       f'<start>{p["tl"]}</start><end>{p["end"]}</end><in>{sin}</in><out>{sin + L}</out>'
                       f'{fe("screen", SCREEN, scr_frames, (3456, 2234))}{motion(SCREEN_SCALE)}</clipitem>', None))
            wid = nid()
            v9.append((wid, f'<clipitem id="{wid}"><name>webcam_CFR2997.mp4</name><enabled>{en}</enabled><duration>{web_frames}</duration>{RATE}'
                       f'<start>{p["tl"]}</start><end>{p["end"]}</end><in>{sin}</in><out>{sin + L}</out>'
                       f'{fe("webcam", WEBCAM, web_frames, (960, 540))}{motion(WIPE_SCALE, WIPE_CENTER)}</clipitem>', None))
        vlink = nid()
        aid1, aid2 = nid(), nid()
        cam_file = fe("camera", CAMERA, cam_frames, (1920, 1080), 2)
        if vlink:
            cam_en = "FALSE" if p["screen"] else "TRUE"      # 07 の both_tracks「使わない方を無効」：画面を映す所はカメラを無効（画面の左右の余白にカメラが透けないように）
            v1.append((vlink, (f'<clipitem id="{vlink}"><name>camera_CFR2997.mov</name><enabled>{cam_en}</enabled><duration>{cam_frames}</duration>{RATE}'
                               f'<start>{p["tl"]}</start><end>{p["end"]}</end><in>{p["src"]}</in><out>{p["src"] + L}</out>'
                               f'{cam_file}{motion(100.0)}'), tuple(x for x in (vlink, aid1, aid2) if x)))
            cam_file = '<file id="camera"/>'
        a1.append((aid1, (f'<clipitem id="{aid1}"><name>camera_CFR2997.mov</name><enabled>TRUE</enabled><duration>{cam_frames}</duration>{RATE}'
                          f'<start>{p["tl"]}</start><end>{p["end"]}</end><in>{p["src"]}</in><out>{p["src"] + L}</out>{cam_file}'
                          f'<sourcetrack><mediatype>audio</mediatype><trackindex>1</trackindex></sourcetrack>{level(plan.VOICE_GAIN_DB)}'), tuple(x for x in (vlink, aid1, aid2) if x)))
        a2.append((aid2, (f'<clipitem id="{aid2}"><name>camera_CFR2997.mov</name><enabled>TRUE</enabled><duration>{cam_frames}</duration>{RATE}'
                          f'<start>{p["tl"]}</start><end>{p["end"]}</end><in>{p["src"]}</in><out>{p["src"] + L}</out><file id="camera"/>'
                          f'<sourcetrack><mediatype>audio</mediatype><trackindex>2</trackindex></sourcetrack>{level(plan.VOICE_GAIN_DB)}'), tuple(x for x in (vlink, aid1, aid2) if x)))
    # 冒頭ハイライト（P15）：hl/ で作った映像（V1）・声（A1・A2）・BGM（A3）・効果音（A4）を 0 から、白から戻る素材（V14）を挨拶の頭に
    a4, v14 = [], []
    if hl_ext:
        hm = json.load(open(os.path.join(HERE, "hl", "hl_manifest.json"), encoding="utf-8"))
        assert hm["frames"] == hl_ext, (hm["frames"], hl_ext)

        def hl_clip(key, path, track_list, ch, video=None, trackindex=1, start=0, frames=None):
            n = frames or hl_ext
            cid_ = nid()
            src = (f"<sourcetrack><mediatype>audio</mediatype><trackindex>{trackindex}</trackindex></sourcetrack>{level(HL_GAIN_DB)}" if not video else "")
            pos_ = 0 if track_list is v1 or track_list is a1 or track_list is a2 else len(track_list)   # トラックの中はクリップの開始順
            track_list.insert(pos_, (cid_, f'<clipitem id="{cid_}"><name>{escape(os.path.basename(path))}</name><enabled>TRUE</enabled><duration>{n}</duration>{RATE}'
                                     f'<start>{start}</start><end>{start + n}</end><in>0</in><out>{n}</out>{fe(key, path, n, video, ch)}{src}</clipitem>', None))
        for k in ("hl_video", "hl_voice", "hl_bgm", "hl_se", "hl_wo"):
            first_file[k] = True
        hl_clip("hl_video", hm["video"], v1, 0, video=(1920, 1080))
        hl_clip("hl_voice", hm["voice"], a1, 2, trackindex=1)
        hl_clip("hl_voice", hm["voice"], a2, 2, trackindex=2)
        hl_clip("hl_bgm", hm["bgm"], a3, 2, trackindex=1)
        hl_clip("hl_se", hm["se"], a4, 2, trackindex=1)
        if hm.get("whiteout"):
            hl_clip("hl_wo", hm["whiteout"], v14, 0, video=(1920, 1080), start=hl_ext, frames=hm["whiteout_frames"])
    # v002：図解（透明の動画を V15、図解の間のワイプを V16。ワイプはカメラを顔の所で切って縮めた動画で、大きさ 100%・中心は元の大きさに比例して読まれる。dots v002 と同じ）
    v15, v16 = [], []
    zk = zukai_manifests()
    for (k, m), nx in zip(zk, zk[1:] + [(None, None)]):
        s0, e0 = m["tl_start_f"], m["tl_end_f"]
        assert s0 >= hl_ext and e0 <= total, (k, s0, e0)
        if nx[1]:
            assert e0 <= nx[1]["tl_start_f"], f"図解 {k} と {nx[0]} が重なる"
        n = e0 - s0
        of = nb_frames(m["overlay"]["file"])           # 長さ×fps の切り捨てだと 457.999→457 になるので、コマ数を数える
        assert of >= n, (k, of, n)
        zid = nid()
        v15.append((zid, f'<clipitem id="{zid}"><name>図解{k}_overlay.mov</name><enabled>TRUE</enabled>'
                         f'<duration>{of}</duration>{RATE}<start>{s0}</start><end>{e0}</end><in>0</in><out>{n}</out>'
                         f'{file_elem("zov_" + k, m["overlay"]["file"], of, (1920, 1080))}{motion(100.0)}</clipitem>', None))
        if m.get("wipe"):
            wf_ = nb_frames(m["wipe"]["file"])
            x, y, w, h = m["wipe"]["box"]
            zid = nid()
            ctr = ((x + w / 2 - 960) / w, (y + h / 2 - 540) / h)
            v16.append((zid, f'<clipitem id="{zid}"><name>図解{k}_wipe.mp4</name><enabled>TRUE</enabled>'
                             f'<duration>{wf_}</duration>{RATE}<start>{s0}</start><end>{e0}</end><in>0</in><out>{n}</out>'
                             f'{file_elem("zwp_" + k, m["wipe"]["file"], wf_, (w, h))}{motion(100.0, ctr)}</clipitem>', None))
        notes.append(f"図解 {k}：{s0 / FPS:.2f}〜{e0 / FPS:.2f}秒（{n}フレーム）")
    # v003：公式のロゴの札（zukai/L*。図解ではない透明の動画。黒い板・ワイプなし）を V16 に置く。字幕・右上タイトルは外さない（make は図解として扱わない）
    if os.path.isdir(ZUKAI):
        for k in sorted(os.listdir(ZUKAI)):
            p_ = os.path.join(ZUKAI, k, "manifest.json")
            if not (k[:1] in ("L", "I") and os.path.exists(p_)):   # v004：I＝画像（zukai/gen_images.py）
                continue
            m = json.load(open(p_, encoding="utf-8"))
            s0, e0 = m["tl_start_f"], m["tl_end_f"]
            assert s0 >= hl_ext and e0 <= total, (k, s0, e0)
            assert all(e0 <= m2["tl_start_f"] or s0 >= m2["tl_end_f"] for _, m2 in zk), f"ロゴの札 {k} が図解に重なる"
            n = e0 - s0
            of = nb_frames(m["overlay"]["file"])
            assert of >= n, (k, of, n)
            zid = nid()
            v16.append((zid, f'<clipitem id="{zid}"><name>ロゴの札{k}_overlay.mov</name><enabled>TRUE</enabled>'
                             f'<duration>{of}</duration>{RATE}<start>{s0}</start><end>{e0}</end><in>0</in><out>{n}</out>'
                             f'{file_elem("lov_" + k, m["overlay"]["file"], of, (1920, 1080))}{motion(100.0)}</clipitem>', None))
            notes.append(f"ロゴの札 {k}：{s0 / FPS:.2f}〜{e0 / FPS:.2f}秒（{n}フレーム）V16")
    v16.sort(key=lambda x: int(x[1].split("<start>")[1].split("<")[0]))
    # BGM（メインは挨拶から。ダイジェスト用はハイライトの中に混ぜてある）
    dg_frames, _ = ffprobe_frames(BGM_DIGEST)
    mn_frames, _ = ffprobe_frames(BGM_MAIN)
    if not hl_ext and hl_end:
        bid = nid()
        L = min(hl_end, dg_frames)
        a3.append((bid, f'<clipitem id="{bid}"><name>ダイジェスト用BGM.mp3</name><enabled>TRUE</enabled><duration>{dg_frames}</duration>{RATE}'
                        f'<start>0</start><end>{L}</end><in>0</in><out>{L}</out>{fe("bgm_digest", BGM_DIGEST, dg_frames, None, 2)}'
                        f'<sourcetrack><mediatype>audio</mediatype><trackindex>1</trackindex></sourcetrack>{level(BGM_DIGEST_DB)}</clipitem>', None))
    t = hl_end
    while t < total:
        L = min(mn_frames, total - t)
        bid = nid()
        a3.append((bid, f'<clipitem id="{bid}"><name>0.【メインテーマ】audiostock_900412.mp3</name><enabled>TRUE</enabled><duration>{mn_frames}</duration>{RATE}'
                        f'<start>{t}</start><end>{t + L}</end><in>0</in><out>{L}</out>{fe("bgm_main", BGM_MAIN, mn_frames, None, 2)}'
                        f'<sourcetrack><mediatype>audio</mediatype><trackindex>1</trackindex></sourcetrack>{level(BGM_MAIN_DB)}</clipitem>', None))
        t += L
    # リンク（カメラの映像と A1・A2）
    idx = {}
    for name, lst in (("V1", v1), ("A1", a1), ("A2", a2)):
        for k, (i, _, _) in enumerate(lst):
            idx[i] = (name, k + 1)

    def close(i, body, link):
        if not link:
            return body if body.endswith("</clipitem>") else body + "</clipitem>"
        out = body
        for j in link:
            tr, k = idx[j]
            mt = "video" if tr == "V1" else "audio"
            ti = 1 if tr in ("V1", "A1") else 2
            out += f"<link><linkclipref>{j}</linkclipref><mediatype>{mt}</mediatype><trackindex>{ti}</trackindex><clipindex>{k}</clipindex></link>"
        return out + "</clipitem>"

    def track(lst, name, audio=False, ch=1):
        body = "".join(close(i, b, l) for i, b, l in lst)
        extra = f"<outputchannelindex>{ch}</outputchannelindex>" if audio else ""
        return f'<track MZ.TrackName="{name}">{extra}{body}</track>'
    vt = [track(v1, "V1 カメラ"), track(v2, "V2 画面")] + [f'<track MZ.TrackName="V{n}"/>' for n in range(3, 11)] + [track(v9, "V11 ワイプ")] + \
         [f'<track MZ.TrackName="V{n}"/>' for n in range(12, VIDEO_TRACKS)] + [track(v14, f"V{VIDEO_TRACKS}") if v14 else f'<track MZ.TrackName="V{VIDEO_TRACKS}"/>'] + \
         [track(v15, "V15 図解") if v15 else '<track MZ.TrackName="V15 図解"/>', track(v16, "V16 図解のワイプ") if v16 else '<track MZ.TrackName="V16 図解のワイプ"/>']
    at = [track(a1, "A1 声 L", True, 1), track(a2, "A2 声 R", True, 2), track(a3, "A3 BGM", True, 1),
          (track(a4, "A4 SE", True, 1) if a4 else '<track MZ.TrackName="A4 SE"><outputchannelindex>1</outputchannelindex></track>'),
          '<track MZ.TrackName="A5 SE2"><outputchannelindex>2</outputchannelindex></track>']
    fmt = (f"<format><samplecharacteristics>{RATE}<width>1920</width><height>1080</height><anamorphic>FALSE</anamorphic>"
           f"<pixelaspectratio>square</pixelaspectratio><fielddominance>none</fielddominance></samplecharacteristics></format>")
    afmt = ("<numOutputChannels>2</numOutputChannels><format><samplecharacteristics><depth>16</depth><samplerate>48000</samplerate>"
            "</samplecharacteristics></format><outputs><group><index>1</index><numchannels>2</numchannels><downmix>0</downmix>"
            "<channel><index>1</index></channel><channel><index>2</index></channel></group></outputs>")
    xml = (f'<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n<xmeml version="4"><sequence id="{escape(SEQ)}"><name>{escape(SEQ)}</name>'
           f"<duration>{total}</duration>{RATE}<timecode>{RATE}<string>00:00:00:00</string><frame>0</frame><displayformat>NDF</displayformat></timecode>"
           f"<media><video>{fmt}{''.join(vt)}</video><audio>{afmt}{''.join(at)}</audio></media></sequence></xmeml>\n")
    out = os.path.join(HERE, "_work", "base_v004.xml")
    open(out, "w", encoding="utf-8").write(xml)
    mp = {"sequence": SEQ, "total_frames": total, "highlight_end": hl_end, "caption_tl": cap_tl, "screen_spans": screen_spans,
          "n_screen": N_SCREEN, "pieces": len(pieces), "zukai": [[k, m["tl_start_f"], m["tl_end_f"]] for k, m in zk], "notes": notes, "switch_snapped": snapped, "slivers_before_assembly": slivers}
    json.dump(mp, open(os.path.join(HERE, "_work", "base_v004_map.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    scr_total = sum(b - a for a, b in screen_spans) / FPS
    print(f"{out}: 尺 {total / FPS / 60:.2f}分、区間 {len(pieces)}、V1 {len(v1)}・V2 {len(v2)}（有効 {sum('<enabled>TRUE' in b for _, b, _ in v2)}）・V11 {len(v9)}・A3 {len(a3)}、"
          f"画面 {len(screen_spans)}区間 {scr_total / 60:.1f}分（{scr_total / (total / FPS):.0%}）")
    for n in notes:
        print("  ", n)
    print(f"切り替えをカットの切れ目に寄せた {snapped}、組み立て前の切れ端（0.2秒未満）{len(slivers)}")
    for x in slivers[:20]:
        print("   切れ端", x)
    if slivers:
        sys.exit(1)


if __name__ == "__main__":
    main()
