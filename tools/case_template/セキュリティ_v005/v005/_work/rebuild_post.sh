#!/bin/zsh
# rebuild_all.sh の Premiere を使う段から後ろ（rebuild_pre.sh の後）。Premiere を使う前と後にチャットで知らせる
set -o pipefail
cd "${0:A:h}/.."
V=$PWD; E=${V:h}
PY=~/Desktop/video_edit_rules/env/bin/python
echo "== Premiere：前の組み立てを閉じる（開いていれば）"
python3 ~/Desktop/video_edit_rules/tools/premiere_case/close.py --proj "$V/sec_v005.prproj" --seq sec_v005 2>&1 | tail -1 || true
rm -rf _work/v005_stills.prproj "_work/v005_stills Masks"
echo "== Premiere：土台の読み込み"
python3 _work/place_stills.py | grep -E '"V4|still_offline|missing|front' | head -6 || { echo "place_stills のエラー"; exit 1; }
echo "== 組み立て"; rm -f _work/kyocho_start_fix.json
python3 make_v005.py > _work/make_out.txt 2>&1 || { tail -5 _work/make_out.txt; echo "make のエラー"; exit 1; }; tail -1 _work/make_out.txt
grep -E "問いの札の頭|図解の札の音" _work/make_out.txt
$PY _work/kyocho_start_fix.py | tail -1; python3 make_v005.py | tail -1 || exit 1
$PY _work/kyocho_start_fix.py | tail -1; python3 make_v005.py | tail -1 || exit 1
python3 ~/Desktop/video_edit_rules/tools/premiere_case/close.py --proj "$V/sec_v005.prproj" --seq sec_v005 --record --check-only | tail -1
echo "== 検査"; zsh _work/run_checks.sh > _work/checks_log.txt 2>&1 || true
grep -E "切れ端 |つなぎ目 |# 強調 |found_in|画角が変わる所" _work/checks_log.txt
echo "== Premiere：確認の画像"; rm -rf 確認; python3 _work/review_jobs.py; python3 _work/finish.py --no-dissolve | tail -1 | tee _work/finish_out.txt
ls 確認 | wc -l
python3 _work/write_preview.py "$(python3 -c "import ast,json;print(json.dumps(ast.literal_eval(open('_work/finish_out.txt').read())))")"
$HOME/Desktop/video_edit_rules/env/bin/python _work/make_sheets.py
echo POST_DONE
