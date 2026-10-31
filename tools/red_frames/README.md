# 画面共有の赤枠（07 の read_frame）の道具

画面を映している間、話している中身が画面のどこかを赤枠で囲む（07 の `read_frame`。2026-10-04 から）。
文字認識だけでは「どこの話か」を決めきれないので、**字幕ごとに AI が画面の画像を見て枠を決め、確かめの絵を作って、別の AI が反証する**。
元：環境設定 v004（`edit/analysis/赤枠_v004/` の prep.py・render.py、`v004/_work/red_frames_g2.py`・`retime_red_frames.py`、`v004/screen_ocr_v004.py`）。赤枠 149個で小川さん OK。

どの道具も案件名を中に持たない。版のフォルダ（`edit/vNNN`）を `--ver` で渡すと `_work/base_vNNN_map.json`・`captions_vNNN.json`・`cuts_vNNN.json` を使う
（置き場所が違う時は `--map`・`--captions`・`--cuts`）。map に要るのは `caption_tl`・`screen_spans`・`total_frames`・`n_screen`（`common.py` の頭）。

## 流れ

```
screen_frames.py frames → screen_frames.py ocr → prep.py → 【AI が決める】→ render.py → 【別の AI が反証・直す】→ render.py → place.py → screen_zoom.py（画面の寄り）→ 組み立て（make）
```

1. **画面の画像と文字認識**（`screen_frames.py`）
   ```
   python3 tools/red_frames/screen_frames.py frames --ver "edit/vNNN" --screen "edit/media/screen_CFR2997.mp4" --out "edit/analysis/screen_ocr_vNNN" [--seed 前の版の screen_ocr]
   python3 tools/red_frames/screen_frames.py ocr --out "edit/analysis/screen_ocr_vNNN"
   ```
   画面を映す字幕ごとに 25%・75% の2枚（長い字幕は1秒ごとに足す）。画像は画面録画の半分の大きさ。文字認識は `tools/screen_ocr.swift`。
2. **束にする**（`prep.py`）
   ```
   python3 tools/red_frames/prep.py --ver "edit/vNNN" --ocr-dir "edit/analysis/screen_ocr_vNNN" --out "edit/analysis/赤枠_vNNN"
   ```
   25字幕ぐらいずつの `batch_NN_in.json`（字幕ID・話者・字幕の文字・画像の場所・文字認識の行と位置。束の頭に前の流れ2つ）。
3. **AI が決める**（束ごとに1つの AI。並べて走らせてよい）：`batch_NN_in.json` を読み、画像を全部見て、字幕ごとに `batch_NN_out.json` を書く。
   ```json
   {"items": [
     {"id": "348", "rect": [0.483, 0.093, 0.834, 0.188], "label": "図の見出し", "group": "見出し", "reason": "「こう説明してくれた」の「こう」は次で読む見出し"},
     {"id": "345", "rect": null, "label": "なし", "group": "", "reason": "出来上がった図全体の話なので枠なし"},
     {"id": "414", "rect": [0.372, 0.095, 0.834, 0.197], "label": "図の見出し", "group": "環境の図の見出し", "reason": "…",
      "splits": [{"at_screen_frame": 18809, "rect": null}]}
   ]}
   ```
   - `rect`＝画面の画像の 0〜1 の [x0, y0, x1, y1]。囲むのは話している要素（読み上げている文・図の箱・ボタン・行）。行の一部だけを読む時はその部分に絞る
   - 枠なし（`null`）：話している物が画面に映っていない・画面全体の話・切り替え中（読み込み・描いている途中）・ボタンの文字にたまたま当たっただけ
   - 同じ所の話が続く字幕は、**`group` と `rect` を全く同じ値**にする（1つの枠として出したままになる）。話が移ったら枠も移る
   - 字幕の途中で画面が替わる（スクロール・ページ・メニュー）時は `splits`（替わる画面録画のコマ `at_screen_frame` から別の `rect`。`null` で枠なし。`rect` が null の字幕に書くと「途中から枠を出す」）。コマは画像の名前 `sNNNNNN.png` の数字と `screen_frame` で分かる
   - 右下のワイプ・左上の札・強調の帯・座布団の下にかかる枠は、かからない形に縮めるか枠なしにする（環境設定 v004 の反証で直した所）
   - `reason` に、字幕のどの言葉が画面のどこを指すかを書く（反証する AI が読む）
