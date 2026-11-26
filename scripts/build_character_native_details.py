"""Native talent groups/stages and verified local thumbnails; no template rewrite."""
import argparse,hashlib,json,math,re,sqlite3,struct,zlib
from collections import Counter
from contextlib import closing
from pathlib import Path
from local_game_database import ROOT,DEFAULT_DB,connect,encoded
from native_layouts import NEW_SHA
from sync_character_templates_supabase import freeze

CAPTURE=ROOT/'data/research/runtime.private/character-capture-20261123T030909Z-da0eaa'
ASSETS=ROOT/'data/extracted/lr_20261116T212608096_7b99bdd0/apk_contents/base/assets/res/tutorial_res/hd'
LANG=ROOT/'data/research/runtime.private/guild-session-20261123/lang_unit.ndb'
SCHEMA='''
CREATE TABLE IF NOT EXISTS character_native_sources(source_id TEXT PRIMARY KEY,payload TEXT NOT NULL CHECK(json_valid(payload)));
CREATE TABLE IF NOT EXISTS current_character_native_sources(scope TEXT PRIMARY KEY,source_id TEXT NOT NULL REFERENCES character_native_sources(source_id));
CREATE TABLE IF NOT EXISTS character_native_details(source_id TEXT NOT NULL REFERENCES character_native_sources(source_id),character_id TEXT NOT NULL,payload TEXT NOT NULL CHECK(json_valid(payload)),PRIMARY KEY(source_id,character_id));
'''


def sha(b):return hashlib.sha256(b).hexdigest()
def inline_string(raw,offset):
 if raw[offset]&1:return None
 n=raw[offset]>>1
 if n>22 or raw[offset+n+1]!=0:raise ValueError('invalid inline group code')
 return raw[offset+1:offset+1+n].decode('utf8')


def png_size(raw):
 if len(raw)>2*1024*1024 or raw[:8]!=b'\x89PNG\r\n\x1a\n':raise ValueError('invalid bounded PNG')
 offset=8;size=None;idat=False
 while offset+12<=len(raw):
  n=struct.unpack_from('>I',raw,offset)[0];kind=raw[offset+4:offset+8];end=offset+12+n
  if end>len(raw) or zlib.crc32(raw[offset+4:offset+8+n])!=struct.unpack_from('>I',raw,offset+8+n)[0]:raise ValueError('PNG chunk integrity differs')
  if kind==b'IHDR':
   if offset!=8 or n!=13:raise ValueError('invalid PNG header')
   size=struct.unpack_from('>II',raw,offset+8)
   if not all(0<v<=2048 for v in size):raise ValueError('invalid thumbnail dimensions')
  idat|=kind==b'IDAT';offset=end
  if kind==b'IEND':
   if n or offset!=len(raw) or not size or not idat:raise ValueError('incomplete PNG')
   return size
 raise ValueError('PNG end missing')


def parse_definitions(folder):
 meta=json.loads((folder/'capture.json').read_bytes())
 if meta['sourceKind']!='verified-native-character-talent-copies' or meta['moduleSha256']!=NEW_SHA or len(meta['tables'])!=2:raise ValueError('unverified talent capture')
 definitions={};groups={}
 for t in meta['tables']:
  if t['stopReason']!='null_tail' or t['consistentSnapshot'] is not True:raise ValueError('incomplete talent traversal')
  b=(folder/t['rawFile']).read_bytes()
  if sha(b)!=t['rawSha256'] or len(b)!=len(t['records'])*t['recordSize']:raise ValueError('talent blob differs')
  for r in t['records']:
   raw=b[r['offset']:r['offset']+r['size']]
   if sha(raw)!=r['sha256'] or r['strings']['0x18']!=r['key']:raise ValueError('talent record differs')
   if t['name']=='groups':
    steps=r['strings']['steps']
    if len(steps)!=4 or any(not re.fullmatch('[A-Za-z0-9_-]+',c) for c in steps) or r['key'] in groups:raise ValueError('group steps differ')
    groups[r['key']]=steps
   else:
    kind=struct.unpack_from('<I',raw,0x30)[0];enhance=struct.unpack_from('<I',raw,0x50)[0];value=struct.unpack_from('<f',raw,0x54)[0]
    if kind not in (1,2) or not math.isfinite(value) or r['key'] in definitions:raise ValueError('unknown talent kind/scalar')
    definitions[r['key']]={'talentCode':r['key'],'kind':'enhancement' if kind==1 else 'major','abilityCode':r['strings']['0x38'] or None,
                          'enhanceTypeRaw':enhance if kind==1 else None,'enhanceValueRaw':value if kind==1 else None}
 for codes in groups.values():
  if any(c not in definitions for c in codes):raise ValueError('group definition missing')
 return meta,definitions,groups


