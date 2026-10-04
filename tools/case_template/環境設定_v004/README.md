# 環境設定 v004 の組み立て一式（次の案件の雛形）

「環境設定について」（みかみ案件依頼書。2026-10-04 最後の版 v004・34:51.1・mp4 書き出し済み・小川さん「今回がラスト修正で書き出しまで」）の
作業場 `edit/v004/` から、**コードと小さい表だけ**を写したもの（2026-10-05 写し。小川さん OK 済みで edit/ はゴミ箱へ）。
動画・画像・.prproj・1MB を超える JSON や XML・音・Adobe のフォルダ・`zukai/out/`・`zukai/assets/` の写真・`確認/` の画像は入っていない。

- `00_案件メモ.md`：edit/ 直下の案件メモ（素材の場所・同期・版の表・決まったこと・作り直しの順）
- `v004/`：edit/v004/ と同じ並び（`*.py`・`*.sh`・`*.jsx`・`plan_parts/`・`script_parts/`・`hl/`（make_hl.py・README と小さいコード・表）・
  `zukai/`（図解ごとの diagram.json・page.html・作り方の .py・lib・README・inputs）・`_work/` のスクリプトと 1MB 以下の表）・`確認_v004.md`・`v004_記録.json` など

## 次の案件はここから写して始める

1. 新しい案件の `edit/` に `v000_source/` などを作るまでは `編集の依頼文.md` の工程どおり。組み立てのスクリプトが要る所で、ここの `v004/` を `edit/v001/` に写す
2. 版の名前・案件名を sed で置き換える（例：`v004`→`v001`、`kankyo_v004`→`<新しい案件の短い名前>_v001`、ファイル名の `_v004` も）。
   `grep -rl kankyo_v004 v001/ | xargs sed -i '' 's/kankyo_v004/<名前>_v001/g'` のように、置き換える前に `grep` で数を見る
3. **中の絶対パスと案件だけの値は直す**（sed では直らない）：
   - 案件の場所：`plan_v004.py`・`hl/make_hl.py`・`_work/merge_script.sh` が `~/Desktop/みかみ案件依頼書/環境設定について` を持つ
   - ユーザー名の入ったパス：`hl/fonts.css`・`hl/hl.js`・`zukai/lib/zukai.css`・`zukai/lib/zukai.js`（図解は `tools/zukai/lib` を使えばよい。下の表）
   - 素材の値：`cuts_plan_v004.py` の `SRC_END`（カメラ IMG_1305.MOV の長さ）、同期のずれ（`N_SCREEN` など。00_案件メモ.md の同期）、字幕ID・時刻を名指ししている所
     （`make_v004.py` の `FACE_SRC`・`caps["1100"]` など、`plan_parts/` の中身、`zukai/` の図解ごとの中身、`hl/clips.tsv`）は全部この案件だけのもの
4. 中身（plan_parts・script_parts・図解・ハイライト）は新しい案件で作り直す。ここは作り方の見本

## どこに何があるか（直しの決まりが入っている所）

- **G4**（話し手が替わる時、前の人の字幕を残さない＝字幕をカットのコマから出す）：`v004/cuts_plan_v004.py` の G4 の所（`# v004 G4` 438行目あたり〜）
- **G5**（02 の P17：AI に話しかけて頼んでいる間、※AI指示中 をゆっくり出し消し・字幕は白い座布団に黒い文字）：`v004/make_v004.py` の G5 の所（`T200_CY0`・`AI_NOTE`・`AI_FADE` の定数 55行目あたり、`# v004 G5` 194・486行目あたり、ディゾルブ 1178行目あたり）
- **小川さんの顔まね**（02 の P18：無言の顔まねを 151% の寄り・字幕と右上タイトルと BGM を外す・頭にポカン）：`v004/make_v004.py` の `FACE_SRC`（199行目あたり）
- 作り直しの順：`00_案件メモ.md` の版の表 v004 の行（merge_script → captions_align → cuts_plan → build → zukai/shift_v004.py → red_frames_g2 → Premiere place_stills → make（kyocho_start_fix を挟んで3回）→ run_checks → finish → export）

## tools/ に一般化して写したものとの関係（どちらが新しいか）

次の物は 2026-10-05 に `tools/` へ「どの案件でも使える道具」として写した。**tools/ の方が新しい**（場所を引数に・案件名なし・直しを足した）。
ここ（v004）の物は v004 で実際に動かした元として残す。新しい案件では tools/ の方を使う。

| ここ（v004） | tools/（新しい） | tools/ で変えた所 |
|---|---|---|
| `_work/check_gakaku.py` | `tools/check_gakaku.py` | プロジェクト・シーケンス・出力・意図のまたぎを引数に。v004 で流すと同じ結果（× 0） |
| `_work/red_frames_g2.py`・`_work/retime_red_frames.py`・`screen_ocr_v004.py`（と edit/analysis/赤枠_v004/ の prep.py・render.py） | `tools/red_frames/`（place.py・retime.py・screen_frames.py・prep.py・render.py） | 版の表・画面の大きさを引数に。place.py は v004 と同じ赤枠 149個。render.py は splits も描く |
| `zukai/make_zukai.py`・`tl.py`・`gen_images.py`・`shift_v004.py`・`lib/`・`_work/run_zukai.py`・`_work/z7_head_pad.py` | `tools/zukai/`（make_zukai.py・tl.py・gen_images.py・shift.py・head_pad.py・run_zukai.py・lib/・facedet.swift） | 版のフォルダを `--ver` に。書体を PostScript 名に・イラストの場所を render_frames.mjs が入れる（ユーザー名なし）。顔検出の数字を中心と読む直し。gen_images の中身は案件の images_spec.py に |
| `_work/finish.py`＋`finish_v004.jsx`・`_work/close_v004.py`・`_work/export.py`＋`export_ame_v004.jsx`・`_work/review_jobs_last.py` | `tools/premiere_case/`（finish・close・export・review_jobs_fixed） | プロジェクト・シーケンス・出力を引数に。close は保存時刻と md5・開いているシーケンスを確かめてから閉じる。finish のディゾルブ（保存する）は `--dissolve` を付けた時だけ |

ほかに新しく作った道具：`tools/diff_user_edits.py`（ユーザーが Premiere で直した所を表に。v004 の 9:48 と 16:36 の直しが出る）・`tools/find_silent_acts.py`（黙って演じている所の候補。16:36 の顔まねが1番目に出る）。
