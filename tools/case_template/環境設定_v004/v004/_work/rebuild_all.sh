#!/bin/zsh
# v001 を台本・表から全部作り直す（直しの後に）。Premiere を2回使う（土台の読み込み・確認の画像の書き出し）。
#   zsh v004/_work/rebuild_all.sh [--no-images]
set -e
cd "${0:A:h}/.."
PY=~/Desktop/video_edit_rules/env/bin/python
echo "== 台本"; zsh _work/merge_script.sh
$PY captions_align_v004.py 2>&1 | grep -E "^字幕|^エラー|  E " 
$PY captions_align_v004.py 2>&1 | grep -q "^エラー 0" || { echo "captions_align のエラー"; exit 1; }
echo "== カット"; $PY cuts_plan_v004.py 2>&1 | tail -3
echo "== 表"; python3 _work/check_plan.py | grep -E "^エラー|  E "
python3 _work/check_plan.py | grep -q "^エラー 0" || { echo "表のエラー"; exit 1; }
$PY _work/prechop.py
python3 _work/joins.py; python3 _work/caps_table.py > /dev/null
echo "== 土台"; $PY build_v004.py 2>&1 | tail -3
python3 screen_ocr_v004.py frames | tail -1; python3 screen_ocr_v004.py ocr | tail -1; python3 screen_marks_v004.py | head -1
echo "== Premiere：土台の読み込み"; python3 _work/close_v004.py
rm -rf _work/v004_stills.prproj "_work/v004_stills Masks"
python3 _work/place_stills.py | grep -E '"ok"|still_offline|missing|error' | head -5
echo "== 組み立て"; rm -f _work/kyocho_start_fix.json
python3 make_v004.py | tail -1
$PY _work/kyocho_start_fix.py | tail -1
python3 make_v004.py | tail -1
$PY _work/kyocho_start_fix.py | tail -1
python3 make_v004.py | tail -1
echo "== 検査"; zsh _work/run_checks.sh > _work/checks_log.txt 2>&1 || true
grep -E "件|つなぎ目|found|# 強調|# 型" _work/checks_log.txt
if [[ "$1" != "--no-images" ]]; then
  echo "== Premiere：確認の画像"; rm -rf 確認; python3 _work/review_jobs.py; python3 _work/finish.py --no-dissolve | tail -1
fi
