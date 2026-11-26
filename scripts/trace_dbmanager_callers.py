"""List direct DEX method references to SQLCipher without exposing string values."""
from pathlib import Path
import struct,json

def uleb(b,p):
 n=s=0
 while True:
  v=b[p];p+=1;n|=(v&127)<<s
  if v<128:return n,p
  s+=7

def inspect(path):
 b=path.read_bytes(); u32=lambda p:struct.unpack_from('<I',b,p)[0]
 ns,so,nt,to,np,po,nf,fo,nm,mo,nc,co=struct.unpack_from('<12I',b,56)
 strings=[]
 for i in range(ns):
  _,p=uleb(b,u32(so+i*4)); e=b.index(0,p); strings.append(b[p:e].decode('utf-8','replace'))
 types=[strings[u32(to+i*4)] for i in range(nt)]
 methods=[]
 for i in range(nm):
  c,pr,n=struct.unpack_from('<HHI',b,mo+i*8); _,r,params=struct.unpack_from('<III',b,po+pr*12)
  args=[]
  if params:
   for j in range(u32(params)):args.append(types[struct.unpack_from('<H',b,params+4+j*2)[0]])
  methods.append((types[c],strings[n],args,types[r]))
 targets={i for i,m in enumerate(methods) if '/linecocos/cocos2dx/db/DBManager;' in m[0] and m[1] in ('get','getInstance')}
 results=[]
 for ci in range(nc):
  cls,flags,sup,interfaces,source,ann,cd,sv=struct.unpack_from('<8I',b,co+ci*32)
  if not cd:continue
  p=cd; counts=[]
  for _ in range(4):v,p=uleb(b,p);counts.append(v)
  for _ in range(counts[0]+counts[1]):_,p=uleb(b,p);_,p=uleb(b,p)
  for count in counts[2:]:
   mid=0
   for _ in range(count):
    diff,p=uleb(b,p);mid+=diff;access,p=uleb(b,p);code,p=uleb(b,p)
    if not code or methods[mid][0].startswith('Lnet/zetetic/'):continue
    ni=u32(code+12);words=struct.unpack_from('<'+'H'*ni,b,code+16)
    for w in range(ni-2):
     if words[w]&255 not in (0x6e,0x6f,0x70,0x71,0x72,0x74,0x75,0x76,0x77,0x78):continue
     target=words[w+1]
     if target in targets:
      results.append({'caller':methods[mid],'target':methods[target],'codeOffset':hex(code),'instructionWord':w,'access':hex(access)})
 return results

if __name__=='__main__':
 root=Path('data/extracted/lr_20261116T212608096_7b99bdd0/apk_contents/base')
 rows=[]
 for p in root.glob('classes6.dex'):
  for r in inspect(p):r['dex']=p.name;rows.append(r)
 out=Path('reports/ghidra/dbmanager-dex-callers.json');out.write_text(json.dumps(rows,indent=2),encoding='utf-8')
 print(json.dumps(rows,indent=2))