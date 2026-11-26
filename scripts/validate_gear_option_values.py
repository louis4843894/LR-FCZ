"""Rebuild option values from immutable copies; compare the previous baseline."""
import ctypes,hashlib,json,math,sqlite3,struct,sys
from datetime import datetime,timezone
from local_game_database import ROOT,DEFAULT_DB
from derive_guildwar_gear_values import build
from native_gear_option_values import interpolate,reinforced
from parse_gear_option_definitions import read

PREVIOUS='guild-gear-rolls-b8082cf3e6b7c0f231750e27'


def validate():
 doc=build()
 with sqlite3.connect(DEFAULT_DB.resolve().as_uri()+'?mode=ro',uri=True) as db:
  old={k:json.loads(p) for k,p in db.execute('SELECT observation_id,payload FROM gear_instance_rolls WHERE source_id=?',(PREVIOUS,))}
  option=read(db)
  definition=json.loads(db.execute("SELECT s.payload FROM current_gear_definitions c JOIN gear_definition_sources s USING(source_id) WHERE scope='ordinary-gearstat'").fetchone()[0])
  active=db.execute("SELECT source_id FROM current_gear_rolls WHERE scope='guildwar'").fetchone()[0]
 if not old or len(old)!=len(doc['records']):raise ValueError('previous complete baseline unavailable')
 unchanged=0;resolved=0;types=set();samples=[];native_comparisons=0
 # Windows' existing C runtime provides an independent IEEE float FMADD.
 native=ctypes.CDLL('ucrtbase').fmaf;native.argtypes=[ctypes.c_float]*3;native.restype=ctypes.c_float
 definitions={r['attributeId']:r for r in definition['records']}
 for record in doc['records']:
  before=old.get(record['observationId'])
  if not before or before['entries']!=record['entries']:raise ValueError('previous ordinary/conditional/Skill+ values changed')
  for field in ['equipmentId','enhancement','instanceGrade','equipmentInstanceHash','sourceObservationSha256']:
   if before[field]!=record[field]:raise ValueError('actual equipment association changed')
  unchanged+=len(record['entries']);extra=record.get('supplementarySpecial')
  if not extra:continue
  if extra['state']!='values_reconstructed' or extra['unresolvedParameterIndexes'] or '{$' in extra['description'] or '%'+'s' in extra['normalText']:raise ValueError('special description not fully reconstructed')
  raw=extra['rawFields'];special=option['tables']['options'][raw['specialOptionCode']];base=definitions[special['normalAttrNo']]
  values=[(base['minValueRaw'],base['maxValueRaw'],raw['specialOptionAttrValueGrade'],base['valueDivideGrades'],special['normalAttrEnchantIncrease'])]
  for talent in option['tables']['talents']:
   if talent['equipTalentCode']!=special['equipTalentCode']:continue
   for prefix in ['buffFactor','subBuffFactor']:
    values.append((talent[prefix+'Min'],talent[prefix+'Max'],raw['specialOptionTalentValueGrade'],special['equipTalentValueDivideGrades'],talent[prefix+'EnchantIncrease']))
  for lo,hi,grade,steps,inc in values:
   a=reinforced(lo,hi,grade,steps,inc,raw['currentSpecialEnchant']);b=native(inc,raw['currentSpecialEnchant'],interpolate(lo,hi,grade,steps))
   if struct.pack('<f',a)!=struct.pack('<f',b):raise ValueError('special float result differs from native fmaf')
   native_comparisons+=1
  resolved+=1;code=raw['specialOptionCode']
  if code not in types and len(samples)<4:
   samples.append({'equipmentId':record['equipmentId'],'specialOptionCode':code,'specialEnchant':raw['currentSpecialEnchant'],
                   'name':extra['name'],'normalText':extra['normalText'],'description':extra['description'],'visuallyVerified':False})
  types.add(code)
 report={'verifiedAt':datetime.now(timezone.utc).isoformat(),'sourceId':doc['sourceId'],'definitionSourceId':option['sourceId'],
         'activeSourceMatchesRebuild':active==doc['sourceId'],'previousValuesUnchanged':unchanged,'specialInstancesReconstructed':resolved,
         'deployedSpecialInstances':doc['summary'].get('deployedReconstructedSpecialEquipment',0),'savedConfigurationSpecialInstances':doc['summary'].get('savedReconstructedSpecialEquipment',0),
         'specialTypesObserved':len(types),'nativeFmafComparisons':native_comparisons,'nativeFmafMismatches':0,
         'unresolvedDisplayPlaceholders':0,'combatActivationVerified':False,'duplicateOptionPriorityVerified':False,'visuallyVerified':False,
         'externalReferenceValuesUsed':False,'samples':samples}
 (ROOT/'reports/guildwar-special-option-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 return report


if __name__=='__main__':print(json.dumps(validate(),ensure_ascii=False))
