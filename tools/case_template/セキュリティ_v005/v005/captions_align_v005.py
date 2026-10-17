"""セキュリティについて v005（2026-10-16。AI動画編集 v005 の雛形を写した。ONSET_FIX は空から）。以下は元の説明：AI動画編集 v005（1015claude project開設 v005 を写した）。以下は元の説明：1015claude project開設 v005 の通常字幕の開始（1003 AIで稼ぐ系 v005 の captions_align を写した。ONSET_FIX は空から）（素材の秒）を決め、台本（script_v005.txt）を上司のルール（30_文節と言葉・字幕と話者の品質規則.json）で検査する。
  - 区切りの頭から出す字幕：その区切りの最初の語の時刻を候補に、聞こえ始め（tools/audible_onset.py の best_onset）
  - 途中から出す字幕：その文字を含む語の時刻を候補に、同じく聞こえ始め
  - 話者：台本の「@」＝聞き手。声の高さ・声色（analysis/speaker/voicefeat.json）の k 近傍で食い違うものを知らせる
  出力 _work/captions_v005.json
  ~/Desktop/video_edit_rules/env/bin/python v005/captions_align_v005.py
"""
import difflib
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from common import A, Aligner, Script, Voice, load_units, norm, width  # noqa: E402
from common import audible_onset  # noqa: E402

# 08 の captions.timing.note：字幕の開始の候補を、whisper small の DTW の語の時刻（analysis/asr/asr_dtw.json）と字幕の文字の並べ合わせ（asr_candidate2）から取る。
#   候補が取れなければ、今までの mlx_whisper の語の時刻の候補
DTW_JSON = os.path.join(A, "asr", "asr_dtw.json")
DTW_TOKENS = audible_onset.load_whisper_tokens(DTW_JSON) if os.path.exists(DTW_JSON) else []
DTW_STARTS = [t_["start"] for t_ in DTW_TOKENS]
# v005（2026-10-05）：この案件は2人の声が重なる所が多く、DTW(small) だけだと 0.5〜1.4秒ずれる字幕が出た（検査係が波形で確かめた 24か所の平均誤差：DTW(small) 0.47秒・mlx 1回目 0.19・mlx 2回目 0.16）。
#   開始の候補を、mlx 1回目（今まで）・DTW(small)・mlx 2回目・DTW(large-v3-turbo。あれば）の4つから出し、0.25秒以内で一番多く集まった所を選ぶ（同数なら DTW(large)＞mlx 2回目＞mlx 1回目＞DTW(small)）
EST = []          # (名前, 語, 語の開始)
if DTW_TOKENS:
    EST.append(("dtwS", DTW_TOKENS, DTW_STARTS))
_P2 = os.path.join(A, "asr", "asr_camera_p.json")
if os.path.exists(_P2):
    _t2 = sorted(({"text": w["word"], "start": round(float(w["start"]), 3)} for seg in json.load(open(_P2, encoding="utf-8")) for w in seg.get("words", [])),
                 key=lambda x: x["start"])
    EST.append(("mlx2", _t2, [x["start"] for x in _t2]))
_DL = os.path.join(A, "asr", "asr_dtw_large.json")
if os.path.exists(_DL):
    _tl = audible_onset.load_whisper_tokens(_DL)
    EST.insert(0, ("dtwL", _tl, [x["start"] for x in _tl]))
PRIORITY = {"mlx2": 0, "mlx1": 1, "dtwL": 2, "dtwS": 3}
# 票の重み（2026-10-05 検査係が波形で確かめた24か所＋自分で確かめた所で試した結果。この案件では DTW が語の頭より 0.15〜0.35秒遅い所が多く、mlx の2回目が声の立ち上がりに一番合った）：
#   基本の重み mlx 2回目 1.0・mlx 1回目 0.8・DTW(large) 0.8・DTW(small) 0.6。さらに、その時刻が「静けさのあとの立ち上がり」になっているほど重くする（コントラスト = 後ろ0.12秒の最大 − 前の最大。15dB 以上で2倍）
#   平均誤差（24か所）：DTW(small) だけ 0.47秒 → DTW を重くした多数決 0.18 → この重み 0.08（最大 0.33）
WEIGHT = {"mlx2": 1.0, "mlx1": 0.8, "dtwL": 0.8, "dtwS": 0.6}
VOTE_TOL = 0.25


