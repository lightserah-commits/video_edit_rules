import json, re, statistics as st, unicodedata as ud, collections as C, sys
def w(s):  # 全角1・半角0.5
    return sum(0.5 if ud.east_asian_width(ch) in "NaH" else 1 for ch in s)
def pct(v,p): v=sorted(v); return v[min(len(v)-1,int(len(v)*p))]
def load(p):
    rows=[]
    for s in json.load(open(p))["subs"]:
        if not any(x in ("みかみテロップ","質問者テロップ") for x in s["style"]): continue
        t="⏎".join(s["texts"]).strip("⏎ ")
        t=re.sub(r"⏎+","⏎",t)
        if re.search(r" {4,}",t): continue  # 見た目の位置合わせ（挨拶の名前の穴など）
        lines=[l.strip() for l in t.split("⏎") if l.strip()]
        if not lines: continue
        rows.append(dict(lines=lines, dur=s["end"]-s["start"], start=s["start"], spk="聞き手" if "質問者テロップ" in s["style"] else "みかみ"))
    return rows
for name,p in [("1本目",sys.argv[1]),("2本目",sys.argv[2])]:
    R=load(p); print("=====",name,len(R),"枚")
    nl=C.Counter(len(r["lines"]) for r in R); print("行数",dict(nl))
    L=[w(l) for r in R for l in r["lines"]]
    print("1行の字数(全角換算) 中央",st.median(L),"p90",pct(L,.9),"p95",pct(L,.95),"p99",pct(L,.99),"max",max(L))
    for th in (17,20,22,24,28): print(f"  {th}字を超える行 {sum(1 for x in L if x>th)} ({sum(1 for x in L if x>th)/len(L):.1%})")
    one=[w(r["lines"][0]) for r in R if len(r["lines"])==1]; two=[w("".join(r["lines"])) for r in R if len(r["lines"])==2]
    print("1行の字幕 合計字数 中央",st.median(one),"p90",pct(one,.9),"max",max(one))
    print("2行の字幕 合計字数 中央",st.median(two),"p10",pct(two,.1),"min",min(two))
    for lo,hi in [(0,10),(10,14),(14,17),(17,20),(20,24),(24,30),(30,99)]:
        g=[r for r in R if lo<w("".join(r["lines"]))<=hi]
        if g: print(f"  合計{lo}〜{hi}字: {len(g)}枚 2行以上 {sum(1 for r in g if len(r['lines'])>=2)/len(g):.0%}")
    t2=[r for r in R if len(r["lines"])==2]
    print("2行の上下 上が短い",sum(1 for r in t2 if w(r['lines'][0])<w(r['lines'][1])),"上が長い",sum(1 for r in t2 if w(r['lines'][0])>w(r['lines'][1])),"同じ",sum(1 for r in t2 if w(r['lines'][0])==w(r['lines'][1])))
    print("上の行の終わり",C.Counter(r["lines"][0][-1] for r in t2).most_common(15))
    print("上の行の終わり2字",C.Counter(r["lines"][0][-2:] for r in t2).most_common(15))
    print("「の」で終わる上の行",[ "/".join(r["lines"]) for r in t2 if r["lines"][0].endswith("の")][:8])
    print("下の行の始まり",C.Counter(r["lines"][1][:2] for r in t2).most_common(10))
    D=[r["dur"] for r in R]; cps=[w("".join(r["lines"]))/r["dur"] for r in R if r["dur"]>0.2]
    print("表示秒 中央",round(st.median(D),2),"p10",round(pct(D,.1),2),"min",round(min(D),2),"| 字/秒 中央",round(st.median(cps),1),"p90",round(pct(cps,.9),1))
    print("字幕の終わりの文字",C.Counter(r["lines"][-1][-1] for r in R).most_common(12))
    prog=sum(1 for a,b in zip(R,R[1:]) if len(b["lines"])>len(a["lines"]) and "".join(b["lines"]).startswith("".join(a["lines"])))
    print("段階表示（前の字幕に行を足す）",prog)
    print("話者",C.Counter(r["spk"] for r in R))
