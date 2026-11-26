"""Special-option UI values: native 0122e270 / 0122e690 / 0122c704.

Uses actual special grades and currentSpecialEnchant. Does not model combat
activation, duplicate-option priority, or replace character skill parameters.
"""
import math,re
from parse_runtime_gear_values import f32,PERCENT_MASK


def interpolate(low,high,grade,steps):
 if type(grade) is not int or type(steps) is not int or not 1<=steps<=10000 or not 0<=grade<steps:raise ValueError('special grade outside definition')
 if not all(math.isfinite(v) for v in (low,high)):raise ValueError('nonfinite special range')
 return f32(low+f32(f32(f32(high-low)*f32(grade))/f32(max(1,steps-1))))


def reinforced(low,high,grade,steps,increment,level):
 if type(level) is not int or not 0<=level<=100 or not math.isfinite(increment):raise ValueError('special enhancement unverified')
 base=interpolate(low,high,grade,steps)
 # The final native instruction is FMADD; do not round its product first.
 return f32(float(increment)*float(level)+float(base))


def clean(text):
 return re.sub(r'<[^>]*>','',text).replace('\\n',' ').strip()


def render_description(template,parameters):
 missing=[]
 def replace(match):
  index=int(match[1])-1;kind=match[2]
  if index not in parameters:missing.append(index);return '（數值尚未解析）'
  value=parameters[index]
  if kind=='n':return str(math.trunc(value))
  if kind=='p':return format(f32(value*100.0),'.1f')+'%'
  return format(value,'.1f')
 text=re.sub(r'\{\$(\d+)([fnp])\}',replace,template)
 # Unknown format tokens must never leak as if they were resolved values.
 if '{$' in text:raise ValueError('unsupported special description placeholder')
 return clean(text),missing


def reconstruct(option,talents,normal,actual,labels):
 code=actual.get('specialOptionCode')
 if code!=option['specialOptionCode']:raise ValueError('special option identity differs')
 level=actual.get('currentSpecialEnchant');grade=actual.get('specialOptionAttrValueGrade');talent_grade=actual.get('specialOptionTalentValueGrade')
 if (type(level) is not int or not 0<=level<=100 or type(grade) is not int or not 0<=grade<normal['valueDivideGrades']
     or type(talent_grade) is not int or not 0<=talent_grade<option['equipTalentValueDivideGrades']):return None
 title=labels.get(option['titleLangCode']);normal_template=labels.get(option['normalDescLangCode']);special_template=labels.get(option['specialDescLangCode'])
 if not title or not normal_template or not special_template:return None
 if normal['attributeId']!=option['normalAttrNo'] or normal['selector1']!='none' or normal['selector2']!='none' or normal['hasDependency68'] or normal['hasDependency70']:raise ValueError('special normal definition unverified')
 value=reinforced(normal['minValueRaw'],normal['maxValueRaw'],grade,normal['valueDivideGrades'],option['normalAttrEnchantIncrease'],level)
 kind=normal['typeEnum']
 if type(kind) is not int or not 1<=kind<=45:raise ValueError('unverified special normal unit')
 percent=bool(PERCENT_MASK&(1<<kind))
 formatted=format(f32(value*100.0),'.1f')+'%' if percent else str(math.trunc(value))
 if value>=0:formatted='+'+formatted
 if normal_template.count('%s')!=1:raise ValueError('special normal format differs')
 selected=[t for t in talents if t['equipTalentCode']==option['equipTalentCode']]
 if not selected or len(selected)>4:raise ValueError('special talent array unverified')
 parameters={};proof=[]
 for i,row in enumerate(selected):
  for offset,prefix in [(0,'buffFactor'),(1,'subBuffFactor')]:
   parameters[i*2+offset]=reinforced(row[prefix+'Min'],row[prefix+'Max'],talent_grade,option['equipTalentValueDivideGrades'],row[prefix+'EnchantIncrease'],level)
  proof.append({'id':row['id'],'arrayIndex':i,'targetAbilityCode':row['targetAbilityCode'],'rootAbilityCode':row['rootAbilityCode'],'recordSha256':row['recordSha256']})
 description,missing=render_description(special_template,parameters)
 return {'state':'values_reconstructed' if not missing else 'partially_reconstructed','name':clean(title),
         'normalText':clean(normal_template.replace('%s',formatted)),'normalValue':float(formatted.rstrip('%')),
         'normalUnit':'PERCENT' if percent else 'FLAT','description':description,'specialEnhancement':level,
         'descriptionParameters':{str(k):v for k,v in parameters.items()},'unresolvedParameterIndexes':missing,
         'talentDefinitions':proof,'optionDefinitionSha256':option['recordSha256'],'normalDefinitionSha256':normal['rawRecordSha256'],
         'valueVerified':True,'valueVisuallyVerified':False,'enhancementIncluded':True,'activationState':'not_verified',
         'duplicateOptionPriorityVerified':False,'sourceKind':'native-option-instance-reconstruction'}