4. **確かめの絵**（`render.py`）：`python3 tools/red_frames/render.py --dir "edit/analysis/赤枠_vNNN"` → `previews/NN/*.jpg` と `previews/sheet_NN.jpg`（splits も描く）
5. **反証**（決めた AI とは別の AI）：`sheet_NN.jpg` と `previews/NN/` を全部見て、「空白や違う画面を囲んでいる」「字幕の途中で画面が替わるのに分けていない」
   「話しているのに枠が無い／画面全体の話なのに枠がある」「ワイプ・札・帯にかかる」を探し、`batch_NN_out.json` を直す（直した所は `fix_MMDD` に理由）。直したら 4 をもう一度
6. **時刻へ**（`place.py`）：
   ```
   python3 tools/red_frames/place.py --src "edit/analysis/赤枠_vNNN" --ver "edit/vNNN" --screen-size 3456x2234 [--prefix rf]
   ```
   → `<版>/_work/red_frames.json` と `<版>/_work/red_frames/*.png`（1920×1080 の透明の PNG。赤 255,30,30・角丸・線 8px）。組み立て（make_vNNN.py）が読んで V4 に置き、
   枠が移った時だけクリック音を鳴らす（07・03）。前の red_frames.json は `red_frames_前.json` に1つ残る。試す時は `--out` を別の所に
7. **カットだけ変わった時**：字幕が残っていれば `place.py` を流し直す（決めた枠は字幕IDと画面録画のコマで持つので、そのまま使える）。
   `batch_NN_out.json` が無く red_frames.json しか無い時だけ `retime.py`（splits の途中の切り替えは失われ、字幕の頭からになる）
   ```
   python3 tools/red_frames/retime.py --frames "前の版/_work/red_frames.json" --ver "edit/vNNN" [--png-dir …]
   ```

