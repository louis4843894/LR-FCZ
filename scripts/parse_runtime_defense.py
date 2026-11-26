"""Offline validation of narrowly captured native PVP team objects.
No device access. Copies, owner identifiers and instance identifiers remain local.
"""
import argparse,hashlib,json,re,struct
from pathlib import Path
from parse_runtime_equipment import decode_grade
from native_layouts import layout_for_sha
ROOT=Path(__file__).resolve().parents[1]
SLOTS={1:'weapon',2:'armor',3:'accessory'}

def validate_member_context(directory,meta):
    if meta.get('ownerContextVerified') is not True:raise ValueError('unverified visible member context')
    context=meta.get('sourceContext',{})
    if context.get('kind') not in ('visible-guild-member','visible-player'):raise ValueError('unknown visible member context')
    def blob(name):
        item=context['files'][name]
        if Path(item['file']).name!=item['file']:raise ValueError('unsafe member context path')
        raw=(directory/item['file']).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=item['sha256']:raise ValueError('member context hash mismatch')
        return raw
    for key in context['files']:blob(key)
    scene=blob('controller');profile=blob('profile');base=meta['moduleBase']
    if len(scene)!=0x170 or len(profile)!=0x220 or struct.unpack_from('<Q',scene)[0]-base+0x100000!=0x1eee558 or struct.unpack_from('<Q',profile)[0]-base+0x100000!=0x1e7d650:raise ValueError('member context type mismatch')
    if struct.unpack_from('<I',scene,0x168)[0]!=5:raise ValueError('member page is not PVP defense mode')
    if struct.unpack_from('<Q',scene,0x138)[0]!=context.get('profileAddress'):raise ValueError('member profile association mismatch')
    if struct.unpack_from('<I',scene,0x148)[0]!=meta['usePvPTeamNo'] or struct.unpack_from('<I',profile,0x160)[0]!=meta['usePvPTeamNo']:raise ValueError('member selected defense differs from display')
    uid=blob('profile-id')
    guild=blob('guild')
    if len(guild)!=0x40 or struct.unpack_from('<Q',guild)[0]-base+0x100000!=0x1eadb48:raise ValueError('member guild object type mismatch')
    if uid.decode('utf8')!=meta['playerId'] or blob('guild-id').decode('utf8')!=context.get('guildId'):raise ValueError('member/roster identity mismatch')
    if context['kind']=='visible-guild-member':
        if uid!=blob('roster-member-id') or blob('guild-id')!=blob('roster-guild-id'):raise ValueError('member/roster identity mismatch')
    elif context.get('rosterCapturedAt') is not None or 'roster-member-id' in context['files'] or 'roster-guild-id' in context['files']:raise ValueError('unrelated player cannot claim saved roster membership')
    name=blob('profile-name')
    for offset,value in [(0x90,uid),(0x48,name)]:
        if profile[offset]&1:
            if struct.unpack_from('<Q',profile,offset+8)[0]!=len(value):raise ValueError('member string dependency length mismatch')
        elif profile[offset]>>1!=len(value) or profile[offset+1:offset+1+len(value)]!=value:raise ValueError('member string differs from source record')
    display=name.decode('utf8')
    if not display or '\0' in display or len(display)>100:raise ValueError('invalid visible display name')
    return {**context,'playerDisplayName':display}

