#!/usr/bin/env python3
"""試作のテロップを Premiere の画像と比べる。ずれ（上下左右・大きさ）と、合っているかの点を出す。読むだけ。
  measure.py <items.jsonl> <出力.json> --case <案件の版のフォルダ（premiere_preview.json と 確認/ がある所）> [--jobs 3] [--telops telops.json]
点（best）は、試作の文字の不透明な所と画像の差の平均（0〜255）。far は同じ文字を 40px ずらした所の点の中央値（その場所が偶然合っていないかを見る）"""
import argparse,base64,io,json,multiprocessing as mp,os
import numpy as np
from PIL import Image
FPS=30000/1001
SCALES=[0.96,0.97,0.98,0.985,0.99,0.995,1.0,1.005,1.01,1.015,1.02,1.03,1.04]
def tc2n(s):return (int(s[:2])*3600+int(s[3:5])*60+int(s[6:8]))*30+int(s[9:11])
def frame_files(case):
    files={}
    for f in json.load(open(os.path.join(case,'premiere_preview.json')))['frames']:
        files.setdefault(tc2n(f['timecode']),[]).append(f['file'])
    return files
def score(still,sp,alpha,x,y):
    h,w=alpha.shape
    if x<0 or y<0 or x+w>still.shape[1] or y+h>still.shape[0]:
        x0=max(0,x);y0=max(0,y);x1=min(still.shape[1],x+w);y1=min(still.shape[0],y+h)
        if x1-x0<8 or y1-y0<8:return 999.
        s=sp[y0-y:y1-y,x0-x:x1-x];a=alpha[y0-y:y1-y,x0-x:x1-x];t=still[y0:y1,x0:x1]
    else:
        s=sp;a=alpha;t=still[y:y+h,x:x+w]
    if a.sum()<5:return 999.
    return float((np.abs(s-t).mean(axis=2)*a).sum()/a.sum())
G={}
def init(case,moves):
    G['case']=case;G['moves']=moves
def one(args):
    n,fn,t,items=args
    still=np.asarray(Image.open(os.path.join(G['case'],'確認',fn)).convert('RGB'),dtype=np.float32)
    ds=still[::2,::2]
    out=[]
    for it in items:
        im=Image.open(io.BytesIO(base64.b64decode(it['png'].split(',')[1]))).convert('RGBA')
        x0,y0,x1,y1=it['bbox'];w,h=x1-x0+1,y1-y0+1
        arr=np.asarray(im,dtype=np.float32);rgb=arr[...,:3];al=(arr[...,3]>230).astype(np.float32)
        base=score(still,rgb,al,x0,y0)
        rs=rgb[::2,::2];aa=al[::2,::2]
        cbest=(1e9,0,0)
        for dy in range(-22,23,2):
            for dx in range(-22,23,2):
                sc=score(ds,rs,aa,(x0+dx)//2,(y0+dy)//2)
                if sc<cbest[0]:cbest=(sc,dx,dy)
        bx,by=cbest[1],cbest[2]
        best=(base,0,0,1.0);cx,cy=(x0+x1)/2,(y0+y1)/2
        for s in SCALES:
            if s==1.0:ri,ai=rgb,al
            else:
                nw,nh=max(2,int(round(w*s))),max(2,int(round(h*s)))
                i2=im.resize((nw,nh),Image.BILINEAR);ar2=np.asarray(i2,dtype=np.float32);ri=ar2[...,:3];ai=(ar2[...,3]>230).astype(np.float32)
            for dy in range(by-3,by+4):
                for dx in range(bx-3,bx+4):
                    sc=score(still,ri,ai,int(round(cx-ri.shape[1]/2+dx)),int(round(cy-ri.shape[0]/2+dy)))
                    if sc<best[0]:best=(sc,dx,dy,s)
        fars=[score(still,rgb,al,x0+a,y0+b) for a,b in ((40,0),(-40,0),(0,40),(0,-40),(40,40),(-40,-40))]
        fars=[f for f in fars if f<999]
        # 上の段の文字に隠れていないか
        cov=0.0
        for o in items:
            if o['track']>it['track']:
                b=o['bbox'];ix=max(0,min(x1,b[2])-max(x0,b[0]));iy=max(0,min(y1,b[3])-max(y0,b[1]));cov=max(cov,ix*iy/max(1,w*h))
        out.append(dict(t=t,n=n,file=fn,idx=it['idx'],track=it['track'],text=it['text'][:40],bbox=it['bbox'],opaque=round(float(al.mean()),3),moving=it['idx'] in G['moves'].get(str(n),[]),covered=round(cov,2),
                        score0=round(base,1),best=round(best[0],1),far=round(float(np.median(fars)),1) if fars else None,dx=best[1],dy=best[2],scale=best[3]))
    return out
def main():
    ap=argparse.ArgumentParser();ap.add_argument('items');ap.add_argument('out');ap.add_argument('--case',required=True);ap.add_argument('--jobs',type=int,default=3);ap.add_argument('--moves',default=None)
    o=ap.parse_args()
    files=frame_files(o.case)
    moves=json.load(open(o.moves)) if o.moves else {}
    jobs=[]
    for line in open(o.items):
        d=json.loads(line);n=int(d['t']*FPS)
        if n in files and d['items']:jobs.append((n,files[n][0],d['t'],d['items']))
    res=[]
    with mp.Pool(o.jobs,init,(o.case,moves)) as p:
        for i,r in enumerate(p.imap_unordered(one,jobs)):
            res+=r
            if (i+1)%50==0:print(i+1,'/',len(jobs),len(res),flush=True)
    res.sort(key=lambda r:(r['t'],r['track']))
    json.dump(res,open(o.out,'w',encoding='utf-8'),ensure_ascii=False)
    print('done',len(res))
if __name__=='__main__':main()
