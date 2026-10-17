echo "== 台本"; zsh _work/merge_script.sh
$PY captions_align_v005.py 2>&1 | grep -E "^字幕|^エラー"
$PY captions_align_v005.py 2>&1 | grep -q "^エラー 0" || { echo "captions_align のエラー"; exit 1; }
echo "== カット"; $PY cuts_plan_v005.py 2>&1 | tail -2
echo "== 表"; python3 _work/check_plan.py | grep -E "^エラー|  E "
python3 _work/check_plan.py | grep -q "^エラー 0" || { echo "表のエラー"; exit 1; }
$PY _work/prechop.py; python3 _work/joins.py; python3 _work/caps_table.py > /dev/null
echo "== 土台"; $PY build_v005.py 2>&1 | tail -2
echo "== 赤枠（analysis/赤枠_v005 の決めた枠を今の土台の時刻に）"
( cd ~/Desktop/video_edit_rules && $PY tools/red_frames/place.py --src "$E/analysis/赤枠_v005" --ver "$V" --screen-size 3456x2234 2>&1 | tail -1 )
