"""Read the proven own-player pvpteam container, without injection or writes.
Raw object copies and owner identifiers stay in runtime.private.
Evidence: own-roster-layout.txt, own-roster-storage-getters.txt,
player-team-groups-owned-instances.txt, owned-manager-group-implementation.txt.
"""
import hashlib,json,struct,time,uuid,subprocess,argparse,sys
from datetime import datetime,timezone
from pathlib import Path
from bounded_equipment_reader import Reader
from equipment_memory import ROOT,GBASE,EXPECTED_SHA,u64
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from native_layouts import layout_for_sha,NEW_SHA,OLD_SHA

def typed(r,address,size,ap):
    raw=r.read(address,size)
    if u64(raw)-r.base+GBASE!=ap:raise ValueError('object type mismatch at proven path')
    return raw

def typed_many(r,addresses,size,ap):
    """Batch known peer objects while preserving per-object vtable verification."""
    addresses=list(addresses)
    if not hasattr(r,'read_many'):return [typed(r,address,size,ap) for address in addresses]
    raws=r.read_many((address,size) for address in addresses)
    if any(u64(raw)-r.base+GBASE!=ap for raw in raws):raise ValueError('object type mismatch at proven batch path')
    return raws

def dictionary(r,address,limit):
    ap=layout_for_sha(getattr(r,'module_sha',OLD_SHA))['dictionaryVtable']
    header=typed(r,address,0x28,ap);node=u64(header,0x18);head=node;seen=set();rows=[]
    while node:
        if node in seen:raise ValueError('dictionary cycle')
        if len(seen)>=limit:raise ValueError('dictionary bound exceeded')
        seen.add(node);raw=r.read(node,0x128);nxt=u64(raw,0x120)
        rows.append((struct.unpack_from('<q',raw,0x100)[0],u64(raw,0x108),raw))
        if u64(r.read(node+0x120,8))!=nxt:raise ValueError('dictionary changed')
        node=nxt
    if u64(r.read(address+0x18,8))!=head:raise ValueError('dictionary head changed')
    return rows

