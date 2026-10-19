# AI動画編集 v004 の組み立て一式（次の案件の雛形。iPhone の撮影を何本かつなぐ＋画面録画〈Loom〉の動画）

「AI動画編集を実演で徹底解説」（みかみ案件依頼書。2026-10-16 最後の版 v004・18:41.3・小川さん「確認1〜10はおすすめどおりで OK です。納品に進めてください。」）の
作業場 `edit/` から、**コードと小さい表だけ**を写したもの（2026-10-16 写し）。
動画・画像・.prproj・1MB を超える JSON や XML・音・Adobe のフォルダ・`zukai/out/`・`zukai/assets/` の絵・`確認/` の画像・ログは入っていない。

- `00_案件メモ.md`：edit/ 直下の案件メモ（素材・通しの時刻・版の表・決まったこと・作り直しの順）
- `scripts/`：edit/scripts/（素材を通しの時刻に並べる・文字起こし・区切り・画面の f5 と動き・赤枠の下ごしらえ）
- `v004/`：edit/v004/ と同じ並び（`*.py`・`*.sh`・`*.jsx`・`plan_parts/`・`script_parts/`・`hl/`・`zukai/`〈図解ごとの page.html・diagram.json・images_spec.py・inserts.json〉・`_work/` のスクリプトと表・`確認_v004.md`・`直し_v004.md`・`v004_記録.json`）

## 環境設定_v004 との違い（こちらが新しい。1015claude project開設 v005 → この案件と写してきた）

- 素材が4本（IMG_1314 → IMG_1317 → Loom → IMG_1315）。撮った時間が重ならないので同期はせず、流れの順に「通しの時刻」へ並べる（`scripts/make_media.py`。sync.json の parts・N_SCREEN・loom_gain_db −13.6）
- 画面録画は Loom の 1108×720。高さに合わせて 150%、ワイプなし（`build_v004.py` の SCREEN_W/H・SCALE）
- 素材のつなぎ目は必ず切れ目にする（`cuts_plan_v004.py` の BOUNDS）。Loom のキーボード・クリックの音を声と取り違えない（同じファイルの LOOM_0/LOOM_1 の所）
- 字幕を出さない区切り：台本で `u|∅…`（Loom の中で流した見本の動画の音）。`make_v004.py` の「∅」の所
- 構成の表は `plan_parts/dNN_<表>.txt`（d00＝メイン、d01・d02＝装飾係の塊、d03＝直し）。画像は IMAGES 表と `zukai/images_spec.py`・`zukai/inserts.json`（右上の部分挿入は hide_title で右上タイトルを外す）
- **画面録画にカメラの丸（Loom の顔）が焼き込まれている時**：強調・ボード・※をその丸と左右の黒い帯にかけない
  - 強調：`make_v004.py` の「顔の丸」（479行目あたり）。幅 1360px を超える物は縮め、真ん中 x830・上へ50px。丸が右上の区間（この案件は字幕 534〜631）は縮めるだけ
  - ボード：同じファイルの 668行目あたり（帯の右端 x≦1510）＋ `plan_parts/d00_BOARDS.txt` の8列目（文字の大きさ）
  - ※：`plan_parts/dNN_NOTES.txt` の6列目（上下のずらし）
  - 丸の位置・区間は案件ごとに違う。画面の f5 を見て決め直す
- 強調が赤枠を隠す時は、赤枠を強調が出る所で終える（`_work/red_frames.json` の end。v004 の 538）

## 1015claude project開設 v007 から足した所（2026-10-16。ルールの変更は 変更履歴.md の同じ日）

- `make_v004.py` の `cap_telop`：強調の前置きで前の字幕を置き直す所が、AI指示中（P17）の字幕を普通の字幕に戻していた不具合の直し（1015 v006 で見つかった）。**Premiere で組み立てての確かめはまだ**（構文だけ）
- 締めの Pan（02 の transitions.closing_pan。毎回）：make の後・検査の前に `tools/premiere_case/pan.py`（rebuild_all.sh にはまだ入れていない。つなぎ目の秒は案件ごとに決める）
- 1015 v007 にあって、ここにはまだ無い仕掛け（要る案件で、その版から写す）：cuts の MOVES（話の並べ替え＝08 の reorder.spoiler）・EXTRA_CUTS（「えー」）・KEEP_WHOLE／END_AT／SPLIT_AT（最後のバイバイを残す＝08 の keep）・`_work/units_patch.json`（区切りに抜けた語）・plan の ZOOM_FACE（顔が取れない寄り）・make の「並列赤」（赤い札 T199 を左上に積む。02 の P11 は判断待ち）。場所は `~/Desktop/みかみ案件依頼書/1015claude project開設/edit/v007/`

## 作り直しの順

`v004/_work/rebuild_all.sh`（merge_script → captions_align → cuts_plan → build → zukai/shift → 赤枠 → Premiere place_stills → make〈kyocho_start_fix を挟んで3回〉→ run_checks → finish）。
make から後だけなら `rebuild_make_only.sh`（Premiere を使わない所までなら `rebuild_make_checks.sh`）。書き出しは `tools/premiere_case/export.py`。

## ハマりどころ

- 前の版のフォルダを写して make だけやり直すと、土台（`_work/vNNN_stills.prproj`）の中のシーケンス名が前の版のまま残る。
  土台の `<Name>aied_vOLD</Name>` と `_work/base_vNNN_map.json` の sequence を新しい版の名前に直す（v004 で直した）
- `make_v004.py` の PEAK_FIX（大きい声のクリップを下げる。キーは camera_CFR2997.mov の秒）は 1015 の素材の値のまま残っていて、この案件で 0:24.3〜0:27.0 の声を理由なく 4dB 下げた。
  新しい案件では空にして、書き出した mp4 を ebur128 で測ってから、その案件の秒で入れる
- sed で版の名前を置き換えるのは `*.py`・`*.sh`・`*.jsx` だけにして、JSON の中の前の版の絶対パス（図解・画像・赤枠の画像）はそのまま指させる（ファイルがあるか確かめる）
- 中の絶対パス（ユーザー名入り）：`hl/fonts.css`・`hl/hl.js`・JSON の記録。案件の場所：`plan_v004.py`・`hl/make_hl.py`・`_work/merge_script.sh`・`scripts/make_media.py`
- 中身（plan_parts・script_parts・図解・ハイライト・赤枠）は新しい案件で作り直す。ここは作り方の見本
