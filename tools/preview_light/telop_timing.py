#!/usr/bin/env python3
"""テロップの出る時刻・消える時刻と動きを、Premiere の書き出しの動画（1コマずつ）と比べる。読むだけ。
  telop_timing.py times <作業フォルダ>          … 測る項目と時刻の一覧を作る（timing_plan.json・timing_times.json）
  node shot_items.mjs still.html timing_times.json timing_items.jsonl
  telop_timing.py run <作業フォルダ> <premiere.mp4> … 比べる（timing.json）"""
import base64,io,json,os,random,subprocess,sys,collections,statistics as st
import numpy as np
from PIL import Image
FPS=30000/1001
fr=lambda t:int(round(t*FPS))
W,H=1920,1080
def has_keys(it):
    for x in [it['motion'],it['group']]+it['effects']+[l['x'] for l in it['layers']]:
        if x:
            for v in x.values():
                if isinstance(v,dict) and v.get('k'):return True
    return False
def plan(work):
    d=json.load(open(os.path.join(work,'telops.json'),encoding='utf-8'));tl=json.load(open(os.path.join(work,'timeline.json'),encoding='utf-8'))
    ov=[(r['start'],r['end']) for r in tl['rows'] if r['track'] in('V14','V15')]
    random.seed(1101);static=collections.defaultdict(list);anim=[]
    for i,it in enumerate(d['items']):
        if any(a<it['end'] and b>it['start'] for a,b in ov):continue
        if not any(l.get('style') for l in it['layers']):continue
        if it['end']-it['start']<0.3:continue
        if not has_keys(it) and not it['fades']:static[it['track']].append(i)
        elif has_keys(it):anim.append(i)
    pick=[]
    for k,v in static.items():
        random.shuffle(v);pick+=v[:200 if k==6 else 40]
    random.shuffle(anim);anim=anim[:40]
    times=[];plan_s=[];plan_a=[]
    for i in pick:
        it=d['items'][i];S,E=fr(it['start']),fr(it['end']);t=(((S+E)//2)+0.25)/FPS
        plan_s.append(dict(idx=i,S=S,E=E,t=round(t,5),track=it['track']));times.append(round(t,5))
    for i in anim:
        it=d['items'][i];S,E=fr(it['start']),fr(it['end'])
        for k in (0,1,2,3,5,8,12,15):
            if S+k<E:
                t=round((S+k+0.25)/FPS,5);plan_a.append(dict(idx=i,n=S+k,k=k,t=t,track=it['track']));times.append(t)
    times=sorted(set(times))
    json.dump(dict(static=plan_s,anim=plan_a),open(os.path.join(work,'timing_plan.json'),'w'));json.dump(times,open(os.path.join(work,'timing_times.json'),'w'))
    print('出る・消えるを測る',len(plan_s),collections.Counter(p['track'] for p in plan_s),'動きを測る',len(anim),'時刻',len(times))
def grab(mp4,n0,count):
    p=subprocess.run(['ffmpeg','-v','error','-ss',f'{n0/FPS-0.005:.5f}','-i',mp4,'-frames:v',str(count),'-f','rawvideo','-pix_fmt','rgb24','-'],capture_output=True)
    a=np.frombuffer(p.stdout,dtype=np.uint8)
    return a.reshape(-1,H,W,3).astype(np.float32)
def sc(fr_,sp,al,x,y):
    h,w=al.shape;x0=max(0,x);y0=max(0,y);x1=min(W,x+w);y1=min(H,y+h)
    if x1-x0<8 or y1-y0<8:return 999.
    a=al[y0-y:y1-y,x0-x:x1-x];s=sp[y0-y:y1-y,x0-x:x1-x];t=fr_[y0:y1,x0:x1]
    if a.sum()<5:return 999.
    return float((np.abs(s-t).mean(axis=2)*a).sum()/a.sum())
def sc_best(fr_,sp,al,x,y,r=3):
    return min(sc(fr_,sp,al,x+dx,y+dy) for dy in range(-r,r+1) for dx in range(-r,r+1))
def run(work,mp4):
    P=json.load(open(os.path.join(work,'timing_plan.json')))
    S={}
    for line in open(os.path.join(work,'timing_items.jsonl')):
        d=json.loads(line)
        for it in d['items']:S[(d['t'],it['idx'])]=it
    def spr(it):
        arr=np.asarray(Image.open(io.BytesIO(base64.b64decode(it['png'].split(',')[1]))).convert('RGBA'),dtype=np.float32)
        return arr[...,:3],(arr[...,3]>230).astype(np.float32)
    res=[]
    for j,p in enumerate(P['static']):
        it=S.get((p['t'],p['idx']))
        if not it:continue
        rgb,al=spr(it);x,y=it['bbox'][0],it['bbox'][1]
        fa=grab(mp4,p['S']-3,6);fb=grab(mp4,p['E']-3,6)
        if len(fa)<6 or len(fb)<6:continue
        sa=[sc_best(f,rgb,al,x,y) for f in fa];sb=[sc_best(f,rgb,al,x,y) for f in fb]
        res.append(dict(idx=p['idx'],track=p['track'],S=p['S'],E=p['E'],text=it['text'][:24],sa=[round(v,1) for v in sa],sb=[round(v,1) for v in sb]))
        if (j+1)%50==0:print(j+1,flush=True)
    an=[]
    by=collections.defaultdict(list)
    for p in P['anim']:by[p['idx']].append(p)
    for idx,ps in by.items():
        S0=min(p['n'] for p in ps);frames=grab(mp4,S0,16)
        for p in ps:
            it=S.get((p['t'],idx));k=p['n']-S0
            if not it or k>=len(frames):continue
            rgb,al=spr(it);x,y=it['bbox'][0],it['bbox'][1]
            an.append(dict(idx=idx,track=p['track'],k=p['k'],text=it['text'][:24],score=round(sc_best(frames[k],rgb,al,x,y,6),1),opaque=round(float(al.mean()),3)))
    json.dump(dict(static=res,anim=an),open(os.path.join(work,'timing.json'),'w'),ensure_ascii=False)
    print('done',len(res),len(an))
if sys.argv[1]=='times':plan(sys.argv[2])
else:run(sys.argv[2],sys.argv[3])
