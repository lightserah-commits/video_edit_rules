#!/bin/zsh
# 土台（v004_stills.prproj）はそのまま、組み立て（make）から後だけをやり直す（直し10 のような make だけの直しの時）
set -e
cd "${0:A:h}/.."
V=$PWD
PY=~/Desktop/video_edit_rules/env/bin/python
python3 ~/Desktop/video_edit_rules/tools/premiere_case/close.py --proj "$V/aied_v004.prproj" --seq aied_v004 2>&1 | tail -1
echo "== 組み立て"; rm -f _work/kyocho_start_fix.json
python3 make_v004.py | tail -1
$PY _work/kyocho_start_fix.py | tail -1; python3 make_v004.py | tail -1
$PY _work/kyocho_start_fix.py | tail -1; python3 make_v004.py | tail -1
python3 ~/Desktop/video_edit_rules/tools/premiere_case/close.py --proj "$V/aied_v004.prproj" --seq aied_v004 --record --check-only | tail -1
echo "== 検査"; zsh _work/run_checks.sh > _work/checks_log.txt 2>&1 || true
grep -E "切れ端 |つなぎ目 |# 強調 |# 型|found_in|画角が変わる所" _work/checks_log.txt
