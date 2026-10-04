"""文字認識の結果（analysis/screen_ocr_v004/ocr.json）から、①画面の中を読み上げている所の赤枠（07 の read_frame）を作り、
②ぼかしの候補（07 の blur：Finder・Google ドライブなどパソコンの中身が見える所）を一覧にする（AI はぼかしを入れない。場所は小川さんが指定）。
  ① 赤枠：字幕の文字の6割以上（5文字以上）が画面の1行に出ていれば「読んでいる」（tools/screen_reading.py と同じ決まり）。
     左の一覧（スレッドの履歴）は除く。続けて同じ場所を読む字幕は1つの枠にまとめる。→ _work/red_frames.json と PNG（1920×1080 透明）。V4 に置く
  ② ぼかしの候補 → _work/blur_candidates_v004.json（報告で一覧にする）
  python3 v004/screen_marks_v004.py
"""
import bisect
import difflib
import json
import os
import re
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
CASE = os.path.dirname(HERE)
OCR = os.path.join(CASE, "analysis", "screen_ocr_v004")
FPS = 30000 / 1001
SIDEBAR = [0.0, 0.07, 0.20, 1.0]           # 左の一覧（Codex のスレッドの履歴）
FINDER_WORDS = ["よく使う項目", "デスクトップ", "アプリケーション", "マイドライブ", "共有アイテム", "アイテムを選択", "ダウンロード"]
_OLD_NAMES = ["大賀", "賀商会", "大気商会", "丸正", "丸上", "誠伸", "城仲", "試仲", "興業", "熊谷", "照谷", "熊貝", "谷 元", "元太", "元木",
         "池島", "池嶋", "裕一", "梶川", "弘徳", "Crazy", "I.K.E", "小澤", "STAY", "アルフ", "hape", "ワークオール", "アホーム", "刈谷",
         "marus", "maruy", "maruge", "arusye", "日本設備工業", "アグリン", "リンテル", "TOKAI", "潮物産", "入江"]
EXCLUDE = {"351", "377", "565", "617", "1289", "356", "357", "385", "410", "663", "685", "955"}   # 読み上げではない所（v001 の一覧と、検査係が画像で見た所）：377・565・617・1289 は「Addness」「Obsidian」の1語が当たっただけ、351 は強調 349 と同じ図の題、356 は左の返事の文（読んでいるのは右の図の箱）、385・410 は声の入力（画面に無い）、663・685 は読んでいない本文の行、955 はボタンの名前（メニューが消えて枠だけ残る）
RECT_FIX = {"1470": [1098, 439, 1303, 497]}   # 手で決めた枠（px）：1470 は2行（知恵はそのままゴールの上に／誰もまとめなくていい）を1つの枠で
MIN_CHARS, MIN_RATIO = 5, 0.6
PAD, STROKE, COLOR = 10, 8, (255, 30, 30, 255)
TOP = 0.075                                  # 画面の上の帯（タブ・ボタン）


def norm(s):
    s = unicodedata.normalize("NFKC", s).lower()
    return re.sub(r"[\s、。・,.!?！？「」『』（）()\[\]【】:：;；\"'`~〜ー\-–—→…／/%〇]", "", s)


def match_len(a, b):
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    return sum(bl.size for bl in sm.get_matching_blocks() if bl.size >= 2)


def in_sidebar(o):
    return o["x"] + o["w"] / 2 < SIDEBAR[2] and o["y"] > SIDEBAR[1]


