#!/bin/zsh
# v004：書き出した mp4 から、直した所のコマを切り出して1枚に並べる（確認/v004_直した所.jpg）
cd "${0:A:h}/.."
MP4=aied_v004.mp4; OUT=確認
i=0; ins=(); lab=()
for t in 0:22.5 0:31.5 0:38.0 0:41.5 0:46.5 0:54.5 1:05.5 1:10.0 1:14.0 1:22.0 1:28.0 1:31.5 1:39.5 2:13.0 2:17.0 2:19.5; do
  f=$OUT/v004_${t//:/m}.jpg
  ffmpeg -v error -y -ss $t -i $MP4 -frames:v 1 -vf "scale=640:-1" $f
  ins+=(-i $f)
done
ffmpeg -v error -y $ins -filter_complex "xstack=inputs=16:layout=0_0|w0_0|w0+w1_0|w0+w1+w2_0|0_h0|w0_h0|w0+w1_h0|w0+w1+w2_h0|0_h0+h4|w0_h0+h4|w0+w1_h0+h4|w0+w1+w2_h0+h4|0_h0+h4+h8|w0_h0+h4+h8|w0+w1_h0+h4+h8|w0+w1+w2_h0+h4+h8" $OUT/v004_直した所.jpg
echo $OUT/v004_直した所.jpg
