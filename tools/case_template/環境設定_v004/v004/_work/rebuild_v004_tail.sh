#!/bin/zsh
# v004：画像（zukai/I*）・赤枠（G2）を入れた後の作り直し。土台 → Premiere で土台を読み込み → make 3回 → 検査 → Premiere で確認の画像（前面は元に戻す）
#   zsh v004/_work/rebuild_v004_tail.sh
set -e
cd "${0:A:h}/.."
PY=~/Desktop/video_edit_rules/env/bin/python
echo "== 土台"; $PY build_v004.py 2>&1 | tail -2
python3 _work/red_frames_g2.py | tail -1
echo "== Premiere：土台の読み込み"; python3 _work/close_v004.py
rm -rf _work/v004_stills.prproj "_work/v004_stills Masks" _work/v004_stills.prin
python3 _work/place_stills.py | grep -E '"ok"|still_offline|missing|error' | head -4
echo "== 組み立て"; rm -f _work/kyocho_start_fix.json
python3 make_v004.py | tail -1
$PY _work/kyocho_start_fix.py | tail -1
python3 make_v004.py | tail -1
$PY _work/kyocho_start_fix.py | tail -1
python3 make_v004.py | grep -E "G1|つなぎ|^字幕"
echo "== 検査"; zsh _work/run_checks.sh > _work/checks_log.txt 2>&1 || true
grep -E "0件|件 |つなぎ目 |# 強調|画角が|found|型の割合" _work/checks_log.txt
echo "== Premiere：確認の画像"; python3 _work/close_v004.py
python3 ~/Desktop/video_edit_rules/tools/font_fix.py --scan kankyo_v004.prproj | tail -1
rm -rf 確認; python3 _work/review_jobs.py; python3 _work/finish.py --no-dissolve | tail -c 300
python3 _work/diff_v002.py | tail -1
python3 _work/review_sheets.py
echo "== 終わり"
