"""Validate typed global GearStat copies; preserve definitions separately from rolls."""
import argparse,hashlib,json,math,sqlite3,struct
from pathlib import Path
from local_game_database import ROOT,DEFAULT_DB,connect,encoded,stamp
from native_layouts import NEW_SHA
SCHEMA='''CREATE TABLE IF NOT EXISTS gear_definition_sources(source_id TEXT PRIMARY KEY,captured_at TEXT NOT NULL,payload TEXT NOT NULL CHECK(json_valid(payload)));
CREATE TABLE IF NOT EXISTS current_gear_definitions(scope TEXT PRIMARY KEY,source_id TEXT NOT NULL REFERENCES gear_definition_sources);
CREATE TABLE IF NOT EXISTS gear_definition_records(source_id TEXT NOT NULL REFERENCES gear_definition_sources,attribute_id INTEGER NOT NULL,payload TEXT NOT NULL CHECK(json_valid(payload)),PRIMARY KEY(source_id,attribute_id));'''
def digest(b):return hashlib.sha256(b).hexdigest()
def short_string(raw,offset):
 if raw[offset]&1:return None
 size=raw[offset]>>1
 if size>22:raise ValueError('definition short string exceeds layout')
 return raw[offset+1:offset+1+size].decode('utf8')
def parse(capture):
 capture=Path(capture).resolve()
 if capture.parent!=(ROOT/'data/research/runtime.private').resolve():raise ValueError('definition copy must stay private')
 manifest=(capture/'capture.json').read_bytes();meta=json.loads(manifest)
 if meta.get('sourceKind')!='verified-global-GearStat-definitions' or meta.get('moduleSha256')!=NEW_SHA or meta.get('consistentSnapshot') is not True:raise ValueError('unverified definition source')
 if meta.get('rootGlobal')!='01fd58c0' or meta.get('managerVtable')!='01e4af90' or meta.get('getter')!='00f45ab0':raise ValueError('definition receiver differs')
 if not 1<=len(meta['records'])<=6000 or meta['traversal']['errors']:raise ValueError('definition bounds/errors')
 traversal=meta['traversal']
 if traversal['visitedNodes']!=len(meta['records']) or traversal['stopReason'] not in ('null_tail','node_limit') or traversal['loadedContainerEnded'] is not (traversal['stopReason']=='null_tail'):raise ValueError('definition traversal coverage differs')
 factor=meta['factor']
 if factor.get('moduleSha256')!=NEW_SHA or factor['pid']!=meta['pid']:raise ValueError('definition and factor process differ')
 coefficient=struct.unpack('<f',bytes.fromhex(factor['coefficientRawHex']))[0]
 if not math.isfinite(coefficient) or coefficient!=factor['coefficient']:raise ValueError('factor bytes differ')
 rows=[];seen=set()
 for entry in meta['records']:
  p=(capture/entry['file']).resolve()
  if p.parent!=capture:raise ValueError('definition path exceeds capture')
  raw=p.read_bytes()
  if len(raw)!=0x78 or digest(raw)!=entry['sha256'] or struct.unpack_from('<Q',raw)[0]-meta['moduleBase']+0x100000!=0x1e99700:raise ValueError('definition hash/type/boundary differs')
  attr,kind,grade,steps=struct.unpack_from('<IIII',raw,0x18);lo,hi=struct.unpack_from('<ff',raw,0x28)
  if attr!=entry['key'] or attr in seen or not all(math.isfinite(v) for v in (lo,hi)):raise ValueError('definition ID/range conflict')
  seen.add(attr);rows.append({'attributeId':attr,'typeEnum':kind,'definitionGradeRaw':grade,'valueDivideGrades':steps,'minValueRaw':lo,'maxValueRaw':hi,
    'selector1':short_string(raw,0x30),'selector2':short_string(raw,0x48),'hasDependency68':bool(struct.unpack_from('<Q',raw,0x68)[0]),'hasDependency70':bool(struct.unpack_from('<Q',raw,0x70)[0]),
    'rawRecordSha256':entry['sha256'],'rawRecordFile':entry['file']})
 doc={'schemaVersion':1,'sourceKind':'verified-native-gear-definitions','moduleSha256':NEW_SHA,'gameVersion':'12.4.2','capturedAt':meta['capturedAt'],'captureDirectory':capture.relative_to(ROOT).as_posix(),
  'captureManifestSha256':digest(manifest),'records':rows,'loadedContainerEnded':meta['traversal']['loadedContainerEnded'],'wholeGameComplete':False,
  'coefficient':coefficient,'factorCapturedAt':factor['capturedAt'],'runtimePid':meta['pid'],'factorEvidence':factor,'numericRollsDerived':False}
 doc['sourceId']='gear-definitions-'+digest(encoded(doc).encode())[:24];return doc
def save(doc,database=DEFAULT_DB):
 directory=ROOT/'data/research/runtime.private/gear-definition-exports'/doc['sourceId'];directory.mkdir(parents=True,exist_ok=True)
 p=directory/'definitions.private.json';text=encoded(doc)+'\n'
 if p.exists() and p.read_text(encoding='utf8')!=text:raise ValueError('immutable definition export differs')
 p.write_text(text,encoding='utf8');db=connect(database);db.executescript(SCHEMA)
 try:
  with db:
   prior=db.execute('SELECT payload FROM gear_definition_sources WHERE source_id=?',(doc['sourceId'],)).fetchone()
   if prior and prior[0]!=encoded(doc):raise ValueError('immutable definition source differs')
   db.execute('INSERT OR IGNORE INTO gear_definition_sources VALUES (?,?,?)',(doc['sourceId'],doc['capturedAt'],encoded(doc)))
   db.executemany('INSERT OR IGNORE INTO gear_definition_records VALUES (?,?,?)',[(doc['sourceId'],r['attributeId'],encoded(r)) for r in doc['records']])
   db.execute('INSERT INTO current_gear_definitions VALUES (?,?) ON CONFLICT(scope) DO UPDATE SET source_id=excluded.source_id',('ordinary-gearstat',doc['sourceId']))
 finally:db.close()
 return directory
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture',type=Path,required=True);p.add_argument('--apply',action='store_true');a=p.parse_args();doc=parse(a.capture)
 if a.apply:save(doc)
 print(json.dumps({'sourceId':doc['sourceId'],'records':len(doc['records']),'loadedContainerEnded':doc['loadedContainerEnded'],'wholeGameComplete':False,'numericRollsDerived':False,'saved':a.apply}))
