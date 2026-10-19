"""作業用コピーを media/ に作り、iPhone 3本と Loom を1本の「通しの時刻」に並べる（元の素材は読むだけ）。
1015claude project開設 の scripts/make_media.sh・make_media_all.py を写して、この案件の素材の形に合わせた。

この案件の素材（2026-10-16 撮影。撮った時間は重ならないので、音で合わせる同期は無い）：
  IMG_1314.MOV  09:22  三上さんと創太くん（冒頭）            5:05.6
  IMG_1315.MOV  09:27  三上さんと創太くん（締め・CTA）        5:54.8
  IMG_1316.MOV  10:29  撮り直し前の 7秒（マイクが入っていない）→ 使わない
  IMG_1317.MOV  10:29  創太くんとこういちさん（実演の前）     2:25.2
  AI動画編集を実演で徹底解説.mp4  10:36  Loom の画面収録（こういちさんの実演。Webカメラの顔は焼き込み・1108×720・30fps・音はモノラル）29:45.1

通しの時刻（動画の流れの順）：IMG_1314 → IMG_1317 → Loom → IMG_1315
  media/camera_CFR2997.mov ＝ 映像 [1314 | 1317 | Loom を高さに合わせて入れたもの | 1315]、音 [1314 | 1317 | Loom（2ch に） | 1315]（PCM 48kHz 2ch）
  media/screen_CFR2997.mp4 ＝ Loom の映像（1108×720 のまま・29.97fps）。通しのカメラのフレーム ＝ 画面コピーのフレーム ＋ N_SCREEN
  analysis/asr/_work/camera.wav（16kHz モノラル）・analysis/sync/sync.json・analysis/asr/asr_camera.json

使い方：python3 scripts/make_media.py parts | concat | asr   （all で全部。camvideo＝カメラの mov だけ作り直す）
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
E = os.path.dirname(HERE)
SRC = os.path.dirname(E)
A = os.path.join(E, "analysis")
M = os.path.join(E, "media")
FPS = 30000 / 1001
LOOM = "AI動画編集を実演で徹底解説.mp4"
ORDER = [("1314", "camera"), ("1317", "camera"), ("loom", "screen"), ("1315", "camera")]
VIDEO_ONLY = False
LOOM_GAIN_DB = None   # None なら声の大きさを iPhone に合わせて自動で決める（concat で測る）


def nframes(p):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets", "-show_entries",
                                   "stream=nb_read_packets", "-of", "csv=p=0", p]).decode().strip()
    return int(out)


def part_copy(name):
    return os.path.join(M, f"loom_CFR2997.mp4" if name == "loom" else f"cam{name}_CFR2997.mov")


def parts():
    os.makedirs(M, exist_ok=True)
    for name, kind in ORDER:
        out = part_copy(name)
        if os.path.exists(out):
            continue
        if kind == "camera":
            src = os.path.join(SRC, f"IMG_{name}.MOV")
            cmd = ["ffmpeg", "-v", "error", "-stats", "-y", "-i", src, "-map", "0:v:0", "-map", "0:a:0", "-vf", "fps=30000/1001",
                   "-c:v", "h264_videotoolbox", "-b:v", "20M", "-profile:v", "high", "-pix_fmt", "yuv420p",
                   "-c:a", "pcm_s16le", "-video_track_timescale", "30000", out]
        else:
            src = os.path.join(SRC, LOOM)
            cmd = ["ffmpeg", "-v", "error", "-stats", "-y", "-i", src, "-map", "0:v:0", "-map", "0:a:0", "-vf", "fps=30000/1001",
                   "-c:v", "h264_videotoolbox", "-b:v", "8M", "-profile:v", "high", "-pix_fmt", "yuv420p",
                   "-c:a", "pcm_s16le", "-ar", "48000", "-video_track_timescale", "30000", out]
        subprocess.run(cmd, check=True)
        print(name, "frames", nframes(out), flush=True)


def speech_db(path, start=0.0, dur=None):
    """声のある所（上位30%の 100ms）の平均の大きさ（dB）"""
    import numpy as np
    cmd = ["ffmpeg", "-v", "error", "-ss", str(start)] + (["-t", str(dur)] if dur else []) + ["-i", path, "-map", "0:a:0", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"]
    a = np.frombuffer(subprocess.check_output(cmd), dtype=np.int16).astype(np.float32) / 32768
    n = len(a) // 1600
    db = 10 * np.log10((a[:n * 1600].reshape(n, 1600) ** 2).mean(1) + 1e-12)
    return float(np.mean(np.sort(db)[-max(1, n * 3 // 10):]))


def concat():
    info = []
    t = 0
    for name, kind in ORDER:
        p = part_copy(name)
        n = nframes(p)
        info.append({"name": name, "kind": kind, "copy": os.path.basename(p), "frames": n, "start_frame": t, "start_sec": t / FPS})
        t += n
    total = t
    # Loom の声の大きさを iPhone（三上さん・こういちさんの声）に合わせる
    cams = [speech_db(part_copy(n)) for n, k in ORDER if k == "camera"]
    loom_db = speech_db(part_copy("loom"))
    gain = LOOM_GAIN_DB if LOOM_GAIN_DB is not None else round(sum(cams) / len(cams) - loom_db, 1)
    print("speech dB camera", [round(c, 1) for c in cams], "loom", round(loom_db, 1), "→ Loom gain", gain, "dB", flush=True)
    ins, fv, fa = [], [], []
    for i, it in enumerate(info):
        ins += ["-i", os.path.join(M, it["copy"])]
        d = it["frames"] * 1001 / 30000
        if it["kind"] == "camera":
            fv.append(f"[{i}:v]trim=end_frame={it['frames']},setpts=PTS-STARTPTS,setsar=1,format=yuv420p[v{i}]")
            fa.append(f"[{i}:a]atrim=end={d:.6f},asetpts=PTS-STARTPTS,apad=whole_dur={d:.6f},aformat=sample_rates=48000:channel_layouts=stereo[a{i}]")
        else:
            # Loom の間のカメラ（V1）は、Loom を高さに合わせて入れたもの（07 の screen_fit と同じ見た目。V2 の画面を映す間は無効になる。
            #   冒頭ハイライトなど、カメラのファイルから切り出す所でも Loom が見えるように。2026-10-16 黒から変えた）
            fv.append(f"[{i}:v]trim=end_frame={it['frames']},setpts=PTS-STARTPTS,scale=-2:1080:flags=lanczos,pad=1920:1080:(ow-iw)/2:0:black,setsar=1,format=yuv420p[v{i}]")
            fa.append(f"[{i}:a]atrim=end={d:.6f},asetpts=PTS-STARTPTS,apad=whole_dur={d:.6f},volume={gain}dB,aformat=sample_rates=48000:channel_layouts=stereo[a{i}]")
    k = len(info)
    fc = ";".join(fv + fa) + ";" + "".join(f"[v{i}][a{i}]" for i in range(k)) + f"concat=n={k}:v=1:a=1[v][a]"
    out = os.path.join(M, "camera_CFR2997.mov")
    tmp = out + ".tmp.mov"
    subprocess.run(["ffmpeg", "-v", "error", "-stats", "-y"] + ins + ["-filter_complex", fc, "-map", "[v]", "-map", "[a]",
                    "-c:v", "h264_videotoolbox", "-b:v", "20M", "-profile:v", "high", "-pix_fmt", "yuv420p",
                    "-c:a", "pcm_s16le", "-video_track_timescale", "30000", tmp], check=True)
    os.replace(tmp, out)
    if VIDEO_ONLY:
        print("camera frames", nframes(out), "expected", total)
        return
    # 画面コピー：Loom の映像だけ（音なし）。通しのカメラのフレーム ＝ 画面コピーのフレーム ＋ N_SCREEN
    loom = next(it for it in info if it["kind"] == "screen")
    scr = os.path.join(M, "screen_CFR2997.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", os.path.join(M, loom["copy"]), "-map", "0:v:0", "-c:v", "copy", "-an",
                    "-video_track_timescale", "30000", scr], check=True)
    # 16kHz の声（文字起こし・波形の検査用）
    os.makedirs(os.path.join(A, "asr", "_work"), exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", out, "-map", "0:a:0", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
                    os.path.join(A, "asr", "_work", "camera.wav")], check=True)
    os.makedirs(os.path.join(A, "sync"), exist_ok=True)
    sync = {"model": "通しのカメラの秒 = 画面コピーの秒 + offset（画面＝Loom。撮った時間が重ならないので音の同期は無い。並べただけ）",
            "rate": 1.0, "offset": loom["start_frame"] * 1001 / 30000, "N_SCREEN": loom["start_frame"],
            "loom_gain_db": gain, "parts": info, "total_frames": total,
            "screen_size": "1108x720", "screen_end_frame": loom["start_frame"] + loom["frames"]}
    json.dump(sync, open(os.path.join(A, "sync", "sync.json"), "w"), ensure_ascii=False, indent=1)
    print(json.dumps({k: sync[k] for k in ("offset", "N_SCREEN", "total_frames", "loom_gain_db")}, ensure_ascii=False))
    print("camera frames", nframes(out), "expected", total)


def asr():
    sync = json.load(open(os.path.join(A, "sync", "sync.json")))
    out = []
    for it in sync["parts"]:
        name = it["name"]
        shift = it["start_sec"]
        end = it["frames"] * 1001 / 30000
        for s in json.load(open(os.path.join(A, "asr", f"asr_{'loom' if name == 'loom' else 'img' + name}.json"))):
            if s["start"] >= end:
                continue
            s = dict(s)
            s["start"] += shift
            s["end"] = min(s["end"], end) + shift
            s["part"] = name
            s["words"] = [dict(w, start=w["start"] + shift, end=min(w["end"], end) + shift) for w in s.get("words", []) if w["start"] < end]
            out.append(s)
    json.dump(out, open(os.path.join(A, "asr", "asr_camera.json"), "w"), ensure_ascii=False, indent=1)
    print("asr_camera.json", len(out), "segments")


if __name__ == "__main__":
    if sys.argv[1] == "camvideo":      # カメラの作業用コピーだけ作り直す（声・sync.json・文字起こしは変えない。音の大きさは sync.json の値）
        VIDEO_ONLY = True
        LOOM_GAIN_DB = json.load(open(os.path.join(A, "sync", "sync.json")))["loom_gain_db"]
        concat()
        sys.exit()
    steps = {"parts": parts, "concat": concat, "asr": asr}
    for s in (["parts", "concat", "asr"] if sys.argv[1] == "all" else sys.argv[1:]):
        steps[s]()
