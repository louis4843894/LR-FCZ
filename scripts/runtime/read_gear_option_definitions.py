"""Copy only proven GearDB +68/+70 definition containers, without credentials.

12.4.2: 00f439bc groups GearTalentAttributeData in +68 by equipTalentCode;
00f43ee8 stores GearSpecialOptionData in +70. No session or game requests.
"""
import hashlib,json,sys,uuid
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bounded_equipment_reader import Reader
from equipment_memory import ROOT,GBASE,u64
from native_layouts import NEW_SHA
from read_defense_team import typed
from read_guild_members import array


def capture(r,out):
 if r.module_sha!=NEW_SHA:raise ValueError('unverified module')
 # Exact native getters: LDR X0,[X0,#0x68/0x70]; RET.
 for address,expected in [(0xf45c90,'003440f9c0035fd6'),(0xf45ce0,'003840f9c0035fd6')]:
  if r.read(r.base+address-GBASE,8).hex()!=expected:raise ValueError('definition getter differs')
 root_global=r.base+0x1fd58c0-GBASE;root=u64(r.read(root_global,8))
 manager=typed(r,root,0x78,0x1e4af90);tables=[];blobs={}
 for name,offset,ap,size,strings in [('talents',0x68,0x1e994e0,0xa0,[0x18,0x30,0x48,0x60]),
                                   ('options',0x70,0x1e995f0,0xd0,[0x18,0x30,0x48,0x60,0x78,0x90,0xa8])]:
  dictionary=u64(manager,offset);header=typed(r,dictionary,0x28,0x1f6a690)
  node=u64(header,0x18);seen=set();keys=set();pointers_seen=set();records=[];parts=[];groups=0
  while node:
   if node in seen or len(seen)>=2048:raise ValueError('definition cycle or node bound')
   seen.add(node);entry=r.read(node,0x128);next_node=u64(entry,0x120)
   key=entry[:256].split(b'\0',1)[0].decode('utf8','strict')
   if not key or len(key)>255 or key in keys:raise ValueError('duplicate or invalid dictionary key')
   keys.add(key);value=u64(entry,0x108)
   if name=='talents':
    pointers,*_=array(r,value,128);groups+=1
   else:pointers=[value]
   for pointer in pointers:
    if not pointer or pointer in pointers_seen or len(records)>=4096:raise ValueError('duplicate definition pointer or record bound')
    pointers_seen.add(pointer);raw=typed(r,pointer,size,ap)
    texts={hex(o):r.string(raw,o).decode('utf8','strict') for o in strings}
    records.append({'key':key,'offset':len(parts)*size,'size':size,'sha256':hashlib.sha256(raw).hexdigest(),'strings':texts})
    parts.append(raw)
    if r.read(pointer,size)!=raw:raise ValueError('definition object changed')
   if name=='talents' and array(r,value,128)[0]!=pointers:raise ValueError('definition group changed')
   if u64(r.read(node+0x120,8))!=next_node:raise ValueError('definition next changed')
   node=next_node
  if r.read(dictionary,0x28)!=header or u64(r.read(root+offset,8))!=dictionary:raise ValueError('definition container changed')
  blob=b''.join(parts);filename=name+'.private.bin';blobs[filename]=blob
  tables.append({'name':name,'dictionaryOffset':hex(offset),'vtable':hex(ap),'recordSize':size,'rawFile':filename,
                 'rawSha256':hashlib.sha256(blob).hexdigest(),'records':records,'visitedNodes':len(seen),
                 'arrayGroups':groups,'maxNodes':2048,'maxRecords':4096,'stopReason':'null_tail','consistentSnapshot':True})
 if u64(r.read(root_global,8))!=root:raise ValueError('definition root changed')
 meta={'schemaVersion':1,'sourceKind':'verified-native-gear-option-definition-copies','moduleSha256':NEW_SHA,
       'gameVersion':'12.4.2','moduleBase':r.base,'capturedAt':datetime.now(timezone.utc).isoformat(),
       'tables':tables,'readBytes':r.read_bytes,'readCount':r.read_count,'credentialsRead':False,'wholeGameComplete':False}
 out.mkdir(parents=True,exist_ok=False)
 for filename,blob in blobs.items():(out/filename).write_bytes(blob)
 (out/'capture.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 return meta


if __name__=='__main__':
 out=ROOT/'data/research/runtime.private'/('gear-option-definitions-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:6])
 try:
  with Reader(r'C:\LDPlayer\LDPlayer9\adb.exe','emulator-5554',300) as r:
   r.expected_module_sha=NEW_SHA;r.refresh();meta=capture(r,out)
  print(json.dumps({'copy':out.relative_to(ROOT).as_posix(),'tables':{t['name']:len(t['records']) for t in meta['tables']},'credentialsRead':False}))
 except Exception as error:
  print(json.dumps({'completed':False,'reason':type(error).__name__,'partialCopyAccepted':False}));raise SystemExit(1)
