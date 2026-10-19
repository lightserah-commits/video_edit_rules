"""画面録画の5秒ごとの静止画（analysis/screen/f5/）を Mac の文字認識で読む（画面係・秘密の探しもの・赤枠の材料）。
  python3 scripts/screen_ocr_f5.py → analysis/screen/ocr_f5.json（{画像名: [{text,x,y,w,h,conf}]}）・analysis/screen/index.txt
  index.txt の1行＝カメラの時刻（通し）|画面コピーの秒|画像のファイル名|画面の大きい文字（高さの上位）（1015：sync.json の rate=1・offset で通しの時刻にする）
  途中で止まっても続きから（40枚ずつ analysis/screen/_ocr/ に残す）。秘密らしい文字（API・Secret・Token・password・sk-…）を secrets.txt に出す
"""
import glob
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
E = os.path.dirname(HERE)
S = os.path.join(E, "analysis", "screen")
F5 = os.path.join(S, "f5")
CACHE = os.path.join(S, "_ocr")
os.makedirs(CACHE, exist_ok=True)
exe = os.path.join(S, "screen_ocr")
if not os.path.exists(exe):
    subprocess.run(["swiftc", "-O", os.path.expanduser("~/Desktop/video_edit_rules/tools/screen_ocr.swift"), "-o", exe], check=True)
sync = json.load(open(os.path.join(E, "analysis", "sync", "sync.json")))
files = sorted(glob.glob(os.path.join(F5, "s*.jpg")))
res = {}
for i in range(0, len(files), 40):
    part = files[i:i + 40]
    cp = os.path.join(CACHE, f"b{i:05d}.json")
    if os.path.exists(cp):
        d = json.load(open(cp))
    else:
        out = subprocess.run([exe] + part, capture_output=True, check=True).stdout
        d = json.loads(out)
        json.dump(d, open(cp, "w"), ensure_ascii=False)
    res.update({os.path.basename(k): v for k, v in d.items()})
    print(f"{min(i + 40, len(files))}/{len(files)}", flush=True)
json.dump(res, open(os.path.join(S, "ocr_f5.json"), "w"), ensure_ascii=False)
SECRET = re.compile(r"secret|token|api\s*key|password|パスワード|シークレット|トークン|sk-[A-Za-z0-9]{8,}|[A-Za-z0-9_\-]{32,}", re.I)
rows, sec = [], []
for f in files:
    name = os.path.basename(f)
    s = int(name[1:6])
    items = res.get(name, [])
    big = sorted(items, key=lambda it: -it["h"])[:4]
    txt = " / ".join(it["text"] for it in sorted(big, key=lambda it: it["y"]))
    cam = s * sync["rate"] + sync["offset"]
    rows.append(f"{cam:.1f}|{s}|{name}|{txt}")
    hits = [it["text"] for it in items if SECRET.search(it["text"])]
    if hits:
        sec.append(f"{cam:.1f}|{s}|{name}|" + " ; ".join(h[:60] for h in hits[:6]))
open(os.path.join(S, "index.txt"), "w", encoding="utf-8").write("\n".join(rows) + "\n")
open(os.path.join(S, "secrets.txt"), "w", encoding="utf-8").write("\n".join(sec) + "\n")
print("index", len(rows), "secret-like frames", len(sec))
