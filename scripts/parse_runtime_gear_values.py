"""Enrich only the proven ordinary GearStat branch, using actual instance copies.

Skill-plus, special-option and item-specific reinforcement branches stay unknown.
External reference numbers are never inputs. Two independent game-screen checks
are required for this capture before any numeric observation is emitted.
"""
import argparse,hashlib,json,math,sqlite3,struct
from pathlib import Path
from native_elf import NativeELF
from native_layouts import NEW_SHA
from parse_runtime_defense import parse_capture
ROOT=Path(__file__).resolve().parents[1]
PERCENT_MASK=0x3ff7ff7ff554

class UnsupportedOrdinaryRange(ValueError):
    """Valid copied fields outside the interpolation range verified so far."""

def f32(v):return struct.unpack('<f',struct.pack('<f',v))[0]
def scalar(raw,enhancement,coefficient):
    if len(raw)!=0x78:raise ValueError('invalid GearStat boundary')
    attr,kind,grade,steps=struct.unpack_from('<IIII',raw,0x18)
    if not 1<=kind<=45 or attr==0 or struct.unpack_from('<Q',raw,0x68)[0] or struct.unpack_from('<Q',raw,0x70)[0]:return None
    # 0122e3f8 checks BOTH selectors against the literal "none".
    if raw[0x30:0x36]!=b'\x08none\0' or raw[0x48:0x4e]!=b'\x08none\0':return None
    if not steps or grade>steps-1:raise UnsupportedOrdinaryRange('ordinary grade outside verified range')
    start,end=struct.unpack_from('<ff',raw,0x28)
    if not all(math.isfinite(x) for x in [start,end,coefficient]):raise ValueError('nonfinite ordinary attribute input')
    base=f32(start+f32(f32(f32(end-start)*f32(grade))/f32(steps-1 if steps!=1 else 1)))
    result=f32(base*f32(f32(coefficient*f32(enhancement))+1.0))
    percent=bool(PERCENT_MASK&(1<<kind))
    displayed=round(f32(result*100.0),1) if percent else math.trunc(result)
    return {'value':displayed,'unit':'PERCENT' if percent else 'FLAT','enhancementIncluded':True,'nativeValue':result}

