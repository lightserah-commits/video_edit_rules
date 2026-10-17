"""作業用コピーを media/ に作る（元の素材は読むだけ）。セキュリティについて（2026-10-16）。
AI動画編集 の scripts/make_media.py（iPhone 3本＋Loom を通しの時刻に並べる）を、素材1本の形に縮めた。

この案件の素材：IMG_1320.MOV（2026-10-16 16:03 撮影・iPhone 16 Pro Max・23:02.0・1920×1080 HEVC 可変〈平均 59.97〉・AAC 48kHz 2ch）
  media/camera_CFR2997.mov ＝ 29.97fps の固定に直した映像（H.264）＋ PCM 48kHz 2ch
  analysis/asr/_work/camera.wav（16kHz モノラル。文字起こし・波形の検査用）
  analysis/sync/sync.json（同期は無い。素材の秒 ＝ 通しの秒）
使い方：python3 scripts/make_media.py
"""
import json
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
E = os.path.dirname(HERE)
SRC = os.path.dirname(E)
A = os.path.join(E, "analysis")
M = os.path.join(E, "media")
NAME = "IMG_1320.MOV"


def nframes(p):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets", "-show_entries",
                                   "stream=nb_read_packets", "-of", "csv=p=0", p]).decode().strip()
    return int(out)


def main():
    os.makedirs(M, exist_ok=True)
    out = os.path.join(M, "camera_CFR2997.mov")
    if not os.path.exists(out):
        tmp = out + ".tmp.mov"
        subprocess.run(["ffmpeg", "-v", "error", "-stats", "-y", "-i", os.path.join(SRC, NAME), "-map", "0:v:0", "-map", "0:a:0",
                        "-vf", "fps=30000/1001", "-c:v", "h264_videotoolbox", "-b:v", "20M", "-profile:v", "high", "-pix_fmt", "yuv420p",
                        "-c:a", "pcm_s16le", "-video_track_timescale", "30000", tmp], check=True)
        os.replace(tmp, out)
    os.makedirs(os.path.join(A, "asr", "_work"), exist_ok=True)
    wav = os.path.join(A, "asr", "_work", "camera.wav")
    if not os.path.exists(wav):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", out, "-map", "0:a:0", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", wav], check=True)
    n = nframes(out)
    os.makedirs(os.path.join(A, "sync"), exist_ok=True)
    sync = {"model": "素材1本（IMG_1320.MOV）。同期は無い。通しの秒 ＝ 素材の秒", "rate": 1.0, "offset": 0.0,
            "parts": [{"name": "1320", "kind": "camera", "copy": os.path.basename(out), "frames": n, "start_frame": 0, "start_sec": 0.0}],
            "total_frames": n}
    json.dump(sync, open(os.path.join(A, "sync", "sync.json"), "w"), ensure_ascii=False, indent=1)
    print("camera frames", n, "=", round(n * 1001 / 30000, 3), "sec")


if __name__ == "__main__":
    main()
