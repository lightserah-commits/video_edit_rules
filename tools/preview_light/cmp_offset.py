#!/usr/bin/env python3
"""Premiere の書き出しの各コマが、軽い映像のどのコマに一番近いか（前後2コマ）を全編で数える。音は扱わない。読むだけ。
  cmp_offset.py <premiere.mp4> <base.mp4> <出力.json>"""
import collections,json,subprocess,sys
import numpy as np
a,b,out=sys.argv[1:4]
W,H=320,180;sz=W*H
def op(p):return subprocess.Popen(['ffmpeg','-v','error','-i',p,'-vf',f'scale={W}:{H}:flags=fast_bilinear','-f','rawvideo','-pix_fmt','gray','-'],stdout=subprocess.PIPE,bufsize=sz*16)
pa,pb=op(a),op(b)
Y0,Y1=int(H*.12),int(H*.62)
ba=collections.deque(maxlen=5);bb=collections.deque(maxlen=5);best=[]
fr=lambda x:np.frombuffer(x,dtype=np.uint8).reshape(H,W)[Y0:Y1].astype(np.int16)
n=0
while True:
    x=pa.stdout.read(sz);y=pb.stdout.read(sz)
    if len(x)<sz or len(y)<sz:break
    ba.append(fr(x));bb.append(fr(y));n+=1
    if len(bb)==5:
        # 真ん中の base のコマ（n-3）に対して Premiere の前後を比べる
        c=ba[2]
        ds=[float(np.abs(c-z).mean()) for z in bb]
        best.append((n-3,ds))
pa.kill();pb.kill()
D=np.array([d for _,d in best],dtype=np.float32)
mn=D.argmin(axis=1)-2
spread=D.max(axis=1)-D.min(axis=1)
clear=spread>2.5
json.dump(dict(frames=len(D),all=collections.Counter(mn.tolist()),clear=int(clear.sum()),clear_hist=collections.Counter(mn[clear].tolist()),by_min=[(int(k),int((mn[(np.arange(len(mn))//1800)==k]==-1).sum()),int((mn[(np.arange(len(mn))//1800)==k]==0).sum()),int((mn[(np.arange(len(mn))//1800)==k]==1).sum())) for k in range(len(mn)//1800+1)]),open(out,'w'))
print('全部',sorted(collections.Counter(mn.tolist()).items()),'はっきり',int(clear.sum()),sorted(collections.Counter(mn[clear].tolist()).items()))
