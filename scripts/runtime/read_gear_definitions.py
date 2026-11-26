"""Capture only the verified 12.4.2 GearDBContainer definition dictionary.

00c30fdc -> global01fd58c0, GearDBContainer AP01e4af90; virtual78/00f45ab0
returns +38 dictionary. Records must be GearStat AP01e99700, keyed by attrNo.
No player/session fields, injection, permission changes or whole-memory dumps.
"""
import argparse,hashlib,json,struct,time,uuid
from datetime import datetime,timezone
from pathlib import Path
from bounded_equipment_reader import Reader
from equipment_memory import ROOT,GBASE,u64
from read_defense_team import typed
from read_gear_factor import read_factor
from native_layouts import NEW_SHA,layout_for_sha

def capture(r,out,max_nodes=6000):
 if r.module_sha!=NEW_SHA or not 1<=max_nodes<=6000:raise ValueError('unverified module or definition bound')
 if r.read(r.base+0xf45ab0-GBASE,8).hex()!='001c40f9c0035fd6':raise ValueError('definition getter differs')
 global_address=r.base+0x1fd58c0-GBASE;manager=u64(r.read(global_address,8));raw=typed(r,manager,0x40,0x1e4af90)
 dictionary=u64(raw,0x38);header=typed(r,dictionary,0x28,layout_for_sha(NEW_SHA)['dictionaryVtable']);head=node=u64(header,0x18)
 out.mkdir(parents=True,exist_ok=False);(out/'manager.bin').write_bytes(raw);(out/'dictionary.bin').write_bytes(header)
 rows=[];seen=set();keys=set();errors=[];stop='node_limit'
 while node and len(seen)<max_nodes:
  if node in seen:stop='cycle';errors.append('repeated-node');break
  seen.add(node);entry=r.read(node,0x128);nxt=u64(entry,0x120);key=struct.unpack_from('<q',entry,0x100)[0]
  value=typed(r,u64(entry,0x108),0x78,layout_for_sha(NEW_SHA)['attributeVtable'])
  attr=struct.unpack_from('<I',value,0x18)[0]
  if key!=attr or not 0<key<0x80000000 or key in keys:raise ValueError('dictionary key/type/attribute identity conflict')
  keys.add(key);filename=f'attribute-{key}.bin';(out/filename).write_bytes(value)
  rows.append({'key':key,'file':filename,'sha256':hashlib.sha256(value).hexdigest()})
  if u64(r.read(node+0x120,8))!=nxt:stop='container_changed';errors.append('next-link-changed');break
  node=nxt
 if not node:stop='null_tail'
 consistent=u64(r.read(global_address,8))==manager and u64(r.read(manager+0x38,8))==dictionary and r.read(dictionary,0x28)==header
 factor=read_factor(r)
 meta={'schemaVersion':1,'sourceKind':'verified-global-GearStat-definitions','capturedAt':datetime.now(timezone.utc).isoformat(),'gameVersion':'12.4.2','moduleSha256':r.module_sha,'moduleBase':r.base,'pid':r.pid,
  'rootGlobal':'01fd58c0','managerVtable':'01e4af90','dictionaryOffset':'0x38','attributeVtable':'01e99700','getter':'00f45ab0','records':rows,'factor':factor,
  'consistentSnapshot':consistent,'traversal':{'visitedNodes':len(seen),'maxNodes':max_nodes,'stopReason':stop,'loadedContainerEnded':node==0,'errors':errors},'wholeGameComplete':False,
  'readBytes':r.read_bytes,'readCount':r.read_count,'credentialsIncluded':False}
 (out/'capture.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf8')
 if not consistent or errors:raise ValueError('definition capture inconsistent; source remains unaccepted')
 return meta

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--max-nodes',type=int,default=6000);a=p.parse_args()
 out=ROOT/'data/research/runtime.private'/('gear-definitions-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:6])
 with Reader(r'C:\LDPlayer\LDPlayer9\adb.exe','emulator-5554',600) as r:
  r.expected_module_sha=NEW_SHA;r.refresh();meta=capture(r,out,a.max_nodes)
 print(json.dumps({'capture':out.relative_to(ROOT).as_posix(),'records':len(meta['records']),'traversal':meta['traversal'],'consistentSnapshot':meta['consistentSnapshot'],'credentialsRead':False}))
