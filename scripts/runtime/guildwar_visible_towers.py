"""Read only actual visible fortress layers under the normal guild-war scene."""
import struct
from datetime import datetime,timezone
from equipment_memory import ROOT,GBASE,u64
from read_defense_team import typed
from read_guild_members import array
from native_layouts import NEW_SHA


class VisibilityUnavailable(ValueError):pass


def authorize_codes(mode,expected,rows):
 if mode!=1:raise VisibilityUnavailable('normal_opponent_view_not_selected')
 codes=[r['code'] for r in rows]
 if not rows or len(set(codes))!=len(codes) or set(codes)-set(expected):raise VisibilityUnavailable('visible_tower_set_incomplete_or_ambiguous')
 if any(r['state'] not in (0,1,2,3) for r in rows):raise VisibilityUnavailable('unknown_normal_tower_state')
 allowed={r['code'] for r in rows if r['state']!=3}
 if not allowed:raise VisibilityUnavailable('normal_opponent_tower_locked')
 return allowed


def inspect(r,expected):
 if r.module_sha!=NEW_SHA:raise VisibilityUnavailable('unverified_tower_module')
 for address,code in [(0x1364efc,'006c41b9c0035fd6'),(0x13453c0,'006040b9c0035fd6'),(0x1347790,'001840b9c0035fd6'),(0x1a787bc,'00104439c0035fd6')]:
  if r.read(r.base+address-GBASE,8).hex()!=code:raise VisibilityUnavailable('tower_visibility_getter_differs')
 director=u64(r.read(r.base+0x204e2f0-GBASE,8));scene=u64(r.read(director+0xf0,8));typed(r,scene,8,0x1eb4840)
 manager=u64(r.read(r.base+0x200a320-GBASE,8));m=typed(r,manager,0x68,0x1eb5c00);mode=struct.unpack_from('<I',m,0x60)[0]
 if not u64(m,0x20):raise VisibilityUnavailable('current_opponent_model_not_loaded')
 if mode!=1:raise VisibilityUnavailable('normal_opponent_view_not_selected')
 queue=[(scene,0,[])];seen=set();rows=[]
 while queue:
  if len(seen)>=2048:raise VisibilityUnavailable('visible_scene_node_limit')
  node,depth,ancestors=queue.pop(0)
  if not node or node in seen:continue
  seen.add(node);raw=r.read(node,0x110)
  if not raw[0x104]:continue
  if u64(raw)-r.base+GBASE==0x1eb8320:
   body=typed(r,node,0x178,0x1eb8320);model=u64(body,0x170);model_raw=typed(r,model,0x20,0x1eb5e20)
   code=struct.unpack_from('<I',model_raw,0x18)[0];state=struct.unpack_from('<I',body,0x16c)[0]
   rows.append({'code':code,'state':state,'layer':node,'model':model,'ancestors':ancestors});continue
  children=u64(raw,0xb8)
  if children:
   if depth>=10:raise VisibilityUnavailable('visible_scene_depth_limit')
   pointers,*_=array(r,children,256);queue.extend((p,depth+1,ancestors+[node]) for p in pointers)
 allowed=authorize_codes(mode,expected,rows)
 if u64(r.read(director+0xf0,8))!=scene or r.read(manager+0x60,4)!=m[0x60:0x64]:raise VisibilityUnavailable('visible_war_scene_changed')
 return {'director':director,'scene':scene,'manager':manager,'pid':r.pid,'rows':rows,'allowedCodes':sorted(allowed),'checkedAt':datetime.now(timezone.utc).isoformat()}


def recheck(r,proof,code):
 if r.pid!=proof['pid'] or u64(r.read(proof['director']+0xf0,8))!=proof['scene'] or struct.unpack('<I',r.read(proof['manager']+0x60,4))[0]!=1:raise VisibilityUnavailable('visible_opponent_context_changed')
 row=next((v for v in proof['rows'] if v['code']==code and code in proof['allowedCodes']),None)
 if not row:raise VisibilityUnavailable('tower_was_not_visible')
 body=typed(r,row['layer'],0x178,0x1eb8320)
 if u64(body,0x170)!=row['model'] or not body[0x104] or struct.unpack_from('<I',body,0x16c)[0] not in (0,1,2):raise VisibilityUnavailable('visible_tower_changed_or_locked')
 if any(not flag[0] for flag in r.read_many((p+0x104,1) for p in row['ancestors'])):raise VisibilityUnavailable('tower_parent_is_hidden')
 model=typed(r,row['model'],0x20,0x1eb5e20)
 if struct.unpack_from('<I',model,0x18)[0]!=code:raise VisibilityUnavailable('visible_tower_code_changed')


def public_proof(proof):
 return {'checkedAt':proof['checkedAt'],'sceneType':'GuildWarMainController','viewMode':1,'towerCodes':[r['code'] for r in proof['rows']],'allowedCodes':proof['allowedCodes'],
         'towerStates':{str(r['code']):r['state'] for r in proof['rows']},'moduleSha256':NEW_SHA,'credentialsRead':False,'memoryAddressesIncluded':False}
