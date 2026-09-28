# iMac の準備（iMac の Claude が読む。2026-09-28 Air で作成）

Air（ユーザー名 `yoshizawakouichi`）の `~/Desktop/video_edit_rules` がマスター。このリポジトリは、Air で確定した版だけが届く。**iMac ではこのフォルダの中のファイルを書き換えない**（直したいことは Addness に書き、Air で反映する。`CLAUDE.md`「iMac と共有する」）。

## 1. リポジトリを置く

- `~/Desktop/video_edit_rules` に clone する（`gh repo clone lightserah-commits/video_edit_rules ~/Desktop/video_edit_rules`）
- 以前の依頼文にあった「AirDrop で `work/` ごと運ぶ」は要らない（2026-09-28 に案件はこのフォルダの外に出した）
- 会話を開いた時に自動で `git pull --ff-only` する（iMac のユーザー設定に入れる。リポジトリは変えない）。取り込めなかった時は、書き換えたファイルがあるはずなので、本人に知らせる

## 2. Mac ごとの設定（Git に入らないので iMac で作る）

- `.claude/settings.local.json`：案件フォルダを書けるように
  ```json
  { "permissions": { "additionalDirectories": ["/Users/addness/Desktop/みかみ案件依頼書"] } }
  ```
- `.claude/addness/cases_local.json`：iMac で始めた案件の表（`CLAUDE.md`「フォルダの使い方」）。無ければ `{"cases": {}}`

## 3. 道具

| もの | Air での入れ方・場所 | iMac でやること |
|---|---|---|
| Premiere のパネル「MCP Bridge (CEP)」（id `com.mcp.premiere.cepbridge` 1.1.6） | `~/Library/Application Support/Adobe/CEP/extensions/MCPBridgeCEP` | `tools/premiere_panel/MCPBridgeCEP` をそこへコピー。署名なしのパネルを許す：`defaults write com.adobe.CSXS.12 PlayerDebugMode 1`（と `.11`）。Premiere の「ウィンドウ > エクステンション > MCP Bridge (CEP)」で開く。共有フォルダは `/tmp/premiere-mcp-bridge`。`python3 tools/premiere_bridge.py status` で `bridge_panels: 1` |
| npm の `premiere-pro-mcp` | 使っていない | 要らない（`tools/premiere_bridge.py` がパネルと直接やり取りする） |
| ffmpeg | Homebrew（`/opt/homebrew/bin/ffmpeg`） | `brew install ffmpeg` |
| whisper-cli | Homebrew の `whisper-cpp` | `brew install whisper-cpp` |
| 文字起こしのモデル `ggml-small.bin` | `~/Documents/Codex/2026-09-25/new-chat/work/models/ggml-small.bin` | AirDrop で受け取り、同じ場所に置く |
| python3 と Pillow | `/usr/bin/python3`（3.9.6）、Pillow 11.3 | デベロッパツールの python3、`python3 -m pip install --user Pillow` |
| numpy の入った python（カット・字幕の時刻合わせ） | `~/Documents/Codex/2026-09-17/new-chat/work/asr-env/bin/python` | 必要になった案件で作る（`python3 -m venv` → `pip install numpy`）。場所は案件メモに書く |
| swift | デベロッパツール | デベロッパツールを入れれば入る（画面の文字認識） |

## 4. 1回だけ AirDrop で受け取るもの（ルールが読みに行く。Git に入れない）

- **最初に要る（小さい）**：上司の方法セット → `~/Desktop/担当2/YT AI自動編集の方法 2/`（1.8MB）、テロップ制作の確定手順・演出図鑑 → `~/Desktop/担当2/03_編集ルール定義/`（234MB）、文字起こしのモデル `ggml-small.bin`（465MB）
- **後でよい（大きい）**：完成版2本 → `~/Downloads/コピー_みかみさんCH0726_1/`（30GB）・`~/Downloads/コピー_AI時代に消える仕事残る仕事/`（11GB）。完成版から取った数字・見本は `実例/` と `見本/` に入っているので、ふつうの編集では要らない。完成版そのものを開いて比べる時だけ

## 5. 最初の案件で確かめること

- Premiere のプロジェクトは素材の場所をユーザー名入り（`/Users/yoshizawakouichi/…`）で覚えている。見本集（`見本/テロップ見本集.prproj`）のコピーを iMac で開いた時に SE・BGM がオフラインになったら、`changeMediaPath` で `~/Desktop/video_edit_rules/素材/` につなぎ直す（やり方は Air の案件メモ「見本集をコピーして別の場所で開くと SE・BGM がオフライン」と同じ）。直し方が決まったら Addness に書き、Air で道具にする
- 開始時の【Addness】の案内が出ること（フックは `.claude/settings.json`）
