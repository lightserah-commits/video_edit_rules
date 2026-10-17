---
name: whisper-local-model-offline
description: mlx_whisper はローカルのモデル（video_edit_rules/models/）をパスで HF_HUB_OFFLINE=1 で使う。リポジトリ名で呼ぶとダウンロードしてしまう
metadata:
  node_type: memory
  type: feedback
  originSessionId: ff7e975b-a7d6-441f-8f5b-92c7b3fb60ca
  modified: 2026-10-03T08:20:02.389Z
---

文字起こし（mlx_whisper）は、`~/Desktop/video_edit_rules/models/whisper-large-v3-turbo`（large-v3-turbo）を `path_or_hf_repo=` にパスで渡し、`os.environ['HF_HUB_OFFLINE']='1'` を先に置く（`実例/カット調査/scripts/transcribe_raw.py` と同じ）。python は `~/Desktop/video_edit_rules/env/bin/python`、whisper-cli のモデルは `models/ggml-small.bin`。無ければ `zsh tools/setup_env.sh`（2026-10-05、前の置き場 ~/Documents/Codex を小川さんが消したので、小川さんの OK でフォルダの中に作り直した）。`mlx-community/whisper-...` のような名前で呼ぶと Hugging Face から落としてくる。

**Why:** 2026-10-03 dots のハイライトの切り出しの文字起こしで名前で呼び、turbo（既存と同じもの 1.6GB）と large-v3（途中まで 1GB）を無断でダウンロードした（CLAUDE.md「無断でモデルのインストールをしない」違反）。ゴミ箱に移した。小川さんに「今までどういう文字起こしだったか」と聞かれた。

**How to apply:** 別のモデルを試したい時は、落とす前に名前・大きさを伝えて OK をもらう。関連 [[concurrent-agents-same-folder]]
