#!/bin/zsh
# 画像 I01〜I14 を描く（tools/zukai/make_zukai.py。1つずつ）。2026-10-17 メインの AI
cd ~/Desktop/video_edit_rules
for k in I01 I02 I03 I04 I05 I06 I07 I08 I09 I10 I11 I12 I13 I14; do
  echo "== $k"; python3 tools/zukai/make_zukai.py --ver "/Users/yoshizawakouichi/Desktop/みかみ案件依頼書/セキュリティについて/edit/v005" $k 2>&1 | tail -4
done
echo RENDER_DONE
