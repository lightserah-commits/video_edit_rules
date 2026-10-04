# 案件の Premiere の小さなスクリプト（tools/premiere_case/）

案件のプロジェクトを Premiere で「確認の画像の書き出し」「保存せずに閉じる」「mp4 の書き出し」をする道具。
どれも MCP Bridge パネル経由（`tools/premiere_bridge.py`）で、前面はユーザーが見ていたプロジェクト・シーケンスに戻す。プロジェクト・シーケンス・出力は引数で渡す。
元：環境設定 v004 の `_work/finish.py`・`finish_v004.jsx`・`close_v004.py`・`export.py`・`export_ame_v004.jsx`・`review_jobs_last.py`。

使う前に（CLAUDE.md）：Premiere を使う工程の前と後にチャットで知らせる／`python3 tools/premiere_bridge.py status` で Premiere 1つ・パネル1つ／
ユーザーのプロジェクトは保存しない・閉じない（ここの道具は案件のプロジェクトだけを相手にする）／開く前に無いフォントが0件か（finish・export が `font_fix` で見て、あれば止まる）。

| ファイル | すること |
|---|---|
| `finish.py`＋`finish.jsx` | 確認の画像を書き出す（`--jobs`）。`--dissolve 15` の時だけ右上タイトル（V8・V9）の頭にディゾルブを付けて**保存**（既定は付けない・保存しない） |
| `review_jobs_fixed.py` | 組み立ての記録（vNNN_記録.json）から、直した所だけの確認の画像の一覧を作る（finish の `--jobs`） |
| `close.py`＋`close.jsx` | 保存せずに閉じる。閉じる前に .prproj の保存時刻と md5 が AI の最後の組み立て（`--record` の記録）と同じか、開いているシーケンスのクリップが .prproj と同じかを見て、違えば止まる |
| `export.py`＋`export_ame.jsx` | Media Encoder で mp4（YouTube 1080p HD）。出力がもうあれば止まる。保存しない |
| `_common.py` | 共通（パス・名前を JSON の文字にして埋め込む・フォントの確かめ・md5） |

```
# 組み立て（make）の直後：AI の最後の組み立てとして記録（Premiere に触らない）
python3 tools/premiere_case/close.py --proj "<版>/<案件>_vNNN.prproj" --record
# 確認の画像（直した所だけ）
python3 tools/premiere_case/review_jobs_fixed.py --record "<版>/vNNN_記録.json" --out "<版>/_work/review_jobs_fixed.json"
python3 tools/premiere_case/finish.py --proj "<版>/<案件>_vNNN.prproj" --seq <シーケンス名> --jobs "<版>/_work/review_jobs_fixed.json"
# 作り直す前に閉じる（ユーザーが保存・直していたら止まる → tools/diff_user_edits.py で違いを見る）
python3 tools/premiere_case/close.py --proj "<版>/<案件>_vNNN.prproj" --seq <シーケンス名>
# 書き出し
python3 tools/premiere_case/export.py --proj "<版>/<案件>_vNNN.prproj" --seq <シーケンス名>
```

確かめたこと（2026-10-05。Premiere は使っていない）：`--help`・`--dry`、close の `--record`／`--check-only`（同じなら通る・保存時刻や md5 が違えば止まる）、
埋めた ExtendScript が JavaScript として読めること（`node --check`）、review_jobs_fixed が v004 の review_jobs_last.json と同じ 130 の時刻を出すこと。
**Premiere で動かしての確かめはしていない**（finish・export は v004 の元と同じ中身。close の「開いているシーケンスとの比べ」は新しく足した所で未確認。
違いを見つけた時は閉じずに止まるので、外れても直しは消えない）。保存していない直しのうち、クリップの位置が変わらないもの（値だけの直し）は見つけられない。
