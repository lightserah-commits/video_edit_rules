---
name: premiere-gui-telop-color
description: 見本集に無いテロップの色は、AI が Premiere を画面操作（プロパティ→アピアランス）で変えて保存し、その文字データを複製する。ユーザーに頼まない
metadata:
  node_type: memory
  type: feedback
  originSessionId: 14e3b00f-e2d0-4c91-9041-8c777aaf1bd6
  modified: 2026-10-04T06:58:57.648Z
---

見本集に無いテロップの見た目（例：白い文字＋色の縁）が要る時は、ユーザーに Premiere での作業を頼まず、AI が computer use で Premiere を操作して作る。テロップを選ぶ → ウィンドウ＞プロパティ → テキストのレイヤー → アピアランスで塗り・ストロークの色を変え、⌘S。保存された文字データを読み、案件の全部の字幕に `replace_runs` で文字だけ差し替えて使う。

**Why:** 2026-10-04 シーケンス07 で、白い文字＋色の縁の見本づくりを小川さんに頼んだら「ほんぐらいできるでしょ、普通に。やってほしい」と言われた。文字データの参照を推測で付け替える方法は Premiere を落とした（[[no-experimental-blobs-in-premiere]]）。

**How to apply:** カラーピッカーの16進の欄は背景の操作（app_*）では打てないので、全画面の操作（request_full_control）にする。音声入力アプリ Aqua Voice の見えない窓が画面の真ん中にかぶってクリックできない所がある → ウィンドウ＞フレームを最大化でパネルを広げて位置をずらす。操作の前後に知らせる（[[announce-premiere-use]]）。
