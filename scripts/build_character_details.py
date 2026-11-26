"""Match public reference details to native templates; never change native fields.

Skill/ability prose prefers the saved local lang_unit translations. Structured
detail values retain external-reference provenance and are template values,
not a player's trained/equipped/awakened state.
"""
import argparse,hashlib,json,math,re,sqlite3
from collections import Counter
from pathlib import Path
from contextlib import closing
from local_game_database import ROOT,DEFAULT_DB,connect,encoded,stamp
from build_equipment_reference_preview import ReferenceLabels
from template_availability import availability

VERSION='native-matched-character-details-v3-availability'
SCOPE='native-matched-reference'
SCHEMA='''
CREATE TABLE IF NOT EXISTS character_detail_sources(source_id TEXT PRIMARY KEY,native_document_sha256 TEXT NOT NULL,payload TEXT NOT NULL CHECK(json_valid(payload)));
CREATE TABLE IF NOT EXISTS current_character_details(scope TEXT PRIMARY KEY,source_id TEXT NOT NULL REFERENCES character_detail_sources(source_id));
CREATE TABLE IF NOT EXISTS character_template_details(source_id TEXT NOT NULL REFERENCES character_detail_sources(source_id),character_id TEXT NOT NULL,status TEXT NOT NULL,payload TEXT NOT NULL CHECK(json_valid(payload)),PRIMARY KEY(source_id,character_id));
'''
LANG=ROOT/'data/research/runtime.private/guild-session-20261123/lang_unit.ndb'


def sha(raw):return hashlib.sha256(raw).hexdigest()
def clean(value):return re.sub(r'<[^>]*>','',re.sub(r'\\+n','\n',value)).strip()
def numeric(value,maximum=None):
 if value is None:return None
 if type(value) not in (int,float) or not math.isfinite(value) or (maximum is not None and not 0<=value<=maximum):raise ValueError('invalid character detail number')
 return value
def n(value):return format(numeric(value),'.8g')


class Labels:
 def __init__(self,folder,translation):
  self.catalog={};self.localKeys=set();self.missing=set();self.conflicts=set()
  with closing(sqlite3.connect(translation.resolve().as_uri()+'?mode=ro',uri=True)) as db:
   local=dict(db.execute("SELECT dataCode,msg FROM lang_unit WHERE language='zh-Hant'"))
  for filename in ['official-locales.json','custom-locales.json']:
   for row in json.loads((folder/filename).read_bytes()):
    key=row['key'];text=row.get('zh_TW')
    own=local.get(key.split(':',1)[-1]) if key.split(':',1)[0] in ('UNIT','SKILL','ABILITY') else None
    if own:
     self.localKeys.add(key)
     if text and re.sub(r'\s+','',clean(own))!=re.sub(r'\s+','',clean(text)):self.conflicts.add(key)
     text=own
    if text:self.catalog[key]=text
  self.renderer=ReferenceLabels(self.catalog)
 def keys(self,ref):
  if isinstance(ref,str):return [ref]
  if isinstance(ref,list):return [key for item in ref for key in self.keys(item)]
  if isinstance(ref,dict):
   result=[]
   for k,v in ref.items():
    if k in ('templateKey','key'):result+=self.keys(v)
    elif k=='parts':result+=self.keys(v)
    elif isinstance(v,list):result += [key for item in v if isinstance(item,(list,dict)) for key in self.keys(item)]
    elif isinstance(v,dict):result+=self.keys(v)
   return result
  return []
 def text(self,ref):
  if ref is None:return None
  keys=self.keys(ref);missing=[key for key in keys if key not in self.catalog]
  self.missing.update(missing)
  if missing:return None
  try:text=clean(self.renderer.render(ref))
  except ValueError:
   self.missing.add('<unsupported-text-reference>');return None
  if re.search(r'\{\$\d+[a-z]\}|%(?:N\d*|d\d*|s|n)',text):return None
  return text or None


def formula(value):
 op={'MULTIPLY':'×','ADD':'+','SUBTRACT':'−'}.get(value.get('operator'))
 if op is None or value.get('levelSource')!='LEVEL':return None
 return '角色等級 '+op+' '+n(value['amount'])+(' 秒' if value.get('unit')=='SECOND' else '')


