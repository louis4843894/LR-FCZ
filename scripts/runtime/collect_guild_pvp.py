"""Bounded normal-UI guild PVP collection. Never edits teams or sends social actions.

Requires 1280x720 Guild member list, verified module and exact roster UID/guild.
Each captured player is independently parsed and committed; progress is resumable.
"""
import argparse,hashlib,json,struct,subprocess,sys,time,uuid,traceback
from datetime import datetime,timezone
from pathlib import Path
from bounded_equipment_reader import Reader
from equipment_memory import ROOT,GBASE,u64
from read_defense_team import capture,typed
from read_visible_member_defense import visible_context
from read_guild_members import find_layer
sys.path.insert(0,str(ROOT/'scripts'))
from native_layouts import NEW_SHA
from parse_runtime_defense import parse_capture
from import_defense_teams import import_file
from local_game_database import sync_database
from local_game_database import get_collection_target

ADB=r'C:\LDPlayer\LDPlayer9\adb.exe'
SERIAL='emulator-5554'
STATE=ROOT/'data/research/runtime.private/guild-bulk-session'

def now():return datetime.now(timezone.utc).isoformat()
def command(*args):return subprocess.run([ADB,'-s',SERIAL,*map(str,args)],capture_output=True,check=True,timeout=25).stdout
def tap(x,y):command('shell','input','tap',x,y);time.sleep(1.2)
def scene(r):
    director=u64(r.read(r.base+0x204e2f0-GBASE,8));node=u64(r.read(director+0xf0,8))
    return node,u64(r.read(node,8))-r.base+GBASE
def wait_scene(r,ap,timeout=15):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        node,actual=scene(r)
        if actual==ap:return node
        time.sleep(.5)
    raise RuntimeError('expected normal scene not reached')
def write_state(state):
    temp=STATE/'progress.tmp';temp.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf8');temp.replace(STATE/'progress.private.json')
def member_tab(r,page=0):
    wait_scene(r,0x1e9b678,15)
    tap(905,175)
    find_layer(r)
    # Returning from FriendHome recreates the guild's announcement tab. The
    # new member layer starts at its top; restore this bounded viewport only.
    for _ in range(page):command('shell','input','swipe',750,520,750,260,1200)
    if page:time.sleep(.7)
