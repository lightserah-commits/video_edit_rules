# 別のPCの準備（フォルダのコピーで同じ環境にする）と、PC どうしの共有（Git）

2026-10-17 小川さん「別のPCで出来る様にしたい」「コピー&ペーストで俺と同じ環境が手に入る様に」。それまでの `iMacの準備.md`（2026-09-28）を、どの PC にも使える形にした。

## 0. 共有の決まり（どの PC でも読む）

- **どの PC でもルール・道具を直してよい。PC どうしは Git で行き来する**（2026-10-17 小川さん「両方で直し、Gitで行き来」。それまでは「Air がマスター・iMac では書き換えない」だった）
  - 始める時に `git pull --ff-only`。取り込めない時は、この PC で直してまだ送っていないファイルがあるので、本人に知らせる
  - ルール・道具を直したら、区切りでコミットして `git push`（何を直したかが分かるメッセージで。直している途中のものは送らない）。同じ PC の別のセッションが直しているファイルは、そのセッションに任せる
  - 送る前に：`python3 -m py_compile tools/*.py .claude/hooks/*.py`、`git status` で入るものを確かめる（案件の素材・書き出し・100MB を超えるもの・鍵が無いこと）。見本集を直した時は、先に `python3 tools/build_parts.py` で部品集を作り直す（`見本/テロップ部品集.prproj`・`見本/テロップ部品集_元.json`・`素材/画像/` は入れる）
  - 送ったら、Addness の「このiMacでも…」（6f519c35-55fd-4683-89a5-cf77c90d42e5）の本文に、送った版（コミットの短いID）と中身を1行で書く
- リポジトリは `lightserah-commits/video_edit_rules`（2026-10-05 から公開：小川さん「上司に共有しないといけなくて、一旦公開して」。社内の情報も見えるので、共有が済んだら非公開に戻すか決める）
- **Git に入れないもの**（`.gitignore`。PC へはフォルダのコピーで運ぶ）：案件（案件フォルダは各 PC の `~/Desktop/みかみ案件依頼書/` など）・`work` のリンク・Mac ごとの設定（`.claude/settings.local.json`）・Addness の記録（`.claude/addness/` は `goals.json` 以外）・`見本/確認/`・Premiere のキャッシュ・`env/`・`models/`・`完成版/`・`上司の資料/`・`環境/フォント/`・`環境/PremiereComposer/`（社内の資料・フォント・有料の部品を公開のリポジトリに上げない）
- **置き場所はどの PC でも `~/Desktop/video_edit_rules`**。案件のスクリプト（`ROOT = os.path.expanduser("~/Desktop/video_edit_rules")`）と Premiere のプロジェクトがこの場所を見る。フォルダの中の道具は自分の置き場所から決めるので、別の所に置いても動くが、その時は準備のスクリプトが `~/Desktop/video_edit_rules` にリンクを作る
- 場所の書き方：このフォルダからの相対か `~/` で書く（PC ごとにユーザー名が違う。Air は `yoshizawakouichi`、iMac は `addness`）
- **鍵はフォルダに入れない**（2026-10-17 小川さん）。OpenAI の API キーは Mac のキーチェーン、YouTube は `~/.video_edit_rules/youtube/`。PC ごとに入れ直す（下の 2）

## 1. 運ぶ（元の PC で）

1. `python3 tools/setup_mac.py --pack`：Claude の AI メモリ・予定タスク・新しく入れたフォント・Composer の Pan を `環境/` に写す（運ぶ前に毎回）。まだ送っていない変更が出たら、コミットしておく
2. フォルダごとコピーする（外付けの SSD・AirDrop など）。大きさは全体で約50GB：`完成版/` 41GB・`見本/` 3.6GB・`models/` 3.5GB・`env/` 1.2GB・`環境/フォント/` 0.3GB・`上司の資料/` 0.24GB。`完成版/` は完成版そのものを開いて比べる時だけ要る（数字と見本は `実例/`・`見本/` にある）ので、急ぐ時は外してよい
3. 新しい PC の `~/Desktop/video_edit_rules` に置く。2回目からは Git（`git pull`）で足りる。大きいもの（上の Git に入れないもの）が変わった時だけ、そのフォルダを運び直す

## 2. 入れる（新しい PC で）

`python3 tools/setup_mac.py` で足りないものを確かめ、`python3 tools/setup_mac.py --install` で1つずつ聞きながら入れる。AI が流す時は、何を入れるかをチャットで見せて OK をもらってから `--install --only <名前> --yes`。

