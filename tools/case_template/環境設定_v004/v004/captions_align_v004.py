"""Air v001 の通常字幕の開始（素材の秒）を決め、台本（script_v004.txt）を上司のルール（30_文節と言葉・字幕と話者の品質規則.json）で検査する。
  - 区切りの頭から出す字幕：その区切りの最初の語の時刻を候補に、聞こえ始め（tools/audible_onset.py の best_onset）
  - 途中から出す字幕：その文字を含む語の時刻を候補に、同じく聞こえ始め
  - 話者：台本の「@」＝聞き手。声の高さ・声色（analysis/speaker/voicefeat.json）の k 近傍で食い違うものを知らせる
  出力 _work/captions_v004.json
  ~/Desktop/video_edit_rules/env/bin/python v004/captions_align_v004.py
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

OUT = os.path.join(HERE, "_work", "captions_v004.json")
LINE_MAX = 17
MIN_DUR = 0.4
# 波形を見て手で決めた聞こえ始め（字幕ID → 素材の秒）。自動の「大きさの谷」が声より前の無音に落ちた所（v001）
ONSET_FIX = {"1623": 4415.48, "1042+1": 2983.31}   # 1042+1「やり方」：「で」の後の谷（2983.24〜2983.29 が −68〜−75dB）の後、2983.30〜2983.33 で立ち上がる（自動は 2983.415）。1623 は下   # 73:35「それこそ」：前の「すごいんです」の語尾（〜4415.44）の後の谷（4415.45〜4415.49 が −63〜−70dB）。自動では 4415.30（語尾の中）になり、並べ替えの Z の頭で声が途中から始まった


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
                t, how = ONSET_FIX[c["id"]], "波形で決めた（v001）"
            last_k[u] = 0
        else:
            k0 = last_k.get(u, -1) + 1
            t, how, k = al.phrase_onset(u, c["anchor"] or c["text"], k0)
            if t is None:
                errors.append(f"行{c['line']}：「{c['text']}」の始まりが区切り{u}「{units[u]['text']}」の中に見つからない")
                continue
            last_k[u] = k
            d["asr"] = al.char_time(u, k)
        d["src"] = round(t, 3)
        d["how"] = how
        caps.append(d)
    shown = [c for c in caps if c["mode"] != "drop" and "src" in c]
    # ---- v001 小川さん「テロップは可聴音（声が聞こえ始める所）に合わせて」----
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
            c["src_before_v004"] = c["src"]
            c["src"] = round(nt, 3)
            c["how"] += f"（v001 {why}）"
            moved[why] += 1
    warns.append(f"v002 可聴音に合わせた：{moved}")
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
                warns.append(f"行{c['line']}：1行が長い（{width(ln):.1f}字）「{ln}」")
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
    MR = {int(k): v for k, v in json.load(open(os.path.join(A, "speaker", "micratio.json"))).items()}
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
