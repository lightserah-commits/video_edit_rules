# 環境設定 v002 の動く図解（zukai/）

2026-10-04 小川さん「dots で言ったことを元に…図解もできるところは作ってしまって」。dots v002 の図解（`~/Desktop/みかみ案件依頼書/dots開設/edit/v002_zukai/絵コンテ.md`。小川さんは v002 の後に図解への直しを出さず、v003〜v005 を経て投稿した）と同じ作り方。

## 見た目の決まり（dots v002 と同じ）

- **黒い板（全面・80%。カメラが薄く透ける）＋右下に三上さんのワイプ（576×324、x 1286〜1862・y 696〜1020）**。ぼかしは使わない（dots v001 で「図解の周りに変なのがある」と言われたのは、ぼかしの縁と札の並び）
- **部品は三上さんがその言葉を言った瞬間に1つずつ出る**（横から流れてくる SLIDE＝5コマ・指向性ブラー 6コマ。矢印は 10コマで伸びる）。最後は全部が同じコマで消える
- 札を3枚並べるだけのものは図解ではない。**絵（人・AI・アプリの箱・矢印・メモ・脳みそ・ロゴ）と配置で、見比べ・流れ・仕組みが一目で分かること**
- 比べる時は左右を同じ形にして、違う所だけを見せる（dots：左右とも「上に AI・右へ矢印・下にあなた」、違いは矢印が1本か3本か）。話していない側は暗くする（data-dim、明るさ 0.45・彩度 0.55。不透明のまま）
- 字は三上さんと聞き手の言葉か、それを縮めたもの。言っていない事実を足さない
- 色：先・既存＝青（#1b5fd1）、後・対比＝赤（#d90a0a）、強調・締め＝黄（#f5e63a）。地の文字は白に黒の縁
- 書体：`Lbl`（わんぱくルイカ。地の文字・札）、`Tsk`（Reggae One。叩きつける一言）、`Jp`（凸版文久見出しゴシック EB）、`Hv`（源ノ角ゴシック Heavy）
- 文字は大きく：見出し 72〜90px、部品の札 48〜64px、吹き出し 44〜54px。1つの絵に出ている字は 40字くらいまで（読めない量を出さない）
- 画面の端から 40px 以上離す。右下のワイプの所（x>1250 かつ y>660）に部品を置かない
- 図解の間は、通常字幕・右上タイトル・重なる強調・※・札・ズームは make_v002.py が外す（図の中の字が字幕の代わり。09 の共通の決まり）
- SE：出だしにピピ、部品ごとに cursor（並べる時）かピピ、締めにドスッ／キッ／キーン／キランッ。連打にしない（0.5秒以内に2つ鳴らさない）

## 作り方

1. 時刻を調べる：`python3 zukai/tl.py words <最初の字幕ID> <最後の字幕ID>`（v002 のタイムラインの絶対のコマ・言葉ごとの聞こえ始め）
2. `zukai/<KEY>/diagram.json` を書く：
   ```json
   {"key": "Z1", "title": "AIの道具を増やす順番", "start_f": 3940, "end_f": 4398, "anchor": {"cap": "69", "f": 3940},
    "wipe": {"show": true}, "se": [{"f": 0, "se": "ピピ", "why": "出だし"}, {"f": 133, "se": "cursor", "why": "②"}],
    "hide_caption_ids": "auto", "removes": "v001 の図解（型3）69〜74", "checks": [60, 200], "story": "絵コンテ（言葉と部品）"}
   ```
   - start_f＝最初の部品を出すコマ（字幕の開始か言葉の聞こえ始め）、end_f＝全部消えるコマ（次の字幕の開始など。含まない）
   - se の名前は plan_v002.SE のもの：ピピ・cursor・キーン・キランッ・キッ・しゃん・決定・ドスッ・ポカン・ドン・シャーン・グキッ・ピコンッ・キラ・カカッ・チーン など
3. `zukai/<KEY>/page.html` を書く（部品の出るコマ＝絶対のコマ − start_f）：
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
   - 絵は SVG・CSS で描いてよい（箱・人・脳みそ・メモ・アイコン）。イラストは `~/Desktop/video_edit_rules/素材/イラスト/`（`イラスト一覧.yaml`。Z.ILLUST + ファイル名）
   - 画像（Orca・Obsidian の公式のロゴや画面）は `zukai/assets/` に置いて `../assets/名前` で読む
   - CSS の animation・transition・setTimeout・Math.random・Date は使わない（コマごとに同じ絵にならない）
4. 作る：`python3 zukai/make_zukai.py <KEY>`（採寸だけなら `--check`、描いたコマのまま画像だけ作り直すなら `--previews`）
   - 「!!」の注意（画面の端・ワイプに重なる・画面を映している所に重なる）は直す
   - `zukai/out/<KEY>/previews/` の画像（カメラ＋図解＋ワイプを重ねた絵。Premiere のリニア合成に近い見え方）を Read で全部見て、読めるか・重ならないか・言葉と合うかを確かめる。`動き_<KEY>.mp4` は半分の大きさの動き
5. Premiere への置き方は build_v002.py（V15 に overlay.mov、V16 に wipe.mp4）と make_v002.py（字幕を外す・SE・右上タイトルを外す）が `out/<KEY>/manifest.json` を読んでやる
