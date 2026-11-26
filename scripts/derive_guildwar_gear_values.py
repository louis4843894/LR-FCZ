"""Offline native gear values, bound to actual guild-war tower observations.

Uses reviewed copies and native definitions. Ordinary, conditional and Skill+
branches have separate parameters; never substitutes external template ranges.
"""
import argparse,json,sqlite3,hashlib,struct,math
from collections import Counter
from contextlib import closing
from pathlib import Path
from local_game_database import ROOT,DEFAULT_DB,connect,encoded,stamp
from native_layouts import NEW_SHA
from guild_war_database import parse_directory
from derive_http_gear_values import SCHEMA,digest,instance_hash,reconstruct,calibrated_inputs,matching_roll_entry
from parse_gear_special_definitions import read as read_special_definitions
from native_gear_special_values import conditional_scalar,skill_scalar
from native_elf import NativeELF
from parse_gear_option_definitions import read as read_option_definitions
from native_gear_option_values import reconstruct as reconstruct_option

SCOPE='guildwar'
KIND='calibrated-native-definition-guildwar-rolls'

def observation_id(doc,tower,owner,team,unit,slot):
 return digest(['guildwar',doc['sourceId'],tower,owner,team['teamNo'],unit['position'],slot])

def observations(doc):
 if doc['kind']=='deployed_defense':
  for tower in doc['towers']:
   if tower['readState']!='success':continue
   for defender in tower.get('defenders') or []:
    for team in defender['teams']:
     for unit in team['units']:
      for slot,gear in unit['equipment'].items():yield tower['code'],defender['playerId'],team,unit,slot,gear
 elif doc['kind']=='saved_configuration':
  for team in doc['teams']:
   for unit in team['units']:
    for slot,gear in unit['equipment'].items():yield None,doc['playerId'],team,unit,slot,gear

def matching_value(record,owner,gear,entry):
 if gear.get('ownerAssociationStatus')!='verified-native':return None
 if entry.get('sourceField')=='skillPlusAttr1No':
  if not record or record['equipmentId']!=gear['equipmentId'] or record['enhancement']!=gear.get('enhancement') or record['instanceGrade']!=gear.get('instanceGrade') or record['equipmentInstanceHash']!=instance_hash(owner,gear.get('equipmentInstanceIdentity')):return None
  return next((a for a in record['entries'] if all(a.get(k)==entry.get(k) for k in ['index','attributeId','valueGradeRaw','sourceField']) and a.get('calculationKind')=='native-skillplus' and a.get('valueVerified') is True and a.get('enhancementIncluded') is True and type(a.get('value')) in (int,float) and math.isfinite(a['value']) and a.get('unit') in ('PERCENT','FLAT','SECOND')),None)
 return matching_roll_entry(record,{'playerId':owner},None,None,gear,entry)

def read_rolls(db):
 if not db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='gear_roll_sources'").fetchone():return None,{}
 row=db.execute("SELECT s.source_id,s.payload FROM current_gear_rolls c JOIN gear_roll_sources s USING(source_id) WHERE scope=?",(SCOPE,)).fetchone()
 if not row:return None,{}
 meta=json.loads(row[1]);proof=meta.get('calibration') or {}
 if (meta.get('sourceKind')!=KIND or meta.get('moduleSha256')!=NEW_SHA or meta.get('externalReferenceValuesUsed') is not False
     or type(proof.get('screenCheckedGearCount')) is not int or proof['screenCheckedGearCount']<2
     or type(proof.get('screenCheckedValueCount')) is not int or proof['screenCheckedValueCount']<6):raise ValueError('guild roll calibration unverified')
 return row[0],{key:json.loads(payload) for key,payload in db.execute('SELECT observation_id,payload FROM gear_instance_rolls WHERE source_id=?',(row[0],))}

