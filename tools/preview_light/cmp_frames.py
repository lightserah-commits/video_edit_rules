#!/usr/bin/env python3
"""全編の1コマずつを、Premiere の書き出し（r3）と軽い映像（base）で比べる。結果は frames_cmp.npz。音は扱わない。読むだけ。
  cmp_frames.py <premiere.mp4> <base.mp4> <出力.npz>"""
import subprocess,sys,time
import numpy as np
a,b,out=sys.argv[1:4]
W,H=160,90;sz=W*H
def op(p):return subprocess.Popen(['ffmpeg','-v','error','-i',p,'-vf',f'scale={W}:{H}:flags=fast_bilinear','-f','rawvideo','-pix_fmt','gray','-'],stdout=subprocess.PIPE,bufsize=sz*16)
pa,pb=op(a),op(b)
mads,mfree,da,db=[],[],[],[];pfa=pfb=None;t0=time.time();n=0
# 字幕・強調が出やすい下の方と上の端を除いた真ん中
Y0,Y1=int(H*.12),int(H*.62)
while True:
    x=pa.stdout.read(sz);y=pb.stdout.read(sz)
    if len(x)<sz or len(y)<sz:break
    fa=np.frombuffer(x,dtype=np.uint8).reshape(H,W).astype(np.int16);fb=np.frombuffer(y,dtype=np.uint8).reshape(H,W).astype(np.int16)
    d=np.abs(fa-fb);mads.append(d.mean());mfree.append(d[Y0:Y1].mean())
    da.append(np.abs(fa-pfa).mean() if pfa is not None else 0);db.append(np.abs(fb-pfb).mean() if pfb is not None else 0)
    pfa,pfb=fa,fb;n+=1
    if n%5000==0:print(n,f'{time.time()-t0:.0f}秒',flush=True)
pa.kill();pb.kill()
np.savez(out,mad=np.array(mads,dtype=np.float32),free=np.array(mfree,dtype=np.float32),da=np.array(da,dtype=np.float32),db=np.array(db,dtype=np.float32))
print('done',n,f'{time.time()-t0:.0f}秒')
