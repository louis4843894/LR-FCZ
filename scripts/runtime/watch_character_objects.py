"""Bounded wait for the verified loaded character dictionary; capture only once nonempty."""
import argparse,json,time,uuid
from datetime import datetime,timezone
from pathlib import Path
from bounded_equipment_reader import Reader
from read_character_objects import capture
from equipment_memory import ROOT,GBASE,u64
from native_layouts import layout_for_sha,NEW_SHA
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--seconds',type=int,default=180);p.add_argument('--rangers-only',action='store_true');p.add_argument('--max-records',type=int,default=5);a=p.parse_args()
    if not 1<=a.max_records<=4096:p.error('record bound must be 1..4096')
    if not 1<=a.seconds<=600:p.error('watch bound must be 1..600 seconds')
    start=time.monotonic();last_log=-30
    with Reader(r'C:\LDPlayer\LDPlayer9\adb.exe','emulator-5554',a.seconds+180) as r:
        r.expected_module_sha=NEW_SHA;r.refresh();pid=r.pid;base=r.base;layout=layout_for_sha(r.module_sha)
        while time.monotonic()-start<a.seconds:
            current=r.shell('pidof com.linecorp.LGRGS').decode().strip().split()
            if not current or int(current[0])!=pid:raise RuntimeError('game process changed; stop rather than reuse pointers')
            ptr=u64(r.read(base+layout['characterGlobal']-GBASE,8));head=0
            if ptr:
                raw=r.read(ptr,0xc0)
                if u64(raw)!=base+layout['characterManager']-GBASE:raise ValueError('manager type changed')
                d=u64(raw,0x28)
                if d:head=u64(r.read(d,0x28),0x18)
            if head:
                r.refresh()
                if r.pid!=pid or r.base!=base:raise RuntimeError('pointer lifetime changed')
                out=ROOT/'data/research/runtime.private'/('character-capture-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:6])
                result=capture(r,out,4096 if a.max_records>5 else 128 if a.rangers_only else 5,a.max_records,a.rangers_only,a.rangers_only and a.max_records==5)
                if result['records'] and not result['errors'] and result['traversal']['consistentSnapshot']:
                    (ROOT/'data/research/runtime.private'/('latest-ranger-capture.json' if a.rangers_only else 'latest-character-capture.json')).write_text(json.dumps({'directory':str(out)},indent=2),encoding='utf8')
                print(json.dumps({'output':str(out),'traversal':result['traversal'],'errors':result['errors']},ensure_ascii=True),flush=True)
                break
            elapsed=time.monotonic()-start
            if elapsed-last_log>=30:print('Waiting: verified character dictionary remains empty.',flush=True);last_log=elapsed
            time.sleep(3)
        else:print('Bounded watch ended: no character records loaded; user game screen action remains required.',flush=True)
