"""区切りごとの話者の当て推量（セキュリティについて 2026-10-16）。中身で話者がはっきりしている区切り（SEED）を手本に、
声の高さ・声色（analysis/speaker/voicefeat.json。tools/voice_features.swift）の近さ（k近傍）で残りを判別する。tools/speaker_id.py の vec と同じ特徴。
  出力 analysis/speaker/guess.json（{u: [話者, 自信]}）。台本の話者の目安（決めるのは台本係・中身）
  python3 scripts/speaker_guess.py
"""
import json
import math
import os
import re
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
A = os.path.join(HERE, "..", "analysis")
U = json.load(open(os.path.join(A, "units.json")))
F = {x["idx"]: x for x in json.load(open(os.path.join(A, "speaker", "voicefeat.json")))}
MI = re.compile(r"俺|やん$|じゃん|やねん|知らん|言わんとく|わけよ|のよ$|なのよ|だよね$|ソウタくん|ソータ君|ソウタ")
SO = re.compile(r"三上さん|みかみさん|僕|っすね|なんすね|ですか[?？]?$|ますか|じゃないですか$")


def vec(x):
    m = x["mel"]
    mu = sum(m) / len(m)
    return [a - mu for a in m] + [math.log(x["f0_med"]) * 3 if x.get("f0_med") else 0]


seed = {}
for u in U:
    t = u["text"]
    a, b = bool(MI.search(t)), bool(SO.search(t))
    if a != b and F.get(u["u"], {}).get("n", 0) >= 20 and F[u["u"]].get("f0_med"):
        seed[u["u"]] = "み" if a else "聞"
V = {k: vec(F[k]) for k in F if F[k].get("f0_med") and F[k].get("n", 0) >= 5}
cnt = Counter(seed.values())


def knn(k0, K=9):
    d = sorted((math.dist(V[k0], V[k]), seed[k]) for k in seed if k in V and k != k0)[:K]
    sc = Counter()
    for dist, s in d:
        sc[s] += 1 / cnt[s]
    tot = sum(sc.values())
    best = sc.most_common(1)[0]
    return best[0], best[1] / tot


ok = sum(knn(k)[0] == seed[k] for k in seed if k in V)
out = {}
for u in U:
    if u["u"] in V:
        out[u["u"]] = list(knn(u["u"]))
        out[u["u"]][1] = round(out[u["u"]][1], 2)
json.dump(out, open(os.path.join(A, "speaker", "guess.json"), "w"), ensure_ascii=False)
print(f"手本 {len(seed)}（{dict(cnt)}）・手本どうしの正解 {ok}/{sum(1 for k in seed if k in V)}・判別 {len(out)}/{len(U)}")
