---
name: no-experimental-blobs-in-premiere
description: テロップの文字データ（FlatBuffer）の参照を推測で付け替えたファイルを、ユーザーが使っている Premiere で開かない。2026-10-04 に Premiere を落とした
metadata:
  node_type: memory
  type: feedback
  originSessionId: 14e3b00f-e2d0-4c91-9041-8c777aaf1bd6
  modified: 2026-10-04T06:16:49.384Z
---

テロップの文字データ（FlatBuffer）の中の参照（uoffset）を推測で別の表に向けたファイルを、ユーザーの Premiere（ほかのプロジェクトが開いている本番の Premiere）で開かせない。値の書き換え（色の表のバイト・文字の大きさの小数）は大丈夫だったが、参照の付け替えは型の違う表を指すと読み込みで落ちる。

**Why:** 2026-10-04 シーケンス07（営業の通話）で、白い文字＋色の縁を作るために T001 の色の参照を6通り付け替えた実験ファイルを開かせたら、Premiere が `FlatBufferToGradientInfo`（グラデーションの表を期待する所に色の表）で落ちた。開いていた kankyo_v001・astra_air_v006・astra_air_v007 が閉じられ、ブリッジのパネルも止まった。

**How to apply:** 文字データの構造を試す時は、①値だけを書き換える（表の形を変えない）②参照を変えるなら、同じ型の表（同じ vtable を使う表）どうしの入れ替えだけにする ③それでも試す時は、ユーザーに「落ちるかもしれない」と言って、他のプロジェクトを保存してもらってから。関連 [[announce-premiere-use]] [[concurrent-agents-same-folder]]
