#!/bin/zsh
# 0.5秒ごとの画面を文字認識する（100枚ずつ ocr/<名前>_<番号>.json。あるものは飛ばす）
cd "$(dirname $0)"
for name in kanzen cowork; do
  ls frames/$name/*.jpg | split -l 100 - ocr/list_${name}_
done
ls ocr/list_* | xargs -P 6 -I{} zsh -c 'out={}.json; out=${out/list_/}; [ -s $out ] || ./screen_ocr $(cat {}) > $out.tmp && mv $out.tmp $out'
echo done
