#!/bin/zsh
# rebuild_all.sh の Premiere を使わない段だけ（台本 → 字幕の時刻 → カット → 表 → 土台 XML → 赤枠の時刻）
set -e; set -o pipefail
cd "${0:A:h}/.."
V=$PWD; E=${V:h}
PY=~/Desktop/video_edit_rules/env/bin/python
sed -n '/^echo "== 台本"/,/^echo "== Premiere：土台の読み込み"/p' _work/rebuild_all.sh | sed '$d' > _work/_pre_body.sh
source _work/_pre_body.sh
echo PRE_DONE
