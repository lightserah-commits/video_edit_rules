#!/bin/zsh
# 工程9 の検査を全部まわす（編集の依頼文.md の工程9 の表）。結果は v004/checks_*.json・_work/flow.txt・_work/repeats.tsv
#   zsh v004/_work/run_checks.sh
cd "${0:A:h}/.."
T=~/Desktop/video_edit_rules/tools
PY=~/Desktop/video_edit_rules/env/bin/python
P=kankyo_v004.prproj; S=kankyo_v004
HL=$(python3 -c "import json;print(json.load(open('_work/cuts_v004.json')).get('highlight_external_frames',0))")
echo "## 切れ端"; python3 $T/check_slivers.py $P --seq $S --out checks_slivers.json | tail -5
echo "## 声のブツッ"; python3 $T/check_chops.py $P --seq $S --track A1 --media camera_CFR2997.mov=../analysis/asr/_work/camera.wav --out checks_chops.json | tail -8
echo "## 強調の文言"; python3 $T/kyocho_check.py --csv decoration_plan.csv > _work/kyocho_check.txt; tail -15 _work/kyocho_check.txt
echo "## 強調の出る瞬間"; $PY $T/check_kyocho_timing.py $P --seq $S --track V7 --asr camera_CFR2997.mov=../analysis/asr/asr_camera.json --wav camera_CFR2997.mov=../analysis/asr/_work/camera.wav --out checks_kyocho_timing.json | tail -12
echo "## くり返し"; python3 $T/find_repeats.py $P --seq $S --track V6 --out _work/repeats.tsv | tail -4
echo "## 流れ"; python3 $T/flow_table.py $P --seq $S --label V6=字幕 --label V7=強調 --label V5=説明 --label V9=話題 --label V10=ボード --label V12=札1 --label V13=札2 --label V14=札3 --label V15=図解 --label V8=札・シリーズ --out _work/flow.txt | tail -2
echo "## フォント"; python3 $T/font_fix.py --scan $P | tail -3
echo "## 画角の変わり目"; python3 _work/check_gakaku.py | head -12
echo "## 構造"; python3 $T/check_deco.py $P --seq $S --camera V1 --cover V2 --visual V3-V5,V7,V9-V10,V12-V16 --se A4 --titles V8 --after $HL --out checks_deco.json | tail -25
