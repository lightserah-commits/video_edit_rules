# 動く図解と画像の道具（tools/zukai/）

AI が HTML で描いた図解・画像を、1コマずつ Chrome で撮って透明の動画（ProRes 4444）にし、案件の組み立て（build・make）が V15・V16 に置く。
dots v002 の図解（小川さん OK）と同じ作り方を、環境設定 v002〜v004 で道具にしたもの（図解 Z1〜Z7・画像 I01〜I14・ロゴの札 L1。v004 で小川さん OK・書き出し済み）。
決め方（どこを図解にするか・型）は `09_図解.md`、画像を出す所は 02 の画像。ここは作り方だけ。

## どの案件・どの版か

道具は案件名・版の番号を持たない。版のフォルダを `--ver "~/Desktop/みかみ案件依頼書/<案件>/edit/vNNN"`（か環境変数 `ZUKAI_VER`）で渡す。
ほかの置き場所は版のフォルダから決まる（`case.py` の頭。違う時は `--zukai`・`--cuts`・`--captions`・`--map`・`--asr`・`--cam`）：

| もの | 既定の場所 |
|---|---|
| 図解のフォルダ | `<版>/zukai/`（`<KEY>/page.html`・`diagram.json`、`assets/`、`out/`、`images_spec.py`） |
| カット・字幕・土台の表 | `<版>/_work/cuts_vNNN.json`・`captions_vNNN.json`・`base_vNNN_map.json` |
| 語の時刻・カメラ | `<edit>/analysis/asr/asr_camera.json`・`<edit>/media/camera_CFR2997.mov`（29.97fps の作業用コピー） |

ページは `../lib/zukai.css`・`../lib/zukai.js` を読む。図解のフォルダに `lib` が無ければ、`make_zukai.py` が `tools/zukai/lib` へのリンクを作る
（前の案件のように lib を写して持っている時は、そちらを使う）。

## 見た目の決まり（dots v002・環境設定 v004 と同じ）

- **黒い板（全面・80%。カメラが薄く透ける）＋右下に話し手のワイプ（576×324、x 1286〜1862・y 696〜1020）**。ぼかしは使わない（dots v001 で「図解の周りに変なのがある」と言われた）
- **部品は話し手がその言葉を言った瞬間に1つずつ出る**（横から流れてくる slide＝5コマ・指向性ブラー 6コマ。矢印は 10コマで伸びる）。最後は全部が同じコマで消える
- 札を並べるだけのものは図解ではない。**絵（人・AI・アプリの箱・矢印・メモ・脳みそ・ロゴ）と配置で、見比べ・流れ・仕組みが一目で分かること**
- 比べる時は左右を同じ形にして、違う所だけを見せる。話していない側は暗くする（`data-dim`、明るさ 0.45・彩度 0.55。不透明のまま）
- 字は話し手と聞き手の言葉か、それを縮めたもの。言っていない事実を足さない
- 色：先・既存＝青（#1b5fd1）、後・対比＝赤（#d90a0a）、強調・締め＝黄（#f5e63a）。地の文字は白に黒の縁
- 書体：`Lbl`（わんぱくルイカ）、`Tsk`（Reggae One。叩きつける一言）、`Jp`（凸版文久見出しゴシック EB）、`Hv`（源ノ角ゴシック Heavy）。`zukai.css` が PostScript 名で探す（Adobe Fonts で有効にしておく）
- 文字は大きく：見出し 72〜90px、部品の札 48〜64px、吹き出し 44〜54px。1つの絵に出ている字は 40字くらいまで
- 画面の端から 40px 以上離す。右下のワイプの所（x>1250 かつ y>660）に部品を置かない
- 図解の間は、通常字幕・右上タイトル・重なる強調・※・札・ズームを組み立て（make）が外す（図の中の字が字幕の代わり。09 の共通の決まり）
- SE：出だしにピピ、部品ごとに cursor（並べる時）かピピ、締めにドスッ／キッ／キーン／キランッ。連打にしない（0.5秒以内に2つ鳴らさない）
- ワイプの切り出しは diagram.json の `wipe.crop` で決めるのがよい（環境設定 v004 は7つとも `[460, 30, 1440, 810]`：頭の上に余白・両手の手振りも入る）。省くと顔検出で決める

