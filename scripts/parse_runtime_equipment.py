"""Parse verified equipment-object copies, without opening the live process or decrypting .db.
Layout evidence: reports/ghidra/equip-static-record-json.txt,
equip-static-grade-layout.txt, equip-static-grade-unpack.txt.
"""
from __future__ import annotations
import argparse,base64,binascii,hashlib,json,re,sqlite3,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
TYPE_NAMES={1:'WEAPON',2:'ARMOR',3:'ACC'}
def u32(b,o):return struct.unpack_from('<I',b,o)[0]
def u64(b,o):return struct.unpack_from('<Q',b,o)[0]
def decode_grade(wrapper:bytes,encoded:bytes)->int:
 if len(wrapper)!=0x30:raise ValueError('grade wrapper must be exactly 0x30 bytes')
 if wrapper[0x18] not in (0,1):raise ValueError('unknown grade encoding mode')
 try:raw=base64.b64decode(encoded,validate=True) if wrapper[0x18]==1 else encoded
 except binascii.Error as e:raise ValueError('invalid grade Base64') from e
 # Native getter uses strtoul(base=0). Accept a complete integer, never a partial parse.
 if not re.fullmatch(rb'(?:0[xX][0-9a-fA-F]+|0[0-7]*|[1-9][0-9]*)',raw):raise ValueError('grade payload is not a complete unsigned integer')
 n=int(raw,16 if raw.lower().startswith(b'0x') else 8 if raw.startswith(b'0') else 10)
 if not 0<=n<=0xffffffff:raise ValueError('encoded grade exceeds uint32')
 checksum=(n^(n>>8)^(n>>16)^(n>>24))&255
 if checksum!=wrapper[0x2c]:raise ValueError('grade checksum mismatch; reject native fallback value')
 return n^u32(wrapper,0x28)
def decode_inline_item_code(record:bytes)->str:
 tag=record[0x20]
 if tag&1:raise ValueError('long itemCode requires an explicitly captured heap dependency')
 n=tag>>1
 if not 0<n<=22:raise ValueError('invalid short itemCode length')
 if record[0x21+n]!=0:raise ValueError('itemCode terminator missing')
 return record[0x21:0x21+n].decode('utf8','strict')
def read_blob(directory, item, field, kind):
 name=item[field]
 if Path(name).name!=name:raise ValueError('capture file must be a direct child')
 blob=(directory/name).read_bytes();expected=item.get('sha256',{}).get(kind)
 if expected and hashlib.sha256(blob).hexdigest()!=expected:raise ValueError('capture hash mismatch: '+kind)
 return blob

def parse_record(directory,meta,item,db):
 b=read_blob(directory,item,'rawFile','record')
 if len(b)!=0x160:raise ValueError('record boundary must be exactly 0x160 bytes')
 if u64(b,0)-meta['moduleBase']+meta['ghidraImageBase']!=0x1e986a8:raise ValueError('equipment record vtable mismatch')
 if b[0x20]&1:
  code=read_blob(directory,item,'itemCodeFile','item-code').decode('utf8','strict')
  if len(code.encode('utf8'))!=u64(b,0x28):raise ValueError('long itemCode length mismatch')
 else:code=decode_inline_item_code(b)
 if code!=item['key']:raise ValueError('dictionary key differs from itemCode')
 kind=u32(b,0x18)
 if kind not in TYPE_NAMES:raise ValueError('unknown equipType enum')
 grade_blob=read_blob(directory,item,'gradeFile','grade')
 if u64(grade_blob,0)-meta['moduleBase']+meta['ghidraImageBase']!=0x1f65b70:raise ValueError('grade wrapper vtable mismatch')
 grade=decode_grade(grade_blob,read_blob(directory,item,'gradeCipherFile','grade-cipher'))
 row={'itemCode':code,'equipType':TYPE_NAMES[kind],'equipTypeRaw':kind,'equipGrade':grade,'starCount':grade,'maxEnchant':u32(b,0x74),'minAttributeCount':u32(b,0x78),'maxAttributeCount':u32(b,0x7c),'goodGearAttr':u32(b,0xd8),'effects':None,'effectsStatus':'unparsed','recordScope':'equipment-template','rawRecordSha256':hashlib.sha256(b).hexdigest(),'sourceRecordFile':item['rawFile'],'validation':{'recordSize':len(b),'vtableVerified':True,'dictionaryKeyMatchesItemCode':True,'gradeChecksumVerified':True},'nameTranslations':[]}
 if db:row['nameTranslations']=[{'dataCode':r[0],'language':r[1],'msg':r[2]} for r in db.execute('SELECT dataCode,language,msg FROM lang_equip WHERE dataCode=?',(code+'_nm',))]
 return row

