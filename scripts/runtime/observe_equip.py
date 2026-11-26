"""Launch/attach target with narrow equipment I/O observation; no secret capture."""
import argparse,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'data/research/runtime.private/python'))
import frida
p=argparse.ArgumentParser();p.add_argument('--seconds',type=int,default=90);p.add_argument('--pid',type=int);p.add_argument('--realm',default='native');a=p.parse_args()
out=ROOT/'data/research/runtime.private';out.mkdir(parents=True,exist_ok=True)
device=frida.get_device_manager().add_remote_device('127.0.0.1:27042')
pid=a.pid or device.spawn(['com.linecorp.LGRGS']);print('PID',pid,flush=True)
s=device.attach(pid,realm=a.realm)
f=(out/'observe-events.jsonl').open('a',encoding='utf8')
def msg(m,data):
 f.write(json.dumps(m,ensure_ascii=True)+'\n');f.flush();print(json.dumps(m,ensure_ascii=True)[:3000],flush=True)
s.on('detached',lambda *x:print('DETACHED',x,flush=True))
script=s.create_script((ROOT/'scripts/runtime/observe_equip.js').read_text(encoding='utf8'));script.on('message',msg);script.load()
if not a.pid:device.resume(pid)
try:
 for i in range(a.seconds//5):
  time.sleep(5)
  try:
   status=script.exports_sync.status();(out/'module-status.json').write_text(json.dumps({'pid':pid,**status},indent=2));
   if i%3==0:print('STATUS',json.dumps(status),flush=True)
  except Exception as e:print(type(e).__name__,str(e),flush=True);break
finally:
 try:s.detach()
 except Exception:pass
 f.close()