def raw_parameters(doc):
 """Only the accepted tower owner's actual equipment fields, from saved copies."""
 folder=ROOT/doc['sourceDirectory'];result={}
 if doc['kind']=='deployed_defense':
  groups=[]
  for tower in doc['towers']:
   if tower['readState']!='success':continue
   copy=json.loads((folder/f"tower-{doc['side']}-{tower['code']}.private.json").read_bytes())
   for row in copy['result']['guildWarDefenceDeckResponses']:
    groups.append((tower['code'],row['mergedGuildPlayer']['uid'],row['deckInfo']['playerUnitTeams']))
 elif doc['kind']=='saved_configuration':
  source=json.loads((folder/'bootstrap.private.json').read_bytes());deck=source['savedDeck']['deckInfoJson']
  groups=[(None,doc['playerId'],json.loads(deck)['playerUnitTeams'])]
 else:return result
 for tower,owner,teams in groups:
  for team,units in teams.items():
   for unit in units:
    for native,slot in [('WEAPON','weapon'),('ARMOR','armor'),('ACC','accessory')]:
     gear=(unit.get('equipMap') or {}).get(native)
     if gear:
      key=(tower,owner,int(team),unit['slot'],slot)
      if key in result:raise ValueError('duplicate actual guild equipment parameters')
      result[key]=gear
 return result

