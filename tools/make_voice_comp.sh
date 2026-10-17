#!/bin/zsh
# 声の作業用コピーを、完成版の大きさ（本編 約 -23 LUFS）まで上げても割れないようにする（04 の bgm.balance.limiter）。どの案件でも使える道具。
# 元：セキュリティについて v004〜v005（2026-10-17 小川さん「話した声がちょっと小さくて SE の音量が多い」→ リミッター OK）。
#   zsh tools/make_voice_comp.sh <声の素材（edit/media/ の作業用コピー）> <出力 edit/media/〇〇.wav> [上げる dB（既定 17）]
# ffmpeg：+17dB（完成版の声のクリップと同じ）→ コンプレッサー（-18dB・3:1・attack 5ms・release 150ms・knee 6）→ リミッター（-2dB）。24bit・48kHz の wav。
# 組み立ては A1・A2 をこの wav にする（plan の VOICE_FILE。声のゲイン 0dB）。素材と同じ 0秒始まり・同じ長さなので、カットの秒はそのまま使える。
# 書き出した後に本編の大きさと真のピークを測る（AAC で 1〜2dB はねる。-1 dBFS を超えたら声・BGM・SE をそろって下げる）。耳での確認はユーザー。
set -e
SRC=${1:?声の素材}; OUT=${2:?出力の wav}; GAIN=${3:-17}
[[ -e "$OUT" ]] && { echo "$OUT はもうある（上書きしない。Premiere が読み込んでいるかもしれない）"; exit 1; }
ffmpeg -nostdin -hide_banner -loglevel error -i "$SRC" -vn \
  -af "volume=${GAIN}dB,acompressor=threshold=-18dB:ratio=3:attack=5:release=150:knee=6,alimiter=limit=0.79:attack=3:release=60:level=disabled" \
  -c:a pcm_s24le -ar 48000 "$OUT"
echo "作った：$OUT"
ffmpeg -nostdin -hide_banner -i "$OUT" -af ebur128=peak=true -f null - 2>&1 | grep -A14 "Summary" | grep -E "I:|LRA:|Peak:"
