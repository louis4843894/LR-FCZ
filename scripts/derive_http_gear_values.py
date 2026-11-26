"""Reconstruct only calibrated ordinary effects from native definitions + real rolls.

Does not overwrite HTTP/native observations. Stores a separate, owner/instance/
snapshot-bound derived source. Special dependencies, selectors, Skill+ and
grades outside the verified range remain unknown. Generic native hydration
establishes the ordinary definition lookup beyond the calibration sample IDs.
"""
import argparse,hashlib,json,sqlite3,struct,re,inspect
from pathlib import Path
from collections import Counter
from local_game_database import ROOT,DEFAULT_DB,connect,encoded,stamp
from native_layouts import NEW_SHA
from parse_gear_definitions import parse
from parse_runtime_gear_values import scalar,UnsupportedOrdinaryRange
from parse_runtime_defense import parse_capture
SCHEMA='''CREATE TABLE IF NOT EXISTS gear_roll_sources(source_id TEXT PRIMARY KEY,created_at TEXT NOT NULL,payload TEXT NOT NULL CHECK(json_valid(payload)));
CREATE TABLE IF NOT EXISTS current_gear_rolls(scope TEXT PRIMARY KEY,source_id TEXT NOT NULL REFERENCES gear_roll_sources);
CREATE TABLE IF NOT EXISTS gear_instance_rolls(source_id TEXT NOT NULL REFERENCES gear_roll_sources,observation_id TEXT NOT NULL,payload TEXT NOT NULL CHECK(json_valid(payload)),PRIMARY KEY(source_id,observation_id));'''
def digest(value):return hashlib.sha256(encoded(value).encode()).hexdigest()
def observation_id(team,member,slot):return digest([team['snapshotId'],team['playerId'],member['memberIndex'],slot])
def instance_hash(uid,identity):return digest([uid,identity['namespace'],identity['value']]) if identity else None
def reconstruct(raw,grade,enhancement,coefficient):
 if type(grade) is not int or not 0<=grade<=0xffffffff or type(enhancement) is not int or not 0<=enhancement<=5:return None
 copy=bytearray(raw);struct.pack_into('<I',copy,0x20,grade)
 try:result=scalar(copy,enhancement,coefficient)
 except UnsupportedOrdinaryRange:return None
 if result:result.pop('nativeValue')
 return result
def definition_bytes(definition):
 directory=ROOT/definition['captureDirectory'];folder=ROOT/'data/research/runtime.private/gear-definition-exports'/definition['sourceId'];cache=folder/'definition-objects.private.bin'
 if cache.exists():blob=cache.read_bytes()
 else:
  blob=b''.join((directory/r['rawRecordFile']).read_bytes() for r in definition['records']);folder.mkdir(parents=True,exist_ok=True)
  with cache.open('xb') as output:output.write(blob)
 if len(blob)!=len(definition['records'])*0x78:raise ValueError('cached definition object boundaries differ')
 result={}
 for index,row in enumerate(definition['records']):
  raw=blob[index*0x78:(index+1)*0x78]
  if hashlib.sha256(raw).hexdigest()!=row['rawRecordSha256']:raise ValueError('cached definition object hash differs')
  result[row['attributeId']]=raw
 return result