8. **画面の寄り**（`screen_zoom.py`。`07` の zoom。2026-10-19 に tools へ）：赤枠で囲んだ所を、画面録画のクリップ自体を寄せて、大きく・字幕より上に見せる。
   土台（build）と `place.py` の後、Premiere の読み込み（place_stills）の前に毎回流す（土台 XML の画面のクリップにキーフレームを書き、赤枠を `zf_*.png` に描き直す）
   ```
   python3 tools/red_frames/screen_zoom.py --ver "edit/vNNN" --screen-size 3456x2234 [--dry]
   ```
   - 案件の値は `<版>/_work/screen_zoom.json`（`--settings` で別の所）。例 `screen_zoom_example.json`、鍵の意味は `--help`：
     `chrome_labels`（上の帯を映さない大きさに寄せたままの区間）・`skip_labels`（寄せない区間）・`slide_labels`＋`slide_rect`（スライドを横いっぱい）・
     `private`（寄せた時に入ると困る文字。字幕ごとの文字認識 `analysis/赤枠_vNNN/batch_*_in.json` で探す）・`top_cut`・`left_cut`。札は plan の SCREEN の3列目
   - `chrome_ids`・`skip_ids`（2026-10-26 1025 v004 から。省くと今までどおり）：`chrome_labels`・`skip_labels` を札でなく字幕の範囲 `[["288", "288"]]`（最初と最後の字幕。タイムラインに無い字幕は書かない）で書く。
     1つの札の区間の途中で画面が替わる時に（1025：288 で Addness の右のメニューを開くのに、前の 284〜287 の寄りが続いてメニューが端で切れた）
   - `top_ok_ids`（2026-10-30 1029 v004 から。省くと今までどおり）：字幕の範囲で書く。その字幕の赤枠だけ、上の帯（`top_cut`）にかかる箱も上の帯ごと映して寄せる。
     会話の頭の送った頼みやファイルの一覧の頭を囲んだ枠が `top_cut` の線より上から始まると「上の帯にかかる箱」で寄らない。上の帯が映ってよいと決まった所だけに使う（1029：Claude のアプリの見出しだけ・小川さんが上の帯は映ってよいとした）
   - `fixed_zoom`（2026-10-30 1029 v004 から。省くと今までどおり）：`[{"ids": ["339", "365"], "zoom": [1.5, -293, 126], "ramp_after": false}]`。その字幕の赤枠は計算せずにこの寄りにする。
     短い枠が前の寄りを引き継いで端で切れる時に、全部の枠が入る1つの寄りにまとめる（1029：365・1044）。決めた寄りは 1.5秒より短くても前の寄りに吸われない。
     `ramp_after`：この寄りから元の大きさへ戻る動き（0.3秒）を枠の後ろへずらす（戻る動きで最後の枠が欠けた 204・1037）。寄りの値は sim を見て決める（案件の `_work/sim_zoom_*.py` で、組み立てる前に素材のコマで見え方を作れる）
   - `jump_ids`（2026-10-30 1029 v004 から。省くと今までどおり）：字幕の範囲で書く。その字幕で終わる赤枠の寄りに変わる時、手前（前の枠の終わりから 2秒以内）にクリップの切れ目があれば、切れ目で一気に寄りを変える。
     画面が替わる所で、前の画面から次の画面へ斜めに流れて見えるのを止める（1029：203・1088）。全部の切れ目に効かせると 20 か所の動きが変わったので、字幕を指して使う。
     赤枠は id_from か id_to のどちらかがその字幕なら効く（2026-10-31 から。それまでは id_to だけで、203〜204 の枠に 203 と書いても効かなかった）
   - `jump_in_ramp`（2026-10-31 1029 v004 r6 から。省くと今までどおり）：`true` にすると、寄りの動き（0.3秒）の途中か終わりに、画面の素材が飛ぶクリップの切れ目がある所は、動かさずにその切れ目で一気に変える。
     切れ目の前後のコマ（画面の素材の、前のクリップの最後のコマと次のクリップの in のコマ）を小さくして比べ、絵が同じ（明るさの差の平均 1.5 未満）なら一気にしない（2026-10-31 r6 の確かめ係：止まった画面の上で声だけ切った切れ目でも一気に変え、12:56.88・24:33.74 で同じ絵が 148px・170px 跳んだ。1029 の切れ目では、同じ絵は 0.00〜1.17、絵が替わる所は 2.19 以上）。
     一気に変えた所をまたぐ赤枠は、そこで終える。その後 0.2秒未満で始まる次の赤枠は、一気に変えた所から出す（r6 の 12:54.54 で、553 と 556 の間に 4コマ枠が消えた）。動きが切れ目をまたぐと、前の画面の上で寄り始める（1285）・make が赤枠の頭を切れ目へ前に出し、寄りきる 2〜3コマ前から枠が文からずれる（1092・1124 ほか 20 か所ほど）のを止める
   - 区間の頭の前の、無効にしてある画面のクリップ（素材が頭へ続いている 12コマまで）にも、頭の寄りを書く（2026-10-31 から。いつも）。make の [35] がカメラの短い切れ端を無効にして画面を前に出した所で、
     前に出した数コマだけ元の大きさになり、そこで一気に寄っていた（1029：1057 の 9コマ）。無効のままなら映らないので、[35] の無い案件の見え方は変わらない
   - `burned_face`（2026-10-20 AI動画編集 v006 から。省くと今までどおり）：画面録画に顔の丸が焼き込まれている時（撮り直しの Loom など）の [真ん中 x, 真ん中 y, 半径]（素材の px）。
     寄せると焼き込みの顔も寄って欠ける・はみ出すので、「寄せていない時の丸の所」の外に顔が 300px² より見える寄せ方は、倍率を 0.05 ずつ下げ、だめなら寄せない（`face_fixed` に記録）。
     顔そのものは別に、顔の丸だけを抜いた映像を V11 に重ねて見せる（例：`AI動画編集/edit/r2/v006/_work/face_overlay.py`）。寄り始め・戻りの 0.3秒は、焼き込みの顔が外へ滑って見えることがある
   - SCREEN に無い札は効かないので知らせる。人名・社内の数字は案件の JSON にだけ書く（このフォルダは公開の Git）
   - 一度寄せた `red_frames.json` はもう一度寄せない（赤枠が二重に寄る。止まる）。`place.py` から流し直す。`--dry` は書かずに数だけ出す
   - 画面は「高さ 1080 に合わせて真ん中」に置いてある前提（`place.py` の `--disp` を省いた時と同じ）。寄りは最大 2.0倍・寄り／戻しは 0.3秒
   - 確かめたこと（2026-10-19）：1017 v009 と 1018 v001 の入力の写しで、元の `_work/screen_zoom.py` と XML・`red_frames.json`・土台の表・`zf_*.png`
     （33枚・84枚）が同じ（`how` の文字だけ違う）。本物の版への `--dry` も元と同じ数。Premiere で読み込んでの確かめは、この道具ではまだ（元は grok v002・1017・1018 で使った）

## 確かめたこと（2026-10-05）

- `place.py` を環境設定 v004 の `batch_*_out.json` と土台の表で流すと、v004 で使った `red_frames.json` と同じ 149個（時刻・場所とも一致）
- `prep.py` は v004 の画像と文字認識で 243字幕（元は v003 の土台で 244。v004 で字幕551 を小川さんが消した分）
- `render.py` は試しの画像で splits の切り替えまで描けた。`screen_frames.py` は動かしていない（`--help` まで）