def magnitude(value):
 if value is None:return None
 kind=value['kind']
 if kind=='statPercent':
  stat={'ATK':'攻擊力','SP_ATK':'魔法攻擊力','HP':'體力'}.get(value['stat'])
  return (stat+'的 '+n(value['percent'])+'%') if stat and value['operator']=='MULTIPLY' else None
 if kind in ('percent','flat'):
  sign={'INCREASE':'+','DECREASE':'−'}.get(value.get('direction'),'')
  return sign+n(value['value'])+('%' if kind=='percent' else '')
 if kind=='levelFormula':return formula(value)
 if kind=='summonLevel':return '召喚等級 '+n(value['level'])
 if kind=='points':return n(value['value'])+' 點'
 if kind=='gradeValue':return n(value['value'])+'（模板分級參數）'
 return None


def effect(row,labels):
 duration=row.get('duration');limit=row.get('targetLimit');trigger=row.get('effectTrigger');availability=row.get('availableIn') or {}
 if duration is None:duration_text=None
 elif duration['kind']=='levelFormula':duration_text=formula(duration)
 elif duration['kind'] in ('fixed','gradeCalculated'):duration_text=n(duration['seconds'])+' 秒'+('（依模板星級）' if duration['kind']=='gradeCalculated' else '')
 else:duration_text=None
 for key in ['events','guardian']:
  if availability.get(key) is not None and type(availability[key]) is not bool:raise ValueError('invalid effect availability')
 return {'effectCode':row['effectCode'],'name':labels.text('CUSTOM:'+row['effectCode']),
         'magnitude':row.get('magnitude'),'magnitudeText':magnitude(row.get('magnitude')),'duration':duration,'durationText':duration_text,
         'rangePoints':numeric(row.get('rangePoints')),'triggerChancePercent':numeric(trigger['percent'],100) if trigger and trigger.get('kind')=='chance' else None,
         'targetLimitText':('無上限' if limit['kind']=='unlimited' else n(limit['maxTargets'])+' 個') if limit else None,
         'availableEvents':availability.get('events'),'availableGuardian':availability.get('guardian')}


def skill(row,labels):
 trigger=row.get('trigger') or {};kind=trigger.get('type');ratio=numeric(trigger.get('searchRatio'))
 title=labels.text(row.get('nameKey'));description=labels.text(row.get('descriptionKey'))
 conflicts=[k for k in labels.keys(row.get('descriptionKey')) if k in labels.conflicts]
 return {'skillCode':row['skillCode'],'name':title,'description':description,'textSource':'local-translation' if row.get('descriptionKey') in labels.localKeys else 'user-confirmed-reference',
         'status':'description_conflict' if conflicts else 'matched-reference','activationRatePercent':None if conflicts else numeric(row.get('activationRate'),100),
         'cooldownSeconds':None if conflicts else numeric(row.get('cooldownSeconds')),
         'triggerType':kind,'searchRatio':ratio,'triggerLabel':{'SELF':'自身','SEARCH':'前方敵人','RSEARCH':'後方敵人'}.get(kind),
         'effects':[] if conflicts else [effect(e,labels) for e in row.get('effects',[])]}


def ability(code,definitions,labels):
 row=definitions.get(code)
 if row is None:return {'abilityCode':code,'status':'definition_missing','name':None,'description':None,'triggerEffects':None}
 conflicts=[k for k in labels.keys(row.get('descriptionKey')) if k in labels.conflicts]
 return {'abilityCode':code,'status':'description_conflict' if conflicts else 'matched-reference','name':labels.text(row.get('nameKey')),
         'description':labels.text(row.get('descriptionKey')),'textSource':'local-translation' if row.get('descriptionKey') in labels.localKeys else 'user-confirmed-reference',
         'triggerEffects':None if conflicts else [{'chancePercent':numeric(t.get('chancePercent'),100),'phase':labels.text(t.get('triggerPhaseKey')),
           'battleMode':labels.text(t.get('battleModeKey')),'condition':labels.text(t.get('conditionKey')),
           'additionalCondition':labels.text(t.get('additionalConditionKey')),'effect':labels.text(t.get('effectKey')),
           'effectCode':t.get('effectCode'),'effectFactor':numeric(t.get('effectFactor')),'effectSubFactor':numeric(t.get('effectSubFactor'))} for t in row.get('triggerEffects',[])]}