def enrich(capture,factor_path,review_path,module_path,translation_path,calibration_capture=None,calibration_factor=None):
    capture=capture.resolve();meta=json.loads((capture/'capture.json').read_text(encoding='utf8'))
    factor=json.loads(factor_path.read_text(encoding='utf8'));review=json.loads(review_path.read_text(encoding='utf8'))
    if factor.get('sourceKind')!='verified-ordinary-gear-factor' or factor.get('moduleSha256')!=NEW_SHA or meta['moduleSha256']!=NEW_SHA or factor['pid']!=meta['pid']:raise ValueError('unverified or different-process ordinary coefficient')
    coefficient=struct.unpack('<f',bytes.fromhex(factor['coefficientRawHex']))[0]
    if coefficient!=factor['coefficient'] or not math.isfinite(coefficient):raise ValueError('factor bytes do not match value')
    calibration_capture=calibration_capture.resolve() if calibration_capture else capture
    calibration=None
    if calibration_capture!=capture:
        if calibration_factor is None:raise ValueError('calibration factor is required')
        # Reproduce the independently checked two-gear result first. Reuse the
        # verified formula, never another player's values or visual-review flag.
        calibration=enrich(calibration_capture,calibration_factor,review_path,module_path,translation_path)
    manifest_sha=hashlib.sha256((calibration_capture/'capture.json').read_bytes()).hexdigest()
    if review.get('sourceKind')!='manual-native-ordinary-gear-review' or review.get('captureManifestSha256')!=manifest_sha:raise ValueError('screen checks belong to another capture')
    elf=NativeELF(module_path)
    if elf.sha256!=NEW_SHA:raise ValueError('unverified scalar code module')
    expected={'00f3b85c':'000c40f9c0035fd6','00fb58e8':'00cc43bdc0035fd6'}
    if factor.get('getterInstructions')!=expected:raise ValueError('unverified getter proof')
    for address,code in expected.items():
        offset=elf.offset(int(address,16))
        if elf.data[offset:offset+8].hex()!=code:raise ValueError('getter proof differs from module')
    if elf.cstring(0x7bce95)!='GEAR_FILTER_%s_nm':raise ValueError('native label pattern differs')
    names={}
    for kind in range(1,46):
        offset=struct.unpack_from('<i',elf.data,elf.offset(0x85611c+(kind-1)*4))[0];names[kind]=elf.cstring(0x85611c+offset)
    labels={}
    with sqlite3.connect(translation_path.resolve().as_uri()+'?mode=ro',uri=True) as db:
        for kind,name in names.items():
            row=db.execute("SELECT msg FROM lang_equip WHERE language='zh-Hant' AND dataCode=?",('GEAR_FILTER_'+name+'_nm',)).fetchone()
            if row:labels[kind]=row[0].replace('\\\\n',' ').replace('\\n',' ')
    data=parse_capture(capture,all_teams=True);values={};gear_by_key={};unsupported=[]
    for team in data['snapshots']:
        for member in team['members']:
            key=member['sourcePositionKey'];raw_row=next(r for r in meta['records'] if r['positionKey']==key)
            for slot_index,slot_name in [(1,'weapon'),(2,'armor'),(3,'accessory')]:
                gear=member['equipment'][slot_name];effects=gear.get('actualEffects')
                if not effects or gear.get('ownerAssociationStatus')!='verified-native':continue
                gear_by_key[(key,slot_index)]=gear
                def blob(name):
                    record=raw_row['files'][name];p=(capture/record['file']).resolve()
                    if p.parent!=capture:raise ValueError('unsafe scalar dependency')
                    raw=p.read_bytes()
                    if hashlib.sha256(raw).hexdigest()!=record['sha256']:raise ValueError('scalar dependency hash mismatch')
                    return raw
                for entry in effects['entries']:
                    raw=blob(f"gear-{slot_index}-attribute-{entry['index']}")
                    kind=entry['attributeTypeRaw'];entry.update(attributeCode=names.get(kind),attributeLabel=labels.get(kind),value=None,unit=None,enhancementIncluded=False,valueVisuallyVerified=False)
                    try:result=scalar(raw,gear['enhancement'],coefficient)
                    except UnsupportedOrdinaryRange:
                        # Do not extrapolate an unverified native grade, nor lose
                        # the rest of this player's valid instance observations.
                        unsupported.append({'position':key,'slot':slot_index,'attributeIndex':entry['index'],'attributeId':entry['attributeId'],'valueGradeRaw':entry['valueGradeRaw'],'stepsRaw':struct.unpack_from('<I',raw,0x24)[0]})
                        continue
                    if result is None:continue
                    result.pop('nativeValue');entry.update(result)
                    entry['valueEvidence']={'method':'native-ordinary-gearstat-v1','moduleSha256':NEW_SHA,'attributeSha256':hashlib.sha256(raw).hexdigest(),'factorSha256':hashlib.sha256(factor_path.read_bytes()).hexdigest(),'enhancement':gear['enhancement'],'attributeId':entry['attributeId'],'attributeTypeRaw':kind,'uiReviewSha256':hashlib.sha256(review_path.read_bytes()).hexdigest()}
                    values[(key,slot_index,entry['index'])]=entry
                if any(e['value'] is not None for e in effects['entries']):
                    effects.update(status='partial_values',verifiedValueCount=sum(e['value'] is not None for e in effects['entries']),valueMethod='native-ordinary-gearstat-v1',valueModuleSha256=NEW_SHA,valueFactorRetrievedAt=factor['capturedAt'])
                    gear['fieldEvidence']['actualEffectValues']='0122dde4 ordinary branch; selectors none; runtime GameFactorData+3cc; 0122f510 format; two native calibration gear screens checked; current-gear visual flag is separate'
    checked_gear=set()
    if calibration is not None:
        if calibration['captureEvidence']['ordinaryValues']['uiCheckedGearCount']<2:raise ValueError('calibration requires two reviewed gear')
        data['parserVersion']+='+ordinary-values-calibrated-v1'
        data['captureEvidence']['ordinaryValues']={'method':'native-ordinary-gearstat-v1','verifiedValueCount':len(values),'factorCapturedAt':factor['capturedAt'],'factorSha256':hashlib.sha256(factor_path.read_bytes()).hexdigest(),'uiCheckedGearCount':0,'calibrationUiCheckedGearCount':calibration['captureEvidence']['ordinaryValues']['uiCheckedGearCount'],'calibrationManifestSha256':manifest_sha,'currentCaptureVisuallyVerified':False,'unsupportedRanges':unsupported}
        return data
    for check in review['gearChecks']:
        key,slot=check['positionKey'],check['slot'];gear=gear_by_key[(key,slot)]
        if gear['equipmentId']!=check['itemCode']:raise ValueError('reviewed gear identity mismatch')
        shot=(capture/check['screenFile']).resolve()
        if shot.parent!=capture or hashlib.sha256(shot.read_bytes()).hexdigest()!=check['screenSha256']:raise ValueError('review screen hash mismatch')
        for expected_entry in check['values']:
            item=values[(key,slot,expected_entry['index'])]
            if item['value']!=expected_entry['value'] or item['unit']!=expected_entry['unit'] or item['attributeId']!=expected_entry['attributeId']:raise ValueError('native scalar does not match independently reviewed game screen')
            item['valueVisuallyVerified']=True
        checked_gear.add(check['itemCode'])
    if len(checked_gear)<2:raise ValueError('requires two different reviewed equipment templates')
    data['parserVersion']+='+ordinary-values-v1';data['captureEvidence']['ordinaryValues']={'method':'native-ordinary-gearstat-v1','verifiedValueCount':len(values),'factorCapturedAt':factor['capturedAt'],'factorSha256':hashlib.sha256(factor_path.read_bytes()).hexdigest(),'uiCheckedGearCount':len(checked_gear),'translationSha256':hashlib.sha256(translation_path.read_bytes()).hexdigest()}
    return data

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--capture',type=Path,required=True);p.add_argument('--factor',type=Path,required=True);p.add_argument('--review',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--module',type=Path,default=ROOT/'data/research/runtime.private/modules/libgame-12.4.2-pull.so');p.add_argument('--translation',type=Path,default=ROOT/'data/extracted/lr_20261116T212608096_7b99bdd0/assets/res/tutorial_res/db/lang_equip/lang_equip.ndb');a=p.parse_args()
    if 'runtime.private' not in a.output.resolve().parts:raise ValueError('enriched player observations must remain private')
    result=enrich(a.capture,a.factor,a.review,a.module,a.translation);a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(result['captureEvidence']['ordinaryValues']))
