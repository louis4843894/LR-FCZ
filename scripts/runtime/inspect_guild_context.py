"""Prepare a bounded own-guild context without assuming a member model layout.
Run after the operator opens the normally visible guild member list. This probe
does not claim guild membership or fetch player data from any endpoint.
"""
import json,sys,uuid,time,struct
from pathlib import Path
from datetime import datetime,timezone
from bounded_equipment_reader import Reader
from equipment_memory import ROOT,GBASE,u64
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from native_layouts import NEW_SHA,layout_for_sha
from native_elf import NativeELF

def inspect(reader):
    layout=layout_for_sha(reader.module_sha)
    result={'schemaVersion':1,'sourceKind':'own-guild-context-probe','capturedAt':datetime.now(timezone.utc).isoformat(),'gameVersion':layout['version'],'moduleSha256':reader.module_sha,'pid':reader.pid,'moduleBase':reader.base,'memberCount':None,'membersRetrieved':0,'membershipComplete':False}
    manager=u64(reader.read(reader.base+layout['guildWarGlobal']-GBASE,8))
    if not manager:return {**result,'status':'not_initialized','reason':'own guild manager not initialized; guild membership is unknown'}
    raw=reader.read(manager,0xc0)
    if u64(raw)-reader.base+GBASE!=layout['guildWarManager']:raise ValueError('GuildWarDataManager type mismatch')
    elf=NativeELF(ROOT/'data/research/runtime.private/modules/libgame-12.4.2-pull.so')
    if elf.sha256!=reader.module_sha:raise ValueError('static/runtime metadata module mismatch')
    models=[]
    # Only retained CCObject fields confirmed by the exact class destructor.
    for offset in [0x18,0x20,0x38,0x40,0x48,0x50,0x78,0x80,0x88,0x90]:
        pointer=u64(raw,offset)
        if not pointer:models.append({'offset':hex(offset),'state':'not_loaded'});continue
        ap=u64(reader.read(pointer,8))-reader.base+GBASE
        try:class_name=elf.type_name(ap)
        except ValueError:class_name=None
        row={'offset':hex(offset),'state':'type_observed' if class_name else 'unknown_type','vtable':hex(ap),'className':class_name}
        if ap==layout['arrayVtable']:
            header=reader.read(pointer,0x20);row['containerCount']=struct.unpack_from('<I',reader.read(u64(header,0x18),4))[0]
        elif ap==layout['dictionaryVtable']:
            header=reader.read(pointer,0x28);row['headPresent']=bool(u64(header,0x18))
        models.append(row)
    return {**result,'status':'guildwar_manager_observed','models':models,'reason':'Exact GuildWarDataManager; member fields still require proof for observed models'}

if __name__=='__main__':
    with Reader(r'C:\LDPlayer\LDPlayer9\adb.exe','emulator-5554',60) as r:
        r.expected_module_sha=NEW_SHA;r.refresh();result=inspect(r)
    output=ROOT/'data/research/runtime.private'/('guild-context-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:6]+'.private.json')
    output.write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps({k:result[k] for k in ['status','reason','membersRetrieved']}))