def main():
    from PIL import Image, ImageDraw
    jobs = json.load(open(os.path.join(OCR, "jobs.json"), encoding="utf-8"))
    ocr = json.load(open(os.path.join(OCR, "ocr.json")))
    mp = json.load(open(os.path.join(HERE, "_work", "base_v004_map.json"), encoding="utf-8"))
    ctl = mp["caption_tl"]
    capj = json.load(open(os.path.join(HERE, "_work", "captions_v004.json"), encoding="utf-8"))
    caps = sorted([c for c in capj["captions"] if c["mode"] != "drop" and "src" in c], key=lambda c: ctl[c["id"]])
    nxt = {c["id"]: (ctl[caps[k + 1]["id"]] if k + 1 < len(caps) else mp["total_frames"]) for k, c in enumerate(caps)}
    text = {c["id"]: c["text"].replace("\r", "") for c in caps}
    order = {c["id"]: k for k, c in enumerate(caps)}
    FT = 8475667200
    def clip_to_screen(a, b):
        """赤枠は画面を映している間だけ（v001：切り替えをカットの切れ目に寄せたので、字幕の区切りと数フレームずれる）"""
        for x, y in mp["screen_spans"]:
            if x < b and a < y:
                return max(a, x), min(b, y)
        return a, b
    # ---- ① 赤枠 ----
    by_cap = {}
    for j in jobs:
        by_cap.setdefault(j["id"], []).append((j, ocr.get(j["png"], [])))
    hits = []
    for cid, lst in by_cap.items():
        if cid in EXCLUDE:
            continue
        cap = norm(text[cid])
        if len(cap) < MIN_CHARS:
            continue
        best = None
        for j, items in lst:
            for o in items:
                if o["y"] < TOP or o.get("conf", 1) < 0.3 or in_sidebar(o):
                    continue
                t = norm(o["text"])
                if len(t) < 10:                 # 「ChatGPT」「Codex」などの見出し・ボタンに当たっただけのものは読み上げではない
                    continue
                L = match_len(cap, t)
                if L >= MIN_CHARS and L / len(cap) >= MIN_RATIO:
                    score = (L / len(cap), L)
                    if best is None or score > best[0]:
                        best = (score, o)
        if best:
            hits.append({"id": cid, "text": text[cid], "ocr": best[1]["text"], "box": best[1], "ratio": round(best[0][0], 2)})
    hits.sort(key=lambda h: order[h["id"]])
    groups = []
    for h in hits:
        if groups:
            g = groups[-1][-1]
            b0, b1 = g["box"], h["box"]
            near = order[h["id"]] - order[g["id"]] <= 2 and abs(b0["y"] - b1["y"]) < 0.08
            if near:
                groups[-1].append(h)
                continue
        groups.append([h])
    disp_w = 3456 * 1080 / 2234
    off_x = (1920 - disp_w) / 2
    os.makedirs(os.path.join(HERE, "_work", "red_frames"), exist_ok=True)
    frames = []
    for k, g in enumerate(groups):
        x0 = min(h["box"]["x"] for h in g)
        y0 = min(h["box"]["y"] for h in g)
        x1 = max(h["box"]["x"] + h["box"]["w"] for h in g)
        y1 = max(h["box"]["y"] + h["box"]["h"] for h in g)
        rect = [off_x + x0 * disp_w - PAD, y0 * 1080 - PAD, off_x + x1 * disp_w + PAD, y1 * 1080 + PAD]
        if g[0]["id"] in RECT_FIX:
            rect = list(RECT_FIX[g[0]["id"]])
        img = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
        ImageDraw.Draw(img).rounded_rectangle(rect, 12, outline=COLOR, width=STROKE)
        png = os.path.join(HERE, "_work", "red_frames", f"frame_{k:03d}_{g[0]['id'].replace('+', 'p')}.png")
        img.save(png)
        frames.append({"id_from": g[0]["id"], "id_to": g[-1]["id"], "png": png, "rect_px": [round(v) for v in rect],
                       "start": clip_to_screen(ctl[g[0]["id"]], nxt[g[-1]["id"]])[0] * FT,
                       "end": clip_to_screen(ctl[g[0]["id"]], nxt[g[-1]["id"]])[1] * FT,
                       "read": " / ".join(h["text"] for h in g), "ocr": " / ".join(h["ocr"] for h in g), "ratio": [h["ratio"] for h in g]})
    json.dump({"frames": frames, "hits": len(hits)}, open(os.path.join(HERE, "_work", "red_frames.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"読んでいる字幕 {len(hits)} 本 → 赤枠 {len(frames)} 個")
    for f in frames:
        print(f"  {f['id_from']:>7}-{f['id_to']:<7} 話：{f['read'][:30]}  画面：{f['ocr'][:34]}")
        # ---- ② ぼかしの候補（パソコンの中身が見える所）----
    cands = []
    for j in jobs:
        items = ocr.get(j["png"], [])
        words = [w for w in FINDER_WORDS if any(w in o["text"] for o in items)]
        if len(words) >= 2:
            cands.append({"id": j["id"], "tl_frame": j["tl"], "time": f"{int(j['tl'] / FPS // 60)}:{j['tl'] / FPS % 60:05.2f}", "words": words, "png": j["png"]})
    json.dump(cands, open(os.path.join(HERE, "_work", "blur_candidates_v004.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"ぼかしの候補（Finder・ドライブの文字が2つ以上）{len(cands)} 枚")
    for c in cands[:20]:
        print("  ", c["time"], c["id"], c["words"])


if __name__ == "__main__":
    main()
