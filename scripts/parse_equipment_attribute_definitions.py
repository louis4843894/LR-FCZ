"""Parse saved unit_eqip_attr definition objects; preserve raw numbers and unknown units."""
import argparse,hashlib,json,math,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def parse(capture):
 meta=json.loads((capture/'capture.json').read_text(encoding='utf8'));rows=[];ids=set()
 for entry in meta['records']:
  raw=(capture/entry['file']).read_bytes()
  if len(raw)!=0x78:raise ValueError('attribute definition must be 0x78 bytes')
  if struct.unpack_from('<Q',raw)[0]-meta['moduleBase']+0x100000!=0x1e990c0:raise ValueError('attribute definition vtable mismatch')
  attr_id,kind=struct.unpack_from('<II',raw,0x18);divisions=struct.unpack_from('<I',raw,0x24)[0];minimum,maximum=struct.unpack_from('<ff',raw,0x28)
  if attr_id!=entry['key']:raise ValueError('dictionary key differs from attrNo')
  if attr_id in ids:raise ValueError('duplicate attrNo')
  if not all(math.isfinite(x) for x in (minimum,maximum)):raise ValueError('invalid IEEE754 value')
  ids.add(attr_id);rows.append({'attrNo':attr_id,'reinforceTypeEnum':kind,'valueDivideGrades':divisions,'minValueRaw':minimum,'maxValueRaw':maximum,'unit':None,'displayMultiplier':None,'equipmentAssociations':None,'rawRecordSha256':hashlib.sha256(raw).hexdigest(),'sourceRecordFile':entry['file'],'recordScope':'attribute-definition','localFieldsVerified':True})
 return {'schemaVersion':1,'sourceKind':'verified-live-attribute-definition-copies','recordCount':len(rows),'capturedAt':meta['capturedAt'],'coverageComplete':False,'equipmentRelationStatus':'not-established','fieldEvidence':{'attrNo':'0122c75c -> 012314a8 -> +0x18 uint32','reinforceTypeEnum':'0122c75c -> 012314b8 -> +0x1c uint32','valueDivideGrades':'0122c75c -> 012314d8 -> +0x24 uint32','minValueRaw':'0122c75c -> 012314e8 -> +0x28 float32','maxValueRaw':'0122c75c -> 012314f8 -> +0x2c float32'},'records':rows}
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture',type=Path,default=ROOT/'data/research/runtime.private/unit-equip-attribute-observation');p.add_argument('--output',type=Path,default=ROOT/'data/research/equipment-attribute-definitions-sample.json');a=p.parse_args();result=parse(a.capture);a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print('Parsed actual attribute definitions:',len(result['records']))
