"""Targeted DEX code listing; literal string values are redacted."""
import struct,json
from pathlib import Path
from trace_sqlcipher_dex import uleb
b=Path('data/extracted/lr_20261116T212608096_7b99bdd0/apk_contents/base/classes6.dex').read_bytes();u32=lambda p:struct.unpack_from('<I',b,p)[0]
ns,so,nt,to,np,po,nf,fo,nm,mo,nc,co=struct.unpack_from('<12I',b,56)
ss=[]
for i in range(ns):
 _,p=uleb(b,u32(so+4*i));ss.append(b[p:b.index(0,p)].decode('utf-8','replace'))
ts=[ss[u32(to+i*4)] for i in range(nt)]
ms=[]
for i in range(nm):
 c,pr,n=struct.unpack_from('<HHI',b,mo+8*i);_,r,params=struct.unpack_from('<III',b,po+pr*12)
 args=[]
 if params:args=[ts[struct.unpack_from('<H',b,params+4+j*2)[0]] for j in range(u32(params))]
 ms.append(ts[c]+'->'+ss[n]+'('+','.join(args)+')'+ts[r])
fs=[]
for i in range(nf):
 c,t,n=struct.unpack_from('<HHI',b,fo+8*i);fs.append(ts[c]+'->'+ss[n]+':'+ts[t])
lines=[]
for ci in range(nc):
 cl,fl,su,it,src,an,cd,sv=struct.unpack_from('<8I',b,co+ci*32)
 if not cd or not any(x in ts[cl] for x in ['/db/DBManager;','/db/DBAsyncTask;','/db/DBHelper;']):continue
 lines.append('CLASS '+ts[cl]);p=cd;cc=[]
 for _ in range(4):v,p=uleb(b,p);cc.append(v)
 for cnt in cc[:2]:
  fid=0
  for _ in range(cnt):d,p=uleb(b,p);fid+=d;acc,p=uleb(b,p);lines.append('FIELD '+fs[fid])
 for cnt in cc[2:]:
  mid=0
  for _ in range(cnt):
   d,p=uleb(b,p);mid+=d;acc,p=uleb(b,p);code,p=uleb(b,p);lines.append('METHOD '+ms[mid]+' access='+hex(acc)+' code='+hex(code))
   if not code:continue
   regs,ins,outs,tries=struct.unpack_from('<4H',b,code);n=u32(code+12);w=struct.unpack_from('<'+'H'*n,b,code+16);lines.append('REGISTERS '+str(regs)+' INPUT_REGISTERS '+str(ins));i=0
   while i<n:
    op=w[i]&255;v=w[i];size=1;desc=''
    if op in (0x02,0x05,0x08,0x13,0x15,0x16,0x19,0x1a,0x1c,0x1f,0x20,0x22,0x23,0x29) or 0x2d<=op<=0x3d or 0x44<=op<=0x6d or 0x90<=op<=0xaf or 0xd0<=op<=0xe2:size=2
    if op in (0x03,0x06,0x09,0x14,0x17,0x1b,0x24,0x25,0x26,0x2a,0x2b,0x2c) or 0x6e<=op<=0x78:size=3
    if op==0x18:size=5
    if op==0x00 and v>>8:
     kind=v>>8
     if kind==1:size=4+w[i+1]*2
     elif kind==2:size=2+w[i+1]*4
     elif kind==3:size=4+(w[i+1]*(w[i+2]+(w[i+3]<<16))+1)//2
    if op in (0x1a,0x1b):desc='const-string <redacted>'
    if 0x52<=op<=0x6d:desc=fs[w[i+1]]
    if 0x6e<=op<=0x78:desc=ms[w[i+1]]
    if op in (0x1c,0x1f,0x20,0x22,0x23):desc=ts[w[i+1]]
    # Do not show raw indexes/words for string literal operands.
    raw=' '.join(f'{x:04x}' for x in w[i:i+size]) if op not in (0x1a,0x1b) else f'{v:04x} [redacted]'
    lines.append(f'{i:04x} op={op:02x} {raw} {desc}');i+=size
out='\n'.join(lines);Path('reports/ghidra/sqlcipher-java-dbmanager.txt').write_text(out,encoding='utf8')