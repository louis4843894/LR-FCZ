"""Attribute/reference links from saved native bytes; never fabricates instance values."""
import hashlib,json,math,struct
from pathlib import Path


def inspect_attribute(root,team,member,slot,entry,cache):
    capture=(Path(root)/'data/research/runtime.private'/team['sourceId']).resolve()
    if capture.parent!=(Path(root)/'data/research/runtime.private').resolve():raise ValueError('unsafe capture source')
    if capture not in cache:cache[capture]=json.loads((capture/'capture.json').read_text(encoding='utf8'))
    meta=cache[capture];position=(int(team['teamId'].split('/')[-1])-1)*5+member['memberIndex']
    records=[r for r in meta['records'] if r['positionKey']==position and r['instanceId']==member['characterInstanceIdentity']['value']]
    if len(records)!=1:raise ValueError('native attribute owner/position differs')
    number={'weapon':1,'armor':2,'accessory':3}[slot]
    file=records[0]['files'][f"gear-{number}-attribute-{entry['index']}"]
    path=(capture/file['file']).resolve()
    if path.parent!=capture:raise ValueError('unsafe attribute blob path')
    raw=path.read_bytes()
    if len(raw)!=0x78 or hashlib.sha256(raw).hexdigest()!=file['sha256']:raise ValueError('native attribute hash/size mismatch')
    attr,kind,grade=struct.unpack_from('<III',raw,0x18)
    if (attr,kind,grade)!=(entry['attributeId'],entry['attributeTypeRaw'],entry['valueGradeRaw']):raise ValueError('native attribute fields differ')
    def text(offset):
        if raw[offset]&1:return None
        length=raw[offset]>>1
        if length>22:raise ValueError('invalid inline selector')
        return raw[offset+1:offset+1+length].decode('utf8')
    return {'attributeSha256':file['sha256'],'selector30':text(0x30),'selector48':text(0x48),
        'hasDependency68':bool(struct.unpack_from('<Q',raw,0x68)[0]),'hasDependency70':bool(struct.unpack_from('<Q',raw,0x70)[0]),
        'baseStart':struct.unpack_from('<f',raw,0x28)[0],'baseEnd':struct.unpack_from('<f',raw,0x2c)[0]}


def map_unknown(entry,reference,effects,native,effects_source):
    result={'status':'unmapped','sourceKind':'external-reference','actualValueVerified':False,
            'sourceUrl':effects_source['url'],'sourceSha256':effects_source['sha256'],
            'nativeAttributeSha256':native['attributeSha256'],'candidates':[]}
    if not reference:return result
    if entry['attributeId']==0:
        if native['hasDependency68'] and not native['hasDependency70']:
            result.update(category='skill-plus',dependencyField='GearStat+0x68',candidates=reference.get('skillPlus',[]))
        elif native['hasDependency70'] and not native['hasDependency68']:
            result.update(category='spec-special',dependencyField='GearStat+0x70',candidates=(reference.get('specPlus') or {}).get('specialOptions',[]))
        if result['candidates']:result['status']='template_candidates_only'
        return result
    key='EQUIP:GEAR_FILTER_'+str(entry.get('attributeCode'))+'_nm'
    effect=effects.get(entry['attributeId'])
    if effect and effect['optionKey']!=key:
        result['status']='conflict';return result
    advanced=reference.get('advanced')
    candidates=[]
    if native['hasDependency70']:
        candidates=[{**x,'branch':'spec-basic'} for x in (reference.get('specPlus') or {}).get('basicOptions',[]) if x['optionKey']==key]
        result.update(category='spec-basic',dependencyField='GearStat+0x70')
    elif not native['hasDependency68'] and advanced:
        selectors=[s for s in [native['selector30'],native['selector48']] if s not in ('none',None)]
        if len(selectors)!=1:return result
        if advanced['condition']['key']!='CUSTOM:EQUIP_RANGER_TYPE_'+selectors[0].upper():
            result['status']='conflict';return result
        candidates=[{**x,'branch':branch,'condition':advanced['condition']} for branch,options in [('advanced-default',[advanced['defaultOption']]),('advanced-switch',advanced['switchOptions'])] for x in options if x['optionKey']==key]
        result.update(category='advanced',nativeSelector=selectors[0],condition=advanced['condition'],conditionActivationVerified=False)
    # Check native base endpoints as an additional constraint, without interpreting
    # grade interpolation, extra-enchant levels, or special-object calculations.
    matched=[]
    for option in candidates:
        bounds=option.get('range')
        if not bounds:continue
        scale=100 if bounds['unit']=='PERCENT' else 1
        left=sorted([native['baseStart']*scale,native['baseEnd']*scale]);right=sorted([bounds['min'],bounds['max']])
        if all(math.isclose(a,b,rel_tol=1e-6,abs_tol=1e-4) for a,b in zip(left,right)):matched.append(option)
    if not matched:
        result['status']='conflict' if candidates else 'unmapped';return result
    result.update(status='exact_attribute_id' if effect else 'same_equipment_key_and_base_range',
        optionKey=key,candidates=matched,branchAmbiguous=len(matched)>1,baseRangeVerified=True)
    return result