def capture(r,out,with_attributes=False,context=None):
    layout=layout_for_sha(getattr(r,'module_sha',OLD_SHA))
    out.mkdir(parents=True,exist_ok=False)
    owners=[];selectors=[]
    if context is None:
        for global_address,manager_ap,profile_offset,profile_ap in [(layout['mainGlobal'],layout['mainManager'],0x50,layout['profileVtable']),(layout['pvpGlobal'],layout['pvpManager'],0x48,layout['profileVtable'])]:
            owner_manager=u64(r.read(r.base+global_address-GBASE,8))
            if not owner_manager:raise RuntimeError('own player manager not initialized; wait for main screen')
            typed(r,owner_manager,8,manager_ap)
            profile=u64(r.read(owner_manager+profile_offset,8));typed(r,profile,8,profile_ap)
            owners.append(r.string(r.read(profile+0x30,24),0).decode('utf8'))
            selectors.append(struct.unpack('<I',r.read(profile+0x124,4))[0])
        if not owners[0] or owners[0]!=owners[1] or selectors[0]!=selectors[1]:raise ValueError('own main/PVP profile context differs')
        manager=u64(r.read(r.base+layout['ownUnitGlobal']-GBASE,8))
        if not manager:raise RuntimeError('owned unit manager not initialized; wait for main screen')
        m=typed(r,manager,0x58,layout['ownUnitManager'])
        groups=u64(m,0x50) # own virtual+a0 ->00f9e380
    else:
        context['validate']()
        owners=[context['playerId']];selectors=[context['usePvPTeamNo']];groups=context['groups']
    group_entries=dictionary(r,groups,32)
    pvp=[obj for kind,obj,_ in group_entries if kind==5]
    if len(pvp)!=1:raise ValueError('expected exactly one pvpteam group')
    rows=[]
    initial=dictionary(r,pvp[0],10)
    units=typed_many(r,[obj for _,obj,_ in initial],layout['unitSize'],layout['unitVtable'])
    for (position,obj,entry),raw in zip(initial,units):
        code=r.string(raw,0x50).decode('utf8');instance=r.string(raw,0x358).decode('ascii')
        inventory=u64(raw,0x370)
        if not instance.isdecimal() or instance!=str(inventory):raise ValueError('instance identity representations disagree')
        stem=f'position-{position}';files={}
        blobs={'unit':raw,'entry':entry,'unit-code':code.encode(),'instance-id':instance.encode()}
        equip=u64(raw,0x378)
        gear=[]
        if equip:
            eraw=typed(r,equip,0x20,layout['equipMapVtable']);blobs['equip-map']=eraw
            equipment_entries=dictionary(r,u64(eraw,0x18),3)
            gear_raws=typed_many(r,[obj for _,obj,_ in equipment_entries],0x160,layout['gearVtable'])
            for (slot,gear_obj,gear_entry),g in zip(equipment_entries,gear_raws):
                if slot not in (1,2,3):raise ValueError('unknown equipment slot enum')
                item=r.string(g,0x20).decode('utf8')
                if struct.unpack_from('<I',g,0x18)[0]!=slot:raise ValueError('equipment slot/type mismatch')
                blobs[f'gear-{slot}']=g;blobs[f'gear-entry-{slot}']=gear_entry
                blobs[f'gear-code-{slot}']=item.encode()
                wrappers=typed_many(r,[u64(g,offset) for offset in (0x50,0x58)],0x30,layout['uintVtable'])
                strings=r.read_many((u64(wrapper,0x20),0x30) for wrapper in wrappers) if hasattr(r,'read_many') else [r.read(u64(wrapper,0x20),0x30) for wrapper in wrappers]
                for (label,offset),wrapper,string in zip([('grade',0x50),('enchant',0x58)],wrappers,strings):
                    blobs[f'gear-{slot}-{label}']=wrapper
                    blobs[f'gear-{slot}-{label}-string']=string
                    blobs[f'gear-{slot}-{label}-cipher']=r.string(string,0x18)
                attribute_state='not_captured';attribute_indices=[];attribute_error=None
                if with_attributes:
                    try:
                        array=typed(r,u64(g,0xb0),0x20,layout['arrayVtable'])
                        data=r.read(u64(array,0x18),0x10);count,capacity=struct.unpack_from('<II',data)
                        if count>16 or count>capacity or capacity>1024:raise ValueError('attribute array exceeds bounded layout')
                        items=r.read(u64(data,8),count*8) if count else b'';dependencies={}
                        dependencies[f'gear-{slot}-attributes-array']=array;dependencies[f'gear-{slot}-attributes-data']=data
                        attributes=typed_many(r,[u64(items,i*8) for i in range(count)],0x78,layout['attributeVtable'])
                        for i,attribute in enumerate(attributes):dependencies[f'gear-{slot}-attribute-{i}']=attribute
                        if r.read(u64(array,0x18),0x10)!=data:raise ValueError('attribute array changed during capture')
                        blobs.update(dependencies);attribute_indices=list(range(count));attribute_state='captured' if count else 'empty_observed_semantics_unknown'
                    except (RuntimeError,ValueError) as error:
                        attribute_state='read_failed';attribute_error=str(error)
                gear.append({'slot':slot,'itemCode':item,'attributeReadState':attribute_state,'attributeIndices':attribute_indices,'attributeError':attribute_error})
        for name,blob in blobs.items():
            filename=f'{stem}-{name}.bin';(out/filename).write_bytes(blob)
            files[name]={'file':filename,'sha256':hashlib.sha256(blob).hexdigest()}
        rows.append({'positionKey':position,'unitCode':code,'instanceId':instance,'equipment':gear,'equipMapState':'present' if equip else 'unavailable','files':files})
    # Re-read only the selected group and identifiers to reject a mixed snapshot.
    again=dictionary(r,pvp[0],10)
    if [(k,o) for k,o,_ in again]!=[(k,o) for k,o,_ in initial]:raise ValueError('group changed')
    for position,obj,_ in initial:
        saved=next(row for row in rows if row['positionKey']==position)
        if str(u64(r.read(obj+0x370,8)))!=saved['instanceId']:raise ValueError('unit changed during capture')
        if r.read(obj+0x378,8)!=(out/saved['files']['unit']['file']).read_bytes()[0x378:0x380]:raise ValueError('equipment map changed during capture')
    if context is None:
        if u64(r.read(r.base+layout['ownUnitGlobal']-GBASE,8))!=manager:raise ValueError('manager changed')
    else:context['validate']()
    image=subprocess.run([r.adb,'-s',r.serial,'exec-out','screencap','-p'],capture_output=True,check=True,timeout=20).stdout
    if not image.startswith(b'\x89PNG\r\n\x1a\n'):raise ValueError('screen capture format mismatch')
    (out/'screen.private.png').write_bytes(image)
    result={'schemaVersion':1,'sourceKind':'own-pvpteam-object-copies','capturedAt':datetime.now(timezone.utc).isoformat(),'gameVersion':layout['version'],'moduleSha256':r.module_sha,'pid':r.pid,'moduleBase':r.base,'playerId':owners[0],'usePvPTeamNo':selectors[0],'ownerProfilesAgree':True,'consistentSnapshot':True,'screenSha256':hashlib.sha256(image).hexdigest(),'groupKind':5,'groupContainerKeys':[k for k,_,_ in group_entries],'records':rows,'wholeGameCoverageConfirmed':False}
    if context is not None:
        dependencies={}
        for name,blob in context['blobs'].items():
            filename='context-'+name+'.bin';(out/filename).write_bytes(blob)
            dependencies[name]={'file':filename,'sha256':hashlib.sha256(blob).hexdigest()}
        result.update(sourceKind='visible-member-pvpteam-object-copies',ownerProfilesAgree=False,ownerContextVerified=True,
                      sourceContext={'kind':context['kind'],'files':dependencies,'guildId':context['guildId'],'rosterCapturedAt':context['rosterCapturedAt'],'groupSource':'FriendModel virtual+0x1f0 ->0113e9a8 ->+0x198; kind5; controller mode5','profileAddress':context['profile'],'controllerAddress':context['controller']})
    if hasattr(r,'shell_calls'):
        result['readerMetrics']={'readRanges':r.read_count,'readBytes':r.read_bytes,'shellCalls':r.shell_calls,'elapsedSeconds':round(time.monotonic()-r.started,3),'transport':'bounded-batch-single-base64-v1'}
    (out/'capture.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--attributes',action='store_true');p.add_argument('--module-sha',choices=[OLD_SHA,NEW_SHA],default=NEW_SHA);a=p.parse_args()
    out=ROOT/'data/research/runtime.private'/('defense-capture-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:6])
    with Reader(r'C:\LDPlayer\LDPlayer9\adb.exe','emulator-5554',600 if a.attributes else 180) as r:
        r.expected_module_sha=a.module_sha;r.refresh();result=capture(r,out,a.attributes)
    (ROOT/'data/research/runtime.private/latest-defense-capture.json').write_text(json.dumps({'directory':str(out)}),encoding='utf8')
    print(json.dumps({'captured':len(result['records']),'units':[x['unitCode'] for x in result['records']],'gearCount':sum(len(x['equipment']) for x in result['records']),'output':str(out)}))
