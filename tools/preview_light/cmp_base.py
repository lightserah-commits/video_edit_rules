#!/usr/bin/env python3
"""テロップ無しの軽い映像（base.mp4）を Premiere の画像と比べる。テロップの枠の外だけを見る。読むだけ。
  cmp_base.py <案件の版のフォルダ> <作業フォルダ>   （作業フォルダに base.mp4・items.jsonl がある。結果 base_cmp.json）"""
import json,os,subprocess,sys,collections,statistics as st
import numpy as np
from PIL import Image
case,work=sys.argv[1:3]
frames=json.load(open(os.path.join(case,'premiere_preview.json')))['frames']
FPS=30000/1001
tc=lambda s:(int(s[:2])*3600+int(s[3:5])*60+int(s[6:8]))*30+int(s[9:11])
seen={}
for f in frames: seen.setdefault(tc(f['timecode']),f)
ns=sorted(seen)
W,H=640,360;sz=W*H*3
# 画像のコマとその前後2コマを取っておく（小さいと速い。コマのずれを見る）
want=collections.defaultdict(list)
for i,n in enumerate(ns):
    for k in range(-2,3): want[n+k].append((i,k))
keep={}
p=subprocess.Popen(['ffmpeg','-v','error','-i',os.path.join(work,'base.mp4'),'-vf',f'scale={W}:{H}:flags=fast_bilinear','-f','rawvideo','-pix_fmt','rgb24','-'],stdout=subprocess.PIPE,bufsize=sz*4)
n=0
while True:
    buf=p.stdout.read(sz)
    if len(buf)<sz:break
    if n in want:
        a=np.frombuffer(buf,dtype=np.uint8).reshape(H,W,3)
        for i,k in want[n]:
            keep[(i,k)]=a[::2,::2].copy() if k else a.copy()
    n+=1
print('コマ',n,flush=True)
items={}
for line in open(os.path.join(work,'items.jsonl')):
    d=json.loads(line);items[int(d['t']*FPS)]=[i['bbox'] for i in d['items']]
res=[]
for i,fnum in enumerate(ns):
    f=seen[fnum]
    a=np.asarray(Image.open(os.path.join(case,'確認',f['file'])).convert('RGB').resize((W,H),Image.BILINEAR),dtype=np.float32)
    mask=np.ones((H,W),bool)
    for bb in items.get(fnum,[]):
        mask[max(0,bb[1]//3-6):bb[3]//3+6,max(0,bb[0]//3-6):bb[2]//3+6]=False
    if (i,0) not in keep: continue
    b=keep[(i,0)].astype(np.float32)
    diff=np.abs(a-b).mean(axis=2)
    mad=float(diff[mask].mean()) if mask.sum()>=5000 else None
    big=float((diff[mask]>40).mean()) if mask.sum()>=5000 else None
    # 前後のコマのどれが一番近いか
    sc={}
    for k in range(-2,3):
        if (i,k) in keep:
            c=keep[(i,k)].astype(np.float32) if k else b[::2,::2]
            sc[k]=float((np.abs(a[::2,::2]-c).mean(axis=2)*mask[::2,::2]).sum()/max(1,mask[::2,::2].sum()))
    res.append(dict(file=f['file'],sec=f['sec'],n=fnum,mad=None if mad is None else round(mad,2),big=None if big is None else round(big,4),free=int(mask.sum()),best_k=min(sc,key=sc.get),sc={k:round(v,2) for k,v in sc.items()}))
json.dump(res,open(os.path.join(work,'base_cmp.json'),'w'),ensure_ascii=False)
print('done',len(res))
