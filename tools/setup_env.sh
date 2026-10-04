#!/bin/zsh
# 道具の Python（env/）と文字起こしのモデル（models/）を video_edit_rules の中に作る。何度流してもよい（あるものは飛ばす）。
# どちらも大きいので Git に入れない（.gitignore）。iMac など別の Mac では、この1本を流す。
#   zsh tools/setup_env.sh
# 入るもの（2026-10-05 に作った時の大きさ）：
#   env/  … Python 3（Homebrew の python3）の venv。numpy・Pillow・PyYAML・mlx-whisper（mlx・torch・numba・scipy など）約 1.2GB
#   models/whisper-large-v3-turbo/ … mlx_whisper の文字起こしのモデル（Hugging Face mlx-community/whisper-large-v3-turbo）約 1.6GB
#   models/ggml-small.bin … whisper-cli の語の時刻（tools/audible_onset.py transcribe の -dtw）約 470MB（Hugging Face ggerganov/whisper.cpp）
#   models/ggml-large-v3-turbo.bin … whisper-cli の大きいモデル（あれば使う。無くてもよい）
# 使い方：python は ~/Desktop/video_edit_rules/env/bin/python。mlx_whisper はモデルをパスで渡し、HF_HUB_OFFLINE=1 を先に置く
#   （名前で呼ぶとダウンロードする。AI メモリ whisper-local-model-offline）
# 2026-10-05 小川さん「このフォルダの中に道具とか全部まとめておいてほしい」（~/Documents/Codex にあった前の環境が消えたため）
set -e
ROOT=~/Desktop/video_edit_rules
cd "$ROOT"
mkdir -p models
PYBASE=$(command -v python3.14 || command -v python3)
if [[ ! -x env/bin/python ]]; then
  echo "== Python の環境（$PYBASE）"; "$PYBASE" -m venv env
fi
env/bin/python -m pip install -q --upgrade pip
env/bin/python -m pip install -q numpy pillow pyyaml mlx-whisper
if [[ ! -f models/whisper-large-v3-turbo/weights.safetensors ]]; then
  echo "== mlx の文字起こしモデル（約 1.6GB）"
  env/bin/python -c 'from huggingface_hub import snapshot_download; snapshot_download("mlx-community/whisper-large-v3-turbo", local_dir="models/whisper-large-v3-turbo")'
fi
if [[ ! -f models/ggml-small.bin ]]; then
  echo "== whisper-cli の small モデル（約 470MB）"
  curl -L --fail -o models/ggml-small.bin https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin
fi
command -v whisper-cli >/dev/null || echo "!! whisper-cli が無い（brew install whisper-cpp。入れる前に小川さんに聞く）"
command -v ffmpeg >/dev/null || echo "!! ffmpeg が無い（brew install ffmpeg。入れる前に小川さんに聞く）"
env/bin/python -c "import numpy, PIL, yaml, mlx_whisper; print('env ok', numpy.__version__)"
du -sh env models
