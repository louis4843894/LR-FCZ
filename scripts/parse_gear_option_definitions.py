"""Offline validation of the native special-option/talent definition copies."""
import argparse,hashlib,json,math,struct
from pathlib import Path
from local_game_database import ROOT,DEFAULT_DB,connect,encoded
from native_layouts import NEW_SHA
from derive_http_gear_values import digest
from parse_gear_special_definitions import SCHEMA

SCOPE='native-option-talents'


def parse(folder):
 folder=Path(folder).resolve()
 if not folder.is_relative_to(ROOT/'data/research/runtime.private'):raise ValueError('private definition copy required')
 manifest=(folder/'capture.json').read_bytes();meta=json.loads(manifest)
 if meta['sourceKind']!='verified-native-gear-option-definition-copies' or meta['moduleSha256']!=NEW_SHA or meta.get('credentialsRead') is not False:raise ValueError('unverified option definitions')
 tables={};bounds={}
 for table in meta['tables']:
  name=table['name'];expected={'talents':(0xa0,0x1e994e0,'0x68'),'options':(0xd0,0x1e995f0,'0x70')}
  if name not in expected or name in tables:raise ValueError('unverified or duplicate definition table')
  size,ap,offset=expected[name]
  if table['vtable']!=hex(ap) or table['dictionaryOffset']!=offset or table['recordSize']!=size or table.get('consistentSnapshot') is not True or table['stopReason']!='null_tail':raise ValueError('definition type/traversal differs')
  if not 1<=table['visitedNodes']<=2048 or not 1<=len(table['records'])<=4096:raise ValueError('definition count bound')
  filename=table['rawFile']
  if Path(filename).name!=filename:raise ValueError('raw copy path differs')
  blob=(folder/filename).read_bytes()
  if hashlib.sha256(blob).hexdigest()!=table['rawSha256'] or len(blob)!=len(table['records'])*size:raise ValueError('definition size/hash differs')
  rows={}
  for i,record in enumerate(table['records']):
   raw=blob[i*size:(i+1)*size]
   if record['offset']!=i*size or record['size']!=size or hashlib.sha256(raw).hexdigest()!=record['sha256'] or struct.unpack_from('<Q',raw)[0]-meta['moduleBase']+0x100000!=ap:raise ValueError('definition record type/boundary differs')
   strings=record['strings'];required=[0x18,0x30,0x48,0x60] if name=='talents' else [0x18,0x30,0x48,0x60,0x78,0x90,0xa8]
   if set(strings)!={hex(o) for o in required}:raise ValueError('definition string fields differ')
   for off in required:
    text=strings[hex(off)];length=struct.unpack_from('<Q',raw,off+8)[0] if raw[off]&1 else raw[off]>>1
    if length>1024 or len(text.encode())!=length or (not raw[off]&1 and raw[off+1:off+1+length]!=text.encode()):raise ValueError('definition string differs')
   if name=='talents':
    key=strings['0x18'];values=struct.unpack_from('<9f',raw,0x78)
    if key!=strings['0x30']+'_'+strings['0x48'] or record['key']!=strings['0x30'] or not all(math.isfinite(v) for v in values):raise ValueError('talent key/value differs')
    row={'id':key,'equipTalentCode':strings['0x30'],'targetAbilityCode':strings['0x48'],'rootAbilityCode':strings['0x60'],
         **dict(zip(['buffFactorMin','buffFactorMax','buffFactorEnchantIncrease','subBuffFactorMin','subBuffFactorMax','subBuffFactorEnchantIncrease','activeProbabilityMin','activeProbabilityMax','activeProbabilityEnchantIncrease'],values))}
    # Each native group is an ARRAY keyed by equipTalentCode, while each
    # row ID additionally includes targetAbilityCode.
    identity=key
    if identity in rows:raise ValueError('duplicate talent definition')
    rows[identity]={**row,'recordSha256':record['sha256']}
   else:
    key=strings['0x18'];grades,attr,increment=struct.unpack_from('<IIf',raw,0xc0)
    if key!=record['key'] or key!=strings['0x30'] or key in rows or not grades or not math.isfinite(increment):raise ValueError('option key/value differs')
    rows[key]={'specialOptionCode':key,'specialOptionGroup':strings['0x48'],'equipTalentCode':strings['0x60'],
               'titleLangCode':strings['0x78'],'normalDescLangCode':strings['0x90'],'specialDescLangCode':strings['0xa8'],
               'equipTalentValueDivideGrades':grades,'normalAttrNo':attr,'normalAttrEnchantIncrease':increment,'recordSha256':record['sha256']}
  tables[name]=list(rows.values()) if name=='talents' else rows
  bounds[name]={'visitedNodes':table['visitedNodes'],'records':len(rows),'stopReason':table['stopReason']}
 if set(tables)!={'options','talents'}:raise ValueError('required option/talent tables missing')
 doc={'sourceKind':'verified-native-gear-option-definitions','moduleSha256':NEW_SHA,'capturedAt':meta['capturedAt'],
      'captureDirectory':folder.relative_to(ROOT).as_posix(),'captureManifestSha256':hashlib.sha256(manifest).hexdigest(),
      'tables':tables,'traversal':bounds,'wholeGameComplete':False,'numericInstanceValuesIncluded':False}
 doc['sourceId']='gear-options-'+digest(doc)[:24];return doc


def save(doc,database=DEFAULT_DB):
 db=connect(database);db.executescript(SCHEMA)
 try:
  with db:
   db.execute('INSERT OR IGNORE INTO gear_special_definition_sources VALUES (?,?)',(doc['sourceId'],encoded(doc)))
   db.execute('INSERT INTO current_gear_special_definitions VALUES (?,?) ON CONFLICT(scope) DO UPDATE SET source_id=excluded.source_id',(SCOPE,doc['sourceId']))
 finally:db.close()


def read(db):
 row=db.execute('SELECT s.payload FROM current_gear_special_definitions c JOIN gear_special_definition_sources s USING(source_id) WHERE scope=?',(SCOPE,)).fetchone()
 if not row:return None
 doc=json.loads(row[0])
 if parse(ROOT/doc['captureDirectory'])!=doc:raise ValueError('accepted option definitions differ from immutable copy')
 return doc


if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture',type=Path,required=True);p.add_argument('--apply',action='store_true');a=p.parse_args();d=parse(a.capture)
 if a.apply:save(d)
 print(json.dumps({'sourceId':d['sourceId'],'tables':{k:len(v) for k,v in d['tables'].items()},'saved':a.apply,'numericInstanceValuesIncluded':False}))