def build(folder,database=DEFAULT_DB,thumbnails=None):
 folder=Path(folder).resolve();capture,definitions,groups=parse_definitions(folder)
 with closing(sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro',uri=True)) as db:
  basic_sha,p=db.execute("SELECT c.sha256,d.payload FROM current_documents c JOIN documents d USING(sha256) WHERE c.filename='verified-characters.json'").fetchone();basic=json.loads(p)
  detail_meta=json.loads(db.execute("SELECT s.payload FROM current_character_details c JOIN character_detail_sources s USING(source_id) WHERE c.scope='native-matched-reference'").fetchone()[0])
 with closing(sqlite3.connect(LANG.resolve().as_uri()+'?mode=ro',uri=True)) as db:labels=dict(db.execute("SELECT dataCode,msg FROM lang_unit WHERE language='zh-Hant'"))
 reference_folder=ROOT/detail_meta['referenceDirectory'];manifest_raw=(reference_folder/'datasets-source.json').read_bytes();manifest=json.loads(manifest_raw)
 if sha(manifest_raw)!=detail_meta['referenceManifestSha256'] or sha(LANG.read_bytes())!=detail_meta['localTranslationSha256']:raise ValueError('accepted label provenance differs')
 for name in ('rangers.json','official-locales.json','custom-locales.json'):
  expected=next(r['sha256'] for r in manifest['files'] if r['file']==name)
  if sha((reference_folder/name).read_bytes())!=expected:raise ValueError('accepted label input hash differs')
 reference=json.loads((reference_folder/'rangers.json').read_bytes());refs={r['rangerCode']:r for r in reference['rangers']}
 enhancements={}
 for ref in refs.values():
  for e in (ref.get('talents') or {}).get('enhancements',[]):
   key=e['talentCode'];prior=enhancements.get(key)
   if prior and any(prior[k]!=e[k] for k in ('effectCode','value','unit')):raise ValueError('reference enhancement conflict')
   enhancements[key]=e
 from build_character_details import Labels
 label_source=Labels(ROOT/detail_meta['referenceDirectory'],LANG)
 def clean(s):return re.sub('<[^>]*>','',s.replace('\\n','\n')).strip() if s else None
 for key,d in definitions.items():
  if d['kind']=='major':
   code=d['abilityCode'];d.update(name=clean(labels.get((code or '')+'_nm')),description=clean(labels.get((code or '')+'_desc')),labelSource='local-translation')
  else:
   e=enhancements.get(key);matched=e is not None and struct.pack('<f',e['value'])==struct.pack('<f',d['enhanceValueRaw'])
   d.update(name='強化才能',description=label_source.text(e['localizedEffect']) if matched else None,
            effectCode=e['effectCode'] if matched else None,unit=e['unit'] if matched else None,
            referenceScalarMatched=matched,labelSource='user-confirmed-reference' if matched else 'unresolved')
 thumbnail_rows={};thumbnail_meta=None
 if thumbnails is not None:
  thumbnails=Path(thumbnails).resolve();thumbnail_raw=(thumbnails/'capture.json').read_bytes();thumbnail_meta=json.loads(thumbnail_raw)
  if thumbnail_meta['sourceKind']!='verified-game-cache-character-thumbnails' or thumbnail_meta['moduleSha256']!=NEW_SHA or thumbnail_meta['nativeDocumentSha256']!=basic_sha or thumbnail_meta['requestedFiles']!=thumbnail_meta['copiedFiles']:raise ValueError('thumbnail capture identity/integrity differs')
  thumbnail_rows={r['characterId']:r for r in thumbnail_meta['records']}
  if len(thumbnail_rows)!=len(thumbnail_meta['records']):raise ValueError('duplicate thumbnail ID')
 raw_meta=json.loads((CAPTURE/'capture.json').read_bytes())
 if raw_meta['moduleSha256']!=NEW_SHA:raise ValueError('native character layout/source differs')
 raw_by_id={r['key']:r for r in raw_meta['records']};records=[];counts=Counter()
 if len(raw_by_id)!=len(raw_meta['records']) or {r['characterId'] for r in basic['records']}-set(raw_by_id):raise ValueError('native character identities differ')
 for base in basic['records']:
  code=base['characterId'];item=raw_by_id[code];raw=(CAPTURE/item['files']['record']['file']).read_bytes()
  if sha(raw)!=item['files']['record']['sha256']:raise ValueError('character raw copy differs')
  group=inline_string(raw,0x668);steps=None;status='group_code_not_captured' if group is None else 'not_configured' if not group else 'definition_missing'
  if group in groups:
   steps=[{'stage':i+1,**definitions[c]} for i,c in enumerate(groups[group])];status='verified-native-group';counts['charactersWithNativeTalentGroup']+=1
   ref=refs.get(code);expected=([ref['talents']['major']['talentCode']]+[e['talentCode'] for e in ref['talents']['enhancements']]) if ref and ref.get('talents') and ref['talents'].get('major') else None
   if expected is not None and expected!=groups[group]:raise ValueError('native/reference talent order differs')
  image=None;path=ASSETS/code/(code+'-thum.png');image_capture=None
  if not path.is_file() and code in thumbnail_rows:
   row=thumbnail_rows[code]
   if row['file']!=code+'.png':raise ValueError('thumbnail filename differs from native ID')
   path=thumbnails/row['file'];image_capture=row
  if path.is_file():
   b=path.read_bytes();w,h=png_size(b)
   if image_capture and (sha(b)!=image_capture['sha256'] or (w,h)!=(image_capture['width'],image_capture['height'])):raise ValueError('copied thumbnail differs')
   image={'path':path.relative_to(ROOT).as_posix(),'sha256':sha(b),'width':w,'height':h,'sourceKind':'verified-local-game-thumbnail','acquiredFrom':'game-cache' if image_capture else 'apk'};counts['images']+=1
  records.append({'characterId':code,'image':image,'talents':{'status':status,'groupCode':group or None,'steps':steps}});counts[status]+=1
 doc={'parserVersion':'native-character-details-v1','sourceKind':'verified-native-character-enrichment','moduleSha256':NEW_SHA,'gameVersion':'12.4.2',
      'nativeDocumentSha256':basic_sha,'capturedAt':capture['capturedAt'],'definitionCapture':folder.relative_to(ROOT).as_posix(),
      'definitionCaptureSha256':sha((folder/'capture.json').read_bytes()),'characterCaptureSha256':sha((CAPTURE/'capture.json').read_bytes()),
      'referenceManifestSha256':detail_meta['referenceManifestSha256'],'translationSha256':sha(LANG.read_bytes()),
      'talentDefinitions':len(definitions),'talentGroups':len(groups),'summary':dict(counts),'records':records,
      'proof':{'groupCodeGetter':'00c15958','groupCodeOffset':'0x668','groupLookup':'00e5e798','stepLookup':'00e62820','enhancementGradePrefix':'00e5fa60',
               'thumbnailFormat':'0194709c','thumbnailCaller':'00f00998','unitCodeGetter':'00c14694','numericStatsAlreadyApplied':False}}
 if thumbnail_meta is not None:doc['thumbnailCapture']={'directory':thumbnails.relative_to(ROOT).as_posix(),'sha256':sha(thumbnail_raw),'capturedAt':thumbnail_meta['capturedAt']}
 doc['sourceId']='character-native-'+sha(encoded(doc).encode())[:24];return doc


def save(doc,database=DEFAULT_DB):
 folder=ROOT/'data/research/runtime.private/character-native-exports'/doc['sourceId'];folder.mkdir(parents=True,exist_ok=True);freeze(folder/'details.private.json',doc)
 index={r['characterId']:{'image':r['image'],'talentStatus':r['talents']['status']} for r in doc['records'] if r['image'] or r['talents']['status']=='verified-native-group'}
 with closing(connect(database)) as db:
  db.executescript(SCHEMA)
  with db:
   if db.execute("SELECT sha256 FROM current_documents WHERE filename='verified-characters.json'").fetchone()[0]!=doc['nativeDocumentSha256']:raise ValueError('native character source changed')
   db.execute('INSERT OR IGNORE INTO character_native_sources VALUES (?,?)',(doc['sourceId'],encoded({k:v for k,v in doc.items() if k!='records'}|{'index':index})))
   db.executemany('INSERT OR IGNORE INTO character_native_details VALUES (?,?,?)',[(doc['sourceId'],r['characterId'],encoded(r)) for r in doc['records']])
   db.execute("INSERT INTO current_character_native_sources VALUES ('native-templates',?) ON CONFLICT(scope) DO UPDATE SET source_id=excluded.source_id",(doc['sourceId'],))


def public_talents(row):
 t=row.get('talents') if row else None
 if not t:return None
 if t['status']=='not_configured':return {'status':'not_configured','steps':[]}
 if t['status']!='verified-native-group':return None
 return {'status':t['status'],'relationshipSource':'verified-native','steps':[{k:s.get(k) for k in ['stage','kind','name','description']}|{'descriptionSource':s.get('labelSource','unresolved')} for s in t['steps']]}


def talent_stages(row,grade):
 t=public_talents(row)
 if t is None:return None
 known=type(grade) is int and 0<=grade<=4
 return {'status':t['status'],'grade':grade if known else None,'steps':[{**s,'state':('reached' if s['stage']<=grade else 'locked') if known else 'unknown'} for s in t['steps']]}


def read_native_details(database=DEFAULT_DB):
 with closing(sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro',uri=True)) as db:
  if not db.execute("SELECT name FROM sqlite_master WHERE name='current_character_native_sources'").fetchone():return None,{}
  sid,p=db.execute("SELECT s.source_id,s.payload FROM current_character_native_sources c JOIN character_native_sources s USING(source_id) WHERE c.scope='native-templates'").fetchone();meta=json.loads(p)
  expected=db.execute("SELECT sha256 FROM current_documents WHERE filename='verified-characters.json'").fetchone()[0]
  if meta['nativeDocumentSha256']!=expected or meta['sourceKind']!='verified-native-character-enrichment' or meta['moduleSha256']!=NEW_SHA or meta['proof']['enhancementGradePrefix']!='00e5fa60':raise ValueError('native enrichment version differs')
  return sid,{c:json.loads(p) for c,p in db.execute('SELECT character_id,payload FROM character_native_details WHERE source_id=?',(sid,))}


def validate(doc,database=DEFAULT_DB):
 sid,rows=read_native_details(database)
 if sid!=doc['sourceId'] or rows!={r['characterId']:r for r in doc['records']}:raise ValueError('stored native enrichment does not reproduce')
 with closing(sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro',uri=True)) as db:
  source=db.execute("SELECT source_id FROM current_character_instance_sources WHERE scope='accepted-defense'").fetchone()[0]
  progress=[json.loads(p) for p, in db.execute("SELECT payload FROM character_instance_progress WHERE source_id=? AND json_extract(payload,'$.scope')='guildwar'",(source,))]
 counts=Counter()
 for p in progress:
  t=talent_stages(rows.get(p['characterId']),p['talentGrade']);counts['guildCharacters']+=1
  if t is not None:
   counts['guildTalentRelationshipVerified']+=1
   if t['status']=='verified-native-group':
    counts['guildWithTalentGroup']+=1;counts['guildReachedTalentStages']+=sum(s['state']=='reached' for s in t['steps'])
  if rows[p['characterId']]['image']:counts['guildWithLocalImage']+=1
 return {'sourceId':sid,'records':len(rows),'summary':doc['summary'],'talentDefinitions':doc['talentDefinitions'],'talentGroups':doc['talentGroups'],
         'offlineReproduction':True,'storedRowsVerified':True,'guildCoverage':dict(counts),'templateTrainingSubstituted':False,'combatActivationVerified':False}


if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture',type=Path,required=True);p.add_argument('--thumbnails',type=Path);p.add_argument('--apply',action='store_true');a=p.parse_args();doc=build(a.capture,thumbnails=a.thumbnails)
 if a.apply:save(doc)
 report=validate(doc) if a.apply else {'sourceId':doc['sourceId'],'records':len(doc['records']),'summary':doc['summary'],'saved':False}
 (ROOT/'reports/character-native-details-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(report))
