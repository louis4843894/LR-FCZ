"""Compare existing and batched reads on known libgame code bytes; no account data."""
import json,base64
import sys
import time
from pathlib import Path
from bounded_equipment_reader import Reader
from equipment_memory import ROOT,GBASE
sys.path.insert(0,str(ROOT/'scripts'))
from native_layouts import NEW_SHA

with Reader(r'C:\LDPlayer\LDPlayer9\adb.exe','emulator-5554',90) as reader:
    reader.expected_module_sha=NEW_SHA
    reader.refresh()
    # Known, read-only native getter code. Same exact byte ranges on both paths.
    offsets=[0x121c474,0x121c4c4,0x121c758,0xf3b85c,0xfb58e8]*4
    requests=[(reader.base+address-GBASE,0x8e8) for address in offsets]
    started=time.perf_counter()
    before=[base64.b64decode(b''.join(reader.shell(f'dd if=/proc/{reader.pid}/mem bs=1 skip={a} count={n} 2>/dev/null | base64').split()),validate=True) for a,n in requests]
    serial=time.perf_counter()-started
    started=time.perf_counter();after=reader.read_many(requests);batch=time.perf_counter()-started
    if before!=after:raise ValueError('batched code reads differ')
    result={'moduleSha256':NEW_SHA,'scope':'20 exact module-code ranges, 2280 bytes each (UnitData size); not a full-capture benchmark','matchingBytes':True,'rangeCount':len(requests),'bytes':sum(n for _,n in requests),'serialSeconds':round(serial,4),'batchSeconds':round(batch,4),'speedup':round(serial/batch,2),'serialShellRoundTrips':20,'batchShellRoundTrips':1}
    (ROOT/'reports/runtime-read-benchmark.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(result))
