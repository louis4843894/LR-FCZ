"""Bounded, read-only capture of the currently visible guild member list.

12.4.2 evidence: guild-member-list-model-link.txt, guild-member-model-getters.txt,
guild-member-fields.txt, guild-count-getters.txt. Never enters another screen.
"""
import hashlib,json,struct,sys,uuid
from datetime import datetime,timezone
from pathlib import Path
from bounded_equipment_reader import Reader
from equipment_memory import ROOT,GBASE,u64
from read_defense_team import typed
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from native_layouts import NEW_SHA,layout_for_sha

def array(r,address,limit=128):
    raw=typed(r,address,0x20,layout_for_sha(r.module_sha)['arrayVtable'])
    data=r.read(u64(raw,0x18),16);count,capacity=struct.unpack_from('<II',data)
    if count>limit or count>capacity or capacity>4096:raise ValueError('array bounds')
    pointers=r.read(u64(data,8),count*8) if count else b''
    return [u64(pointers,i*8) for i in range(count)],raw,data,pointers

def find_layer(r):
    director=u64(r.read(r.base+0x204e2f0-GBASE,8))
    scene=u64(r.read(director+0xf0,8))
    typed(r,scene,8,0x1e9b678) # GuildController, not a generic scene
    queue=[(scene,0)];seen=set()
    while queue and len(seen)<320:
        node,depth=queue.pop(0)
        if not node or node in seen:continue
        seen.add(node);raw=r.read(node,0xc0)
        if u64(raw)-r.base+GBASE==0x1ea22f8:return node
        if depth<7 and u64(raw,0xb8):
            children,*_=array(r,u64(raw,0xb8))
            queue.extend((child,depth+1) for child in children)
    raise RuntimeError('visible GuildMemberListLayer not found within bounds')

def capture(r,out):
    layer=find_layer(r);layer_raw=typed(r,layer,0x190,0x1ea22f8)
    info=u64(layer_raw,0x180);guild=typed(r,info,0xa8,0x1eadb48)
    member_array=u64(layer_raw,0x178)
    # init 0128bad4: this+178 = source virtual+c0; +180 = GuildInfoModel.
    if member_array!=u64(guild,0x70):raise ValueError('UI/model member-list mismatch')
    pointers,header,data,items=array(r,member_array)
    if len(set(pointers))!=len(pointers):raise ValueError('duplicate member object pointers')
    out.mkdir(parents=True,exist_ok=False);files={}
    def save(name,blob):
        filename=name+'.bin';(out/filename).write_bytes(blob)
        files[name]={'file':filename,'sha256':hashlib.sha256(blob).hexdigest(),'length':len(blob)}
    def text(name,pointer):
        raw=typed(r,pointer,0x30,0x1f6a7a8);save(name+'-object',raw)
        save(name,r.string(raw,0x18))
    save('guild',guild);save('array',header);save('array-data',data);save('member-pointers',items)
    text('guild-id',u64(guild,0x30));text('guild-name',u64(guild,0x38))
    errors=[];members=[]
    for index,address in enumerate(pointers):
        prefix=f'member-{index:03d}'
        try:
            raw=typed(r,address,0x60,0x1eade20);save(prefix,raw)
            for label,offset in [('id',0x30),('guild-id',0x38),('name',0x40)]:text(prefix+'-'+label,u64(raw,offset))
            members.append({'index':index,'status':'captured'})
        except (ValueError,RuntimeError) as error:
            errors.append({'index':index,'error':str(error)});members.append({'index':index,'status':'failed'})
    final,*_=array(r,member_array)
    if final!=pointers or u64(r.read(layer+0x180,8))!=info:raise ValueError('guild source changed during capture')
    result={'schemaVersion':1,'sourceKind':'native-visible-guild-members','parserVersion':'guild-members-v1','capturedAt':datetime.now(timezone.utc).isoformat(),'gameVersion':'12.4.2','moduleSha256':r.module_sha,'pid':r.pid,'moduleBase':r.base,'loadedCount':len(pointers),'members':members,'errors':errors,'consistent':True,'files':files}
    (out/'capture.private.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    return {'loaded':len(pointers),'captured':len(pointers)-len(errors),'errors':len(errors),'output':str(out.relative_to(ROOT))}

if __name__=='__main__':
    out=ROOT/'data/research/runtime.private'/('guild-members-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:6])
    with Reader(r'C:\LDPlayer\LDPlayer9\adb.exe','emulator-5554',180) as r:
        r.expected_module_sha=NEW_SHA;r.refresh();print(json.dumps(capture(r,out)))