def parse_capture(directory:Path,localization:Path|None=None,strict:bool=True)->dict:
 meta=json.loads((directory/'capture.json').read_text(encoding='utf8'));records=[];seen={};errors=[];duplicates=[];conflicts=set()
 db=sqlite3.connect(localization.resolve().as_uri()+'?mode=ro',uri=True) if localization else None
 try:
  for item in meta['records']:
   try:
    row=parse_record(directory,meta,item,db);code=row['itemCode']
    if code in conflicts:raise ValueError('conflicting itemCode '+code)
    if code in seen:
     signature=lambda r:{k:v for k,v in r.items() if k not in ('sourceRecordFile','rawRecordSha256')}
     if signature(seen[code])!=signature(row):
      conflicts.add(code);records=[r for r in records if r['itemCode']!=code];seen.pop(code,None)
      raise ValueError('conflicting itemCode '+code)
     duplicates.append(code);continue
    seen[code]=row;records.append(row)
   except (ValueError,KeyError,OSError,struct.error) as error:
    if strict:raise
    errors.append({'itemCode':item.get('key'),'error':str(error)})
 finally:
  if db:db.close()
 return {'schemaVersion':1,'parserVersion':'runtime-equipment-v2','sourceKind':'verified-live-equipment-object-copies','gameVersion':meta.get('gameVersion','12.4.0'),'capturedAt':meta['capturedAt'],'outerDbDecryption':{'completed':False,'equipmentDbToObjectsCallChainVerified':False},'recordParsing':{'completed':bool(records),'capturedRecordCount':len(meta['records']),'recordCount':len(records),'failedRecordCount':len(errors),'duplicates':duplicates,'conflicts':sorted(conflicts),'errors':errors,'loadedDictionaryTraversalEnded':meta.get('traversal',{}).get('loadedListEnded',meta.get('complete',False)),'wholeGameCoverageConfirmed':False,'moduleSha256':meta['moduleSha256']},'traversal':meta.get('traversal'),'fieldEvidence':{'itemCode':'01218478 -> +0x50 setter 0121be44 -> record+0x20; getter0121be18','equipType':'01218478 string enum -> record+0x18; getter0121be08','equipGrade':'01218478 -> 01a5bc88 -> record+0x50; getter01a5bf7c; Base64 decoder01a32664','starCount':'01180bf8 -> record+0x68 -> 01a5bf7c -> 019c3ff0 -> 019c42c8 -> 019c4324 -> 019c4490(common/star_layer.plist count)','maxEnchant':'01218478 -> vtable+0xf0 -> setter0121bf88 -> record+0x74','minAttributeCount':'01218478 -> vtable+0x100 -> setter0121bf98 -> record+0x78','maxAttributeCount':'01218478 -> vtable+0x110 -> setter0121bfa8 -> record+0x7c','goodGearAttr':'01218478 -> vtable+0x1e0 -> setter0121c15c -> record+0xd8; relation and numeric effect semantics unresolved'},'records':records}

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture',type=Path,default=ROOT/'data/research/runtime.private/objects');p.add_argument('--localization',type=Path);p.add_argument('--output',type=Path,default=ROOT/'data/research/equipment-runtime-records.json');p.add_argument('--allow-partial',action='store_true');a=p.parse_args()
 result=parse_capture(a.capture,a.localization,strict=not a.allow_partial);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 print(json.dumps({'recordCount':len(result['records']),'outerDbDecryption':False,'output':str(a.output)},ensure_ascii=True))
if __name__=='__main__':main()