## 作り方（図解 Z*）

1. 時刻を調べる：`python3 tools/zukai/tl.py --ver <版> words <最初の字幕ID> <最後の字幕ID>`（タイムラインの絶対のコマ・言葉ごとの聞こえ始め）。
   ほか `caps`・`at 5:20.0`・`prev <前の版の cuts_vMMM.json> 5:19.9`（前の版の時刻 → この版）
2. `<図解のフォルダ>/<KEY>/diagram.json` を書く：
   ```json
   {"key": "Z1", "title": "AIの道具を増やす順番", "start_f": 3940, "end_f": 4398, "anchor": {"cap": "69", "f": 3940},
    "wipe": {"show": true, "crop": [460, 30, 1440, 810]}, "se": [{"f": 0, "se": "ピピ", "why": "出だし"}, {"f": 133, "se": "cursor", "why": "②"}],
    "hide_caption_ids": "auto", "removes": "前の版の図解（型3）69〜74", "checks": [60, 200], "story": "絵コンテ（言葉と部品）"}
   ```
   - start_f＝最初の部品を出すコマ（字幕の開始か言葉の聞こえ始め）、end_f＝全部消えるコマ（次の字幕の開始など。含まない）
   - anchor＝start を決めた字幕とその時の開始コマ。カットが変わって字幕が動くと、make がその分ずらす
   - se の名前は組み立て（plan_vNNN.py の SE）にあるもの：ピピ・cursor・キーン・キランッ・キッ・しゃん・決定・ドスッ・ポカン・ドン・シャーン・ピコンッ・キラ・カカッ・チーン など
3. `<図解のフォルダ>/<KEY>/page.html` を書く（部品の出るコマ＝絶対のコマ − start_f）：
   ```html
   <!doctype html><html><head><meta charset="utf-8">
   <link rel="stylesheet" href="../lib/zukai.css"><script src="../lib/zukai.js"></script></head><body>
   <div id="board"></div>
   <div class="part" id="head" data-f0="0" style="left:110px;top:60px"><div class="in" id="h"></div></div>
   <div class="part" id="arr1" data-f0="133" data-m="grow" style="left:620px;top:400px"><div class="in" id="r1"></div></div>
   <script>
   window.ZUKAI = { frames: 458 };               // ＝ end_f − start_f（違うと make が止まる）
   document.getElementById('h').innerHTML = Z.stk('AIの道具を増やす順番', {size: 84});
   document.getElementById('r1').innerHTML = Z.arrow({len: 300, dir: 'right'});
   </script></body></html>
   ```
   - 部品の属性・道具（Z.stk・Z.plate・Z.bubble・Z.arrow・Z.img・Z.ILLUST）と動き（slide・slideL・pop・bounce・fade・grow・draw・type・data-dim・data-out・.fill・ZUKAI.custom）は `lib/zukai.js` の頭
   - 絵は SVG・CSS で描いてよい。イラストは `素材/イラスト/`（`イラスト一覧.yaml`。`Z.ILLUST + ファイル名`。場所は render_frames.mjs が入れるので、ページをブラウザで直に開くとイラストは出ない）
   - 公式のロゴや画面・写真は `<図解のフォルダ>/assets/` に置いて `../assets/名前` で読む。どこから取ったかを `assets/出どころ.md` に書く（使う許しの範囲も）
   - CSS の animation・transition・setTimeout・Math.random・Date は使わない（コマごとに同じ絵にならない）