def build(database=DEFAULT_DB):
 with closing(sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro',uri=True)) as db:
  db.execute('BEGIN')
  definition=json.loads(db.execute("SELECT s.payload FROM current_gear_definitions c JOIN gear_definition_sources s USING(source_id) WHERE scope='ordinary-gearstat'").fetchone()[0])
  document=json.loads(db.execute("SELECT d.payload FROM current_documents c JOIN documents d USING(sha256) WHERE c.filename='defense-teams.private.json'").fetchone()[0])
  http_sources={r[0] for r in db.execute('SELECT capture_id FROM pvp_http_sources')}
  wars=[json.loads(r[0]) for r in db.execute('SELECT s.payload FROM current_guild_war_sources c JOIN guild_war_sources s USING(source_id) ORDER BY s.source_id')]
  special=read_special_definitions(db)
  skill_upgrades=read_special_definitions(db,'native-skill-upgrades')
  options=read_option_definitions(db)
 manifest=(ROOT/definition['captureDirectory']/'capture.json').read_bytes()
 if definition.get('moduleSha256')!=NEW_SHA or definition.get('sourceKind')!='verified-native-gear-definitions' or hashlib.sha256(manifest).hexdigest()!=definition['captureManifestSha256']:raise ValueError('native definitions differ')
 rebuilt={}
 option_labels={};option_proof=None
 if options:
  elf=NativeELF(ROOT/'data/research/runtime.private/modules/libgame-12.4.2-pull.so')
  if elf.sha256!=NEW_SHA or elf.ptr(0x1e98ce8+0x288)!=0x121c9f8 or elf.ptr(0x1e99700+0x100)!=0x1231bd4:raise ValueError('special option native input proof differs')
  float_report=(ROOT/'reports/ghidra/gear-special-option-float-1242.txt').read_text(encoding='utf8')
  if not all(x in float_report for x in ['122e3bc fmadd','122ea18 fmadd','122e7c0 fmadd']):raise ValueError('special option float proof missing')
  translation=ROOT/'data/extracted/lr_20261116T212608096_7b99bdd0/assets/res/tutorial_res/db/lang_equip/lang_equip.ndb'
  with sqlite3.connect(translation.resolve().as_uri()+'?mode=ro',uri=True) as language:
   for row in options['tables']['options'].values():
    for key in ['titleLangCode','normalDescLangCode','specialDescLangCode']:
     found=language.execute("SELECT msg FROM lang_equip WHERE language='zh-Hant' AND dataCode=?",(row[key],)).fetchone()
     if found:option_labels[row[key]]=found[0]
  reports=['gear-special-option-talent-definitions-1242.txt','gear-special-option-instance-inputs-1242.txt','gear-special-option-format-and-enchant-1242.txt','gear-special-option-float-1242.txt','actual-attribute-core-1242.txt','guild-gear-conditional-json-and-skill-render-1242.txt']
  option_proof={'normalFunction':'0122e270','talentDescriptionFunction':'0122e690','placeholderFormatter':'0122c704',
                'specialEnchantGetter':'0121c9f8','sourceFields':['specialOptionCode','specialOptionAttrValueGrade','specialOptionTalentValueGrade','currentSpecialEnchant'],
                'reports':{name:hashlib.sha256((ROOT/'reports/ghidra'/name).read_bytes()).hexdigest() for name in reports},
                'translationSha256':hashlib.sha256(translation.read_bytes()).hexdigest(),'activationVerified':False,'visuallyVerified':False}
 for doc in wars:
  directory=doc['sourceDirectory']
  if directory not in rebuilt:rebuilt[directory]={d['sourceId']:d for d in parse_directory(ROOT/directory)}
  if rebuilt[directory].get(doc['sourceId'])!=doc:raise ValueError('guild-war immutable copy differs')
 base,allowed,proof=calibrated_inputs(definition,document,http_sources)
 records=[];counts=Counter();seen=set();definitions={r['attributeId']:r for r in definition['records']};codes={};skill_labels={};skill_proof=None
 if special:
  instruction_report=ROOT/'reports/ghidra/guild-conditional-float-instructions-1242.txt'
  assembly=instruction_report.read_text(encoding='utf8')
  if 'f45304 movi d0,#0x0' not in assembly or '122e194 fmadd s0,s8,s0,s9' not in assembly:raise ValueError('conditional float/missing-key proof incomplete')
  elf=NativeELF(ROOT/'data/research/runtime.private/modules/libgame-12.4.2-pull.so')
  if elf.sha256!=NEW_SHA:raise ValueError('conditional module differs')
  for kind in range(1,46):
   relative=struct.unpack_from('<i',elf.data,elf.offset(0x85611c+(kind-1)*4))[0];codes[kind]=elf.cstring(0x85611c+relative)
  if skill_upgrades:
   if elf.cstring(0x7fdf68)!='SKILL_PLUS_%d_nm' or elf.cstring(0x7fdd77)!='%d_%d':raise ValueError('Skill+ keys differ')
   # Do not infer an operator sign from English labels; read the formatter's
   # actual string table. ADD/MUL have +, SUB/DIV have -.
   operators=[elf.cstring(0x856058+struct.unpack_from('<i',elf.data,elf.offset(0x856058+i*4))[0]) for i in range(5)]
   if operators[1:]!=['+','-','+','-']:raise ValueError('Skill+ operator signs differ')
   translation=ROOT/'data/extracted/lr_20261116T212608096_7b99bdd0/assets/res/tutorial_res/db/lang_equip/lang_equip.ndb'
   with sqlite3.connect(translation.resolve().as_uri()+'?mode=ro',uri=True) as language:
    for key in special['tables']['skillplus']:
     found=language.execute("SELECT msg FROM lang_equip WHERE language='zh-Hant' AND dataCode=?",(f'SKILL_PLUS_{key}_nm',)).fetchone()
     if found:skill_labels[int(key)]=found[0].replace('\\\\n',' ').replace('\\n',' ')
   reports=['guild-skillplus-name-grade-and-upgrade-1242.txt','guild-skillplus-float-instructions-1242.txt','guild-skillplus-instance-factory-1242.txt','guild-gear-conditional-json-and-skill-render-1242.txt']
   skill_proof={'formulaFunction':'0122ed7c','formatterFunction':'0122f11c','nameFunction':'01230e34','currentPlayersVisuallyVerified':False,
    'reports':{name:hashlib.sha256((ROOT/'reports/ghidra'/name).read_bytes()).hexdigest() for name in reports},'translationSha256':hashlib.sha256(translation.read_bytes()).hexdigest(),'operators':operators}
 for doc in wars:
  parameters=raw_parameters(doc) if special else {}
  for tower,owner,team,unit,slot,gear in observations(doc):
   prefix='deployed' if doc['kind']=='deployed_defense' else 'saved'
   counts[prefix+'Slots']+=1
   if gear['state']!='equipped':
    counts[prefix+'_'+gear['state']]+=1;continue
   counts[prefix+'Equipment']+=1;entries=[]
   source=parameters.get((tower,owner,team['teamNo'],unit['position'],slot))
   supplementary=None
   if source and source.get('specialOptionCode') not in (None,'','none','NONE'):
    if not gear.get('equipmentInstanceIdentity') or str(source['invenId'])!=gear['equipmentInstanceIdentity']['value'] or source['itemCode']!=gear['equipmentId']:raise ValueError('special observation instance differs')
    supplementary={'state':'observed_unparsed','rawFields':{k:source[k] for k in ['specialOptionCode','specialOptionAttrValueGrade','specialOptionTalentValueGrade','currentSpecialEnchant'] if k in source}}
    option=options['tables']['options'].get(source['specialOptionCode']) if options else None
    normal=definitions.get(option['normalAttrNo']) if option else None
    if option and normal:
     decoded=reconstruct_option(option,options['tables']['talents'],normal,source,option_labels)
     if decoded:supplementary.update(decoded)
    counts[prefix+('ReconstructedSpecialEquipment' if supplementary['state']=='values_reconstructed' else 'UnparsedSpecialEquipment')]+=1
   for entry in (gear.get('actualEffects') or {}).get('entries',[]):
    counts[prefix+'EffectEntries']+=1;attr=entry['attributeId']
    is_skill=entry.get('sourceField')=='skillPlusAttr1No' and special and skill_upgrades and str(attr) in special['tables']['skillplus']
    if not is_skill and (entry.get('sourceField') not in [f'attr{i}No' for i in range(1,6)] or attr not in base):
     counts[prefix+'UnknownValues']+=1;continue
    if gear.get('ownerAssociationStatus')!='verified-native' or not gear.get('equipmentInstanceIdentity'):
     counts[prefix+'UnknownValues']+=1;continue
    result=reconstruct(base[attr],entry['valueGradeRaw'],gear.get('enhancement'),definition['coefficient']) if not is_skill and attr in allowed else None
    if result is None and special:
     if source:
      if (str(source['invenId'])!=gear['equipmentInstanceIdentity']['value'] or source['itemCode']!=gear['equipmentId'] or source['currentEnchant']!=gear['enhancement']
          or source[entry['sourceField']]!=attr or source[entry['sourceField'].replace('No','ValueGrade')]!=entry['valueGradeRaw']):raise ValueError('actual conditional instance differs')
      if is_skill:
       result=skill_scalar(special['tables']['skillplus'][str(attr)],entry['valueGradeRaw'],source.get('currentSkillPlusEnchant'),skill_upgrades['tables']['skillupgrades'])
       if result:
        result['labelTemplate']=skill_labels.get(attr);counts[prefix+'SkillPlusValues']+=1
        if result['labelTemplate']:counts[prefix+'SkillPlusChineseLabels']+=1
      else:
       result=conditional_scalar(base[attr],definitions[attr],entry['valueGradeRaw'],source.get('currentAdvancedEnchant'),codes,special['tables']['increments'])
       if result:counts[prefix+'ConditionalValues']+=1
    if result is None:counts[prefix+'UnknownValues']+=1;continue
    entries.append({**{k:entry[k] for k in ['index','attributeId','valueGradeRaw','sourceField']},**result,
     'valueVerified':True,'valueVisuallyVerified':False,'definitionRecordSha256':special['tables']['skillplus'][str(attr)]['recordSha256'] if is_skill else hashlib.sha256(base[attr]).hexdigest()})
    counts[prefix+'ReconstructedValues']+=1
   key=observation_id(doc,tower,owner,team,unit,slot)
   if key in seen:raise ValueError('duplicate guild-war observation')
   seen.add(key)
   if entries or supplementary:records.append({'observationId':key,'equipmentId':gear['equipmentId'],'enhancement':gear['enhancement'],'instanceGrade':gear.get('instanceGrade'),
    'equipmentInstanceHash':instance_hash(owner,gear['equipmentInstanceIdentity']),'sourceObservationSha256':doc['sourceSha256'],
    'factorCapturedAt':definition['factorCapturedAt'],'entries':entries,'supplementarySpecial':supplementary})
 result={'schemaVersion':1,'sourceKind':KIND,'method':'native-definition-and-instance-grade-v1','moduleSha256':NEW_SHA,
  'definitionSourceId':definition['sourceId'],'specialDefinitionSourceId':special['sourceId'] if special else None,
  'skillUpgradeDefinitionSourceId':skill_upgrades['sourceId'] if skill_upgrades else None,'skillPlusProof':skill_proof,
  'optionDefinitionSourceId':options['sourceId'] if options else None,'optionProof':option_proof,
  'conditionalFloatReportSha256':hashlib.sha256(instruction_report.read_bytes()).hexdigest() if special else None,
  'warSources':sorted(d['sourceId'] for d in wars),'calibration':proof,'records':records,'summary':dict(counts),
  'coefficientCapturedAt':definition['factorCapturedAt'],'externalReferenceValuesUsed':False,'nativeObservationsOverwritten':False,'currentPlayersVisuallyVerified':False}
 result['sourceId']='guild-gear-rolls-'+digest(result)[:24]
 return result

def save(doc,database=DEFAULT_DB):
 folder=ROOT/'data/research/runtime.private/gear-roll-exports'/doc['sourceId'];folder.mkdir(parents=True,exist_ok=True)
 output=folder/'rolls.private.json';text=encoded(doc)+'\n'
 if output.exists() and output.read_text(encoding='utf8')!=text:raise ValueError('immutable guild roll export differs')
 db=connect(database);db.executescript(SCHEMA)
 try:
  with db:
   db.execute('BEGIN IMMEDIATE')
   current=sorted(r[0] for r in db.execute('SELECT source_id FROM current_guild_war_sources'))
   definition=db.execute("SELECT source_id FROM current_gear_definitions WHERE scope='ordinary-gearstat'").fetchone()[0]
   if current!=doc['warSources'] or definition!=doc['definitionSourceId']:raise ValueError('guild inputs changed; rebuild before activation')
   special=read_special_definitions(db)
   if (special['sourceId'] if special else None)!=doc.get('specialDefinitionSourceId'):raise ValueError('special definitions changed before activation')
   upgrades=read_special_definitions(db,'native-skill-upgrades')
   if (upgrades['sourceId'] if upgrades else None)!=doc.get('skillUpgradeDefinitionSourceId'):raise ValueError('Skill+ upgrades changed before activation')
   options=read_option_definitions(db)
   if (options['sourceId'] if options else None)!=doc.get('optionDefinitionSourceId'):raise ValueError('option definitions changed before activation')
   output.write_text(text,encoding='utf8')
   db.execute('INSERT OR IGNORE INTO gear_roll_sources VALUES (?,?,?)',(doc['sourceId'],stamp(),encoded({k:v for k,v in doc.items() if k!='records'})))
   db.executemany('INSERT OR IGNORE INTO gear_instance_rolls VALUES (?,?,?)',[(doc['sourceId'],r['observationId'],encoded(r)) for r in doc['records']])
   db.execute('INSERT INTO current_gear_rolls VALUES (?,?) ON CONFLICT(scope) DO UPDATE SET source_id=excluded.source_id',(SCOPE,doc['sourceId']))
 finally:db.close()
 return folder

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--apply',action='store_true');a=p.parse_args();doc=build()
 if a.apply:save(doc)
 report={k:v for k,v in doc.items() if k!='records'}
 (ROOT/'reports/guildwar-gear-values-reconstruction.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
 print(json.dumps({'sourceId':doc['sourceId'],'summary':doc['summary'],'saved':a.apply}))
