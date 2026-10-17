# セキュリティについて v005 の組み立て一式（次の案件の雛形。カメラ1本の対談＝三上さん＋カメラの外の聞き手）

「セキュリティについて」（みかみ案件依頼書。security_20261016。2026-10-17 最後の版 v005・15:13.7・小川さん「v005 を聴いて確認した。OK、納品へ進めて」）の
作業場 `edit/` から、**コードと小さい表だけ**を写したもの（2026-10-17 写し）。
動画・画像・音・.prproj・1MB を超えるファイル・`zukai/out/`・`zukai/assets/` の絵・`確認/` の画像は入っていない。

- `00_案件メモ.md`：edit/ 直下の案件メモ（素材・版の表・決まったこと・作り直しの順）
- `scripts/`：edit/scripts/（文字起こし・区切り・声の大きさなどの下ごしらえ）
- `v005/`：edit/v005/ と同じ並び（`*.py`・`*.sh`・`*.jsx`・`plan_parts/`・`script_parts/`・`hl/`〈冒頭ハイライトの make_hl.py・clips.tsv・manifest〉・`zukai/`〈images_spec.py・inserts.json・図解ごとの page.html・diagram.json〉・`_work/` のスクリプトと表・`確認_v005.md`・`直し_v005.md`・`v005_記録.json`）

## AI動画編集_v004 との違い（こちらが新しい）

- 素材は iPhone の1本（画面の録画なし）。画面・Loom・ワイプの所は空（plan の SCREEN が空・NO_SCREEN）
- **声を別のファイルにできる**（04 の bgm.balance.limiter）：`plan_v005.py` の `VOICE_FILE`（コンプレッサー＋リミッターを掛けた作業用の声。`tools/make_voice_comp.sh` で作る）。`build_v005.py` は A1・A2 をこの wav にする（無ければカメラの音）。
  声のクリップを名前で探す所も合わせてある：`_work/kyocho_start_fix.py`（強調の出だしを声に合わせる）・`_work/run_checks.sh`（check_kyocho_timing の `--asr`・`--wav`）。make の PEAK_FIX はカメラの名前のまま（空なので影響なし）。
  **VOICE_FILE のファイル名に版の名前（vNNN）を入れない**：`next_version.sh` が中身の「vNNN」を全部書き換えるので、無いファイルを指すようになる（v005 で起きた。plan で直した）
- **版を上げる時、図解・画像を自分のフォルダに持つ**：`_work/next_version.sh` は zukai/ をリンクにせず、表と manifest を写し、重い動画・画像だけ前の版の実ファイルへのリンクにする。描き直す絵は `out/<KEY>` のリンクを消してから描く。
  前の版の .prproj が読み込んでいる overlay を同じ名前で描き直さない（前の版の中身が変わり、Media Encoder が「フレーム 0 の取得に失敗」で止まる。v005 で起きた）
- **笑い・言葉の途中の間を詰める**（08 の cut.pauses.laugh_gaps）：`tools/find_laugh_gaps.py --ver <版>` で候補 → 決めた物を `cuts_plan_v005.py` の EXTRA_CUTS に理由つきで（例は v005 の中。図解の区間の中は切らない）
- **字幕の1行が 17字を超えたらエラー**（08 の captions.layout.stop_long_line）：`captions_align_v005.py`（v005 の案件では注意だけで、29字の行がはみ出した）
- **途中から出す字幕（mid）にも ONSET_FIX が効く**（`captions_align_v005.py`）：同じ言葉が続く所（「カモ認定された」→「そうです カモ認定されて」）で、DTW の候補が前の人の言葉を取ることがある
- **組み直し → 締めの Pan → 書き出し を1本で**：`_work/rebuild_pan_export.sh <Pan のつなぎ目の秒>`（書き出しの成否は Media Encoder の記録 AMEEncodingLog.txt の「ファイルが正常にエンコードされました」／「失敗」で判定する。ファイルの大きさが止まったかで見ると、止まった書き出しを終わったと見誤る）
- 画像は実写寄り（02 の P13.generated）。本人が出る絵・紙芝居は `tools/gen_image.py --ref` に素材の顔のコマを渡す（v005 の `zukai/images_spec.py` の I04・I17。紙芝居は 02 の P13.kamishibai）

## 作り直しの順

`v005/_work/rebuild_all.sh`（merge_script → captions_align → cuts_plan → 表の検査 → zukai/shift → build → Premiere place_stills → make〈kyocho_start_fix を挟んで3回〉→ run_checks → 確認の画像）
→ `rebuild_pan_export.sh`（Pan・書き出し）→ `tools/check_blackout.py`・音の大きさ（ebur128）。make から後だけなら `rebuild_make_checks.sh`。

## ハマりどころ（この案件で起きた物）

- 声を wav に替えたら、名前で声を探す道具が声を見つけられず、強調の出だしの直しが 0件になった（強調の「早い」が 4 → 10）。直した後は v004 と同じ
- リミッター -2dB でも、AAC の書き出しで真のピークが 0.0 dBFS に届いた（大笑い）→ 声・BGM・SE を -1dB（本編 -23.0 LUFS・-0.5 dBFS）
- Premiere の close.py は、締めの Pan を付けて保存した後は md5 が違うので「ユーザーが保存した可能性」で止まる → `tools/diff_user_edits.py --base _work/sec_vNNN_before_pan.prproj --saved sec_vNNN.prproj` で Pan の部品だけか確かめてから `close.py --record`
- 同じ Premiere を別のセッションと共有している時は、使う前に `/tmp/premiere_use.lock` を置き、相手のセッションに一言送る（2026-10-17 grok の案件と）
