"""Bounded ADR/ADRP+ADD references to exact guild-defense literals in the verified ELF.

No auto-analysis, new tool installation, runtime memory scan or network request.
Results are instruction candidates, to be checked against existing function bounds.
"""
import hashlib,json,re,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SHA='1185e119efeb6a67d30d289f8a183b36aebe53126a4765698509cd7a822a42a0'


def find():
 blob=(ROOT/'data/research/runtime.private/modules/libgame-12.4.2-pull.so').read_bytes()
 if hashlib.sha256(blob).hexdigest()!=SHA or blob[:6]!=b'\x7fELF\x02\x01' or struct.unpack_from('<H',blob,18)[0]!=183:raise ValueError('verified ARM64 ELF required')
 shoff=struct.unpack_from('<Q',blob,0x28)[0];entry_size,count,string_index=struct.unpack_from('<HHH',blob,0x3a)
 s=shoff+string_index*entry_size;string_offset,string_size=struct.unpack_from('<QQ',blob,s+0x18);strings=blob[string_offset:string_offset+string_size];text=None
 for i in range(count):
  s=shoff+i*entry_size;name_offset=struct.unpack_from('<I',blob,s)[0];name=strings[name_offset:strings.find(b'\0',name_offset)]
  if name==b'.text':text=struct.unpack_from('<QQQ',blob,s+0x10)
 if not text or text[2]>24*1024*1024:raise ValueError('bounded code section missing')
 targets={}
 for marker in [b'guildWarDefence',b'guildWarFortress']:
  for m in re.finditer(re.escape(marker),blob):
   end=blob.find(b'\0',m.start(),m.start()+100)
   if end<0:continue
   value=blob[m.start():end]
   if all(32<=n<127 for n in value):targets[m.start()+0x100000]=value.decode()
 if not targets or len(targets)>50:raise ValueError('literal bound')
 targets[0x0133bd38]='callback: guildWarDefenceDeckResponses parser'
 pages={addr&~0xfff for addr in targets};va,offset,size=text;code=memoryview(blob)[offset:offset+size-size%4];hits=[]
 for i,(ins,) in enumerate(struct.iter_unpack('<I',code)):
  op=ins&0x9f000000
  if op not in (0x90000000,0x10000000):continue
  pc=va+0x100000+i*4;imm=((ins>>29)&3)|(((ins>>5)&0x7ffff)<<2);imm=imm-(1<<21) if imm&(1<<20) else imm
  base=(pc&~0xfff)+(imm<<12) if op==0x90000000 else pc+imm
  if op==0x10000000:
   if base in targets:hits.append({'instruction':hex(pc),'target':hex(base),'literal':targets[base],'encoding':'ADR'})
   continue
  if base not in pages:continue
  reg=ins&31
  for distance in range(1,5):
   at=(i+distance)*4
   if at+4>len(code):break
   following=struct.unpack_from('<I',code,at)[0]
   if following&0xffc00000!=0x91000000 or ((following>>5)&31)!=reg:continue
   target=base+((following>>10)&0xfff)
   if target in targets:hits.append({'instruction':hex(pc),'addInstruction':hex(pc+distance*4),'target':hex(target),'literal':targets[target],'encoding':'ADRP+ADD candidate'})
 report={'moduleSha256':SHA,'bytesOfCodeChecked':len(code),'scope':'Exact defense/fortress JSON literals only; bounded immutable code section, not runtime memory','literals':{hex(k):v for k,v in targets.items()},'references':hits,'networkRequests':0}
 (ROOT/'reports/guild-defense-literal-readers.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8');return report


if __name__=='__main__':
 r=find();print(json.dumps({'literals':r['literals'],'references':r['references']},ensure_ascii=False))
