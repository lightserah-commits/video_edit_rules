#!/usr/bin/env python3
"""作った音と Premiere の書き出しの音を数字だけで比べる（再生しない）。8kHz のモノラルに直して1秒ごとに比べる。
  cmp_audio.py <試作.m4a|mp4> <premiere.mp4> <出力.json>"""
import json,re,subprocess,sys
import numpy as np
SR=8000
a,b,out=sys.argv[1:4]
def dec(p):
    r=subprocess.run(['ffmpeg','-v','error','-i',p,'-vn','-ac','1','-ar',str(SR),'-f','f32le','-'],capture_output=True)
    return np.frombuffer(r.stdout,dtype=np.float32)
def ebu(p):
    r=subprocess.run(['ffmpeg','-hide_banner','-nostats','-i',p,'-vn','-af','ebur128=peak=true:framelog=quiet','-f','null','-'],capture_output=True,text=True).stderr
    s=r[r.rfind('Summary:'):]
    g=lambda k:float(re.search(k+r':\s+(-?[\d.]+)',s).group(1))
    return dict(I=g('I'),LRA=g('LRA'),peak=g('Peak'))
A,B=dec(a),dec(b)
n=min(len(A),len(B));print('長さ',len(A)/SR,len(B)/SR,flush=True)
# ずれ：いくつかの場所で相互相関
offs=[]
for s in range(60,int(n/SR)-20,300):
    x=A[s*SR:(s+10)*SR];y=B[s*SR-SR//2:(s+10)*SR+SR//2]
    if x.std()<1e-4:continue
    F=np.fft.rfft;L=len(y)+len(x)
    c=np.fft.irfft(F(y,L)*np.conj(F(x,L)),L)
    offs.append(int(np.argmax(c[:len(y)]))-SR//2)
secs=n//SR
ra=np.array([np.sqrt((A[i*SR:(i+1)*SR]**2).mean()) for i in range(secs)]);rb=np.array([np.sqrt((B[i*SR:(i+1)*SR]**2).mean()) for i in range(secs)])
db=lambda v:20*np.log10(np.maximum(v,1e-5))
da=db(ra)-db(rb)
loud=rb>10**(-50/20)
res=np.array([np.sqrt(((A[i*SR:(i+1)*SR]-B[i*SR:(i+1)*SR])**2).mean()) for i in range(secs)])
resid=db(res)-db(rb)
r=dict(ebu_a=ebu(a),ebu_b=ebu(b),len_a=len(A)/SR,len_b=len(B)/SR,offset_samples_8k=offs,loud_secs=int(loud.sum()),
       diff_db_median=float(np.median(da[loud])),diff_db_abs_p95=float(np.percentile(np.abs(da[loud]),95)),diff_db_abs_max=float(np.abs(da[loud]).max()),
       within_1db=float((np.abs(da[loud])<=1).mean()),resid_db_median=float(np.median(resid[loud])),resid_db_p95=float(np.percentile(resid[loud],95)),
       worst=[dict(sec=int(i),diff=round(float(da[i]),1),a=round(float(db(ra)[i]),1),b=round(float(db(rb)[i]),1)) for i in np.argsort(-np.abs(da)*loud)[:15]])
json.dump(r,open(out,'w'),ensure_ascii=False,indent=1);print(json.dumps(r,ensure_ascii=False)[:1500])
