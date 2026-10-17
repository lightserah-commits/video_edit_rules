#!/bin/zsh
# 次の版のフォルダを作る（セキュリティについて。2026-10-17 メインの AI）。v005 を作った時の手順をそのまま書いた：
#   台本・表・スクリプトだけを写し（書き出し・.prproj・確認の画像・記録は写さない）、名前と中身の「vNNN」を新しい版にする。
#   図解・画像（zukai/）と冒頭ハイライト（hl/）は大きいので v001 のフォルダを指すリンクのまま（描き直しは make_zukai.py --name=auto の新しい名前）
#   zsh v005/_work/next_version.sh v005
set -e
NEW=$1
[[ -n "$NEW" ]] || { echo "使い方：zsh next_version.sh v005"; exit 1; }
cd "${0:A:h}/.."
CUR=${PWD:t}; E=${PWD:h}
[[ -e "$E/$NEW" ]] && { echo "$E/$NEW はもうある（上書きしない）"; exit 1; }
rsync -a --exclude 'zukai' --exclude 'hl' --exclude '確認' --exclude '*.mp4' --exclude '*.prproj' --exclude "_work/${CUR}_stills Masks" \
  --exclude '_work/_wake' --exclude 'checks_*.json' --exclude "${CUR}_記録.json" --exclude "sec_${CUR}.ai_build.json" --exclude '_work/*.log' \
  --exclude '確認_*.md' --exclude '直し_*.md' --exclude 'Adobe*' "$E/$CUR/" "$E/$NEW/"
cd "$E/$NEW"
ln -s ../v001/hl hl
# 図解・画像（zukai/）は前の版から「自分の分」を作る（2026-10-17 セキュリティについて v004〜v005）：表（images_spec.py・inserts.json・図解ごとの diagram.json・page.html）と
#   out/<KEY>/manifest.json は写し（shift.py が書き換えるので前の版のを書き換えない）、重い動画・画像は前の版の実ファイルへのリンク。
#   描き直す絵は、out/<KEY> のリンクを消してから描く（リンクのまま描くと前の版の動画を上書きする）。前の版の .prproj が読み込んでいる場所に同じ名前で描かない（--name=auto）
$HOME/Desktop/video_edit_rules/env/bin/python - "$E/$CUR/zukai" "$E/$NEW/zukai" <<'PY'
import os, shutil, sys
src, dst = sys.argv[1], sys.argv[2]
src = os.path.realpath(src)
os.mkdir(dst)
for name in sorted(os.listdir(src)):
    s, d = os.path.join(src, name), os.path.join(dst, name)
    if name == "out":
        continue
    if os.path.isdir(s):
        shutil.copytree(s, d, symlinks=True)
    else:
        shutil.copy2(s, d)
os.mkdir(os.path.join(dst, "out"))
for key in sorted(os.listdir(os.path.join(src, "out"))):
    so, do = os.path.join(src, "out", key), os.path.join(dst, "out", key)
    if not os.path.isdir(so):
        continue
    os.mkdir(do)
    for f in os.listdir(so):
        sf, df = os.path.join(so, f), os.path.join(do, f)
        if f.startswith("manifest"):
            shutil.copy2(sf, df)
        else:
            os.symlink(os.path.realpath(sf), df)
print("zukai：表と manifest は写し、動画・画像はリンク")
PY
for f in $(find . -name "*${CUR}*" -not -path './zukai*' -not -path './hl*' | sort -r); do mv "$f" "${f:h}/${${f:t}//$CUR/$NEW}"; done
find . -path ./zukai -prune -o -path ./hl -prune -o -type f \( -name '*.py' -o -name '*.sh' -o -name '*.jsx' \) -print | while read f; do
  perl -i -pe "s/(?<!hl_)${CUR}/${NEW}/g" "$f"
done
echo "作った：$E/$NEW（残った ${CUR} の名前）"; find . -name "*${CUR}*" -not -path './zukai/*' -not -path './hl/*'
