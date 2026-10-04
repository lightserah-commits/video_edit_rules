# iMac と共有する（Git。2026-09-28 から）と、iMac の準備

## 0. 共有の決まり（Air と iMac の両方で読む）

- **この Mac（Air、ユーザー名 `yoshizawakouichi`）の `~/Desktop/video_edit_rules` がマスター。** ルール・見本・道具・フックを直すのは Air だけ。確定した版だけを GitHub のリポジトリ（`lightserah-commits/video_edit_rules`。2026-10-05 から公開：小川さん「上司に共有しないといけなくて、一旦公開して」。購入した素材・社内の情報も見えるので、共有が済んだら非公開に戻すか決める）経由で iMac（ユーザー名 `addness`）に届ける。直している途中は届けない
- iMac は会話を開くたびに自動で最新を取り込む。**iMac ではこのフォルダの中のファイル（`作業状況.md` も）を書き換えない**。iMac で気づいたルール・道具の直しと案件の状況は Addness（と案件の `edit/00_案件メモ.md`）に書き、Air で反映する
- Git に入れないもの（`.gitignore`）：案件（案件フォルダは各 Mac の `~/Desktop/みかみ案件依頼書/`。続きを別の Mac でやる時は案件フォルダごと AirDrop）・`work` のリンク・Mac ごとの設定（`.claude/settings.local.json`：追加フォルダの許可など）・Addness の記録（`.claude/addness/` は `goals.json` 以外）・`見本/確認/`・Premiere のキャッシュ
- 場所の書き方：`~/` か、このフォルダからの相対で書く（ユーザー名が違うため。`CLAUDE.md` の「どこに何があるか」）。上司の方法セットは両方の Mac で `~/Desktop/担当2/`、完成版2本は `~/Desktop/video_edit_rules/完成版/コピー_…` に置く

### 「iMacに反映して」と言われたら（Air で）

1. 道具が壊れていないか軽く確かめる：`python3 -m py_compile tools/*.py .claude/hooks/*.py`、`python3 .claude/hooks/addness_session_start.py < /dev/null`
2. `git status` で入るものを確かめる（案件の素材・書き出し・100MB を超えるものが無いこと）。`見本/テロップ部品集.prproj`・`見本/テロップ部品集_元.json`・`素材/画像/` は入れる（部品集が使う。2026-10-03 から）。見本集を直した時は、先に `python3 tools/build_parts.py` で部品集を作り直してから入れる
3. `git add -A` → 何を直したかが分かるメッセージでコミット → `git push`
4. Addness の「このiMacでも…」（6f519c35-55fd-4683-89a5-cf77c90d42e5）の本文に、反映した版（コミットの短いID）と中身を1行で書く

---

以下は iMac の Claude が読む準備の手順（2026-09-28 Air で作成）。

## 1. リポジトリを置く

- `~/Desktop/video_edit_rules` に clone する（`gh repo clone lightserah-commits/video_edit_rules ~/Desktop/video_edit_rules`）
- 以前の依頼文にあった「AirDrop で `work/` ごと運ぶ」は要らない（2026-09-28 に案件はこのフォルダの外に出した）
- 会話を開いた時に自動で `git pull --ff-only` する（iMac のユーザー設定に入れる。リポジトリは変えない）。取り込めなかった時は、書き換えたファイルがあるはずなので、本人に知らせる

## 2. Mac ごとの設定（Git に入らないので iMac で作る）

- `.claude/settings.local.json`：案件フォルダを書けるように
  ```json
  { "permissions": { "additionalDirectories": ["/Users/addness/Desktop/みかみ案件依頼書"] } }
  ```
- `.claude/addness/cases_local.json`：iMac で始めた案件の表（`編集の依頼文.md` の工程1）。無ければ `{"cases": {}}`

## 3. 道具

| もの | Air での入れ方・場所 | iMac でやること |
|---|---|---|
| Premiere のパネル「MCP Bridge (CEP)」（id `com.mcp.premiere.cepbridge` 1.1.6） | `~/Library/Application Support/Adobe/CEP/extensions/MCPBridgeCEP` | `tools/premiere_panel/MCPBridgeCEP` をそこへコピー。署名なしのパネルを許す：`defaults write com.adobe.CSXS.12 PlayerDebugMode 1`（と `.11`）。Premiere の「ウィンドウ > エクステンション > MCP Bridge (CEP)」で開く。共有フォルダは `/tmp/premiere-mcp-bridge`。`python3 tools/premiere_bridge.py status` で `bridge_panels: 1` |
| npm の `premiere-pro-mcp` | 使っていない | 要らない（`tools/premiere_bridge.py` がパネルと直接やり取りする） |
| ffmpeg | Homebrew（`/opt/homebrew/bin/ffmpeg`） | `brew install ffmpeg` |
| whisper-cli | Homebrew の `whisper-cpp` | `brew install whisper-cpp` |
| 文字起こしのモデル（whisper-cli の `ggml-small.bin`・mlx_whisper の large-v3-turbo） | `~/Desktop/video_edit_rules/models/`（Git に入れない） | `zsh tools/setup_env.sh`（Hugging Face から約 2GB をダウンロード。流す前に小川さんに聞く） |
| python3 と Pillow | `/usr/bin/python3`（3.9.6）、Pillow 11.3 | デベロッパツールの python3、`python3 -m pip install --user Pillow` |
| numpy・mlx_whisper の入った python（文字起こし・カット・字幕の時刻合わせ） | `~/Desktop/video_edit_rules/env/bin/python`（Git に入れない） | `zsh tools/setup_env.sh`（上と同じ1本。約 1.2GB） |
| swift | デベロッパツール | デベロッパツールを入れれば入る（画面の文字認識） |

## 4. 1回だけ AirDrop で受け取るもの（ルールが読みに行く。Git に入れない）

- **最初に要る（小さい）**：上司の方法セット → `~/Desktop/担当2/YT AI自動編集の方法 2/`（1.8MB）、テロップ制作の確定手順・演出図鑑 → `~/Desktop/担当2/03_編集ルール定義/`（234MB）、文字起こしのモデル `ggml-small.bin`（465MB）
- **後でよい（大きい）**：完成版2本 → `~/Desktop/video_edit_rules/完成版/コピー_みかみさんCH0726_1/`（30GB）・`~/Desktop/video_edit_rules/完成版/コピー_AI時代に消える仕事残る仕事/`（11GB）。完成版から取った数字・見本は `実例/` と `見本/` に入っているので、ふつうの編集では要らない。完成版そのものを開いて比べる時だけ

## 5. 最初の案件で確かめること

- Premiere のプロジェクトは素材の場所をユーザー名入り（`/Users/yoshizawakouichi/…`）で覚えている。案件のプロジェクトは部品集から `python3 tools/build_parts.py --case-copy "$HOME/Desktop/みかみ案件依頼書/<案件>/edit/v001/<案件>_v001.prproj"`（案件の .prproj は絶対パスで書く） で作ると、SE・画像の素材がこの Mac の `~/Desktop/video_edit_rules/素材/` を指す（2026-10-03 から。Air では Premiere でオフライン0を確認済み。iMac では最初の案件で、開いた時にオフラインが0か確かめる）。見本集のコピーをそのまま開くと SE・BGM・背景がオフラインになる（`changeMediaPath` で `素材/` につなぎ直すか、部品集を使う）
- 開始時の【Addness】の案内が出ること（フックは `.claude/settings.json`）
