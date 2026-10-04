"""強調が「書いた最初の言葉」より早く出ている所（tools/check_kyocho_timing.py の「早い」）を、その言葉の聞こえ始めから出すように直す表を作る。
  01_判断フロー.md の「出す時刻」：字幕の頭に前置きがある時は、前置きの間は前の字幕（か前置きだけの字幕）を出し、書いた言葉が聞こえてから強調を出す。
  check_kyocho_timing と同じ測り方（文字起こしの語 → 波形の立ち上がり）で、タイムラインのフレームを出す。
  出力 _work/kyocho_start_fix.json {強調の開始フレーム（直す前）: {"to": 直した開始フレーム, "text", "diff"}}。make_v004.py が読む。前の結果に足していく
  ~/Desktop/video_edit_rules/env/bin/python v004/_work/kyocho_start_fix.py"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
V = os.path.dirname(HERE)
T = os.path.expanduser("~/Desktop/video_edit_rules/tools")
sys.path.insert(0, T)
import check_kyocho_timing as K  # noqa: E402
from dump_timeline import dump  # noqa: E402
E = os.path.dirname(V)
asr = K.words(os.path.join(E, "analysis", "asr", "asr_camera.json"))
db = K.env_db(os.path.join(E, "analysis", "asr", "_work", "camera.wav"))
tl = dump(os.path.join(V, "kankyo_v004.prproj"), "kankyo_v004")
fps = tl["fps"]
srcmap = {}
for r in tl["tracks"].get("A1", []):
    if r["muted"] or r["name"] != "camera_CFR2997.mov" or r["in_ticks"] is None:
        continue
    for f in range(r["start_f"], r["end_f"]):
        srcmap[f] = r["in_ticks"] / K.TPS + (f - r["start_f"]) / fps
out_p = os.path.join(HERE, "kyocho_start_fix.json")
fix = json.load(open(out_p)) if os.path.exists(out_p) else {}
inv = {v["to"]: k for k, v in fix.items()}
n = 0
for r in tl["tracks"].get("V7", []):
    t = "".join(r.get("texts") or [])
    if r["muted"] or len(K.NORM.sub("", t)) < 2 or r["start_f"] not in srcmap:
        continue
    if r["start_f"] in inv:                                # 前の回に直した強調は直し直さない（v001 2回目の検査係）
        continue
    first = K.NORM.sub("", r["texts"][0].split("\r")[0]).lower()
    sec = srcmap[r["start_f"]]
    best = None
    span = sorted(srcmap[f] for f in range(r["start_f"], r["end_f"]) if f in srcmap)   # 強調が出ている間に聞こえる素材の秒だけで探す（切った所の語に当てない。v001 の検査係）
    import bisect as _b
    for i, (ws, w) in enumerate(asr):
        if abs(ws - sec) > 3:
            continue
        j_ = _b.bisect_left(span, ws)
        inside = any(abs(span[q] - ws) < 0.05 for q in (j_ - 1, j_) if 0 <= q < len(span)) or (span and span[0] - 0.3 <= ws <= span[0])
        if not inside:
            continue
        if "".join(v for _, v in asr[i:i + 4]).startswith(first[:2]) and (best is None or ws < best):   # いちばん早い候補（「それだけ…それだけ」）
            best = ws
    if best is None:
        continue
    on = K.wave_onset(db, best)
    if sec - on > -0.095:
        continue
    f = r["start_f"]
    while f < r["end_f"] - 6 and (f not in srcmap or srcmap[f] < on - 0.01):
        f += 1
    if f >= r["end_f"] - 6 or (f - r["start_f"]) / fps > 0.6 or (r["end_f"] - f) / fps < 1.2:
        print(f"要確認（直さない）{r['start_f'] / fps // 60:.0f}:{r['start_f'] / fps % 60:05.2f} +{(f - r['start_f']) / fps:.2f}秒 残り{(r['end_f'] - f) / fps:.2f}秒  {t}")
        continue
    key = inv.get(r["start_f"], str(r["start_f"]))          # 前の回に直した所をさらに直す時は、元の開始フレームを鍵にする
    fix[key] = {"to": f, "text": t, "diff": round(sec - on, 2)}
    n += 1
    print(f"{r['start_f'] / fps / 60:.0f}:{r['start_f'] / fps % 60:05.2f} → +{(f - r['start_f']) / fps:.2f}秒  {t}")
json.dump(fix, open(out_p, "w"), ensure_ascii=False, indent=0)
print(f"直す {n}（表 {len(fix)}）")
