"""Capture the current normal FriendHome PVP defense; no UI changes or injection.

Requires exact verified 12.4.2 module, mode5, and a UID/guild match against the
saved real guild roster. Own UnitManager is never used by this entry point.
"""
import argparse,hashlib,json,struct,sys,uuid
from datetime import datetime,timezone
from pathlib import Path
from bounded_equipment_reader import Reader
from equipment_memory import ROOT,GBASE,u64
from read_defense_team import typed,capture
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from native_layouts import NEW_SHA

def visible_context(r,allow_visible_player=False):
    if r.module_sha!=NEW_SHA:raise ValueError('visible member layout not verified for this module')
    roster=json.loads((ROOT/'data/normalized/guild-roster.private.json').read_text(encoding='utf8'))
    if roster['sourceKind']!='validated-native-guild-roster':raise ValueError('unverified roster source')
    director=u64(r.read(r.base+0x204e2f0-GBASE,8));controller=u64(r.read(director+0xf0,8))
    scene=typed(r,controller,0x170,0x1eee558)
    if struct.unpack_from('<I',scene,0x168)[0]!=5:raise ValueError('visible page is not PVP defense mode5')
    profile=u64(scene,0x138);raw=typed(r,profile,0x220,0x1e7d650)
    uid=r.string(raw,0x90);name=r.string(raw,0x48)
    matches=[m for m in roster['members'] if m['playerId']==uid.decode('utf8')]
    matched=len(matches)==1 and matches[0]['name']==name.decode('utf8')
    if not matched and not allow_visible_player:raise ValueError('visible player does not match one saved guild member')
    guild=typed(r,u64(raw,0x150),0x40,0x1eadb48)
    guild_string=typed(r,u64(guild,0x30),0x30,0x1f6a7a8);guild_id=r.string(guild_string,0x18)
    matched=matched and guild_id.decode('utf8')==roster['guildId']
    if not matched and not allow_visible_player:raise ValueError('visible member guild differs from roster')
    selected=struct.unpack_from('<I',raw,0x160)[0]
    if selected not in (1,2) or struct.unpack_from('<I',scene,0x148)[0]!=selected:raise ValueError('displayed and selected PVP team differ')
    groups=u64(raw,0x198)
    def validate():
        if u64(r.read(director+0xf0,8))!=controller:raise ValueError('visible scene changed')
        current=typed(r,controller,0x170,0x1eee558)
        if u64(current,0x138)!=profile or struct.unpack_from('<I',current,0x168)[0]!=5 or struct.unpack_from('<I',current,0x148)[0]!=selected:raise ValueError('visible defense context changed')
        current=typed(r,profile,0x220,0x1e7d650)
        if r.string(current,0x90)!=uid or u64(current,0x198)!=groups or struct.unpack_from('<I',current,0x160)[0]!=selected or u64(current,0x150)!=u64(raw,0x150):raise ValueError('visible player source changed')
    blobs={'controller':scene,'profile':raw,'profile-id':uid,'profile-name':name,'guild':guild,'guild-id':guild_id}
    if matched:blobs.update({'roster-member-id':matches[0]['playerId'].encode('utf8'),'roster-guild-id':roster['guildId'].encode('utf8')})
    return {'kind':'visible-guild-member' if matched else 'visible-player','playerId':uid.decode('utf8'),'guildId':guild_id.decode('utf8'),'rosterCapturedAt':roster['capturedAt'] if matched else None,'usePvPTeamNo':selected,'groups':groups,'profile':profile,'controller':controller,'validate':validate,'blobs':blobs}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--allow-visible-player',action='store_true',help='Preserve an unrelated normally visible PVP player without claiming saved-guild membership');a=p.parse_args()
    out=ROOT/'data/research/runtime.private'/('member-defense-capture-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:6])
    with Reader(r'C:\LDPlayer\LDPlayer9\adb.exe','emulator-5554',600) as r:
        r.expected_module_sha=NEW_SHA;r.refresh();context=visible_context(r,a.allow_visible_player);result=capture(r,out,True,context)
    (ROOT/'data/research/runtime.private/latest-member-defense-capture.private.json').write_text(json.dumps({'directory':str(out)}),encoding='utf8')
    print(json.dumps({'captured':len(result['records']),'equipment':sum(len(x['equipment']) for x in result['records']),'output':str(out.relative_to(ROOT))}))
