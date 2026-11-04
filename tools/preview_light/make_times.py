#!/usr/bin/env python3
"""Premiere の画像のコマの時刻の一覧（times.json）・ブラウザ用のテロップの表（telops_data.js）・動いている最中の表（moves.json）を作る
  make_times.py <案件の版のフォルダ> <作業フォルダ>"""
import json,os,sys
FPS=30000/1001
def tc2n(s):return (int(s[:2])*3600+int(s[3:5])*60+int(s[6:8]))*30+int(s[9:11])
case,out=sys.argv[1:3]
ns=sorted({tc2n(f['timecode']) for f in json.load(open(os.path.join(case,'premiere_preview.json')))['frames']})
ts=[round((n+0.25)/FPS,5) for n in ns]   # コマの頭より少し後（四捨五入でひとつ前のコマにならないように）
json.dump(ts,open(os.path.join(out,'times.json'),'w'))
d=json.load(open(os.path.join(out,'telops.json'),encoding='utf-8'))
open(os.path.join(out,'telops_data.js'),'w',encoding='utf-8').write('const DATA='+json.dumps(d,ensure_ascii=False,separators=(',',':'))+';')
def keys(x):
    if not x:return []
    return [v['k'] for v in x.values() if isinstance(v,dict) and v.get('k')]
moves={}
for i,it in enumerate(d['items']):
    ks=[]
    for x in [it['motion'],it['group']]+it['effects']+[l['x'] for l in it['layers']]:
        ks+=keys(x)
    for n,t in zip(ns,ts):
        if not it['start']<=t<it['end']:continue
        lt=t-it['start'];mv=False
        for k in ks:
            for (a,va),(b,vb) in zip(k,k[1:]):
                if a<=lt<=b and va!=vb:mv=True
        for a,b,_ in it['fades']:
            if a<=t<=b:mv=True
        if mv:moves.setdefault(str(n),[]).append(i)
json.dump(moves,open(os.path.join(out,'moves.json'),'w'))
print(len(ts),'コマ','動いている最中',sum(len(v) for v in moves.values()))
