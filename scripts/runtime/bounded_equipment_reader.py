"""Bounded capture; max-nodes counts VISITED nodes, not just successful records."""
from __future__ import annotations
import argparse,base64,hashlib,json,queue,re,shlex,shutil,struct,subprocess,threading,time,uuid
from datetime import datetime,timezone
from pathlib import Path
from equipment_memory import Reader as BaseReader,OUT,GBASE,EXPECTED_SHA,u64,memory_read_command
class RootShell:
 def __init__(self,adb,serial):
  self.p=subprocess.Popen([adb,'-s',serial,'shell','-T','su','0','sh'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL);self.q=queue.Queue()
  def pump():
   for line in iter(self.p.stdout.readline,b''):self.q.put(line)
   self.q.put(None)
  threading.Thread(target=pump,daemon=True).start()
 def run(self,command):
  marker='__LR_'+uuid.uuid4().hex;self.p.stdin.write((f'echo {marker}\n{command}\nlr_status=$?\nprintf "\\n{marker}:%s\\n" "$lr_status"\n').encode());self.p.stdin.flush();begun=False;out=[]
  while True:
   try:line=self.q.get(timeout=20)
   except queue.Empty:self.close();raise TimeoutError('root command timeout')
   if line is None:raise RuntimeError('root shell disconnected')
   tag=line.strip()
   if tag==marker.encode():begun=True;continue
   if begun and tag.startswith((marker+':').encode()):
    if int(tag.split(b':')[-1]):raise RuntimeError('remote command failed')
    return b''.join(out).rstrip(b'\r\n')
   if begun:out.append(line)
 def close(self):
  if self.p.poll() is None:
   try:self.p.stdin.write(b'exit\n');self.p.stdin.flush();self.p.wait(timeout=2)
   except (OSError,subprocess.TimeoutExpired):self.p.kill()
class Reader(BaseReader):
 def __init__(self,adb,serial,max_seconds=600):
  self.adb=adb;self.serial=serial;self.remote=RootShell(adb,serial);self.started=time.monotonic();self.max_seconds=max_seconds;self.read_count=0;self.read_bytes=0;self.shell_calls=0
 def close(self):self.remote.close()
 def shell(self,command):
  self.shell_calls+=1;return self.remote.run(command)
 def read(self,address,count):
  if time.monotonic()-self.started>self.max_seconds:raise TimeoutError('capture time budget reached')
  if self.read_count>=20000 or self.read_bytes+count>32*1024*1024:raise RuntimeError('read budget reached')
  self.read_count+=1;self.read_bytes+=count;return super().read(address,count)
 def read_many(self,requests):
  """One shell round trip for known bounded ranges; no page cache or stale pointer reuse."""
  requests=list(requests)
  if not requests:return []
  if len(requests)>128 or sum(n for _,n in requests)>256*1024:raise ValueError('batch exceeds bounds')
  if time.monotonic()-self.started>self.max_seconds:raise TimeoutError('capture time budget reached')
  if self.read_count+len(requests)>20000 or self.read_bytes+sum(n for _,n in requests)>32*1024*1024:raise RuntimeError('read budget reached')
  for address,count in requests:
   if type(address) is not int or type(count) is not int or not 1<=count<=16384 or not any(a<=address and address+count<=b for a,b in self.ranges):raise RuntimeError('requested read exceeds known readable mapping')
  self.read_count+=len(requests);self.read_bytes+=sum(n for _,n in requests)
  commands=[memory_read_command(self.pid,address,count).removesuffix(' | base64') for address,count in requests]
  # One base64 process for the whole bounded batch; each dd emits at most its
  # exact requested byte count. Any short read invalidates the entire response.
  output=self.shell('{\n'+'\n'.join(commands)+'\n} | base64')
  data=base64.b64decode(b''.join(output.split()),validate=True)
  if len(data)!=sum(n for _,n in requests):raise RuntimeError('short or incomplete batch read')
  chunks=[];offset=0
  for _,count in requests:
   chunks.append(data[offset:offset+count]);offset+=count
  return chunks
 def string(self,data,offset):
  if data[offset]&1:
   n=u64(data,offset+8)
   if n>1024:raise ValueError('long string exceeds capture bound')
   return self.read(u64(data,offset+16),n) if n else b''
  n=data[offset]>>1
  if n>22:raise ValueError('invalid short string')
  return data[offset+1:offset+1+n]
 def capture(self,max_nodes,output,resume=None):
  if not 1<=max_nodes<=2048:raise ValueError('max-nodes must be 1..2048 visited nodes')
  output=Path(output);output.mkdir(parents=True,exist_ok=False)
  global_address=self.base+(0x1fd5270-GBASE);manager=u64(self.read(global_address,8))
  if not manager:raise RuntimeError('equipment singleton not initialized')
  m=self.read(manager,0x88)
  if u64(m)!=self.base+(0x1e4a950-GBASE):raise ValueError('manager vtable mismatch')
  d=u64(m,0x18);dh=self.read(d,0x28);node=u64(dh,0x18);seen=set();records=[];errors=[];reason='node_limit'
  (output/'manager.bin').write_bytes(m);(output/'dictionary.bin').write_bytes(dh)
  initial_head=node;consistent=True
  if resume:
   previous=json.loads((Path(resume)/'capture.json').read_text(encoding='utf8'))
   if previous['pid']!=self.pid or previous['moduleBase']!=self.base or previous['dictionaryAddress']!=d:raise RuntimeError('resume pointer lifetime differs')
   if previous.get('traversal',{}).get('errors'):raise RuntimeError('cannot resume a capture with unresolved errors')
   records=list(previous['records']);seen={r['entryAddress'] for r in records}
   if records and initial_head!=records[0]['entryAddress']:raise RuntimeError('container head changed since saved capture')
   for file in Path(resume).iterdir():
    if file.is_file() and file.suffix=='.bin':shutil.copyfile(file,output/file.name)
   if records:
    last=records[-1];last_entry=Path(resume)/last['rawFile'].replace('record-','entry-')
    saved_next=u64(last_entry.read_bytes(),0x120)
    if u64(self.read(last['entryAddress']+0x120,8))!=saved_next:raise RuntimeError('resume link changed')
    node=saved_next
  while node and len(seen)<max_nodes:
   if node in seen:reason='cycle';errors.append({'node':node,'error':'repeated node'});break
   seen.add(node)
   try:entry=self.read(node,0x128)
   except Exception as e:reason='node_read_failure';errors.append({'node':node,'error':str(e)});break
   nxt=u64(entry,0x120);i=len(seen)-1
   try:
    key=entry[:256].split(b'\0',1)[0].decode('utf8','strict')
    if not re.fullmatch(r'eq_[A-Za-z0-9_]+',key):raise ValueError('non-equipment dictionary key')
    obj=u64(entry,0x108);raw=self.read(obj,0x160)
    if u64(raw)!=self.base+(0x1e986a8-GBASE):raise ValueError('equipment record vtable mismatch')
    code=self.string(raw,0x20)
    if code.decode('utf8')!=key:raise ValueError('dictionary key differs from itemCode')
    g=self.read(u64(raw,0x50),0x30)
    if u64(g)!=self.base+(0x1f65b70-GBASE):raise ValueError('grade wrapper vtable mismatch')
    st=self.read(u64(g,0x20),0x30);cipher=self.string(st,0x18)
    blobs={'entry':entry,'record':raw,'grade':g,'grade-string':st,'grade-cipher':cipher,'item-code':code}
    for kind,b in blobs.items():(output/f'{kind}-{i}.bin').write_bytes(b)
    records.append({'key':key,'entryAddress':node,'objectAddress':obj,'vtable':u64(raw),'rawFile':f'record-{i}.bin','itemCodeFile':f'item-code-{i}.bin','gradeFile':f'grade-{i}.bin','gradeStringFile':f'grade-string-{i}.bin','gradeCipherFile':f'grade-cipher-{i}.bin','sha256':{k:hashlib.sha256(b).hexdigest() for k,b in blobs.items()}})
   except Exception as e:
    errors.append({'node':node,'error':str(e)})
    if isinstance(e,TimeoutError) or 'budget' in str(e):reason='budget';break
   if u64(self.read(node+0x120,8))!=nxt:
    consistent=False;reason='container_changed';errors.append({'node':node,'error':'next pointer changed during capture'});break
   node=nxt
   if len(seen)%25==0:print(f'Visited {len(seen)}; captured {len(records)}; errors {len(errors)}',flush=True)
  if not node:reason='null_tail'
  try:
   if u64(self.read(global_address,8))!=manager or u64(self.read(d+0x18,8))!=initial_head:
    consistent=False;reason='container_changed';errors.append({'error':'manager or dictionary head changed'})
  except Exception as e:
   consistent=False;errors.append({'error':'final consistency check unavailable: '+str(e)})
  result={'pid':self.pid,'moduleBase':self.base,'ghidraImageBase':GBASE,'moduleSha256':EXPECTED_SHA,'gameVersion':'12.4.0','versionCode':201240,'globalAddress':global_address,'managerAddress':manager,'dictionaryAddress':d,'records':records,'capturedRecordCount':len(records),'complete':False,'coverage':{'scope':'loaded-equipment-manager','wholeGameComplete':False,'reason':'no independent total-equipment inventory'},'traversal':{'stopReason':reason,'visitedNodeCount':len(seen),'maxNodes':max_nodes,'loadedListEnded':node==0,'consistentSnapshot':consistent,'resumedFrom':str(resume) if resume else None,'errors':errors},'readCount':self.read_count,'readBytes':self.read_bytes,'capturedAt':time.time()}
  (output/'capture.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');(OUT.parent/'latest-capture.json').write_text(json.dumps({'directory':str(output.resolve())}),encoding='utf8');return result
 def __enter__(self):return self
 def __exit__(self,*args):self.close()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--adb',default=r'C:\LDPlayer\LDPlayer9\adb.exe');p.add_argument('--serial',default='emulator-5554');p.add_argument('--max-nodes',type=int,default=256);p.add_argument('--max-seconds',type=int,default=600);p.add_argument('--output',type=Path);p.add_argument('--resume-capture',type=Path);a=p.parse_args()
 if not 1<=a.max_nodes<=2048 or not 1<=a.max_seconds<=1800:p.error('node/time limits out of range')
 output=a.output or OUT.parent/('capture-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:6])
 with Reader(a.adb,a.serial,a.max_seconds) as r:r.refresh();result=r.capture(a.max_nodes,output,a.resume_capture)
 print(json.dumps({'capturedCount':len(result['records']),'coverageComplete':False,'traversal':result['traversal'],'output':str(output)},ensure_ascii=True),flush=True)