def calibrate(definition,document,native_sources=None):
 base=definition_bytes(definition);allowed=set();blocked=set();compared=0;ordinary=0;hashes=[]
 for sid in sorted(native_sources if native_sources is not None else {t['sourceId'] for t in document['snapshots']}):
  folder=ROOT/'data/research/runtime.private'/sid;p=folder/'capture.json'
  if not p.exists():continue
  meta=json.loads(p.read_bytes())
  if meta.get('moduleSha256')!=NEW_SHA or not meta.get('consistentSnapshot'):continue
  for row in meta['records']:
   for name,entry in row['files'].items():
    if not re.fullmatch(r'gear-[123]-attribute-(?:[0-9]|1[0-5])',name):continue
    raw=(folder/entry['file']).read_bytes()
    if len(raw)!=0x78 or hashlib.sha256(raw).hexdigest()!=entry['sha256'] or struct.unpack_from('<Q',raw)[0]-meta['moduleBase']+0x100000!=0x1e99700:raise ValueError('native calibration object differs')
    attr=struct.unpack_from('<I',raw,0x18)[0]
    if not attr:continue
    candidate=base.get(attr)
    if not candidate:blocked.add(attr);continue
    compared+=1;hashes.append(entry['sha256'])
    # Grade differs by instance. Compare all definition inputs and branch flags.
    a=(raw[0x18:0x20],raw[0x24:0x30],raw[0x30:0x36],raw[0x48:0x4e],bool(struct.unpack_from('<Q',raw,0x68)[0]),bool(struct.unpack_from('<Q',raw,0x70)[0]))
    b=(candidate[0x18:0x20],candidate[0x24:0x30],candidate[0x30:0x36],candidate[0x48:0x4e],bool(struct.unpack_from('<Q',candidate,0x68)[0]),bool(struct.unpack_from('<Q',candidate,0x70)[0]))
    if a!=b:blocked.add(attr);continue
    if raw[0x30:0x36]==b'\x08none\0' and raw[0x48:0x4e]==b'\x08none\0' and not a[-1] and not a[-2]:allowed.add(attr);ordinary+=1
 allowed-=blocked
 # Generic native hydration is now independently established: JSON creates
 # each ID/grade, 01226b44 visits every GearStat, 01226f08 copies definition
 # inputs using 00f44fdc -> GearDBContainer+38 integer-key lookup. This applies
 # to every definition in the proven ordinary branch, including unseen IDs.
 resolution=ROOT/'reports/ghidra/gear-manager-attribute-resolution-1242.txt'
 lookup=ROOT/'reports/ghidra/gear-definition-lookup-and-skillplus-1242.txt'
 resolution_text=resolution.read_text(encoding='utf8');lookup_text=lookup.read_text(encoding='utf8')
 for required in ['FUNCTION 01226f08','func_0x00f44fdc','*param_2 + 0x60','*param_2 + 0x80','*param_2 + 0xa0','*param_2 + 0x90']:
  if required not in resolution_text:raise ValueError('native definition hydration evidence incomplete')
 for required in ['FUNCTION 00f44fdc','param_1 + 0x38','FUNCTION 01226b44','target_012193fc','target_01226f08']:
  if required not in lookup_text:raise ValueError('native ID/grade-to-definition call chain incomplete')
 witnessed_ids=sorted(allowed)
 allowed={r['attributeId'] for r in definition['records'] if 1<=r['typeEnum']<=45 and r['selector1']=='none' and r['selector2']=='none' and not r['hasDependency68'] and not r['hasDependency70']}-blocked
 # Reproduce both independently reviewed gear, using definitions captured now
 # with their own native roll grades and their original coefficient.
 capture=ROOT/'data/research/runtime.private/member-defense-capture-20261125T023755Z-ee891f'
 review_path=capture/'ordinary-value-screen-review.private.json';review=json.loads(review_path.read_bytes());meta=json.loads((capture/'capture.json').read_bytes())
 if review['captureManifestSha256']!=hashlib.sha256((capture/'capture.json').read_bytes()).hexdigest():raise ValueError('calibration review source differs')
 factor=json.loads((ROOT/'data/research/runtime.private/gear-factor-20261125T031832Z.private.json').read_bytes())
 if factor['pid']!=meta['pid'] or factor['moduleSha256']!=NEW_SHA:raise ValueError('original calibration coefficient differs')
 coef=struct.unpack('<f',bytes.fromhex(factor['coefficientRawHex']))[0]
 if coef!=factor['coefficient']:raise ValueError('calibration factor bytes differ')
 parsed=parse_capture(capture,all_teams=True);gears={(m['sourcePositionKey'],s):(m['equipment'][s]) for t in parsed['snapshots'] for m in t['members'] for s in ['weapon','armor','accessory']}
 checked=0;items=set()
 for check in review['gearChecks']:
  if hashlib.sha256((capture/check['screenFile']).read_bytes()).hexdigest()!=check['screenSha256']:raise ValueError('review screen differs')
  position,slot=check['positionKey'],check['slot'];gear=gears[position,{1:'weapon',2:'armor',3:'accessory'}[slot]]
  if gear['equipmentId']!=check['itemCode']:raise ValueError('review gear differs')
  native=next(r for r in meta['records'] if r['positionKey']==position)
  for expected in check['values']:
   original=(capture/native['files'][f"gear-{slot}-attribute-{expected['index']}"]['file']).read_bytes();attr=struct.unpack_from('<I',original,0x18)[0];grade=struct.unpack_from('<I',original,0x20)[0]
   if attr!=expected['attributeId'] or attr not in allowed:raise ValueError('review attribute outside calibrated ordinary IDs')
   result=reconstruct(base[attr],grade,gear['enhancement'],coef)
   if not result or result['value']!=expected['value'] or result['unit']!=expected['unit']:raise ValueError('definition reconstruction differs from independent game-screen value')
   checked+=1
  items.add(check['itemCode'])
 if len(items)<2 or checked<6 or ordinary<6:raise ValueError('insufficient native ordinary calibration')
 proof={'method':'native-definition-and-instance-grade-v1','moduleSha256':NEW_SHA,'definitionSourceId':definition['sourceId'],'nativeObjectsCompared':compared,'ordinaryNativeWitnesses':ordinary,
  'ordinaryAttributeIds':sorted(allowed),'nativeWitnessAttributeIds':witnessed_ids,'withheldAttributeIds':sorted(blocked),'nativeWitnessHashesSha256':digest(sorted(hashes)),'screenCheckedGearCount':len(items),'screenCheckedValueCount':checked,
  'definitionHydrationVerified':True,'nativeHydrationReportSha256':hashlib.sha256(resolution.read_bytes()).hexdigest(),'nativeLookupAndParserReportSha256':hashlib.sha256(lookup.read_bytes()).hexdigest(),
  'uiReviewSha256':hashlib.sha256(review_path.read_bytes()).hexdigest(),'formulaFunction':'0122dde4','formatterFunction':'0122f510','currentPlayersVisuallyVerified':False}
 proof['proofSha256']=digest(proof);return base,allowed,proof
