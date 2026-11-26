"""Offline parser for proven native character fields; no external numeric fallback.
Star counts require the exact module's verified native UI relation; other unknowns remain null.
"""
import argparse,hashlib,json,re,sqlite3,struct
from pathlib import Path
from parse_runtime_equipment import decode_grade
from native_layouts import layout_for_sha, NEW_SHA
ROOT=Path(__file__).resolve().parents[1]

STAR_EVIDENCE='reports/ghidra/character-star-count-confirmed-native1242.txt'
PARSER_VERSION='runtime-character-v4-native-star-ui'

def verified_star_count(grade, identity, module_sha):
    # Exact 12.4.2 RTTI: StarLayerBuilder 019c461c casts to UnitData,
    # calls virtual+b0 -> 00c147cc -> +f8, decodes via 01a5c570 and
    # writes Builder+18. 019c4a84 renders that same value as the stars.
    # Other unit kinds / modules are not covered by this display proof.
    if module_sha==NEW_SHA and identity=='RANGERS' and type(grade) is int and 1<=grade<=9:
        return grade
    return None

def parse_capture(directory,localization=None):
    meta=json.loads((directory/'capture.json').read_text(encoding='utf8'))
    if meta.get('sourceKind')!='verified-live-character-definition-copies':raise ValueError('wrong capture source')
    if meta['traversal'].get('consistentSnapshot') is not True:raise ValueError('inconsistent native capture')
    layout=layout_for_sha(meta['moduleSha256'])
    records=[];seen=set();translations={};localization_sha=None
    if localization:
        if not localization.read_bytes().startswith(b'SQLite format 3\0'):raise ValueError('translation source is not SQLite')
        with sqlite3.connect(localization.resolve().as_uri()+'?mode=ro',uri=True) as db:
            translations=dict(db.execute("SELECT dataCode,msg FROM lang_unit WHERE language='zh-Hant'"))
        localization_sha=hashlib.sha256(localization.read_bytes()).hexdigest()
    for item in meta['records']:
        def blob(kind):
            entry=item['files'][kind];name=entry['file']
            if Path(name).name!=name:raise ValueError('capture file must be a direct child')
            raw=(directory/name).read_bytes()
            if hashlib.sha256(raw).hexdigest()!=entry['sha256']:raise ValueError('capture hash mismatch: '+kind)
            return raw
        raw=blob('record')
        if len(raw)!=layout['unitSize'] or struct.unpack_from('<Q',raw)[0]-meta['moduleBase']+0x100000!=layout['unitVtable']:raise ValueError('native character record type mismatch')
        if struct.unpack_from('<Q',raw,0x370)[0]!=0:raise ValueError('owned character instance cannot be promoted to a global template')
        code=blob('unit-code').decode('utf8')
        if code!=item['key'] or not re.fullmatch(r'[A-Za-z0-9_-]+',code):raise ValueError('unitCode identity mismatch')
        if code in seen:raise ValueError('duplicate/conflicting character ID')
        seen.add(code)
        wrapper=blob('grade')
        if len(wrapper)!=0x30 or struct.unpack_from('<Q',wrapper)[0]-meta['moduleBase']+0x100000!=layout['uintVtable']:raise ValueError('grade wrapper type mismatch')
        grade=decode_grade(wrapper,blob('grade-cipher'))
        def field(kind):
            text=blob(kind).decode('utf8')
            if len(text)>1024 or '\x00' in text:raise ValueError('invalid captured string')
            return text or None
        corrected=[]
        def record_string(kind,offset):
            saved=field(kind)
            if raw[offset]&1:
                if saved is not None and len(saved.encode('utf8'))!=struct.unpack_from('<Q',raw,offset+8)[0]:raise ValueError('captured long string dependency length mismatch')
                return saved
            length=raw[offset]>>1
            if length>22 or raw[offset+length+1]!=0:raise ValueError('invalid inline native string boundary')
            actual=raw[offset+1:offset+1+length].decode('utf8') or None
            if actual!=saved:corrected.append(kind)
            return actual
        name_key=record_string('name-key',0x98);description_key=record_string('description-key',0x1f0);category=struct.unpack_from('<I',raw,layout['category'])[0]
        unit_copy=field('unit-code-copy');identity_raw=struct.unpack_from('<I',raw,layout['identity'])[0]
        identity={1:'RANGERS',2:'ENEMY',3:'GUARDIAN',4:'SUMN_UNIT',5:'LBRT_BOSS'}.get(identity_raw)
        def reference_string(kind,offset):
            if kind in item['files']:return field(kind)
            if raw[offset]&1:return None # missing long-string heap dependency
            length=raw[offset]>>1
            if length>22 or raw[offset+1+length]!=0:raise ValueError('invalid inline native reference string')
            return raw[offset+1:offset+1+length].decode('utf8') or None
        primary_skill=reference_string('primary-skill-code',layout['primarySkill']);primary_ability=reference_string('primary-ability-code',layout['primaryAbility'])
        stars=verified_star_count(grade,identity,meta['moduleSha256'])
        records.append({'characterId':code,'unitCodeCopy':unit_copy,'resourceCode':code if unit_copy==code else None,'gradeRaw':grade,'starCount':stars,
            'primarySkillCode':primary_skill,'primaryAbilityCode':primary_ability,
            'unitIdentityRaw':identity_raw,'unitIdentity':identity,'unitType':record_string('unit-type',layout['unitType']),'unitCategoryRaw':category,'unitCategory':{8:'STR',7:'AGI',9:'INT',999:'ALL'}.get(category),'unitElement':record_string('unit-element',layout['element']),'name':translations.get(name_key),'nameKey':name_key,
            'description':translations.get(description_key),'descriptionKey':description_key,'imageMapping':None,'skills':None,'effects':None,'recordScope':'character-template' if identity=='RANGERS' else 'unit-definition',
            'fieldStatus':{'identity':'verified-native','grade':'verified-native','starCount':'verified-native-ui-relation' if stars is not None else 'ui-relation-unconfirmed','name':'local-translation-key-match' if name_key in translations else 'unresolved','image':'not-established','skills':'unparsed','primarySkill':'native-reference-only' if primary_skill else 'unresolved','primaryAbility':'native-reference-only' if primary_ability else 'unresolved'},
            'provenance':{'sourceKind':'verified-live-character-definition-copies','gameVersion':meta['gameVersion'],'moduleSha256':meta['moduleSha256'],
                'capturedAt':meta['capturedAt'],'parserVersion':PARSER_VERSION,'rawRecordSha256':hashlib.sha256(raw).hexdigest(),'dependencyFieldsRecoveredFromRecord':corrected,
                'starCountEvidence':STAR_EVIDENCE if stars is not None else None}})
    meta['fieldEvidence']['unitType']='12.4.2 unitType setter 00c15428 virtual+0x688 -> +0x430; +0x448 is unitMoveType, not behavior' if meta['gameVersion']=='12.4.2' else meta['fieldEvidence'].get('unitType','native unitType +0x430')
    return {'schemaVersion':1,'parserVersion':PARSER_VERSION,'sourceKind':'verified-native-unit-definitions','recordCount':len(records),'localVerification':True,
        'capturedAt':meta['capturedAt'],'gameVersion':meta['gameVersion'],'coverageComplete':False,'loadedContainerTraversalEnded':meta['traversal']['loadedContainerEnded'],'sourceCaptureSha256':hashlib.sha256((directory/'capture.json').read_bytes()).hexdigest(),
        'localizationSha256':localization_sha,'fieldEvidence':{**meta['fieldEvidence'],'primarySkill':'00e4e908 skillCode ->virtual+0x6b8 ->00c15328 ->+0x468;12.4.2 00e4ecf8 ->virtual+0x6c8 ->00c154e0 ->+0x480','primaryAbility':'00e4e908 abilityCode ->virtual+0x728 ->00c154c8 ->+0x500;12.4.2 ->00c15680 ->+0x518',
        'starCount':STAR_EVIDENCE if meta['moduleSha256']==NEW_SHA else 'UI relation not established for this module'},'records':records}
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture',type=Path,required=True);p.add_argument('--localization',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=parse_capture(a.capture,a.localization);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print('Native characters parsed:',len(result['records']))