def talents(row,labels):
 if row is None:return None
 major=row.get('major');result={'major':None,'enhancements':[]}
 if major:
  result['major']={'talentCode':major['talentCode'],'abilityCode':major.get('abilityCode'),'description':labels.text(major.get('descriptionKey')),
                   'activationChancePercent':numeric(major.get('activationChancePercent'),100),'condition':labels.text(major.get('activationConditionKey')),
                   'additionalConditions':[labels.text(c.get('text') or c.get('textKey') or c) if isinstance(c,dict) else labels.text(c) for c in major.get('additionalConditions',[])],
                   'effects':[{'effectCode':e['effectCode'],'description':labels.text(e.get('localizedEffect')),'factor':numeric(e.get('factor')),
                     'durationSeconds':numeric(e.get('durationSeconds')),'activationChancePercent':numeric(e.get('activationChancePercent'),100)} for e in major.get('effects',[])]}
 result['enhancements']=[{'talentCode':e['talentCode'],'effectCode':e['effectCode'],'value':numeric(e.get('value')),'unit':e.get('unit'),
                          'description':labels.text(e.get('localizedEffect'))} for e in row.get('enhancements',[])]
 return result


def build(folder,native_path=ROOT/'data/normalized/verified-characters.json',translation=LANG,startup_folder=None):
 folder=Path(folder).resolve();manifest_bytes=(folder/'datasets-source.json').read_bytes();manifest=json.loads(manifest_bytes)
 if manifest.get('sourceKind')!='external-user-confirmed' or manifest.get('localVerification') is not False:raise ValueError('unverified reference kind')
 for row in manifest['files']:
  if Path(row['file']).name!=row['file'] or sha((folder/row['file']).read_bytes())!=row['sha256']:raise ValueError('reference file hash differs')
 native_bytes=Path(native_path).read_bytes();native=json.loads(native_bytes)
 if native.get('sourceKind')!='verified-character-template' or native.get('localVerification') is not True:raise ValueError('verified native character source required')
 reference=json.loads((folder/'rangers.json').read_bytes());ability_data=json.loads((folder/'abilities.json').read_bytes())
 if reference.get('schemaVersion')!=2 or ability_data.get('schemaVersion')!=2:raise ValueError('reference schema differs')
 refs={r['rangerCode']:r for r in reference['rangers']};defs={r['abilityCode']:r for r in ability_data['abilities']}
 if len(refs)!=len(reference['rangers']) or len(defs)!=len(ability_data['abilities']):raise ValueError('duplicate character/ability identity')
 labels=Labels(folder,translation);records=[];summary=Counter();conflicts=[]
 startup_units={};startup_source=None
 if startup_folder is not None:
  from character_skill_startup import load_startup
  startup_units,startup_source=load_startup(startup_folder)
 for native_row in native['records']:
  code=native_row['characterId'];ref=refs.get(code)
  row={'characterId':code,'status':'not_in_reference','skills':None,'abilities':None,'awakeningAbilities':None,'talents':None,'stats':None,
       'evolution':None,'releaseDate':None,'associationEvidence':None,
       'availability':{key:'unknown' for key in ['skills','abilities','awakening','talents']}}
  mismatches=[]
  if ref:
   for field,x,y in [('stars',native_row['starCount'],ref['starGrade']),('role',native_row['unitCategory'],ref['roleType']),('element',(native_row['unitElement'] or '').upper(),ref['elementType'])]:
    if x!=y:mismatches.append(field)
   if native_row['primarySkillCode'] and native_row['primarySkillCode'] not in [s['skillCode'] for s in ref['skillSet']]:mismatches.append('primarySkillCode')
   if native_row['primaryAbilityCode'] and native_row['primaryAbilityCode'] not in ref['abilityCodes']:mismatches.append('primaryAbilityCode')
   if mismatches:row['status']='identity_conflict';conflicts.append({'characterId':code,'fields':mismatches})
   else:
    row.update(status='matched-reference',skills=[skill(s,labels) for s in ref['skillSet']],abilities=[ability(c,defs,labels) for c in ref['abilityCodes']],
               # chancePercent on an awakening candidate has no established
               # runtime meaning. Never display it as an ability trigger rate.
               awakeningAbilities=[{**ability(a['abilityCode'],defs,labels),'candidateProbabilityRaw':a.get('chancePercent'),'probabilityMeaning':'unverified'} for a in ref['awakeningAbilities']] if isinstance(ref.get('awakeningAbilities'),list) else None,
               talents=talents(ref.get('talents'),labels),stats=ref.get('stats'),evolution=ref.get('evolution'),releaseDate=ref.get('releaseDate'),
               associationEvidence={'starsTypeElementMatch':True,'primarySkillMatched':bool(native_row['primarySkillCode']),'primaryAbilityMatched':bool(native_row['primaryAbilityCode'])})
    row['availability']={key:availability(ref,field,kind) for key,field,kind in [('skills','skillSet','list'),('abilities','abilityCodes','list'),('awakening','awakeningAbilities','list'),('talents','talents','object')]}
    for key,state in row['availability'].items():summary[key+'_'+state]+=1
    if startup_source is not None:
     from character_skill_startup import startup_for
     for i,s in enumerate(row['skills']):
      timing=startup_for(startup_units,code,i)
      s['startupSeconds']=timing['seconds'] if timing else None;s['startupEvidence']=timing
      summary['skillsWithStartup']+=timing is not None
     summary['charactersWithStartup']+=any(s.get('startupSeconds') is not None for s in row['skills'])
    summary['matchedCharacters']+=1
    for field in ['skills','abilities','awakeningAbilities','talents','stats']:
     if row[field]:summary[field+'Characters']+=1
    summary['skills']+=len(row['skills']);summary['skillEffects']+=sum(len(s['effects']) for s in row['skills'])
    summary['abilities']+=len(row['abilities']);summary['awakeningCandidates']+=len(row['awakeningAbilities'] or [])
  records.append(row);summary[row['status']]+=1
 summary['nativeCharacters']=len(records);summary['referenceCharacters']=len(refs);summary['textConflicts']=len(labels.conflicts);summary['missingTextKeys']=len(labels.missing)
 doc={'schemaVersion':1,'parserVersion':VERSION,'sourceKind':'native-matched-user-confirmed-character-details','localNumericVerification':False,
      'nativeDocumentSha256':sha(native_bytes),'nativeGameVersion':native.get('gameVersion'),'retrievedAt':manifest['retrievedAt'],
      'referenceDirectory':folder.relative_to(ROOT).as_posix(),'referenceManifestSha256':sha(manifest_bytes),'localTranslationSha256':sha(translation.read_bytes()),
      'summary':dict(summary),'conflicts':conflicts,'missingTextKeys':sorted(labels.missing),'referenceOnlyIds':sorted(set(refs)-{r['characterId'] for r in records}),
      'templateOnly':True,'playerTrainingOrEquipmentApplied':False,'awakeningCandidatesAreNotPlayerAwakening':True,'records':records}
 doc['index']={r['characterId']:{'status':r['status'],'skillCount':len(r['skills']) if r['skills'] is not None else None,
               'abilityCount':len(r['abilities']) if r['abilities'] is not None else None,'awakeningCount':len(r['awakeningAbilities']) if r['awakeningAbilities'] is not None else None,
               'talentsAvailable':r['talents'] is not None,'availability':r['availability']} for r in records}
 if startup_source is not None:
  doc['startupSource']={**startup_source,'directory':Path(startup_folder).resolve().relative_to(ROOT).as_posix()}
  doc['parserVersion']='native-matched-character-details-v3-startup-availability'
 doc['sourceId']='character-details-'+sha(encoded(doc).encode())[:24];return doc


