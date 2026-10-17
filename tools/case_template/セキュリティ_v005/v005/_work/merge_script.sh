#!/bin/zsh
# script_parts/p01〜p02.txt を script_v005.txt にまとめる（台本係2人が塊ごとに書き、検査係が確かめた。頭の説明はここで付ける）
cd "${0:A:h}/.."
{ cat <<'H'
# セキュリティについて v005 の台本（カットと通常字幕）。analysis/units.txt（mlx_whisper large-v3-turbo の区切り。IMG_1320.MOV の1本）を、2 の塊に分けて全部読んで書いた（2026-10-16 台本係2人・検査係）
# 書き方（common.py の Script）：
#   u|文字 … 区切り u の頭から出す字幕／u+|文字・u+語|文字 … 区切り u の途中（語から）／u-| … 文字を出さず前の字幕を延ばす
#   x A..B|理由 … カット（A・B は u か u/語）／@ … 聞き手（創太くん）／ ／ … 2行／h A..B … 冒頭ハイライトの区間
H
for f in script_parts/p[0-9][0-9].txt; do echo; cat "$f"; done; } > script_v005.txt
