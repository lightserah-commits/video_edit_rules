#!/bin/zsh
# AI動画編集 v005 を台本・表から全部作り直す（1015 v005 の rebuild_all を写した。図解・画像の時刻合わせ〔shift.py〕を土台の前に足した・画面は Loom 1108×720）。元の説明：v005 を台本・表から全部作り直す（編集の依頼文.md の工程12「作り直しは1本のスクリプトに全部の段を入れて元から流す」）。
#   zsh v005/_work/rebuild_all.sh [--no-images]
#   段：台本 → 字幕の時刻 → カット → 表の検査 → 土台 XML → 赤枠の時刻 → Premiere：読み込み → 組み立て（強調の出だしの直し2回）→ 検査 → Premiere：確認の画像
#   冒頭ハイライトは hl/make_hl.py（別に作る。hl/hl_manifest.json を土台と組み立てが読む）
#   Premiere を使う所（place_stills・finish）は、使う前と後にチャットで知らせる。前の組み立てを開いていれば close.py で閉じてから（ユーザーの直しが無いか確かめる）
set -e
cd "${0:A:h}/.."
V=$PWD; E=${V:h}
PY=~/Desktop/video_edit_rules/env/bin/python
echo "== 台本"; zsh _work/merge_script.sh
$PY captions_align_v005.py 2>&1 | grep -E "^字幕|^エラー"
$PY captions_align_v005.py 2>&1 | grep -q "^エラー 0" || { echo "captions_align のエラー"; exit 1; }
echo "== カット"; $PY cuts_plan_v005.py 2>&1 | tail -2
echo "== 表"; python3 _work/check_plan.py | grep -E "^エラー|  E "
python3 _work/check_plan.py | grep -q "^エラー 0" || { echo "表のエラー"; exit 1; }
$PY _work/prechop.py; python3 _work/joins.py; python3 _work/caps_table.py > /dev/null
echo "== 図解・画像の時刻（カットで字幕が動いた分。区間の素材が変わったら止まる＝描き直し）"
( cd ~/Desktop/video_edit_rules && python3 tools/zukai/shift.py --ver "$V" 2>&1 | grep -v "+0コマ" | tail -12 )
echo "== 土台"; $PY build_v005.py 2>&1 | tail -2
echo "== Premiere：土台の読み込み"
python3 ~/Desktop/video_edit_rules/tools/premiere_case/close.py --proj "$V/sec_v005.prproj" --seq sec_v005 2>/dev/null | tail -1 || true
rm -rf _work/v005_stills.prproj "_work/v005_stills Masks"
python3 _work/place_stills.py | grep -E '"V4|still_offline|missing|front' | head -6
echo "== 組み立て"; rm -f _work/kyocho_start_fix.json
python3 make_v005.py | tail -1
$PY _work/kyocho_start_fix.py | tail -1; python3 make_v005.py | tail -1
$PY _work/kyocho_start_fix.py | tail -1; python3 make_v005.py | tail -1
python3 ~/Desktop/video_edit_rules/tools/premiere_case/close.py --proj "$V/sec_v005.prproj" --seq sec_v005 --record --check-only | tail -1
echo "== 検査"; zsh _work/run_checks.sh > _work/checks_log.txt 2>&1 || true
grep -E "切れ端 |つなぎ目 |# 強調 |# 型|found_in|画角が変わる所" _work/checks_log.txt
if [[ "$1" != "--no-images" ]]; then
  echo "== Premiere：確認の画像"; rm -rf 確認; python3 _work/review_jobs.py; python3 _work/finish.py --no-dissolve | tail -1
  python3 _work/write_preview.py
fi
