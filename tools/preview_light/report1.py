#!/usr/bin/env python3
"""measure.py の結果をトラックごとの数にする。
  report1.py <measure.json> <telops.json> [合う点の上限=45]"""
import json,sys,collections,statistics as st
R=json.load(open(sys.argv[1]));T=json.load(open(sys.argv[2]));TH=float(sys.argv[3]) if len(sys.argv)>3 else 45
NAME={5:'※注釈',6:'字幕',7:'強調',8:'右上の左札',9:'右上の問い・章の札',10:'章の帯・誘導札',12:'問い・カード1',13:'カード2',14:'カード3'}
over=T.get('over',[])
for r in R:r['under']=any(a<=r['t']<b for a,b in over)
vis=[r for r in R if not r['under']]
print('比べた文字',len(R),'うち図解の板の下',len(R)-len(vis),'・残り',len(vis))
good=lambda r:r['best']<TH and (r['far'] is None or r['best']<r['far']*0.75)
def line(g,name):
    if not g:return
    m=[r for r in g if good(r)]
    s=f"{name}: {len(g)}個 合う {len(m)}（{len(m)/len(g)*100:.0f}%）"
    if m:
        adx=[abs(r['dx']) for r in m];ady=[abs(r['dy']) for r in m]
        p2=sum(abs(r['dx'])<=2 and abs(r['dy'])<=2 for r in m)/len(m)*100
        sc=[abs(r['scale']-1)*100 for r in m]
        s+=f" 左右中央{st.median(r['dx'] for r in m):+.1f}（絶対{st.median(adx):.0f}）上下中央{st.median(r['dy'] for r in m):+.1f}（絶対{st.median(ady):.0f}）px ±2px以内{p2:.0f}% 大きさ中央{st.median(r['scale'] for r in m):.3f}（±1%以内{sum(x<=1.01 for x in sc)/len(m)*100:.0f}%）点の中央{st.median(r['best'] for r in m):.0f}"
    print(s)
static=[r for r in vis if not r['moving']]
line(vis,'全部（動きの途中も含む）');line(static,'止まっている物だけ');line([r for r in vis if r['moving']],'動きの途中')
for t in sorted({r['track'] for r in vis}):
    line([r for r in static if r['track']==t],f"V{t} {NAME.get(t,'')}")
print('--- 止まっていて合わない物（上の文字に隠れていないもの）')
bad=[r for r in static if not good(r) and r['covered']<0.3]
print(len(bad),'隠れている',sum(1 for r in static if not good(r) and r['covered']>=0.3))
c=collections.Counter(r['track'] for r in bad);print(sorted(c.items()))
for r in sorted(bad,key=lambda r:-r['best'])[:40]:print(r['t'],'V%d'%r['track'],r['best'],r['far'],r['dx'],r['dy'],r['scale'],r['text'][:24].replace('\r',' '),r['file'][:28])
