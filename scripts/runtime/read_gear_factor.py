"""Read one proven ordinary-gear coefficient, not keys or account fields.

0122dde4 -> GameDBContainer virtual+38 -> GameFactorData virtual+640.
The exact getter instructions, class identities and module SHA are checked.
"""
import json,math,struct,sys
from datetime import datetime,timezone
from pathlib import Path
from bounded_equipment_reader import Reader
from equipment_memory import ROOT,GBASE,u64
from read_defense_team import typed
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from native_layouts import NEW_SHA

def read_factor(r):
    if r.module_sha!=NEW_SHA:raise ValueError('unverified gear coefficient layout')
    getters={0xf3b85c:'000c40f9c0035fd6',0xfb58e8:'00cc43bdc0035fd6'}
    for address,expected in getters.items():
        if r.read(r.base+address-GBASE,8).hex()!=expected:raise ValueError('factor getter code differs')
    manager=u64(r.read(r.base+0x1fd4df8-GBASE,8));raw=typed(r,manager,0x20,0x1e498f0)
    config=u64(raw,0x18);typed(r,config,8,0x1e51208);value=r.read(config+0x3cc,4)
    factor=struct.unpack('<f',value)[0]
    if not math.isfinite(factor):raise ValueError('nonfinite gear coefficient')
    if u64(r.read(manager+0x18,8))!=config or r.read(config+0x3cc,4)!=value:raise ValueError('factor changed during capture')
    return {'schemaVersion':1,'sourceKind':'verified-ordinary-gear-factor','capturedAt':datetime.now(timezone.utc).isoformat(),'moduleSha256':r.module_sha,'pid':r.pid,
            'rootGlobal':'01fd4df8','managerVtable':'01e498f0','configVtable':'01e51208','getterInstructions':{f'{k:08x}':v for k,v in getters.items()},
            'coefficientOffset':'0x3cc','coefficientRawHex':value.hex(),'coefficient':factor,'formulaFunction':'0122dde4','formatterFunction':'0122f510','typeNameFunction':'0122f924'}

if __name__=='__main__':
    with Reader(r'C:\LDPlayer\LDPlayer9\adb.exe','emulator-5554',40) as r:
        r.expected_module_sha=NEW_SHA;r.refresh();data=read_factor(r)
    output=ROOT/'data/research/runtime.private'/('gear-factor-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.private.json')
    output.write_text(json.dumps(data,indent=2),encoding='utf8');print(json.dumps({'output':str(output.relative_to(ROOT)),'coefficient':data['coefficient']}))
