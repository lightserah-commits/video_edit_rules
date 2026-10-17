---
name: moji-pv-dynamic-camera
description: 文字PV（リリックビデオ）は「歌詞が出るだけ」はダメ。カメラが切り替わる・動く・3D のダイナミックさを最初から入れる。早め早めに動画で見せる
metadata:
  node_type: memory
  type: feedback
  originSessionId: bf00932f-b9c4-4f5b-a2ec-3d8d2e7be932
  modified: 2026-10-04T04:33:56.410Z
---

文字PVを作る時は、最初の版からカメラの切り替え（0.3〜1秒）・寄り引き・3D の傾き・振りのブレを入れる。歌詞のタイミング確認だけの版を出すなら「見た目は仮」と最初にはっきり言う。

**Why:** 2026-10-04 の「Stranger Than Heaven」の文字PVで、タイミング確認版を送ったら「歌詞が表示されるだけなのね、もっとカメラが切り替わったり、動いたり、ダイナミックなものを期待してた」と言われた。カメラを動かした版（巨大な I → 振り → 遠近の床 → 鉄格子ごと斬る等）には「いいね、めっちゃいい」。途中で「早め早めで見たい」「早よみたい」とも言われた。

**How to apply:** 作業場所は `~/Movies/video_edit_cases/moji_pv_stranger_than_heaven_20261004/`（Canvas 2D のエンジン・ヘッドレス Chrome の書き出し・`engine/README.md`）。区切りごとに並列で作り、出来た区切りから 960×540 の動画で送る。音はAIには聞けないので、時刻のずれは依頼者にヘッドホンで見てもらう。関連 [[show-visual-options-as-screenshots]]
