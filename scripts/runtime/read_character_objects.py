"""Capture verified character definitions, using their own native layout.
No injection or unknown memory search. Default five visited nodes, maximum 4096.
Evidence: character-native-manager.txt / character-native-fields.txt.
"""
import argparse,hashlib,json,re,struct,time,uuid
from datetime import datetime,timezone
from pathlib import Path
from bounded_equipment_reader import Reader
from equipment_memory import GBASE,EXPECTED_SHA,u64,ROOT
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from native_layouts import layout_for_sha

def capture(reader,output,max_nodes,max_records=None,rangers_only=False,diverse=False,ordinary_only=False,include_ids=None):
    if not 1<=max_nodes<=4096:raise ValueError('character node bound must be 1..4096')
    max_records=max_nodes if max_records is None else max_records
    if not 1<=max_records<=4096:raise ValueError('record bound must be 1..4096')
    sha=getattr(reader,'module_sha',EXPECTED_SHA);layout=layout_for_sha(sha)
    output.mkdir(parents=True,exist_ok=False)
    global_addr=reader.base+layout['characterGlobal']-GBASE;manager=u64(reader.read(global_addr,8))
    if not manager:raise RuntimeError('character manager not initialized')
    manager_raw=reader.read(manager,0xc0)
    if u64(manager_raw)!=reader.base+layout['characterManager']-GBASE:raise ValueError('character manager type mismatch')
    dictionary=u64(manager_raw,0x28) # getter00f652cc, own manager vtable+0x58
    header=reader.read(dictionary,0x28);head=u64(header,0x18);node=head
    baseline=ROOT/'data/research/runtime.private/objects';meta=json.loads((baseline/'capture.json').read_text(encoding='utf8'))
    dictionary_type=layout['dictionaryVtable']
    if u64(header)-reader.base+GBASE!=dictionary_type:raise ValueError('not the verified cocos2d dictionary type')
    (output/'manager.bin').write_bytes(manager_raw);(output/'dictionary.bin').write_bytes(header)
    seen=set();records=[];errors=[];reason='node_limit';consistent=True;skipped_kind=0;skipped_policy=0;categories={}
    while node and len(seen)<max_nodes and len(records)<max_records:
        if node in seen:reason='cycle';errors.append({'error':'repeated node'});break
        seen.add(node);i=len(seen)-1
        try:
            entry=reader.read(node,0x128);nxt=u64(entry,0x120)
            key=entry[:256].split(b'\0',1)[0].decode('utf8')
            if not re.fullmatch(r'[A-Za-z0-9_-]+',key):raise ValueError('invalid character dictionary key')
            if include_ids and key not in include_ids:
                skipped_policy+=1
                if u64(reader.read(node+0x120,8))!=nxt:consistent=False;reason='container_changed';break
                node=nxt;continue
            object_address=u64(entry,0x108)
            if u64(reader.read(object_address,8))-reader.base+GBASE!=layout['unitVtable']:raise ValueError('character record type mismatch')
            category,identity=struct.unpack('<II',reader.read(object_address+layout['category'],8))
            skip_kind=rangers_only and identity!=1
            skip_policy=diverse and categories.get(category,0)>={7:2,8:2,9:1}.get(category,0)
            if skip_kind or skip_policy:
                skipped_kind+=int(skip_kind);skipped_policy+=int(not skip_kind and skip_policy)
                if u64(reader.read(node+0x120,8))!=nxt:consistent=False;reason='container_changed';break
                node=nxt;continue
            record=reader.read(object_address,layout['unitSize'])
            if ordinary_only and reader.string(record,layout['unitType']).decode('utf8') not in {'ATTACK','BALANCE','HP','SPEED','SPLASH','SUPPORT'}:
                skipped_policy+=1
                if u64(reader.read(node+0x120,8))!=nxt:consistent=False;reason='container_changed';break
                node=nxt;continue
            code=reader.string(record,0x50)
            if code.decode('utf8')!=key:raise ValueError('unitCode differs from dictionary key')
            grade=reader.read(u64(record,0xf8),0x30)
            if u64(grade)-reader.base+GBASE!=layout['uintVtable']:raise ValueError('grade wrapper type mismatch')
            grade_string=reader.read(u64(grade,0x20),0x30)
            blobs={'entry':entry,'record':record,'unit-code':code,'unit-code-copy':reader.string(record,0x68),
                   'primary-skill-code':reader.string(record,layout['primarySkill']),'primary-ability-code':reader.string(record,layout['primaryAbility']),
                   'unit-type':reader.string(record,layout['unitType']),'unit-element':reader.string(record,layout['element']),
                   'name-key':reader.string(record,0x98),'description-key':reader.string(record,0x1f0),
                   'grade':grade,'grade-string':grade_string,'grade-cipher':reader.string(grade_string,0x18)}
            files={}
            for kind,raw in blobs.items():
                name=f'{kind}-{i}.bin';(output/name).write_bytes(raw);files[kind]={'file':name,'sha256':hashlib.sha256(raw).hexdigest()}
            records.append({'key':key,'files':files});categories[category]=categories.get(category,0)+1
            if len(records)%100==0:print(f'Visited {len(seen)}; captured {len(records)} native definitions',flush=True)
            if u64(reader.read(node+0x120,8))!=nxt:consistent=False;reason='container_changed';break
            node=nxt
        except Exception as e:
            errors.append({'error':str(e)});reason='read_or_validation_failure';break
    if not node:reason='null_tail'
    elif len(records)>=max_records and consistent and not errors:reason='sample_limit'
    if u64(reader.read(global_addr,8))!=manager or u64(reader.read(dictionary+0x18,8))!=head:consistent=False;reason='container_changed'
    result={'schemaVersion':1,'sourceKind':'verified-live-character-definition-copies','gameVersion':layout['version'],'moduleSha256':sha,'layoutVersion':layout['version'],
            'moduleBase':reader.base,'pid':reader.pid,'capturedAt':time.time(),'selection':{'rangersOnly':rangers_only,'ordinaryBehaviorOnly':ordinary_only,'samplePolicy':'native-category-quota' if diverse else 'first-valid'},'records':records,'errors':errors,
            'traversal':{'visited':len(seen),'captured':len(records),'maxNodes':max_nodes,'maxRecords':max_records,'skippedOtherUnitKinds':skipped_kind,'skippedSamplePolicy':skipped_policy,'stopReason':reason,'consistentSnapshot':consistent,'loadedContainerEnded':not node,'wholeGameCoverageConfirmed':False},
            'fieldEvidence':{'unitIdentity':'00e4e668(RANGERS=1,ENEMY=2,GUARDIAN=3,SUMN_UNIT=4,LBRT_BOSS=5) -> virtual+0x9e8 -> 00c15b38 -> record+0x6fc','managerDictionary':'00f652cc -> manager+0x28','unitCode':'00e4e908 -> vtable+0x58 -> 00c14540 -> record+0x50',
                'grade':'00e4e908 -> 01a5bc88 -> vtable+0xb8 -> 00c14654 -> record+0xf8','unitType':'00e4e908 -> vtable+0x688 -> 00c152a8 -> record+0x430',
                'unitElement':'00e4e908 -> vtable+0xad8 -> 00c15c50 -> record+0x738',
                'nameKey':'00e4e908 -> vtable+0x78 -> 00c145a8 -> record+0x98',
                'descriptionKey':'00e4e908 -> vtable+0x338 -> 00c14b80 -> record+0x1f0',
                'unitCategory':'00e4e908 -> 00e4e550(STR=8,AGI=7,INT=9,ALL=999) -> vtable+0x9d8 -> 00c15b28 -> record+0x6f8',
                'resourceCode':'00e53b90 selects unitCodeCopy or virtual+0x50 unitCode; resolve offline only if both agree'}}
    if layout['version']=='12.4.2':result['fieldEvidence']={'versionLayout':'reports/ghidra/version1242-unit-fields-annotated.txt; version1242-field-layout-leaves.txt; version1242-character-category-element.txt; version1242-uint-wrapper-character-fields.txt','layout':layout,'gradeDecoder':'01a5c570 preserves unsigned wrapper checksum/XOR rules; unknown hashes rejected'}
    (output/'capture.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--max-nodes',type=int,default=5);p.add_argument('--max-seconds',type=int,default=180);p.add_argument('--max-records',type=int);p.add_argument('--rangers-only',action='store_true');p.add_argument('--diverse',action='store_true');p.add_argument('--ordinary-only',action='store_true');p.add_argument('--include-id',action='append');p.add_argument('--output',type=Path);a=p.parse_args()
    out=a.output or ROOT/'data/research/runtime.private'/('character-capture-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:6])
    with Reader(r'C:\LDPlayer\LDPlayer9\adb.exe','emulator-5554',a.max_seconds) as r:
        from native_layouts import NEW_SHA
        r.expected_module_sha=NEW_SHA
        r.refresh()
        try:result=capture(r,out,a.max_nodes,a.max_records,a.rangers_only,a.diverse,a.ordinary_only,set(a.include_id or []))
        except Exception as error:
            if out.is_dir() and not (out/'capture.json').exists():
                (out/'capture-failure.json').write_text(json.dumps({'sourceKind':'character-capture-failure','capturedAt':time.time(),'pid':r.pid,'moduleSha256':r.module_sha,'error':str(error)},indent=2),encoding='utf8')
            raise
    if result['records'] and result['traversal']['consistentSnapshot'] and not result['errors']:
        latest='latest-ranger-capture.json' if a.rangers_only else 'latest-character-capture.json'
        (ROOT/'data/research/runtime.private'/latest).write_text(json.dumps({'directory':str(out)},indent=2),encoding='utf8')
    print(json.dumps({'traversal':result['traversal'],'errors':result['errors'],'output':str(out)},ensure_ascii=True))
