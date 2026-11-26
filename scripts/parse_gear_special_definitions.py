"""Validate the selected native special-definition copies, offline only."""
import argparse,hashlib,json,math,sqlite3,struct
from pathlib import Path
from local_game_database import ROOT,DEFAULT_DB,connect,encoded,stamp
from native_layouts import NEW_SHA
from derive_http_gear_values import digest

SCHEMA='''CREATE TABLE IF NOT EXISTS gear_special_definition_sources(source_id TEXT PRIMARY KEY,payload TEXT NOT NULL CHECK(json_valid(payload)));
CREATE TABLE IF NOT EXISTS current_gear_special_definitions(scope TEXT PRIMARY KEY,source_id TEXT NOT NULL REFERENCES gear_special_definition_sources);'''

def parse(folder):
 folder=Path(folder).resolve()
 if not folder.is_relative_to(ROOT/'data/research/runtime.private'):raise ValueError('private definition copy required')
 manifest=(folder/'capture.json').read_bytes();meta=json.loads(manifest)
 if meta['sourceKind']!='verified-native-gear-special-definition-copies' or meta['moduleSha256']!=NEW_SHA:raise ValueError('unverified special module')
 result={}
 for table in meta['tables']:
  name=table['name'];expected={'increments':(0x50,0x1e4af18,'0x48'),'skillplus':(0x80,0x1e993a8,'0x58'),'skillupgrades':(0x40,0x1e99258,'0x50')}
  if name not in expected:raise ValueError('unverified special dictionary name')
  size,ap,offset=expected[name]
  if table['vtable']!=hex(ap) or table['dictionaryOffset']!=offset or not table['consistentSnapshot'] or table['stopReason']!='null_tail':raise ValueError('unverified special dictionary')
  filename=table['rawFile']
  if Path(filename).name!=filename:raise ValueError('raw copy path differs')
  blob=(folder/filename).read_bytes();rows={}
  if hashlib.sha256(blob).hexdigest()!=table['rawSha256'] or len(blob)!=len(table['records'])*size:raise ValueError('special copy size/hash differs')
  for i,record in enumerate(table['records']):
   raw=blob[i*size:(i+1)*size]
   if record['offset']!=i*size or record['size']!=size or hashlib.sha256(raw).hexdigest()!=record['sha256'] or struct.unpack_from('<Q',raw)[0]-meta['moduleBase']+0x100000!=ap:raise ValueError('special record type/boundary differs')
   for off,text in record['strings'].items():
    off=int(off,16);length=struct.unpack_from('<Q',raw,off+8)[0] if raw[off]&1 else raw[off]>>1
    if len(text.encode())!=length or (not raw[off]&1 and raw[off+1:off+1+length]!=text.encode()):raise ValueError('special string differs')
   key=record['key']
   if key in rows:raise ValueError('duplicate special definition')
   if name=='increments':
    level,value=struct.unpack_from('<If',raw,0x48);selector=record['strings']['0x18'];code=record['strings']['0x30']
    if key!=selector.upper()+code.upper()+str(level) or not math.isfinite(value):raise ValueError('native increment lookup key differs')
    row={'selector':selector,'code':code,'level':level,'value':value}
   elif name=='skillupgrades':
    group,level,value=struct.unpack_from('<IIf',raw,0x30)
    if key!=f'{group}_{level}' or record['strings']['0x18']!=key or not math.isfinite(value):raise ValueError('Skill+ increment key differs')
    row={'groupId':group,'level':level,'value':value}
   else:
    attr,group=struct.unpack_from('<II',raw,0x30);target,apply,low,high,steps,use=struct.unpack_from('<IIffIB',raw,0x68)
    if key!=str(attr) or record['strings']['0x18']!=key or not steps or not all(math.isfinite(v) for v in (low,high)) or use not in (0,1):raise ValueError('native Skill+ definition differs')
    row={'attributeId':attr,'groupId':group,'targetFactor':record['strings']['0x38'],'applyType':record['strings']['0x50'],
     'targetFactorEnum':target,'applyTypeEnum':apply,'minValue':low,'maxValue':high,'steps':steps,'use':bool(use)}
   rows[key]={**row,'recordSha256':record['sha256']}
  result[name]=rows
 doc={'sourceKind':'verified-native-gear-special-definitions','moduleSha256':NEW_SHA,'capturedAt':meta['capturedAt'],
  'captureDirectory':folder.relative_to(ROOT).as_posix(),'captureManifestSha256':hashlib.sha256(manifest).hexdigest(),'tables':result,
  'loadedContainersEnded':True,'wholeGameComplete':False,'numericInstanceValuesIncluded':False}
 doc['sourceId']='gear-special-'+digest(doc)[:24];return doc

def save(doc,database=DEFAULT_DB):
 db=connect(database);db.executescript(SCHEMA)
 try:
  with db:
   db.execute('INSERT OR IGNORE INTO gear_special_definition_sources VALUES (?,?)',(doc['sourceId'],encoded(doc)))
   scope='native-skill-upgrades' if set(doc['tables'])=={'skillupgrades'} else 'native-special'
   db.execute('INSERT INTO current_gear_special_definitions VALUES (?,?) ON CONFLICT(scope) DO UPDATE SET source_id=excluded.source_id',(scope,doc['sourceId']))
 finally:db.close()

def read(db,scope='native-special'):
 if not db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='gear_special_definition_sources'").fetchone():return None
 row=db.execute("SELECT s.payload FROM current_gear_special_definitions c JOIN gear_special_definition_sources s USING(source_id) WHERE scope=?",(scope,)).fetchone()
 if not row:return None
 doc=json.loads(row[0]);rebuilt=parse(ROOT/doc['captureDirectory'])
 if rebuilt!=doc:raise ValueError('accepted special definitions differ from immutable copy')
 return doc

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture',type=Path,required=True);p.add_argument('--apply',action='store_true');a=p.parse_args();d=parse(a.capture)
 if a.apply:save(d)
 print(json.dumps({'sourceId':d['sourceId'],'tables':{k:len(v) for k,v in d['tables'].items()},'saved':a.apply,'numericInstanceValuesIncluded':False}))
