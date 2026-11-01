#!/usr/bin/env python3
"""黙って PC を操作・待っている所を、カメラの早回しの動画にする（02 の P19。どの案件でも使える道具）。
元：1029 の早回しの試作 v001（2026-11-01。案件の edit/早回し試作/v001/make_ff_v001.py）。見本は YouTube Zo607dJQUG8 の 4:23.53〜4:25.84
（引きの絵を数倍速・真ん中に ▶▶▶・横の帯のノイズ・高くなった音の約2.3秒）。小川さん「この方向でOK」「画面共有の方じゃなくて、普通のカメラの方」。

  ~/Desktop/video_edit_rules/env/bin/python tools/fast_forward.py --src "<edit>/media/camera_CFR2997.mov" --in 854.65 --out 870.84 --dest "<版>/ff/ff_01.mp4" [--sec 2.3 | --speed 7]

  - 素材の --in〜--out 秒を、--speed 倍（省略なら --sec 秒＝既定 2.3 に近くなる整数の倍率）で早回しにする。絵は N コマに1コマを選ぶ（Premiere の速度と同じくコマを飛ばす）
  - 真ん中に ▶▶▶（白い線の三角3つ。1つ 幅160×高さ190・間隔150・線 7px）。白く塗った三角が左 → 真ん中 → 右と --icon-step コマ（既定 20）ごとに移り、また左へ
  - 横の帯のノイズ：1コマに 26〜46本、太さ 4〜40px・長さ 120〜760px の帯を、横にずらして写すか1列を引き伸ばして重ねる（--seed で同じ形をもう一度作れる）
  - 音：同じ倍率で速くする（高さも上がる。テープの早送り）。大きさは --lufs（既定 -30。声は約 -23〜-25）。頭と終わりに 20・30ms のフェード
  - 書き出し：--dest の mp4（1920×1080・29.97fps・H.264・bt709・AAC）と、同じ名前の .json（倍率・コマ数・秒・三角の位置の記録）
  決めるのは人（AI）：どこを早回しにするか（08 の pauses.screen・02 の P19）。Premiere ではこの mp4 をカメラのトラックに1本のクリップとして置き、
  早回しの間は字幕・強調・図解を出さない。この道具は音を聴けないので、音は未聴取として小川さんに聴いてもらう
"""
import argparse
import json
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

FPS = 30000 / 1001
W, H = 1920, 1080


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, **kw)


def read_frames(src, t_in, t_out, speed):
    """素材の絵を speed コマに1コマ選んで読む"""
    vf = (f"select='not(mod(n\\,{speed}))',setpts=N/({FPS})/TB,scale={W}:{H}:in_color_matrix=bt709:in_range=tv:out_range=pc,format=rgb24")
    raw = run(["ffmpeg", "-v", "error", "-ss", f"{t_in}", "-t", f"{t_out - t_in}", "-i", src,
               "-vf", vf, "-fps_mode", "passthrough", "-f", "rawvideo", "-"], capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3)