def save(doc,database=DEFAULT_DB):
 folder=ROOT/'data/research/runtime.private/character-detail-exports'/doc['sourceId'];folder.mkdir(parents=True,exist_ok=True)
 output=folder/'details.private.json';raw=(encoded(doc)+'\n').encode()
 if output.exists() and output.read_bytes()!=raw:raise ValueError('immutable character details export differs')
 if not output.exists():output.write_bytes(raw)
 db=connect(database);db.executescript(SCHEMA)
 try:
  with db:
   accepted=db.execute("SELECT sha256 FROM current_documents WHERE filename='verified-characters.json'").fetchone()
   if not accepted or accepted[0]!=doc['nativeDocumentSha256']:raise ValueError('native character snapshot changed before activation')
   db.execute('INSERT OR IGNORE INTO character_detail_sources VALUES (?,?,?)',(doc['sourceId'],doc['nativeDocumentSha256'],encoded({k:v for k,v in doc.items() if k!='records'})))
   db.executemany('INSERT OR IGNORE INTO character_template_details VALUES (?,?,?,?)',[(doc['sourceId'],r['characterId'],r['status'],encoded(r)) for r in doc['records']])
   db.execute('INSERT INTO current_character_details VALUES (?,?) ON CONFLICT(scope) DO UPDATE SET source_id=excluded.source_id',(SCOPE,doc['sourceId']))
 finally:db.close()


if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--reference',type=Path,required=True);p.add_argument('--startup',type=Path);p.add_argument('--apply',action='store_true');a=p.parse_args();doc=build(a.reference,startup_folder=a.startup)
 if a.apply:save(doc)
 report={k:v for k,v in doc.items() if k!='records'}
 (ROOT/'reports/character-detail-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 print(json.dumps({'sourceId':doc['sourceId'],'summary':doc['summary'],'saved':a.apply},ensure_ascii=False))
