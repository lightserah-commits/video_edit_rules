#!/bin/zsh
# v005：元から組み直し → 締めの Pan → 記録 → Media Encoder で書き出し（Pan つき）→ 書き出しの成否を AME の記録で確かめる（2026-10-17 メインの AI）
#   zsh v005/_work/rebuild_pan_export.sh <Pan のつなぎ目の秒>
#   Premiere を使う前と後にチャットで知らせる。/tmp/premiere_use.lock を置いてから流す（ほかのセッションと Premiere を共有）
set -e
AT=${1:?Pan のつなぎ目の秒}
cd "${0:A:h}/.."
V=$PWD
T=~/Desktop/video_edit_rules/tools
zsh _work/rebuild_all.sh
cp sec_v005.prproj _work/sec_v005_before_pan.prproj
python3 $T/premiere_case/close.py --proj "$V/sec_v005.prproj" --seq sec_v005 | tail -1
python3 $T/premiere_case/pan.py --proj "$V/sec_v005.prproj" --seq sec_v005 --at $AT | tail -1
python3 $T/premiere_case/close.py --proj "$V/sec_v005.prproj" --seq sec_v005 --record | tail -1
echo "== 書き出し"
LOG="$HOME/Documents/Adobe/Adobe Media Encoder/26.0/AMEEncodingLog.txt"
n0=$(iconv -f UTF-16LE -t UTF-8 "$LOG" 2>/dev/null | wc -l)
python3 _work/export.py sec_v005_pan.mp4 | tail -1
for i in $(seq 1 360); do
  new=$(iconv -f UTF-16LE -t UTF-8 "$LOG" 2>/dev/null | tail -n +$((n0 + 1)))
  if echo "$new" | grep -q "失敗"; then echo "書き出し 失敗"; echo "$new" | tail -8; exit 1; fi
  if echo "$new" | grep -q "正常にエンコード"; then echo "書き出し 成功"; break; fi
  sleep 5
done
ls -la sec_v005_pan.mp4
ffprobe -v error -show_entries format=duration -of default=nk=1:nw=1 sec_v005_pan.mp4