def valid_cached_owners(roster):
    doc=json.loads((ROOT/'data/normalized/defense-teams.private.json').read_text(encoding='utf8'))
    result=set()
    for uid in (m['playerId'] for m in roster['members']):
        rows=[r for r in doc['snapshots'] if r['playerId']==uid and r['purpose']=='pvp_defense' and r['status']=='success' and not r.get('unobservedPositionIndices') and r['retrievedAt']>=roster['capturedAt']]
        # Do not assume a B team exists. Cache each validated visible player's
        # observed group(s), without inventing an absent second group.
        if rows:result.add(uid)
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--max-pages',type=int,default=22);parser.add_argument('--start-page',type=int,default=0);parser.add_argument('--max-seconds',type=int,default=2700);a=parser.parse_args()
    if not 1<=a.max_pages<=30 or not 0<=a.start_page<a.max_pages or not 60<=a.max_seconds<=3600:parser.error('bounded page/time limits required')
    STATE.mkdir(parents=True,exist_ok=True)
    if get_collection_target(module='pvp')=='rankings':
        raise RuntimeError('Guild-derived PVP collection disabled: the user selected ranking-first PVP collection')
    roster=json.loads((ROOT/'data/normalized/guild-roster.private.json').read_text(encoding='utf8'))
    known={m['playerId']:m for m in roster['members']};cached=valid_cached_owners(roster);visited=set();started=time.monotonic()
    state={'sourceKind':'bounded-normal-visible-guild-pvp','startedAt':now(),'rosterCapturedAt':roster['capturedAt'],'observedTotal':len(known),'cachedPlayers':len(cached),'players':{},'pagesVisited':0,'stopReason':None}
    if (STATE/'progress.private.json').exists():
        previous=json.loads((STATE/'progress.private.json').read_text(encoding='utf8'))
        (STATE/('previous-'+uuid.uuid4().hex[:6]+'.private.json')).write_text(json.dumps(previous,ensure_ascii=False,indent=2),encoding='utf8')
    size=command('shell','wm','size').decode()
    if '1280x720' not in size:raise RuntimeError('unverified screen dimensions')
    with Reader(ADB,SERIAL,a.max_seconds) as control:
        control.expected_module_sha=NEW_SHA;control.refresh()
        _,initial_scene=scene(control)
        if initial_scene==0x1eee558:
            tap(45,35);member_tab(control)
        elif initial_scene==0x1e9b678:
            try:find_layer(control)
            except RuntimeError:member_tab(control)
        else:raise RuntimeError('start at a verified guild/member scene')
        # Reset through the two normal tabs before restoring a resume viewport.
        tap(675,175);member_tab(control,a.start_page)
        try:
            for page in range(a.start_page,a.max_pages):
                if time.monotonic()-started>a.max_seconds:state['stopReason']='time_limit';break
                if (STATE/'stop').exists():state['stopReason']='user_stop_file';break
                find_layer(control);state['pagesVisited']=page+1
                (STATE/'current.private.png').write_bytes(command('exec-out','screencap','-p'))
                for y in (235,325,415,505):
                    find_layer(control);tap(605,y)
                    try:controller=wait_scene(control,0x1eee558,8)
                    except RuntimeError:
                        if scene(control)[1]==0x1e9b678:
                            # The clipped top/bottom of a row or the separator
                            # can receive a tap without opening a profile.
                            find_layer(control);continue
                        # Never blindly tap through an own-profile/configuration/dialog screen.
                        state['stopReason']='unexpected_member_destination';raise
                    raw=typed(control,controller,0x170,0x1eee558)
                    profile=typed(control,u64(raw,0x138),0x220,0x1e7d650)
                    uid=control.string(profile,0x90).decode('utf8')
                    if uid not in known:state['stopReason']='unmatched_visible_player';raise RuntimeError('UID outside saved roster')
                    visited.add(uid)
                    if uid not in cached and uid not in state['players']:
                        attempted=now();state['players'][uid]={'attemptedAt':attempted,'status':'running'};write_state(state)
                        try:
                            if struct.unpack_from('<I',raw,0x168)[0]!=5:
                                tap(635,625);tap(545,551)
                            # Game's normal request must finish before its own validated object is read.
                            time.sleep(1)
                            out=ROOT/'data/research/runtime.private'/('guild-member-pvp-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:6])
                            with Reader(ADB,SERIAL,600) as reader:
                                reader.expected_module_sha=NEW_SHA;reader.refresh();context=visible_context(reader)
                                if context['playerId']!=uid:raise RuntimeError('visible owner changed before capture')
                                raw_capture=capture(reader,out,True,context)
                            doc=parse_capture(out,all_teams=True)
                            observed=out/'observations.private.json';observed.write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf8')
                            import_file(observed,ROOT/'data/normalized/defense-teams.private.json');sync_database(modules=['pvp'])
                            partial=any(t.get('unobservedPositionIndices') for t in doc['snapshots'])
                            state['players'][uid]={'attemptedAt':attempted,'retrievedAt':raw_capture['capturedAt'],'status':'partial' if partial else 'success','captureDirectory':str(out.relative_to(ROOT)),'teams':len(doc['snapshots']),'members':sum(len(t['members']) for t in doc['snapshots'])}
                            cached.add(uid)
                            print(json.dumps({'event':'captured','completedPlayers':len(cached),'rosterTotal':len(known),'teams':len(doc['snapshots']),'partial':partial}),flush=True)
                        except Exception:
                            error=STATE/('error-'+uuid.uuid4().hex[:6]+'.private.txt');error.write_text(traceback.format_exc(),encoding='utf8')
                            state['players'][uid]={'attemptedAt':attempted,'status':'failed','reasonCode':'visible_capture_failed','diagnostic':error.name}
                            print(json.dumps({'event':'member_failed','completedPlayers':len(cached)}),flush=True)
                    write_state(state)
                    # Only the verified read-only FriendHome back button.
                    wait_scene(control,0x1eee558,3);tap(45,35);member_tab(control,page)
                if set(known)<=cached:state['stopReason']='all_roster_players_observed';break
                command('shell','input','swipe',750,520,750,260,1200);time.sleep(1)
            else:state['stopReason']='page_limit'
        except Exception:
            (STATE/'stopped-error.private.txt').write_text(traceback.format_exc(),encoding='utf8')
            state['stopReason']=state['stopReason'] or 'unexpected_ui_or_device_state'
        finally:
            state.update(finishedAt=now(),visitedPlayers=len(visited),successfulOrCachedPlayers=len(cached),unreadPlayers=len(set(known)-cached),complete=set(known)<=cached)
            write_state(state)
            (STATE/'current.private.png').write_bytes(command('exec-out','screencap','-p'))
            print(json.dumps({k:state[k] for k in ['stopReason','visitedPlayers','successfulOrCachedPlayers','unreadPlayers','complete']}),flush=True)

if __name__=='__main__':main()
