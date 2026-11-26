"""Copy only verified UnitManager +98/+a0 talent definition dictionaries."""
import hashlib,json,struct,sys,uuid
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bounded_equipment_reader import Reader
from equipment_memory import ROOT,GBASE,u64
from native_layouts import NEW_SHA
from read_defense_team import typed


def capture(r,out):
 if r.module_sha!=NEW_SHA:raise ValueError('module differs')
 root_global=r.base+0x1fd41e8-GBASE;root=u64(r.read(root_global,8));manager=typed(r,root,0xc0,0x1e4db98)
 tables=[];blobs={}
 for name,offset,ap,size in [('talents',0x98,0x1e36240,0x58),('groups',0xa0,0x1e362c8,0x48)]:
  dictionary=u64(manager,offset);header=typed(r,dictionary,0x28,0x1f6a690);node=u64(header,0x18);seen=set();keys=set();records=[];parts=[]
  while node:
   if node in seen or len(seen)>=2048:raise ValueError('cycle or dictionary limit')
   seen.add(node);entry=r.read(node,0x128);nxt=u64(entry,0x120);key=entry[:256].split(b'\0',1)[0].decode('utf8')
   if not key or key in keys or len(key)>160:raise ValueError('invalid definition key')
   keys.add(key);pointer=u64(entry,0x108);raw=typed(r,pointer,size,ap);texts={'0x18':r.string(raw,0x18).decode('utf8')}
   if texts['0x18']!=key:raise ValueError('definition key mismatch')
   vector=None
   if name=='talents':texts['0x38']=r.string(raw,0x38).decode('utf8')
   else:
    begin,end,capacity=struct.unpack_from('<QQQ',raw,0x30)
    if end-begin!=4*24 or not begin<=end<=capacity:raise ValueError('four-step vector bound differs')
    vector=r.read(begin,96);texts['steps']=[r.string(vector,i*24).decode('utf8') for i in range(4)]
    if r.read(begin,96)!=vector:raise ValueError('step vector changed')
   if r.read(pointer,size)!=raw or u64(r.read(node+0x120,8))!=nxt:raise ValueError('definition changed')
   records.append({'key':key,'offset':len(parts)*size,'size':size,'sha256':hashlib.sha256(raw).hexdigest(),'strings':texts});parts.append(raw);node=nxt
  if r.read(dictionary,0x28)!=header or u64(r.read(root+offset,8))!=dictionary:raise ValueError('dictionary changed')
  blob=b''.join(parts);filename=name+'.private.bin';blobs[filename]=blob
  tables.append({'name':name,'vtable':hex(ap),'recordSize':size,'dictionaryOffset':hex(offset),'rawFile':filename,'rawSha256':hashlib.sha256(blob).hexdigest(),
                 'records':records,'visitedNodes':len(seen),'maxNodes':2048,'stopReason':'null_tail','consistentSnapshot':True})
 if u64(r.read(root_global,8))!=root:raise ValueError('manager changed')
 meta={'schemaVersion':1,'sourceKind':'verified-native-character-talent-copies','gameVersion':'12.4.2','moduleSha256':NEW_SHA,
       'capturedAt':datetime.now(timezone.utc).isoformat(),'tables':tables,'readCount':r.read_count,'readBytes':r.read_bytes,'credentialsRead':False,'wholeGameComplete':False}
 out.mkdir(parents=True,exist_ok=False)
 for filename,blob in blobs.items():(out/filename).write_bytes(blob)
 (out/'capture.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf8');return meta


if __name__=='__main__':
 out=ROOT/'data/research/runtime.private'/('character-talent-definitions-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:6])
 try:
  with Reader(r'C:\LDPlayer\LDPlayer9\adb.exe','emulator-5554',240) as r:
   r.expected_module_sha=NEW_SHA;r.refresh();meta=capture(r,out)
  print(json.dumps({'copy':out.relative_to(ROOT).as_posix(),'tables':{t['name']:len(t['records']) for t in meta['tables']},'credentialsRead':False}))
 except Exception as e:
  print(json.dumps({'captured':False,'reasonType':type(e).__name__,'accepted':False}));raise SystemExit(1)