4. 作る：`python3 tools/zukai/make_zukai.py --ver <版> <KEY>`（採寸だけなら `--check`、描いたコマのまま画像だけ作り直すなら `--previews`。
   作り直しで前の overlay を残すなら `--name=auto`）。いくつも作る時・Chrome が止まる時は `run_zukai.py`（420秒で打ち切って3回まで）
   - 「!!」の注意（画面の端・ワイプに重なる・画面を映している所に重なる）は直す
   - `out/<KEY>/previews/` の画像（カメラ＋図解＋ワイプを重ねた絵。Premiere のリニア合成に近い見え方）を全部見て、読めるか・重ならないか・言葉と合うかを確かめる。`動き_<KEY>.mp4` は半分の大きさの動き（音なし）
   - 別の AI に反証してもらう（髪の上が切れる・顔にかかる・言っていない字・出るのが言葉より遅い）
5. 組み立て：build が `out/<KEY>/manifest.json` を読み、Z* は V15 に overlay・V16 に wipe、I*・L* は V16 に overlay を置く。make が `hide_caption_ids` の字幕・右上タイトルを外し、`se_events` を鳴らす
   （manifest の中身は make_zukai.py の build() の最後）

## 画像（I*）

`<図解のフォルダ>/images_spec.py` に1か所1行で書き（`examples/images_spec_example.py`）、`python3 tools/zukai/gen_images.py --ver <版> [I01 …]` で page.html と diagram.json を作る
（黒い板・ワイプなし）。そのあと `make_zukai.py I01`。写真は白い縁・角丸・影でポンと出す、ロゴは白いカードで流れてくる、言葉の頭に出す。顔・右上のタイトル・強調の帯にかけない。

## カットが変わった時

- 字幕が動いただけ：`python3 tools/zukai/shift.py --ver <新しい版> [--dry]`（描き直さず manifest と diagram.json の時刻を直す。区間の素材のコマが変わったら止まる＝描き直し）
- 図解の頭がカットより数コマ後で、素のカメラが一瞬出る：`python3 tools/zukai/head_pad.py --ver <版> <KEY>`（目印の字幕の頭まで。overlay・wipe は新しい名前）
- 新しい版のフォルダに図解を写して使う時は、`out/` の manifest が前の版の overlay を指したままでよい（ファイルは前の版のフォルダに残す）

## 道具

| ファイル | すること |
|---|---|
| `make_zukai.py` | 描く → overlay・wipe・確かめの画像・manifest（`--check`・`--previews`・`--name=auto`） |
| `tl.py` | タイムラインのコマと字幕・言葉の時刻 |
| `gen_images.py` | 画像を出す所の page.html・diagram.json（`images_spec.py` から） |
| `shift.py` | 字幕が動いた分だけ時刻をずらす（描き直さない） |
| `head_pad.py` | 図解の頭を数コマ前へ倒す（描き直さない） |
| `run_zukai.py` | make_zukai.py を順に回す（止まったらやり直す） |
| `case.py` | 案件・版の置き場所を決める |
| `lib/zukai.js`・`zukai.css`・`render_frames.mjs` | ページの動き・書体・板／1コマずつ透明の PNG に撮る（Chrome ヘッドレス。Node 22 以上：組み込みの WebSocket を使う） |
| `facedet.swift` | 顔検出（ワイプの自動の切り出し。初回に `out/_bin/facedet` へコンパイル） |

元（環境設定 v004）から変えた所：場所を引数に／書体をユーザー名の入ったパスから PostScript 名（local()）に／`Z.ILLUST` を render_frames.mjs が入れる形に／
顔検出の数字を「中心」と読む（v004 は左上と読んでいて顔の幅・高さの半分ずれていた。v004 の図解は crop を手で決めていたので影響なし）／
gen_images.py の中身（I01〜I14）を案件の images_spec.py に分けた／shift・head_pad の記録の名前（`shifted`・`head_pad`）。
