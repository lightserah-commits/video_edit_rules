#!/usr/bin/env python3
"""クリップだけを文字起こしして、狙ったセリフだけが入っているか（前後の言葉の混入・取りこぼし）を確かめる。
クリップの音（analysis/asr/_work/camera.wav、16kHz・カメラの秒）を切り出し、前後に 0.3秒の無音を足して mlx_whisper にかける。
語の時刻はクリップの頭からの秒（無音の分を引いてある。負の数は無音の中）。結果は _work/words.json（make_hl.py が文字を声に合わせるのに使う）。
  ~/Desktop/video_edit_rules/env/bin/python asr_clips.py [clips.tsv] [--only H1,H2]
"""
import json
import os
import sys
import wave
from pathlib import Path

os.environ["HF_HUB_OFFLINE"] = "1"
import mlx_whisper  # noqa: E402
import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
WAV = HERE.parent.parent / "analysis" / "asr" / "_work" / "camera.wav"
MODEL = os.path.expanduser("~/Desktop/video_edit_rules/models/whisper-large-v3-turbo")
PAD = float(sys.argv[sys.argv.index("--pad") + 1]) if "--pad" in sys.argv else 0.3

args = [a for i, a in enumerate(sys.argv[1:], 1) if not a.startswith("--") and sys.argv[i - 1] not in ("--only", "--pad")]
tsv = Path(args[0]) if args else HERE / "clips.tsv"
only = set(sys.argv[sys.argv.index("--only") + 1].split(",")) if "--only" in sys.argv else None
with wave.open(str(WAV)) as f:
    sr = f.getframerate()
    audio = np.frombuffer(f.readframes(f.getnframes()), dtype=np.int16).astype(np.float32) / 32768
out_p = HERE / "_work" / "words.json"
res = json.load(open(out_p, encoding="utf-8")) if out_p.exists() and tsv.name == "clips.tsv" else {}
prev = None
for ln in tsv.read_text(encoding="utf-8").splitlines():
    if not ln.strip() or ln.startswith("#"):
        continue
    cid, a, b, txt = ln.split("\t")[:4]
    a, b = float(a), float(b)
    if only and cid not in only:
        prev = (a, b)
        continue
    seg = audio[int(a * sr):int(b * sr)]
    pad = np.zeros(int(PAD * sr), dtype=np.float32)
    r = mlx_whisper.transcribe(np.concatenate([pad, seg, pad]), path_or_hf_repo=MODEL, language="ja", word_timestamps=True,
                               condition_on_previous_text=False, verbose=None)
    words = [{"w": w["word"].strip(), "s": round(w["start"] - PAD, 2), "e": round(w["end"] - PAD, 2)}
             for s in r["segments"] for w in s.get("words", [])]
    got = "".join(s["text"] for s in r["segments"]).strip()
    res[cid] = words
    print(f"{cid}\t{a:.2f}-{b:.2f} ({b - a:.2f}秒)\n  狙い: {txt}\n  起こし: {got}\n  語: " +
          " ".join(f"{w['w']}@{w['s']:.2f}" for w in words), flush=True)
    # 1秒未満のクリップは whisper が聞き違えやすい（無音の所で「ご視聴ありがとうございました」などが出る）ので、
    # ハイライトの中と同じく前のクリップの後ろに 0.1秒あけてつなげて、もう一度起こす（つなげた所の後ろに狙いの言葉が出るか）
    if b - a < 1.0 and prev is not None:
        pa, pb = prev
        both = np.concatenate([pad, audio[int(pa * sr):int(pb * sr)], np.zeros(int(0.1 * sr), dtype=np.float32), seg, pad])
        r2 = mlx_whisper.transcribe(both, path_or_hf_repo=MODEL, language="ja", word_timestamps=True, condition_on_previous_text=False,
                                    verbose=None)
        cut = PAD + (pb - pa) + 0.1
        tail = "".join(w["word"] for s in r2["segments"] for w in s.get("words", []) if w["end"] > cut + 0.05).strip()
        print(f"  前のクリップとつなげて: {''.join(s['text'] for s in r2['segments']).strip()}\n  つなげた所の後ろ: {tail}", flush=True)
    prev = (a, b)
if tsv.name == "clips.tsv":
    json.dump(res, open(out_p, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