def make_icons():
    """▶▶▶ の4つの形（白い三角なし・左・真ん中・右）。白い壁の上でも見えるように、ごく薄い影を付ける（見本に目立つ影は無い）"""
    ss = 3
    tw, th, stride, lw = 160, 190, 150, 7
    total = stride * 2 + tw
    x0 = (W - total) // 2
    cy = H // 2
    box = (x0 - 30, cy - th // 2 - 30, x0 + total + 30, cy + th // 2 + 30)
    bw, bh = box[2] - box[0], box[3] - box[1]
    icons = []
    for filled in (None, 0, 1, 2):
        im = Image.new("RGBA", (bw * ss, bh * ss), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        for i in range(3):
            lx = (x0 - box[0] + stride * i) * ss
            top, bot, mid = (cy - th // 2 - box[1]) * ss, (cy + th // 2 - box[1]) * ss, (cy - box[1]) * ss
            pts = [(lx, top), (lx, bot), (lx + tw * ss, mid)]
            if i == filled:
                d.polygon(pts, fill=(255, 255, 255, 255))
            else:
                d.polygon(pts, outline=(255, 255, 255, 255), width=lw * ss)
        im = im.resize((bw, bh), Image.LANCZOS)
        sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
        sh.putalpha(im.getchannel("A").point(lambda a: int(a * 0.35)))
        sh = sh.filter(ImageFilter.GaussianBlur(5))
        sh.paste(im, (0, 0), im)
        icons.append(np.asarray(sh).astype(np.float32) / 255.0)
    return icons, box


def glitch(img, rng):
    """横の帯のノイズ：帯をずらして写す・1列を横に引き伸ばす（見本の 4:24 前後の形と量）"""
    out = img.copy()
    bands = rng.integers(0, H, size=int(rng.integers(4, 7)))
    n = int(rng.integers(26, 46))
    for _ in range(n):
        h = int(rng.choice([4, 6, 8, 12, 16, 20, 26, 32, 40], p=[.1, .12, .14, .14, .14, .12, .1, .08, .06]))
        y = int(np.clip(rng.choice(bands) + rng.normal(0, 90), 0, H - h))
        w = int(rng.integers(120, 760))
        x = int(rng.integers(0, W - 60)); x2 = min(W, x + w); w = x2 - x
        if w < 20:
            continue
        if rng.random() < 0.5:
            dx = int(rng.integers(-180, 180))
            sx = int(np.clip(x + dx, 0, W - w))
            strip = img[y:y + h, sx:sx + w].astype(np.float32)
        else:
            cx = int(np.clip(x + rng.integers(-40, 40), 0, W - 1))
            strip = np.repeat(img[y:y + h, cx:cx + 1].astype(np.float32), w, axis=1)
        light = rng.uniform(0.1, 0.5)
        strip = strip * (1 - light) + 205 * light
        al = rng.uniform(0.75, 1.0)
        out[y:y + h, x:x2] = (out[y:y + h, x:x2].astype(np.float32) * (1 - al) + strip * al).astype(np.uint8)
    return out


def put_icon(img, icon, box):
    x0, y0, x1, y1 = box
    a = icon[..., 3:4]
    reg = img[y0:y1, x0:x1].astype(np.float32)
    img[y0:y1, x0:x1] = (reg * (1 - a) + icon[..., :3] * 255.0 * a).astype(np.uint8)
    return img


def lufs(path):
    r = subprocess.run(["ffmpeg", "-v", "info", "-i", path, "-af", "ebur128", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    line = [l for l in r.split("Summary:")[-1].splitlines() if l.strip().startswith("I:")][0]
    return float(line.split()[1])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", required=True, help="カメラの素材（作業用コピー edit/media/camera_*.mov）")
    ap.add_argument("--in", dest="t_in", type=float, required=True, help="早回しにする所の頭（素材の秒）")
    ap.add_argument("--out", dest="t_out", type=float, required=True, help="早回しにする所の終わり（素材の秒）")
    ap.add_argument("--dest", required=True, help="書き出す mp4")
    ap.add_argument("--sec", type=float, default=2.3, help="早回しの長さの目安（--speed が無い時。既定 2.3＝見本）")
    ap.add_argument("--speed", type=int, help="倍率（整数）。省略なら --sec に近くなる倍率")
    ap.add_argument("--icon-step", type=int, default=20, help="白い三角が隣へ移るコマ数（既定 20＝見本の約0.65秒）")
    ap.add_argument("--lufs", type=float, default=-30.0, help="早回しの音の大きさ（既定 -30）")
    ap.add_argument("--seed", type=int, default=1029, help="ノイズの形の種")
    a = ap.parse_args()

    span = a.t_out - a.t_in
    speed = a.speed or max(2, round(span / a.sec))
    os.makedirs(os.path.dirname(os.path.abspath(a.dest)), exist_ok=True)
    stem = os.path.splitext(a.dest)[0]
    rng = np.random.default_rng(a.seed)

    frames = read_frames(a.src, a.t_in, a.t_out, speed)
    n = len(frames)
    dur = n / FPS

    a_raw, a_out = stem + "_audio_raw.wav", stem + "_audio.wav"
    run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a.t_in}", "-t", f"{span}", "-i", a.src, "-vn",
         "-af", f"asetrate={48000 * speed},aresample=48000", "-ac", "2", a_raw])
    gain = a.lufs - lufs(a_raw)
    run(["ffmpeg", "-v", "error", "-y", "-i", a_raw, "-af",
         f"volume={gain:.2f}dB,apad,atrim=end={dur:.6f},afade=t=in:d=0.02,afade=t=out:st={dur - 0.03:.6f}:d=0.03",
         "-ar", "48000", "-ac", "2", a_out])

    icons, box = make_icons()
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", "30000/1001", "-i", "-", "-i", a_out,
                            "-vf", "scale=in_range=pc:out_color_matrix=bt709:out_range=tv,format=yuv420p",
                            "-c:v", "libx264", "-crf", "14", "-preset", "medium",
                            "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
                            "-c:a", "aac", "-b:a", "320k", "-shortest", a.dest], stdin=subprocess.PIPE)
    states = []
    for i, f in enumerate(frames):
        k = (i // a.icon_step) % 3 + 1          # 1=左 2=真ん中 3=右
        enc.stdin.write(put_icon(glitch(f, rng), icons[k], box).tobytes())
        states.append(k)
    enc.stdin.close()
    if enc.wait() != 0:
        sys.exit("書き出しに失敗した")
    for p in (a_raw, a_out):
        os.remove(p)

    rec = {"src": a.src, "in": a.t_in, "out": a.t_out, "speed": speed, "frames": n, "sec": round(dur, 3),
           "audio_gain_db": round(gain, 2), "lufs": a.lufs, "seed": a.seed, "icon_step": a.icon_step,
           "icon_box": box, "icon_state_per_frame": states, "dest": a.dest}
    json.dump(rec, open(stem + ".json", "w"), ensure_ascii=False, indent=1)
    print(f"{span:.2f}秒 → {speed}倍・{n}コマ（{dur:.3f}秒）・音 {gain:+.2f}dB → {a.dest}")


if __name__ == "__main__":
    main()
