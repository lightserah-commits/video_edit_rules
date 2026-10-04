#!/bin/zsh
# script_parts/p01〜p10.txt を script_v004.txt にまとめる（台本係・検査係が塊ごとに書いた。頭の説明はここで付ける）
cd "${0:A:h}/.."
{ cat <<'H'
# 環境設定について v001 の台本（カットと通常字幕）。analysis/units.txt（mlx_whisper large-v3-turbo の区切り 1792）を、10 の塊に分けて全部読んで書いた（2026-10-02 台本係10人・検査係10人。ワークフロー kankyo-script）
# 書き方（astra v006・ワークの完全解説と同じ。v002/common.py の Script）：
#   u|文字 … 区切り u の頭から出す字幕／u+|文字・u+語|文字 … 区切り u の途中（語から）／u-| … 文字を出さず前の字幕を延ばす
#   x A..B|理由 … カット（A・B は u か u/語）／@ … 聞き手（創太くん）。行末の「  # 田中さん」は田中さんの字幕／ ／ … 2行
# 並べ替え（A→X→Y→Z）は cuts_plan_v004.py の REORDER で行う。台本は区切りの番号順
H
for f in script_parts/p*.txt; do echo; cat "$f"; done; } > script_v004.txt
