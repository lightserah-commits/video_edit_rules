#!/usr/bin/env python3
"""Premiere の画像と試作（軽い映像＋テロップ）を並べた一覧画像を作る。左 Premiere・中 試作・右 差
  sheet.py <案件の版のフォルダ> <作業フォルダ> <出力.jpg> <ファイル名の頭または秒,...>"""
import base64,io,json,os,subprocess,sys
import numpy as np
from PIL import Image,ImageDraw,ImageFont
case,work,out,keys=sys.argv[1:5]
FPS=30000/1001
tc=lambda s:(int(s[:2])*3600+int(s[3:5])*60+int(s[6:8]))*30+int(s[9:11])
frames=json.load(open(os.path.join(case,'premiere_preview.json')))['frames']
items={}
for l in open(os.path.join(work,'items.jsonl')):
    d=json.loads(l);items[int(d['t']*FPS)]=d['items']
sel=[]
for k in keys.split(','):
    f=next((x for x in frames if x['file'].startswith(k) or k in x['file']),None)
    if f:sel.append(f)
W,H=640,360
font=ImageFont.truetype('/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc',18)
sheet=Image.new('RGB',(W*3,(H+26)*len(sel)),'white');dr=ImageDraw.Draw(sheet)
for i,f in enumerate(sel):
    n=tc(f['timecode'])
    pr=Image.open(os.path.join(case,'確認',f['file'])).convert('RGB')
    raw=subprocess.run(['ffmpeg','-v','error','-ss',f'{n/FPS-0.005:.4f}','-i',os.path.join(work,'base.mp4'),'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-'],capture_output=True).stdout
    b=Image.frombytes('RGB',(1280,720),raw).resize((1920,1080),Image.BILINEAR).convert('RGBA')
    for it in items.get(n,[]):
        sp=Image.open(io.BytesIO(base64.b64decode(it['png'].split(',')[1]))).convert('RGBA');b.alpha_composite(sp,(max(0,it['bbox'][0]),max(0,it['bbox'][1])))
    b=b.convert('RGB')
    d=np.abs(np.asarray(pr,dtype=np.int16)-np.asarray(b,dtype=np.int16)).max(axis=2).clip(0,255).astype(np.uint8)
    y=i*(H+26)
    dr.text((4,y+2),f"{f['file'][:40]}  {f['sec']}秒  左 Premiere / 中 試作 / 右 差",fill='black',font=font)
    for j,im in enumerate((pr,b,Image.fromarray(d).convert('RGB'))):
        sheet.paste(im.resize((W,H),Image.BILINEAR),(j*W,y+26))
sheet.save(out,quality=78);print(out,sheet.size)