| 名前 | 何を入れるか | 人がやること |
|---|---|---|
| place | `~/Desktop/video_edit_rules` に無い時、そこへのリンク | ― |
| brew | Homebrew の ffmpeg・whisper-cpp・python@3.14 | Homebrew が無ければ https://brew.sh の1行（パスワードが要る） |
| env | 道具の Python（`env/`）と文字起こしのモデル（`models/`）。Apple Silicon で Homebrew の python@3.14 があれば、コピーした `env/` がそのまま動く。動かなければ `zsh tools/setup_env.sh`（作り直し約1.2GB。モデルが無ければ Hugging Face から約2GB。流す前に小川さんに聞く） | ― |
| fonts | `環境/フォント/`（56個）→ `~/Library/Fonts` | Adobe Fonts は Creative Cloud にログインして同期。A1ゴシック（AP-OTF-A1GOTHICSTD-BOLD）はモリサワの有料フォントなので、その PC に入れてよいかライセンスで確かめる |
| panel | Premiere のパネル「MCP Bridge (CEP)」（`tools/premiere_panel/MCPBridgeCEP`、id `com.mcp.premiere.cepbridge` 1.1.6）→ `~/Library/Application Support/Adobe/CEP/extensions/`。署名なしのパネルを許す `defaults write com.adobe.CSXS.12 PlayerDebugMode 1`（と `.11`） | Premiere を開き直し、「ウィンドウ > エクステンション > MCP Bridge (CEP)」で開く。共有フォルダは `/tmp/premiere-mcp-bridge`。npm の `premiere-pro-mcp` は要らない |
| composer | Premiere Composer の Starter Pack の Pan（締めのトランジション。`02` の transitions.closing_pan）。控えは `環境/PremiereComposer/` | Composer の本体は Mister Horse の Product Manager で入れる（アカウントが要る） |
| memory | `環境/AIメモリ/` → Claude の AI メモリの場所（`~/.claude/projects/<このフォルダの絶対パスの英数字以外を - にした名前>/memory/`）。新しい方を残し、`MEMORY.md` は行を足し合わせる | ― |
| local | `.claude/settings.local.json` の追加フォルダを、この PC の `~/Desktop/みかみ案件依頼書` などに直す（コピーした元の PC の場所は外す）。`.claude/addness/cases_local.json` が無ければ作る | 案件フォルダの置き場が違う時は追加フォルダに足す |
| links | `~/Downloads/コピー_…` → `完成版/…` のリンク（見本集の .prproj が完成版をこの場所で覚えている） | ― |
| keys | 見るだけ | OpenAI：キーをコピーしてから `security add-generic-password -U -a "$USER" -s openai_api_key -w "$(pbpaste)"`。YouTube：Air の `~/.video_edit_rules/youtube/client_secret.json` を AirDrop で受け取り、`python3 tools/youtube_upload.py auth --import <JSON>`。画像生成の費用の記録（`~/.video_edit_rules/gen_image_log.csv`）は PC ごとなので、月10ドルは全部の PC の合計で見る |
| git | 見るだけ | `gh auth login`（GitHub に送るため） |
| hook | 開始時の【Addness】の案内が出るか見る | ― |

ほかに PC ごとに要るもの：

- **Addness**：Claude デスクトップは、Claude にログインすれば claude.ai のコネクタ（ツール名 `mcp__40e7bd83-…__`）で使える。CLI はフォルダの `.mcp.json` の `addness`（ツール名 `mcp__addness__`）を最初に許可し、ブラウザでログインする
- **予定タスク「動画編集フォルダとAddnessの同期」**（毎日 9時・18時）：要る PC だけ。Claude に「`環境/予定タスク/video-edit-addness-sync/SKILL.md` の中身で、毎日 9時と18時の予定タスクを作って」と頼む。2台で動かしても、Addness に無い差分だけを書くので二重にはならないが、その PC で作業しない日は止めてよい
- **python3 と Pillow**（フックと多くの道具）：デベロッパツールの python3（`xcode-select --install`）と `python3 -m pip install --user Pillow`。swift（画面の文字認識）もデベロッパツールで入る
- Premiere 本体・Media Encoder（Creative Cloud）

## 3. 確かめる（新しい PC で）

1. `python3 tools/setup_mac.py` が「足りないもの 0 件」（keys は使う時まででよい）
2. Premiere を開き、パネルを出して `python3 tools/premiere_bridge.py status` で Premiere 1つ・`bridge_panels: 1`
3. 部品集から試しの案件を作って開き、オフラインが0・「フォントを解決」の画面が出ない（開く前に `python3 tools/font_fix.py --scan <案件の .prproj>` で0件）。案件のプロジェクトは `python3 tools/build_parts.py --case-copy "$HOME/Desktop/みかみ案件依頼書/<案件>/edit/v001/<案件>_v001.prproj"`（絶対パスで書く）で作ると、SE・画像の素材がその PC の `素材/` を指す。見本集のコピーをそのまま開くと SE・BGM・背景がオフラインになる（`changeMediaPath` で `素材/` につなぎ直すか、部品集を使う）
4. 文字起こし：`HF_HUB_OFFLINE=1 env/bin/python -c "import mlx_whisper"` が通り、短い音声で `tools/audible_onset.py transcribe` が動く
5. Claude を開くと【Addness】の案内が出て、Addness のゴールが読める

動かなかった所は直して、この手順に書き足す（Addness の「1-4 別のPCにコピーして…」43e6b4a3-19b4-418a-b922-0a69db5d8a8c に結果を書く）。
