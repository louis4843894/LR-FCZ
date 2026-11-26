"""The native conditional branch; ordinary +5 multipliers are not used here."""
import math,struct
from parse_runtime_gear_values import f32,PERCENT_MASK

def conditional_scalar(raw,definition,grade,advanced_level,codes,increments):
 if type(grade) is not int or type(advanced_level) is not int or not 0<=advanced_level<=100:return None
 attr,kind,_,steps=struct.unpack_from('<IIII',raw,0x18)
 if not attr or not 1<=kind<=45 or not steps or not 0<=grade<steps or struct.unpack_from('<Q',raw,0x68)[0] or struct.unpack_from('<Q',raw,0x70)[0]:return None
 a,b=definition['selector1'],definition['selector2']
 if (a=='none')==(b=='none'):return None
 selector=b if b!='none' else a;code=codes.get(kind)
 if code is None:return None
 low,high=struct.unpack_from('<ff',raw,0x28)
 if not all(math.isfinite(v) for v in (low,high)):return None
 base=f32(low+f32(f32(f32(high-low)*f32(grade))/f32(steps-1 if steps!=1 else 1)))
 bonus=0.0
 for level in range(advanced_level+1):
  # 00f451d8's missing dictionary entry returns float zero. This source is a
  # completely traversed loaded dictionary, not a hand-made default table.
  entry=increments.get(selector.upper()+code.upper()+str(level))
  if entry and (entry['selector'].upper()!=selector.upper() or entry['code'].upper()!=code.upper() or entry['level']!=level):raise ValueError('conditional increment key differs')
  bonus=f32(bonus+(entry['value'] if entry else 0.0))
 value=f32(base+bonus);percent=bool(PERCENT_MASK&(1<<kind))
 return {'value':round(f32(value*100.0),1) if percent else math.trunc(value),'unit':'PERCENT' if percent else 'FLAT',
  'enhancementIncluded':True,'calculationKind':'native-conditional','appliedEnhancementLevel':advanced_level,
  'conditionState':'applicability_not_verified'}

def skill_scalar(definition,grade,level,upgrades):
 if type(grade) is not int or type(level) is not int or not 0<=level<=100 or not definition['use']:return None
 low,high,steps=definition['minValue'],definition['maxValue'],definition['steps']
 if not steps or not 0<=grade<steps:return None
 bonus=0.0
 for i in range(1,level+1):
  # 0122ed7c uses the actual Skill+ ID, not attrNumberGroup.
  row=upgrades.get(f"{definition['attributeId']}_{i}")
  if row:bonus=f32(bonus+row['value'])
 base=low
 if f32(high-low)!=0:
  denominator=max(1,steps-1)
  base=f32(low+f32(f32(f32(high-low)*f32(grade))/f32(denominator)))
 value=f32(bonus+base);apply=definition['applyTypeEnum'];target=definition['targetFactorEnum']
 if apply not in (1,2,3,4) or target not in (0,1):return None
 if apply==3:value=f32(value*100.0)
 if target==1:display=round(value,1);unit='SECOND'
 elif apply==1:display=math.trunc(value);unit='FLAT'
 else:display=round(value,1);unit='PERCENT'
 # The formatter's operator table is checked by the caller. Preserve SUB's
 # displayed sign. Native DIV, like SUB, uses '-' in the display table; this
 # is a modifier value, not an already-applied change to a character's skill.
 if apply in (2,4):display=-display
 return {'value':display,'unit':unit,'enhancementIncluded':True,'calculationKind':'native-skillplus','appliedEnhancementLevel':level,
  'conditionState':'skill_activation_not_verified','modifierOperator':{1:'+',2:'-',3:'+',4:'-'}[apply]}
