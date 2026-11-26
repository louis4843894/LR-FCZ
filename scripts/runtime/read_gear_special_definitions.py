"""Bounded copies of verified GearDB increment and Skill+ dictionaries only."""
import json,hashlib,uuid,sys,argparse
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bounded_equipment_reader import Reader
from equipment_memory import ROOT,GBASE,u64
from native_layouts import NEW_SHA,layout_for_sha
from read_defense_team import typed

def capture(r,out,only=None):
 if r.module_sha!=NEW_SHA:raise ValueError('module differs')
 root_address=r.base+0x1fd58c0-GBASE;root=u64(r.read(root_address,8));manager=typed(r,root,0x60,0x1e4af90)
 out.mkdir(parents=True,exist_ok=False);tables=[]
 for name,offset,ap,size,strings,limit in [('increments',0x48,0x1e4af18,0x50,[0x18,0x30],4096),('skillplus',0x58,0x1e993a8,0x80,[0x18,0x38,0x50],2048),('skillupgrades',0x50,0x1e99258,0x40,[0x18],2048)]:
  if only and name!=only:continue
  dictionary=u64(manager,offset);header=typed(r,dictionary,0x28,layout_for_sha(NEW_SHA)['dictionaryVtable']);node=u64(header,0x18)
  records=[];seen=set();keys=set();blobs=[]
  while node:
   if node in seen or len(seen)>=limit:raise ValueError('cycle or definition node bound')
   seen.add(node);entry=r.read(node,0x128);nxt=u64(entry,0x120)
   key=entry[:256].split(b'\0',1)[0].decode('utf8','strict')
   if not key or len(key)>255 or key in keys:raise ValueError('duplicate or invalid key')
   keys.add(key);ptr=u64(entry,0x108);raw=typed(r,ptr,size,ap)
   decoded={hex(o):r.string(raw,o).decode('utf8','strict') for o in strings}
   if u64(r.read(node+0x120,8))!=nxt:raise ValueError('dictionary changed')
   records.append({'key':key,'offset':len(blobs)*size,'size':size,'sha256':hashlib.sha256(raw).hexdigest(),'strings':decoded});blobs.append(raw);node=nxt
  if u64(r.read(root_address,8))!=root or u64(r.read(root+offset,8))!=dictionary or r.read(dictionary,0x28)!=header:raise ValueError('definition container changed')
  blob=b''.join(blobs);filename=name+'.private.bin';(out/filename).write_bytes(blob)
  tables.append({'name':name,'dictionaryOffset':hex(offset),'vtable':hex(ap),'rawFile':filename,'rawSha256':hashlib.sha256(blob).hexdigest(),'records':records,
   'maxNodes':limit,'visitedNodes':len(seen),'stopReason':'null_tail','consistentSnapshot':True})
 meta={'schemaVersion':1,'sourceKind':'verified-native-gear-special-definition-copies','moduleSha256':NEW_SHA,'moduleBase':r.base,'pid':r.pid,
  'gameVersion':'12.4.2','capturedAt':datetime.now(timezone.utc).isoformat(),'tables':tables,'readBytes':r.read_bytes,'readCount':r.read_count,
  'credentialsRead':False,'wholeGameComplete':False}
 (out/'capture.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf8');return meta

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--only',choices=['increments','skillplus','skillupgrades']);args=p.parse_args()
 out=ROOT/'data/research/runtime.private'/('gear-special-definitions-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:6])
 try:
  with Reader(r'C:\LDPlayer\LDPlayer9\adb.exe','emulator-5554',600) as r:
   r.expected_module_sha=NEW_SHA;r.refresh();meta=capture(r,out,args.only)
  print(json.dumps({'copy':out.relative_to(ROOT).as_posix(),'tables':[{'name':t['name'],'records':len(t['records']),'stopReason':t['stopReason']} for t in meta['tables']],'credentialsRead':False}))
 except Exception as error:
  print(json.dumps({'completed':False,'reason':type(error).__name__,'partialCopyAccepted':False}));raise SystemExit(1)