def calibrated_inputs(definition,document,http_sources):
 # Reuse already validated immutable native witnesses. New HTTP snapshots do
 # not invalidate these native copies or require 4,000 small-file reads again.
 sources={t['sourceId'] for t in document['snapshots']}-http_sources;manifests=[]
 for sid in sorted(sources):
  p=ROOT/'data/research/runtime.private'/sid/'capture.json'
  if p.exists():manifests.append([sid,hashlib.sha256(p.read_bytes()).hexdigest()])
 code=[hashlib.sha256((inspect.getsource(calibrate)+inspect.getsource(reconstruct)).encode()).hexdigest(),hashlib.sha256((ROOT/'scripts/parse_runtime_gear_values.py').read_bytes()).hexdigest()]
 key=digest([definition['sourceId'],manifests,code]);folder=ROOT/'data/research/runtime.private/gear-definition-exports'/definition['sourceId'];cache=folder/('calibration-'+key+'.private.json')
 if cache.exists():
  proof=json.loads(cache.read_bytes());body={k:v for k,v in proof.items() if k!='proofSha256'}
  if proof.get('proofSha256')!=digest(body) or proof.get('definitionSourceId')!=definition['sourceId'] or proof.get('screenCheckedGearCount',0)<2 or proof.get('screenCheckedValueCount',0)<6:raise ValueError('cached native calibration differs')
  return definition_bytes(definition),set(proof['ordinaryAttributeIds']),proof
 base,allowed,proof=calibrate(definition,document,sources);folder.mkdir(parents=True,exist_ok=True);cache.write_text(encoded(proof)+'\n',encoding='utf8');return base,allowed,proof
def matching_roll_entry(record,team,member,slot,gear,entry):
 if not record or record['equipmentId']!=gear['equipmentId'] or record['enhancement']!=gear.get('enhancement') or record['instanceGrade']!=gear.get('instanceGrade') or record['equipmentInstanceHash']!=instance_hash(team['playerId'],gear.get('equipmentInstanceIdentity')):return None
 if entry.get('sourceField') not in ['attr1No','attr2No','attr3No','attr4No','attr5No']:return None
 import math
 return next((e for e in record['entries'] if all(e.get(k)==entry.get(k) for k in ['index','attributeId','valueGradeRaw','sourceField']) and e.get('valueVerified') is True and e.get('enhancementIncluded') is True and type(e.get('value')) in (int,float) and math.isfinite(e['value']) and e.get('unit') in ('PERCENT','FLAT')),None)
