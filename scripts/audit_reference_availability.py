"""Compare explicit absence with unknown data using public reference copies.

Only template data and accepted local character sources are read. No player,
account, session or private web endpoint is involved.
"""
import argparse,hashlib,json,sqlite3,uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.parse import urlparse
from template_availability import availability

ROOT=Path(__file__).resolve().parents[1]
ORIGIN='https://rangerbook.warmycat.com'
PUBLIC={'rangers.json':'/res/v2/rangers.json','abilities.json':'/res/v2/abilities.json','equipment.json':'/res/v2/equipment.json',
 'official-locales.json':'/res/v2/locales/official.json','custom-locales.json':'/res/v2/locales/custom.json',
 'v2-data.js':'/assets/js/v2-data.js','ranger.js':'/assets/js/ranger.js','gear-detail.js':'/assets/js/gear-detail.js'}
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def fetch():
 folder=ROOT/'data/research/external-reference'/('availability-audit-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:6]);folder.mkdir(parents=True)
 def one(item):
  name,path=item
  with urlopen(Request(ORIGIN+path,headers={'User-Agent':'LR-local-template-audit/1.0','Accept':'application/json' if name.endswith('.json') else 'text/javascript','Cache-Control':'no-cache'}),timeout=40) as response:
   if urlparse(response.url).netloc!='rangerbook.warmycat.com':raise ValueError('unexpected redirect')
   data=response.read(32*1024*1024+1)
   if len(data)>32*1024*1024:raise ValueError('size bound')
   modified=response.headers.get('Last-Modified');etag=response.headers.get('ETag')
  if name.endswith('.json'):json.loads(data)
  p=folder/name;p.write_bytes(data)
  return {'file':name,'url':ORIGIN+path,'sha256':sha(p),'bytes':len(data),'lastModified':modified,'etag':etag}
 with ThreadPoolExecutor(max_workers=3) as pool:files=list(pool.map(one,PUBLIC.items()))
 (folder/'manifest.json').write_text(json.dumps({'retrievedAt':datetime.now(timezone.utc).isoformat(),'sourceKind':'public-reference-availability-audit','files':files},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 return folder


def audit(folder):
 folder=Path(folder).resolve();manifest=json.loads((folder/'manifest.json').read_text(encoding='utf8'))
 if not folder.is_relative_to(ROOT/'data/research/external-reference') or manifest['sourceKind']!='public-reference-availability-audit':raise ValueError('invalid reference copy')
 for r in manifest['files']:
  if Path(r['file']).name!=r['file'] or sha(folder/r['file'])!=r['sha256']:raise ValueError('reference copy hash mismatch')
 chars=json.loads((ROOT/'data/normalized/verified-characters.json').read_text(encoding='utf8'))
 equipment=json.loads((ROOT/'data/normalized/verified-equipment.json').read_text(encoding='utf8'))
 refs=json.loads((folder/'rangers.json').read_text(encoding='utf8'))['rangers'];gears=json.loads((folder/'equipment.json').read_text(encoding='utf8'))['equipment']
 by_id={r['rangerCode']:r for r in refs};by_gear={r['equipCode']:r for r in gears}
 if len(by_id)!=len(refs) or len(by_gear)!=len(gears):raise ValueError('duplicate reference identities')
 with closing(sqlite3.connect((ROOT/'data/local/lr.private.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
  sid,payload=db.execute("SELECT s.source_id,s.payload FROM current_character_details c JOIN character_detail_sources s USING(source_id) WHERE c.scope='native-matched-reference'").fetchone();meta=json.loads(payload)
  details={code:json.loads(p) for code,p in db.execute('SELECT character_id,payload FROM character_template_details WHERE source_id=?',(sid,))}
  nid=db.execute("SELECT source_id FROM current_character_native_sources WHERE scope='native-templates'").fetchone()[0]
  native={code:json.loads(p) for code,p in db.execute('SELECT character_id,payload FROM character_native_details WHERE source_id=?',(nid,))}
 baseline=ROOT/meta['referenceDirectory'];unchanged={name:sha(folder/name)==sha(baseline/name) for name in ['rangers.json','abilities.json','official-locales.json','custom-locales.json']}
 unchanged['equipment.json']=sha(folder/'equipment.json')==sha(ROOT/'data/research/external-reference/equipment.json')
 features={'skills':('skillSet','list'),'abilities':('abilityCodes','list'),'awakening':('awakeningAbilities','list'),'talents':('talents','object')}
 character_rows=[]
 for n in chars['records']:
  code=n['characterId'];r=by_id.get(code);d=details.get(code);mismatch=[]
  if r:
   for field,x,y in [('starCount',n['starCount'],r['starGrade']),('roleType',n['unitCategory'],r['roleType']),('elementType',(n['unitElement'] or '').upper(),r['elementType'])]:
    if x!=y:mismatch.append(field)
  states={key:availability(r,field,kind) if r and not mismatch else 'unknown' for key,(field,kind) in features.items()}
  talent=native.get(code,{}).get('talents',{}).get('status');native_talent='absent' if talent=='not_configured' else 'present' if talent=='verified-native-group' else 'unknown'
  character_rows.append({'characterId':code,'name':n['name'],'referenceListed':r is not None,'identityDifferences':mismatch,'storedDetailStatus':d.get('status') if d else 'not_acquired',
   'referenceAvailability':states,'nativeTalentAvailability':native_talent,'nativePrimarySkillPresent':bool(n.get('primarySkillCode')),'nativePrimaryAbilityPresent':bool(n.get('primaryAbilityCode'))})
 gear_features={'normal':('normalOptions','list'),'advanced':('highLevelOptions','object'),'skillPlus':('skillPlus','list'),'specPlus':('specPlus','object')}
 gear_rows=[]
 for n in equipment['records']:
  r=by_gear.get(n['itemCode']);match=bool(r and r['starGrade']==n['starCount'] and r['equipType']==n['equipType'])
  gear_rows.append({'itemCode':n['itemCode'],'identityMatch':match,'referenceAvailability':{key:availability(r,field,kind) if match else 'unknown' for key,(field,kind) in gear_features.items()}})
 summary={'localCharacters':len(character_rows),'referenceCharacters':len(refs),'matchedCharacters':sum(r['referenceListed'] and not r['identityDifferences'] for r in character_rows),
  'charactersNotListed':[r['characterId'] for r in character_rows if not r['referenceListed']],'characterIdentityConflicts':[r for r in character_rows if r['identityDifferences']],
  'referenceOnlyIds':sorted(set(by_id)-{r['characterId'] for r in character_rows}),
  'characterSections':{k:dict(Counter(r['referenceAvailability'][k] for r in character_rows)) for k in features},
  'nativeTalentSections':dict(Counter(r['nativeTalentAvailability'] for r in character_rows)),
  'unnamedCharacters':sum(r['name'] is None for r in character_rows),'localEquipment':len(gear_rows),'equipmentIdentityMatches':sum(r['identityMatch'] for r in gear_rows),
  'equipmentSections':{k:dict(Counter(r['referenceAvailability'][k] for r in gear_rows)) for k in gear_features},
  'nativeReferenceTalentConflicts':[r['characterId'] for r in character_rows if r['referenceListed'] and r['referenceAvailability']['talents']!=r['nativeTalentAvailability']]}
 report={'checkedAt':datetime.now(timezone.utc).isoformat(),'referenceDirectory':folder.relative_to(ROOT).as_posix(),'referenceManifestSha256':sha(folder/'manifest.json'),
  'nativeDocumentSha256':sha(ROOT/'data/normalized/verified-characters.json'),'acceptedCharacterDetailSource':sid,'acceptedNativeSource':nid,'comparedReferenceBytesUnchanged':unchanged,
  'summary':summary,'characters':character_rows,'equipment':gear_rows,'rules':{'explicitEmptyList':'absent','explicitNullObject':'absent','missingKeyOrUnlistedId':'unknown','nativeEmptyTalentGroup':'absent','emptyPrimarySkillDoesNotProveAllSkillsAbsent':True,'playerInstancesAreNotTemplateAbsence':True}}
 (ROOT/'reports/reference-availability-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 print(json.dumps({k:v for k,v in report.items() if k in ['referenceDirectory','comparedReferenceBytesUnchanged']}|{'summary':{k:v for k,v in summary.items() if not isinstance(v,list)}},ensure_ascii=False),flush=True)
 return report


if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--fetch',action='store_true');parser.add_argument('--directory',type=Path);args=parser.parse_args()
 if not args.fetch and not args.directory:parser.error('--fetch or --directory is required')
 audit(fetch() if args.fetch else args.directory)