def vote(cands, contrast=None):
    """cands = [(名前, 秒, 決め方)]。VOTE_TOL 秒以内に集まった票の重さが一番大きいまとまりから、優先順位の高い推定の秒を選ぶ"""
    def w(x):
        return WEIGHT[x[0]] * (1 + (min(1.0, max(0.0, contrast(x[1]) / 15.0)) if contrast else 0.0))
    best = None
    for _, t0, _ in cands:
        grp = [x for x in cands if abs(x[1] - t0) <= VOTE_TOL]
        key = (round(sum(w(x) for x in grp), 3), -min(PRIORITY[x[0]] for x in grp))
        if best is None or key > best[0]:
            best = (key, grp)
    grp = best[1]
    pick = min(grp, key=lambda x: PRIORITY[x[0]])
    return pick[1], f"{pick[0]}→{pick[2]}（{len(grp)}/{len(cands)}一致）", {n: round(t_, 3) for n, t_, _ in cands}

OUT = os.path.join(HERE, "_work", "captions_v005.json")
LINE_MAX = 17
MIN_DUR = 0.4
# 波形を見て手で決めた聞こえ始め（字幕ID → 素材の秒）。自動の「大きさの谷」が声より前の無音に落ちた所（v005）
ONSET_FIX = {
    "260": 588.15,
    "30": 69.50,     # 「間違えて」の「ま」（ASR 69.60。69.51〜69.75 の声）。自動は「ち」の無音の後から出していた（確かめ係2回目 A9）
    "424": 982.84,   # 「システムは」の「シ」（982.85 からの擦れる音）（確かめ係2回目 A9）
    "48+1": 108.00,  # v005 小川さん（Loom 2:28「ここおかしい、今なんか一瞬」）：「そうです」の頭（文字起こし 108.04。107.92〜107.96 の谷の後）。DTW の2つが三上さんの「それでカモ認定された」の「カモ」（107.08）を取って、三上さんの字幕 47 が 0.15秒しか出ていなかった
    "514": 1193.05,  # 「あなたは」の「あ」（ASR 1193.16。1193.05〜1193.23 の声の後に間がある）（確かめ係2回目 A9）   # 「いや（防ぐのは）もう無理よ」の「いや」（588.15〜588.40 の声）。自動は「いや」の後の間から出していて、強調が 0.42秒遅れた（確かめ係1回目 A9。2026-10-17 波形で見た）
}   # 波形を見て手で決めた聞こえ始め（字幕ID → 素材の秒）。自動の「大きさの谷」が声より前の無音に落ちた所を、見つけたらここに足す


def cut_units(script, units):
    """カットで丸ごと消える区切り、頭が切られる区切り（→ その語から）、後ろが切られる区切り（→ その語まで）"""
    full, head_cut, tail_cut = set(), {}, {}
    ids = sorted(units)
    for c in script.cuts:
        (ua, wa), (ub, wb) = c["a"], c["b"]
        if wa is not None:
            tail_cut[ua] = wa
        if wb is not None:
            head_cut[ub] = wb
        lo = ua + (1 if wa is not None else 0)
        hi = ub - (1 if wb is not None else 0)
        for u in ids:
            if lo <= u <= hi:
                full.add(u)
    return full, head_cut, tail_cut


