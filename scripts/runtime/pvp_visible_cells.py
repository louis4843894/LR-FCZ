"""Read verified PVP row identities and CCNode geometry; never calls game code."""
import math,struct,sys
from pathlib import Path
from equipment_memory import ROOT,GBASE,u64
from read_pvp_rankings import find_layer,ROW
from read_guild_members import array
from read_defense_team import typed
sys.path.insert(0,str(ROOT/'scripts'))
from native_elf import NativeELF
from native_layouts import NEW_SHA

CELL=0x1f14730
# Exact exported getters, checked against the same native module before use.
# add x0,x0,#offset / ldr s0,[x0,#offset] / ldr x0 / ldrb w0, then ret.
GETTERS={
 'position':(0x1a7857c,0x9100b000,0x2c),'anchorInPoints':(0x1a787cc,0x9100f000,0x3c),
 'parent':(0x1a78924,0xf9406000,0xc0),'scaleX':(0x1a78544,0xbd402000,0x20),
 'scaleY':(0x1a78560,0xbd402400,0x24),'rotationX':(0x1a784f0,0xbd401800,0x18),
 'rotationY':(0x1a7850c,0xbd401c00,0x1c),'skewX':(0x1a7842c,0xbd403400,0x34),
 'skewY':(0x1a78448,0xbd403800,0x38),'visible':(0x1a787bc,0x39441000,0x104),
 'ignoreAnchor':(0x1a78934,0x39441400,0x105),
}
_verified=False

def verify_geometry_module():
 global _verified
 if _verified:return
 elf=NativeELF(ROOT/'data/research/runtime.private/modules/libgame-12.4.2-pull.so')
 if elf.sha256!=NEW_SHA:raise ValueError('geometry metadata module differs')
 for _,(address,instruction,_) in GETTERS.items():
  if struct.unpack_from('<II',elf.data,elf.offset(address))!=(instruction,0xd65f03c0):raise ValueError('CCNode getter evidence differs')
 # CCDirector::getWinSize: add x1,x0,#0x120; mov x0,x8; b CCSize copy.
 if struct.unpack_from('<II',elf.data,elf.offset(0x1a82ae0))!=(0x91048001,0xaa0803e0):raise ValueError('director size source differs')
 _verified=True

def visible_cells(r):
 if r.module_sha!=NEW_SHA:raise ValueError('unverified PVP geometry module')
 verify_geometry_module()
 cached=getattr(r,'_pvp_geometry_context',None)
 if cached and u64(r.read(cached[0]+0xf0,8))==cached[1] and u64(r.read(cached[2],8))-r.base+GBASE==0x1f14af8:
  director,scene,layer=cached
 else:
  director,scene,layer=find_layer(r);r._pvp_geometry_context=(director,scene,layer)
 width,height=struct.unpack('<ff',r.read(director+0x120,8))
 # Actual game design viewport is 568x320, slightly rounded from 16:9.
 if not (100<=height<=2000 and abs(width/height-1280/720)<.01):raise ValueError('unverified game viewport')
 pending=[(layer,0)];seen=set();cells=[];cache={}
 def node_raw(address):
  if address not in cache:cache[address]=r.read(address,0x110)
  return cache[address]
 def center_y(address):
  # tableCellSizeForIndex 0174554c supplies 43 logical units per row.
  y=21.5;visited=set()
  for _ in range(16):
   if not address:return (height-y)*720/height
   if address in visited:raise ValueError('CCNode parent cycle')
   visited.add(address);raw=node_raw(address)
   if not raw[0x104]:return None
   if any(abs(struct.unpack_from('<f',raw,offset)[0])>.0001 for offset in [0x18,0x1c,0x34,0x38]):raise ValueError('rotated ranking row requires another verified transform')
   scale=struct.unpack_from('<f',raw,0x24)[0];position=struct.unpack_from('<f',raw,0x30)[0];anchor=struct.unpack_from('<f',raw,0x40)[0]
   if not all(math.isfinite(v) for v in [scale,position,anchor]) or scale<=0:raise ValueError('invalid row geometry')
   y=(y-anchor)*scale+position+(anchor if raw[0x105] else 0)
   address=u64(raw,0xc0)
  raise ValueError('CCNode parent depth bound')
 while pending and len(seen)<320:
  node,depth=pending.pop(0)
  if not node or node in seen:continue
  seen.add(node);raw=node_raw(node)
  if not raw[0x104]:continue
  if u64(raw)-r.base+GBASE==CELL:
   body=typed(r,node,0x170,CELL);model=typed(r,u64(body,0x160),0xb0,ROW)
   uid=r.string(body,0x130).decode('utf8');index=struct.unpack_from('<I',body,0x128)[0]
   if uid!=r.string(model,0x18).decode('utf8'):raise ValueError('row UID differs from RankingData')
   y=center_y(node)
   if y is not None and 218<=y<=603:cells.append({'playerId':uid,'rank':struct.unpack_from('<i',model,0x34)[0],'index':index,'tapY':round(y)})
   continue
  if depth<8 and u64(raw,0xb8):
   children,*_=array(r,u64(raw,0xb8),128);pending.extend((child,depth+1) for child in children)
 if pending:raise ValueError('ranking cell traversal bound')
 return sorted(cells,key=lambda c:c['index'])
