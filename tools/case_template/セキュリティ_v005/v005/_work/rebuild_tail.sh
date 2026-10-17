#!/bin/zsh
# rebuild_all.sh の「組み立て」から後ろだけ（土台の読み込みが済んでいる時）
cd "${0:A:h}/.."
V=$PWD; PY=~/Desktop/video_edit_rules/env/bin/python
rm -f _work/kyocho_start_fix.json; python3 make_v005.py | tail -1
$PY _work/kyocho_start_fix.py | tail -1; python3 make_v005.py | tail -1
$PY _work/kyocho_start_fix.py | tail -1; python3 make_v005.py | tail -1
python3 ~/Desktop/video_edit_rules/tools/premiere_case/close.py --proj "$V/sec_v005.prproj" --seq sec_v005 --record --check-only | tail -1
zsh _work/run_checks.sh > _work/checks_log.txt 2>&1 || true
grep -E "切れ端 |つなぎ目 |# 強調 |found_in|画角が変わる所" _work/checks_log.txt
rm -rf 確認; python3 _work/review_jobs.py; python3 _work/finish.py --no-dissolve | tail -1
python3 _work/write_preview.py
echo TAIL_DONE