def parse_capture(directory,all_teams=False):
    meta=json.loads((directory/'capture.json').read_text(encoding='utf8'))
    if meta.get('sourceKind') not in ('own-pvpteam-object-copies','visible-member-pvpteam-object-copies') or meta.get('groupKind')!=5:raise ValueError('not a proven PVP group capture')
    layout=layout_for_sha(meta['moduleSha256'])
    if meta.get('consistentSnapshot') is not True:raise ValueError('unverified owner or inconsistent capture')
    visible_context=None
    if meta['sourceKind']=='visible-member-pvpteam-object-copies':
        if layout['version']!='12.4.2':raise ValueError('visible member version layout not verified')
        visible_context=validate_member_context(directory,meta)
    elif meta.get('ownerProfilesAgree') is not True:raise ValueError('unverified owner or inconsistent capture')
    if meta.get('usePvPTeamNo') not in (1,2):raise ValueError('unknown selected defense team number')
    image=(directory/'screen.private.png').read_bytes()
    if hashlib.sha256(image).hexdigest()!=meta['screenSha256']:raise ValueError('screen hash mismatch')
    verification=None
    checked=directory/'screen-verification.private.json'
    if checked.exists():
        review=json.loads(checked.read_text(encoding='utf8'))
        if review.get('screenSha256')!=meta['screenSha256'] or review.get('purpose')!='pvp_defense' or review.get('selectedTeamNo')!=meta['usePvPTeamNo']:raise ValueError('screen review does not match this capture')
        verification={k:review.get(k) for k in ['checkedAt','method','purposeConfirmed','visibleRangerCount','selectedTeamNo','equipmentValuesVisuallyVerified','characterIdentitiesVisuallyVerified']}
    members=[];seen_positions=set();seen_instances=set()
    for row in meta['records']:
        position=row['positionKey']
        if not isinstance(position,int) or not 0<=position<10 or position in seen_positions:raise ValueError('invalid/duplicate native position')
        seen_positions.add(position)
        def blob(name):
            item=row['files'][name]
            if Path(item['file']).name!=item['file']:raise ValueError('unsafe capture path')
            raw=(directory/item['file']).read_bytes()
            if hashlib.sha256(raw).hexdigest()!=item['sha256']:raise ValueError('capture hash mismatch: '+name)
            return raw
        def typed(raw,size,ap):
            if len(raw)!=size or struct.unpack_from('<Q',raw)[0]-meta['moduleBase']+0x100000!=ap:raise ValueError('native object boundary/type mismatch')
        unit=blob('unit');typed(unit,layout['unitSize'],layout['unitVtable'])
        code=blob('unit-code').decode('utf8');instance=blob('instance-id').decode('ascii')
        if not re.fullmatch(r'[A-Za-z0-9_-]+',code) or code!=row['unitCode']:raise ValueError('unitCode mismatch')
        if not instance.isdecimal() or int(instance)!=struct.unpack_from('<Q',unit,0x370)[0] or instance!=row['instanceId']:raise ValueError('invenId mismatch')
        if instance in seen_instances:raise ValueError('same character instance in multiple captured positions')
        seen_instances.add(instance)
        equipment={}
        if row['equipMapState']=='present':typed(blob('equip-map'),0x20,layout['equipMapVtable'])
        for gear in row['equipment']:
            slot=gear['slot']
            if slot not in SLOTS or SLOTS[slot] in equipment:raise ValueError('invalid/duplicate equipment slot')
            raw=blob(f'gear-{slot}');typed(raw,0x160,layout['gearVtable'])
            item=blob(f'gear-code-{slot}').decode('utf8')
            if struct.unpack_from('<I',raw,0x18)[0]!=slot or gear['itemCode']!=item or not re.fullmatch(r'eq_[A-Za-z0-9_]+',item):raise ValueError('equipment type/code mismatch')
            owner_instance=struct.unpack_from('<Q',raw,0x98)[0]
            if owner_instance and owner_instance!=int(instance):raise ValueError('equipment unitInvenId does not match owning character instance')
            values={}
            for field in ['grade','enchant']:
                wrapper=blob(f'gear-{slot}-{field}');typed(wrapper,0x30,layout['uintVtable'])
                values[field]=decode_grade(wrapper,blob(f'gear-{slot}-{field}-cipher'))
            actual_effects=None;attribute_state=gear.get('attributeReadState','not_captured')
            if attribute_state=='captured':
                array=blob(f'gear-{slot}-attributes-array');typed(array,0x20,layout['arrayVtable'])
                data=blob(f'gear-{slot}-attributes-data');count=struct.unpack_from('<I',data)[0]
                if not 0<count<=16 or gear.get('attributeIndices')!=list(range(count)):raise ValueError('captured attribute boundaries do not match array count')
                entries=[]
                for i in range(count):
                    attribute=blob(f'gear-{slot}-attribute-{i}');typed(attribute,0x78,layout['attributeVtable'])
                    entries.append({'index':i,'attributeId':struct.unpack_from('<I',attribute,0x18)[0],'valueGradeRaw':struct.unpack_from('<I',attribute,0x20)[0],'attributeTypeRaw':struct.unpack_from('<I',attribute,0x1c)[0],'value':None,'unit':None})
                actual_effects={'status':'identifiers_only','entries':entries,'numericalValuesVerified':False}
            equipment[SLOTS[slot]]={'state':'equipped','equipmentId':item,'enhancement':values['enchant'],'instanceGrade':values['grade'],
                'equipmentInstanceIdentity':{'value':str(struct.unpack_from('<Q',raw,0x68)[0]),'sourceField':'equipMap.*.invenId','namespace':'player-owned-equipment'},'ownerAssociationStatus':'verified-native' if owner_instance else 'unknown','actualEffects':actual_effects,'attributeReadState':attribute_state,
                'fieldEvidence':{'enhancement':'12.4.0:01218e08;12.4.2:012193fc currentEnchant -> virtual+0x80 -> instance+0x58 -> checksum-validated uint wrapper','instanceGrade':'currentGrade -> virtual+0x70 -> instance+0x50','equipmentInstanceIdentity':'invenId ->virtual+0xd0 ->instance+0x68','actualEffects':'instance+0xb0 CCArray ->0122d2fc/0122d8f0; attrNo+0x18/valueGrade+0x20; numerical value and unit unresolved'}}
        for slot in SLOTS.values():
            if slot not in equipment:equipment[slot]={'state':'not_equipped' if row['equipMapState']=='present' else 'unknown','equipmentId':None}
        members.append({'memberIndex':position%5,'sourcePositionKey':position,'sourceTeamGroupKey':str(position//5+1),'characterState':'present','characterId':code,
            'characterInstanceIdentity':{'value':instance,'sourceField':'FriendModel+0x198[kind=5].DataUnit.invenId' if visible_context else 'playerUnitTeamGroupMap.pvpteam.*.invenId','namespace':'player-owned-unit'},'equipment':equipment})
    selected=str(meta['usePvPTeamNo']);selected_members=sorted([m for m in members if m['sourceTeamGroupKey']==selected],key=lambda m:m['memberIndex'])
    if [m['memberIndex'] for m in selected_members]!=list(range(5)):raise ValueError('selected five-position team not completely observed')
    groups=sorted({m['sourceTeamGroupKey'] for m in members}) if all_teams else [selected]
    snapshots=[]
    for group in groups:
        group_members=sorted([m for m in members if m['sourceTeamGroupKey']==group],key=lambda m:m['memberIndex'])
        # A missing position is not filled with a fabricated empty unit. Until an
        # explicit container-completeness marker is available it stays unobserved.
        snapshots.append({'snapshotId':directory.name+'-pvp-'+group,'teamId':'pvpteam/'+group,'playerId':meta['playerId'],'playerDisplayName':visible_context['playerDisplayName'] if visible_context else None,'purpose':'pvp_defense','status':'success','retrievedAt':meta['capturedAt'],'members':group_members,
            'unobservedPositionIndices':[i for i in range(5) if i not in {m['memberIndex'] for m in group_members}],
            'isSelected':group==selected,'gameVersion':meta['gameVersion'],'verification':verification if group==selected else None})
    memberships=[]
    if visible_context and visible_context['kind']=='visible-guild-member':
        memberships=[{'snapshotId':directory.name+'-membership','guildId':visible_context['guildId'],'playerId':meta['playerId'],'observedAt':meta['capturedAt'],'sourceRecordIdentity':directory.name+'-visible-profile'}]
    return {'schemaVersion':1,'parserVersion':'runtime-defense-v3-visible-player','recordScope':'player-team-observations','sourceId':directory.name,'memberships':memberships,
        'snapshots':snapshots,
        'captureEvidence':{'moduleSha256':meta['moduleSha256'],'gameVersion':meta['gameVersion'],'capturedUnitCount':len(members),'capturedEquipmentCount':sum(len(r['equipment']) for r in meta['records']),
            'group':meta['sourceContext']['groupSource'] if meta['sourceKind']=='visible-member-pvpteam-object-copies' else '00f95eb0 pvpteam ->kind5;00f96594 JSON key1 positions0..4, key2 positions5..9;00f9e380 manager+0x50',
            'unit':f"version {layout['version']};vtable {layout['unitVtable']:08x};unitCode+0x50,invenId+0x358/+0x370,equipMap+0x378; layout selected by exact module SHA"}}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--all-teams',action='store_true');a=p.parse_args()
    # The observation includes owner identifiers and must stay in a private location.
    if not any(part=='runtime.private' for part in a.output.resolve().parts):raise ValueError('observations must stay under runtime.private')
    doc=parse_capture(a.capture,a.all_teams);a.output.write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'snapshots':len(doc['snapshots']),'members':sum(len(s['members']) for s in doc['snapshots'])}))