def build(database=DEFAULT_DB):
 with sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro',uri=True) as db:
  db.execute('BEGIN');row=db.execute("SELECT s.payload FROM current_gear_definitions c JOIN gear_definition_sources s USING(source_id) WHERE scope='ordinary-gearstat'").fetchone()
  if not row:raise ValueError('accepted native definitions missing')
  definition=json.loads(row[0]);sha,payload=db.execute("SELECT d.sha256,d.payload FROM current_documents c JOIN documents d USING(sha256) WHERE c.filename='defense-teams.private.json'").fetchone();document=json.loads(payload)
  current={r[0] for r in db.execute('SELECT snapshot_id FROM current_rankings')};attempts={}
  for sid,uid,p in db.execute('SELECT ranking_snapshot_id,player_id,payload FROM ranking_defense_attempts ORDER BY attempted_at'):
   if sid in current:attempts[sid,uid]=json.loads(p)
  keys={(uid,s) for (_,uid),a in attempts.items() if a['status'] in ('success','partial') for s in a.get('defenseSnapshotIds',[])}
  http_sources={r[0] for r in db.execute('SELECT capture_id FROM pvp_http_sources')}
 manifest=(ROOT/definition['captureDirectory']/'capture.json').read_bytes()
 if definition.get('moduleSha256')!=NEW_SHA or definition.get('sourceKind')!='verified-native-gear-definitions' or hashlib.sha256(manifest).hexdigest()!=definition['captureManifestSha256']:raise ValueError('accepted native definition source differs')
 base,allowed,calibration=calibrated_inputs(definition,document,http_sources);records=[];summary=Counter()
 for t in document['snapshots']:
  if (t['playerId'],t['snapshotId']) not in keys or t['sourceId'] not in http_sources:continue
  for m in t['members'] or []:
   for slot,g in m['equipment'].items():
    if g['state']!='equipped':continue
    summary['equippedInstances']+=1;entries=[]
    for a in (g.get('actualEffects') or {}).get('entries',[]):
     summary['effectEntries']+=1;attr=a['attributeId']
     if a.get('sourceField') not in ['attr1No','attr2No','attr3No','attr4No','attr5No'] or attr not in allowed:summary['unsupportedEffectEntries']+=1;continue
     if g.get('ownerAssociationStatus')!='verified-native' or not g.get('equipmentInstanceIdentity'):summary['unknownOwnerEntries']+=1;continue
     result=reconstruct(base[attr],a['valueGradeRaw'],g['enhancement'],definition['coefficient'])
     if not result:summary['unverifiedGradeOrBranchEntries']+=1;continue
     entries.append({**{k:a[k] for k in ['index','attributeId','valueGradeRaw','sourceField']},**result,'valueVerified':True,'valueVisuallyVerified':False,'definitionRecordSha256':hashlib.sha256(base[attr]).hexdigest()});summary['reconstructedValues']+=1
    if entries:records.append({'observationId':observation_id(t,m,slot),'equipmentId':g['equipmentId'],'enhancement':g['enhancement'],'instanceGrade':g.get('instanceGrade'),
      'equipmentInstanceHash':instance_hash(t['playerId'],g['equipmentInstanceIdentity']),'sourceObservationSha256':t['sourceSha256'],'factorCapturedAt':definition['factorCapturedAt'],'entries':entries})
 doc={'schemaVersion':1,'sourceKind':'calibrated-native-definition-http-rolls','method':'native-definition-and-instance-grade-v1','moduleSha256':NEW_SHA,'definitionSourceId':definition['sourceId'],
  'defenseDocumentSha256':sha,'rankingSources':sorted(current),'calibration':calibration,'records':records,'summary':dict(summary),'coefficientCapturedAt':definition['factorCapturedAt'],
  'externalReferenceValuesUsed':False,'nativeObservationsOverwritten':False,'currentPlayersVisuallyVerified':False}
 doc['sourceId']='gear-rolls-'+digest(doc)[:24];return doc
def save(doc,database=DEFAULT_DB):
 folder=ROOT/'data/research/runtime.private/gear-roll-exports'/doc['sourceId'];folder.mkdir(parents=True,exist_ok=True);output=folder/'rolls.private.json';text=encoded(doc)+'\n'
 if output.exists() and output.read_text(encoding='utf8')!=text:raise ValueError('immutable derived roll export differs')
 output.write_text(text,encoding='utf8');db=connect(database);db.executescript(SCHEMA)
 try:
  with db:
   db.execute('INSERT OR IGNORE INTO gear_roll_sources VALUES (?,?,?)',(doc['sourceId'],stamp(),encoded({k:v for k,v in doc.items() if k!='records'})))
   db.executemany('INSERT OR IGNORE INTO gear_instance_rolls VALUES (?,?,?)',[(doc['sourceId'],r['observationId'],encoded(r)) for r in doc['records']])
   db.execute('INSERT INTO current_gear_rolls VALUES (?,?) ON CONFLICT(scope) DO UPDATE SET source_id=excluded.source_id',('ranked-http',doc['sourceId']))
 finally:db.close()
 return folder
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--apply',action='store_true');a=p.parse_args();doc=build()
 if a.apply:save(doc)
 report={k:doc[k] for k in ['sourceId','sourceKind','definitionSourceId','defenseDocumentSha256','calibration','summary','externalReferenceValuesUsed','nativeObservationsOverwritten','currentPlayersVisuallyVerified']}
 (ROOT/'reports/http-gear-values-reconstruction.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'sourceId':doc['sourceId'],'summary':doc['summary'],'screenChecks':doc['calibration']['screenCheckedValueCount'],'nativeWitnesses':doc['calibration']['ordinaryNativeWitnesses'],'saved':a.apply}))
