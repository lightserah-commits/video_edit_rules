"""DTW の語の時刻つきの文字起こし（tools/audible_onset.py transcribe と同じ形の出力）。失敗したかけらは半分に分けてやり直す。
  python3 scripts/dtw_transcribe.py analysis/asr/_work/camera.wav analysis/asr/asr_dtw.json [--model ~/Desktop/video_edit_rules/models/ggml-large-v3-turbo.bin]
  1015 で、最初のかけら（0〜190秒。短い発話が続く）で whisper-cli 1.9.4 が「WHISPER_ASSERT: filter_width < a->ne[2]」（DTW の中央値フィルタ。
  語の少ない区切りで起きる）で止まった（1003 では起きなかった）。道具（audible_onset.py）は変えず、案件の中でやり直しを足した：
  失敗したかけら（190秒）→ 前半・後半（各 100秒）に分けてやり直す → それでも失敗したら 50秒ずつ → それでも失敗した所は飛ばして記録（その間の字幕の候補は mlx の2つだけになる）
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import wave

sys.path.insert(0, os.path.expanduser("~/Desktop/video_edit_rules/tools"))
import audible_onset as AO  # noqa: E402


def run_piece(wav, t, dur, model, preset, tmp, tag):
    part, base = os.path.join(tmp, f"{tag}.wav"), os.path.join(tmp, tag)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-t", str(dur), "-i", wav, "-c", "copy", part], check=True)
    r = subprocess.run(["whisper-cli", "-m", model, "-l", "ja", "-nfa", "-mc", "0", "-dtw", preset, "-ojf", "-of", base, part],
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=900)
    if r.returncode != 0:
        return None, (r.stderr or b"").decode("utf-8", errors="replace").strip().splitlines()[-1:]
    return json.loads(open(base + ".json", "rb").read().decode("utf-8", errors="replace")), None


def collect(d, t, lo, hi):
    out = []
    for seg in d.get("transcription", []):
        for tok in seg.get("tokens", []):
            off = dict(tok.get("offsets") or {})
            f = off.get("from", 0) / 1000 + t
            dtw = tok.get("t_dtw")
            at = dtw / 100 + t if isinstance(dtw, (int, float)) and dtw >= 0 else f
            if not (lo <= at < hi):
                continue
            off["from"], off["to"] = int(round(f * 1000)), int(round(off.get("to", 0) + t * 1000))
            tok = {**tok, "offsets": off}
            if isinstance(tok.get("t_dtw"), (int, float)) and tok["t_dtw"] >= 0:
                tok["t_dtw"] = int(round(tok["t_dtw"] + t * 100))
            out.append(tok)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("wav")
    ap.add_argument("out")
    ap.add_argument("--model")
    a = ap.parse_args()
    model = a.model or next((m for m in AO.MODEL_CANDIDATES if os.path.exists(m)), None)
    preset = AO.dtw_preset(model)
    with wave.open(a.wav, "rb") as w:
        total = w.getnframes() / w.getframerate()
    CH, OV = AO.CHUNK_SEC, AO.CHUNK_OVERLAP
    tokens, log, t, i = [], [], 0.0, 0
    with tempfile.TemporaryDirectory() as tmp:
        while t < total:
            lo, hi = t + (OV / 2 if i > 0 else 0.0), t + CH + OV / 2
            d, err = run_piece(a.wav, t, CH + OV, model, preset, tmp, f"c{i:03d}")
            if d is not None:
                got = collect(d, t, lo, hi)
                note = ""
            else:
                got, fails = [], []
                # 半分ずつ（重ねて）→ さらに半分
                def sub(s0, s1, depth):
                    nonlocal got
                    dd, e2 = run_piece(a.wav, max(0.0, s0 - OV / 2), (s1 - s0) + OV, model, preset, tmp, f"c{i:03d}_{s0:.0f}")
                    if dd is not None:
                        got += collect(dd, max(0.0, s0 - OV / 2), s0, s1)
                    elif depth < 2:
                        m = (s0 + s1) / 2
                        sub(s0, m, depth + 1)
                        sub(m, s1, depth + 1)
                    else:
                        fails.append(f"{s0:.0f}〜{s1:.0f}秒")
                m = (lo + hi) / 2
                sub(lo, m, 1)
                sub(m, hi, 1)
                got.sort(key=lambda x: x.get("t_dtw", 0))
                note = f"（やり直し。飛ばした所：{'・'.join(fails) or 'なし'}）"
            tokens += got
            log.append({"start": t, "tokens": len(got), "note": note})
            print(f"  {t / 60:5.1f}分〜 {len(got)}語{note}", flush=True)
            i, t = i + 1, t + CH
    json.dump({"model": model, "dtw": preset, "chunks": log, "transcription": [{"tokens": tokens}]},
              open(a.out, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"{a.out}: {len(tokens)}語（{len(log)}かけら）")


if __name__ == "__main__":
    main()
