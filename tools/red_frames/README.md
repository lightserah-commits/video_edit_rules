# 画面共有の赤枠（07 の read_frame）の道具

画面を映している間、話している中身が画面のどこかを赤枠で囲む（07 の `read_frame`。2026-10-04 から）。
文字認識だけでは「どこの話か」を決めきれないので、**字幕ごとに AI が画面の画像を見て枠を決め、確かめの絵を作って、別の AI が反証する**。
元：環境設定 v004（`edit/analysis/赤枠_v004/` の prep.py・render.py、`v004/_work/red_frames_g2.py`・`retime_red_frames.py`、`v004/screen_ocr_v004.py`）。赤枠 149個で小川さん OK。

どの道具も案件名を中に持たない。版のフォルダ（`edit/vNNN`）を `--ver` で渡すと `_work/base_vNNN_map.json`・`captions_vNNN.json`・`cuts_vNNN.json` を使う
（置き場所が違う時は `--map`・`--captions`・`--cuts`）。map に要るのは `caption_tl`・`screen_spans`・`total_frames`・`n_screen`（`common.py` の頭）。

## 流れ

```
screen_frames.py frames → screen_frames.py ocr → prep.py → 【AI が決める】→ render.py → 【別の AI が反証・直す】→ render.py → place.py → 組み立て（make）
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

## 確かめたこと（2026-10-05）

- `place.py` を環境設定 v004 の `batch_*_out.json` と土台の表で流すと、v004 で使った `red_frames.json` と同じ 149個（時刻・場所とも一致）
- `prep.py` は v004 の画像と文字認識で 243字幕（元は v003 の土台で 244。v004 で字幕551 を小川さんが消した分）
- `render.py` は試しの画像で splits の切り替えまで描けた。`screen_frames.py` は動かしていない（`--help` まで）