def main():
    units = load_units()
    sc = Script()
    voice = Voice()
    al = Aligner(units, voice)
    full, head_cut, tail_cut = cut_units(sc, units)
    errors, warns = [], []
    import numpy as np

    def contrast(t):
        """t が声の立ち上がりか：後ろ0.12秒の最大の大きさ − 前 0.15〜0.04秒の最大（dB）"""
        i0, i1 = voice.idx(t), voice.idx(t + 0.12)
        j0, j1 = voice.idx(t - 0.15), voice.idx(t - 0.04)
        return float(np.max(voice.db[i0:i1 + 1]) - np.max(voice.db[j0:j1 + 1]))
    # ---- 区切りごとに、どの字幕に入るか ----
    starts = {c["u"]: c for c in sc.captions if c["mode"] == "start"}
    drops = {c["u"] for c in sc.captions if c["mode"] == "drop"}
    mids = defaultdict(list)
    for c in sc.captions:
        if c["mode"] == "mid":
            mids[c["u"]].append(c)
    for c in sc.captions:
        if c["u"] in full:
            errors.append(f"行{c['line']}：字幕 {c['id']} の区切り{c['u']}はカットの中")
    owner = {}
    cur = None
    for u in sorted(units):
        if u in full:
            cur = None if u + 1 in starts or u + 1 in full else cur
            continue
        if u in starts:
            cur = starts[u]
        elif u in head_cut and mids.get(u):
            cur = mids[u][0]
        elif cur is None and u not in drops:
            errors.append(f"区切り{u}「{units[u]['text']}」がどの字幕にも入っていない（カットの後の頭に字幕が無い）")
        owner[u] = cur["id"] if cur else None
        if mids.get(u):
            cur = mids[u][-1]
    # ---- 開始時刻 ----
    caps = []
    last_k = {}
    prev_text = None
    dtw_n = {"candidate": 0, "changed": 0, "none": 0}
    for c in sc.captions:
        u = c["u"]
        d = dict(c)
        if c["mode"] == "drop":
            caps.append(d)
            continue
        if c["mode"] == "start":
            if u in head_cut:
                errors.append(f"行{c['line']}：区切り{u}は頭が切られているので「{u}+|」で書く")
            t, how = al.unit_onset(u)
            d["asr"] = units[u]["start"]
            if c["id"] in ONSET_FIX:
                t, how = ONSET_FIX[c["id"]], "波形で決めた"
            last_k[u] = 0
        else:
            k0 = last_k.get(u, -1) + 1
            t, how, k = al.phrase_onset(u, c["anchor"] or c["text"], k0)
            if t is None:
                errors.append(f"行{c['line']}：「{c['text']}」の始まりが区切り{u}「{units[u]['text']}」の中に見つからない")
                continue
            last_k[u] = k
            d["asr"] = al.char_time(u, k)
            if c["id"] in ONSET_FIX:   # v005：途中から出す字幕も手で決めた聞こえ始めにする
                t, how = ONSET_FIX[c["id"]], "波形で決めた"
        if EST and c["id"] not in ONSET_FIX:
            ctext = c["text"].replace("\r", "")
            cands = [("mlx1", t, how)]
            for name, toks_, sts_ in EST:
                cd_ = audible_onset.asr_candidate2(toks_, sts_, ctext, d["asr"], prev_text=prev_text)
                if cd_ is not None and abs(cd_ - d["asr"]) <= 1.0:
                    t2_, how2_ = al.onset(cd_)
                    cands.append((name, t2_, how2_))
            if len(cands) > 1:
                t2, how2, info = vote(cands, contrast)
                dtw_n["candidate"] += 1
                if abs(t2 - t) >= 0.01:
                    d["src_before_dtw"] = round(t, 3)
                    dtw_n["changed"] += 1
                d["cands"] = info
                t, how = t2, how2
            else:
                dtw_n["none"] += 1
        prev_text = c["text"].replace("\r", "")
        d["src"] = round(t, 3)
        d["how"] = how
        caps.append(d)
    warns.append(f"DTW の候補：{dtw_n}")
    shown = [c for c in caps if c["mode"] != "drop" and "src" in c]
    # ---- v005 小川さん「テロップは可聴音（声が聞こえ始める所）に合わせて」----
    #   ① 字幕の出だしが無音の中（10ms ごとの大きさが「声の境目 −6dB」より小さい）→ 次に音が聞こえ始める所の 0.03秒前へ
    #   ② 続けて話している所で「大きさの谷」にした字幕が、文字起こしの語の頭より 0.15秒以上遅い → 語の頭の近くの谷へ
    moved = {"無音の中から聞こえ始めへ": 0, "遅れていたのを語の頭へ": 0}
    for i, c in enumerate(shown):
        if c["id"] in ONSET_FIX:
            continue
        t = c["src"]
        lo = shown[i - 1]["src"] + 0.15 if i else 0.0
        hi = shown[i + 1]["src"] - 0.15 if i + 1 < len(shown) else t + 1.0
        nt = None
        soft = voice.db > voice.thr - 6          # 小さい声（聞き手・語の頭）も聞こえる音として見る
        if not soft[voice.idx(t + 0.03)]:
            k = voice.idx(t)
            j = k
            while j < len(soft) - 1 and not soft[j] and j - k < 80:
                j += 1
            if soft[j] and j > k:
                nt, why = j / 100 - 0.03, "無音の中から聞こえ始めへ"
        elif "大きさの谷" in c["how"] and c.get("asr") is not None and t - c["asr"] > 0.15:
            nt, why = voice.dip(c["asr"], before=0.06, after=0.06), "遅れていたのを語の頭へ"
        if nt is not None and lo < nt < hi and abs(nt - t) >= 0.03:
            c["src_before_v005"] = c["src"]
            c["src"] = round(nt, 3)
            c["how"] += f"（v005 {why}）"
            moved[why] += 1
    warns.append(f"v005 可聴音に合わせた：{moved}")
    for a, b in zip(shown, shown[1:]):
        if b["src"] <= a["src"]:
            errors.append(f"行{b['line']}：字幕 {b['id']} の開始 {b['src']} が前の字幕 {a['id']}（{a['src']}）より前")
    # ---- 表示の検査 ----
    for c in shown:
        lines = c["text"].split("\r")
        if len(lines) > 2:
            errors.append(f"行{c['line']}：3行以上「{c['text']}」")
        for ln in lines:
            if width(ln) > LINE_MAX:
                errors.append(f"行{c['line']}：1行が長い（{width(ln):.1f}字。17字まで。改行の位置を変えるか字幕を分ける＝08 の captions.layout.stop_long_line）「{ln}」")   # 2026-10-17：注意だけでは29字の行が画面からはみ出した
        if re.search(r"[、。]", c["text"]):
            errors.append(f"行{c['line']}：句読点「{c['text']}」")
        if re.search(r"(^|[\s\r])(えー|えっと|あのー|まあ|うーん)", c["text"]):
            warns.append(f"行{c['line']}：フィラーが残っている？「{c['text']}」")
    # 字幕の長さ（次の字幕までの素材の秒。カット前なので目安）
    for a, b in zip(shown, shown[1:]):
        if b["src"] - a["src"] < MIN_DUR:
            warns.append(f"行{a['line']}：短い（素材で {b['src'] - a['src']:.2f}秒）「{a['text']}」")
    # ---- 文字の突き合わせ：区切りの文字と字幕の文字 ----
    src_by_cap = defaultdict(str)
    for u in sorted(units):
        if u in full or owner.get(u) is None:
            continue
        src_by_cap[owner[u]] += norm(units[u]["text"])
    low = []
    for c in shown:
        if c["mode"] != "start":
            continue
        grp = [x for x in shown if x["u"] == c["u"] or x["id"] in ()]
    for c in shown:
        pass
    # 字幕ごとではなく、区切りの並びで全体を突き合わせる
    src_all = "".join(norm(units[u]["text"]) for u in sorted(units) if u not in full and u not in drops)
    dst_all = "".join(norm(c["text"]) for c in shown)
    sm = difflib.SequenceMatcher(None, src_all, dst_all, autojunk=False)
    dropped, added = [], []
    for op, a0, a1, b0, b1 in sm.get_opcodes():
        if op in ("delete", "replace") and a1 - a0 >= 3:
            dropped.append(src_all[max(0, a0 - 4):a0] + "【" + src_all[a0:a1] + "】" + src_all[a1:a1 + 4])
        if op in ("insert", "replace") and b1 - b0 >= 3:
            added.append(dst_all[max(0, b0 - 4):b0] + "【" + dst_all[b0:b1] + "】" + dst_all[b1:b1 + 4])
    # ---- 話者の検査（声の高さ・声色の k 近傍） ----
    F = {x["idx"]: x for x in json.load(open(os.path.join(A, "speaker", "voicefeat.json")))}
    cap_who = {c["id"]: c["who"] for c in caps}
    lab = []
    for u in sorted(units):
        cid = owner.get(u)
        if cid is None or u in full:
            continue
        x = F.get(u)
        if x and "mel" in x and x.get("f0_n", 0) >= 3:
            m = x["mel"]
            mu = sum(m) / len(m)
            lab.append((u, cap_who[cid], [v - mu for v in m] + [math.log(x["f0_med"]) * 3]))
    prior = Counter(w for _, w, _ in lab)

    def knn(i, k=15):
        v = lab[i][2]
        ds = sorted((math.dist(v, lab[j][2]), lab[j][1]) for j in range(len(lab)) if j != i)[:k]
        sc_ = defaultdict(float)
        for dd, s in ds:
            sc_[s] += 1 / (dd + 1e-3) / prior[s]
        tot = sum(sc_.values())
        best = max(sc_, key=sc_.get)
        return best, sc_[best] / tot

    ok = 0
    spk_warn = []
    for i, (u, w, _) in enumerate(lab):
        p, cf = knn(i)
        ok += p == w
        if p != w and cf >= 0.75:
            spk_warn.append({"u": u, "caption": owner[u], "script": w, "voice": p, "conf": round(cf, 2),
                             "f0": round(F[u]["f0_med"]), "text": units[u]["text"]})
    # Mac のマイク÷カメラの差（三上さんは Mac の前にいるので大きい。+5dB 以上＝三上さん、0dB 以下＝聞き手）
    _mr = os.path.join(A, "speaker", "micratio.json")   # AI動画編集：Mac のマイクの録音が無いので、無ければ空
    MR = {int(k): v for k, v in json.load(open(_mr)).items()} if os.path.exists(_mr) else {}
    mic_warn = []
    for u in sorted(units):
        cid = owner.get(u)
        if cid is None or u in full or u not in MR:
            continue
        w = cap_who[cid]
        if (w == "み" and MR[u] <= -0.5) or (w == "聞" and MR[u] >= 5.5):
            mic_warn.append({"u": u, "caption": cid, "script": w, "micratio": MR[u], "text": units[u]["text"]})
    res = {"captions": caps, "errors": errors, "mic_warn": mic_warn, "warns": warns, "dropped_text": dropped, "added_text": added,
           "match_ratio": round(sm.ratio(), 3), "speaker_check": {"agree": round(ok / max(1, len(lab)), 3), "labeled": dict(prior),
                                                                    "disagree": spk_warn},
           "owner": {str(u): owner.get(u) for u in sorted(units) if u not in full}}
    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"字幕 {len(shown)} 枚／カットで消える区切り {len(full)}／一致率 {sm.ratio():.3f}")
    print("開始の決め方", Counter(c["how"] for c in shown))
    print(f"エラー {len(errors)}")
    for e in errors[:60]:
        print("  E", e)
    print(f"注意 {len(warns)}")
    for w in warns[:60]:
        print("  W", w)
    print(f"話者：台本と声が一致 {ok}/{len(lab)}、食い違い（自信0.75以上）{len(spk_warn)}")
    for s in spk_warn[:80]:
        print("  S", s)
    print(f"話者：マイクの差と食い違い {len(mic_warn)}")
    for s in mic_warn[:80]:
        print("  M", s)


if __name__ == "__main__":
    main()
