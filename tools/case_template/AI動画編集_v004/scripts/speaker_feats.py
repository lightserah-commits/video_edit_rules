"""区切り（units）ごとの話者の材料：声の高さ・声色（tools/voice_features.swift）。AI動画編集（2026-10-16）：Mac のマイクの録音が無いので、マイクの差（micratio）は作らない。
  三上さんは Mac の前にいるので Mac のマイクに大きく入る（iMac の測定で +5〜8dB、聞き手は 0dB 前後）。
  出力 analysis/speaker/voicefeat.json・analysis/speaker/micratio.json（{u: dB差}）
  ~/Desktop/video_edit_rules/env/bin/python scripts/speaker_feats.py（1015：mic_16k.wav は make_media_all.py mic が画面コピーの秒に並べたもの）
"""
import json
import os
import subprocess
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
A = os.path.join(HERE, "..", "analysis")
ROOT = os.path.expanduser("~/Desktop/video_edit_rules")
SP = os.path.join(A, "speaker")
os.makedirs(SP, exist_ok=True)
units = json.load(open(os.path.join(A, "units.json")))
sync = json.load(open(os.path.join(A, "sync", "sync.json")))


def load(p):
    with wave.open(p) as f:
        return np.frombuffer(f.readframes(f.getnframes()), dtype=np.int16).astype(np.float32) / 32768


cam = load(os.path.join(A, "asr", "_work", "camera.wav"))
pcm = os.path.join(SP, "camera_16k.f32")
if not os.path.exists(pcm):
    cam.astype(np.float32).tofile(pcm)
json.dump([{"idx": u["u"], "spk": "?", "ranges": [[u["start"], u["end"]]]} for u in units], open(os.path.join(SP, "cap_ranges.json"), "w"))
exe = os.path.join(SP, "voice_features")
if not os.path.exists(exe):
    subprocess.run(["swiftc", "-O", os.path.join(ROOT, "tools", "voice_features.swift"), "-o", exe], check=True)
subprocess.run([exe, SP], check=True)

print("voicefeat done（この案件は Mac のマイクが無いので micratio は作らない）")
