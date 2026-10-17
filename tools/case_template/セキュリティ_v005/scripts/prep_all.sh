#!/bin/zsh
# 下準備をまとめて流す（make_media.py の後）。ログは analysis/prep_*.log（セキュリティについて 2026-10-16。AI動画編集 の prep_all.sh から画面の所を外した）
#   1. 区切り（make_units）
#   2. 並べて：2回目の文字起こし（mlx・固有名詞のヒント）／DTW の語の時刻（small → large-v3-turbo）／話者の声の特徴
#   3. 塊（chunk_units）
cd "${0:A:h:h}"
PY=~/Desktop/video_edit_rules/env/bin/python
$PY scripts/make_units.py > analysis/prep_units.log 2>&1 || { echo "units failed"; exit 1; }
( HF_HUB_OFFLINE=1 $PY scripts/transcribe_prompt.py > analysis/asr/transcribe_p.log 2>&1 ) &
( $PY scripts/dtw_transcribe.py analysis/asr/_work/camera.wav analysis/asr/asr_dtw.json > analysis/asr/dtw.log 2>&1;
  $PY scripts/dtw_transcribe.py analysis/asr/_work/camera.wav analysis/asr/asr_dtw_large.json --model ~/Desktop/video_edit_rules/models/ggml-large-v3-turbo.bin > analysis/asr/dtw_large.log 2>&1 ) &
( $PY scripts/speaker_feats.py > analysis/prep_speaker.log 2>&1 ) &
wait
$PY scripts/chunk_units.py ${CHUNKS:-1} > analysis/prep_chunks.log 2>&1
echo PREP_DONE
