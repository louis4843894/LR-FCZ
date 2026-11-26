"""Read only the verified equipment singleton/dictionary via existing root access.
No injection, permission changes, whole-process dumps, or key capture.
"""
from __future__ import annotations
import argparse,base64,hashlib,json,struct,subprocess,time,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/research/runtime.private/objects'
GBASE=0x100000
EXPECTED_SHA='8795d855d2f0aff223c93d6ee7ea3cadd01859dbbbaa15846a07dbfcf07b5d97'
def u64(b,o=0):return struct.unpack_from('<Q',b,o)[0]
def memory_read_command(pid,address,count):
  # dd skip/count are in blocks. A common divisor reads the EXACT requested
  # interval in fewer syscalls, including on old Android dd without skip_bytes.
  block=math.gcd(address,count)
  return f'dd if=/proc/{pid}/mem bs={block} skip={address//block} count={count//block} 2>/dev/null | base64'
class Reader:
 def __init__(self,adb,serial):self.adb=adb;self.serial=serial
 def shell(self,command):
  r=subprocess.run([self.adb,'-s',self.serial,'shell','-T','su','-c',"'"+command+"'"],capture_output=True,timeout=30)
  if r.returncode:raise RuntimeError(r.stderr.decode('utf8','replace')[:300])
  return r.stdout
 def refresh(self):
  text=self.shell('pidof com.linecorp.LGRGS').decode().strip()
  if not text:raise RuntimeError('game is not running')
  self.pid=int(text.split()[0]);self.maps=self.shell(f'cat /proc/{self.pid}/maps').decode('utf8','replace');self.ranges=[];self.base=None
  for line in self.maps.splitlines():
   f=line.split();start,end=(int(x,16) for x in f[0].split('-'))
   if 'r' in f[1]:self.ranges.append((start,end))
   if '/lib/arm64/libgame.so' in line and f[2]=='00000000':self.base=start;self.module=f[-1]
  if self.base is None:raise RuntimeError('matching ARM64 libgame not loaded')
  sha=self.shell('sha256sum '+self.module).decode().split()[0]
  if sha!=getattr(self,'expected_module_sha',EXPECTED_SHA):raise RuntimeError('module hash differs; refusing static offsets')
  self.module_sha=sha
  if self.read(self.base,4)!=b'\x7fELF':raise RuntimeError('module base did not validate')
 def read(self,address,count):
  if count<1 or count>16384 or not any(a<=address and address+count<=b for a,b in self.ranges):raise RuntimeError('requested read exceeds known readable mapping')
  encoded=self.shell(memory_read_command(self.pid,address,count))
  data=base64.b64decode(b''.join(encoded.split()),validate=True)
  if len(data)!=count:raise RuntimeError(f'short read: expected {count}, received {len(data)}')
  return data
