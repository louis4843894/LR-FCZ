"""Resume normal-UI PVP ranking defense capture; no endpoints or social actions."""
import argparse,json,sys,time,subprocess,hashlib,uuid,traceback
from datetime import datetime,timezone
from pathlib import Path
from bounded_equipment_reader import Reader
from equipment_memory import ROOT,GBASE,u64
from pvp_visible_cells import visible_cells
from read_visible_member_defense import visible_context
from read_defense_team import capture
sys.path.insert(0,str(ROOT/'scripts'))
from native_layouts import NEW_SHA
from ranking_database import load_snapshot,latest_attempts,save_capture,save_failure
from parse_runtime_defense import parse_capture

ADB=r'C:\LDPlayer\LDPlayer9\adb.exe';SERIAL='emulator-5554'
STATE=ROOT/'data/research/runtime.private/ranking-session-20261125'
def command(*args):return subprocess.run([ADB,'-s',SERIAL,*map(str,args)],capture_output=True,check=True,timeout=15).stdout
def tap(x,y):command('shell','input','tap',x,y)
def scene(r):
 d=u64(r.read(r.base+0x204e2f0-GBASE,8));s=u64(r.read(d+0xf0,8));return u64(r.read(s,8))-r.base+GBASE
def wait_scene(r,ap,seconds=20):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  if scene(r)==ap:return
  time.sleep(.35)
 raise TimeoutError('normal UI scene did not become ready')

def prepare_scope(r,allowed):
 ap=scene(r)
 if ap==0x1eee558:
  tap(45,35);wait_scene(r,0x1f150f8)
 elif ap!=0x1f150f8:raise ValueError('unexpected UI scene; no automatic dismissal')
 r._pvp_geometry_context=None
 rows=visible_cells(r)
 if rows and all(c['playerId'] in allowed for c in rows):return rows
 # The verified back button recreates the own bronze league. The first normal
 # dropdown choice is Legend in this exact 1280x720 screen/module.
 tap(550,150);time.sleep(.4);tap(500,215);time.sleep(1)
 r._pvp_geometry_context=None
 end=time.monotonic()+20
 while time.monotonic()<end:
  rows=visible_cells(r)
  if rows and all(c['playerId'] in allowed for c in rows):return rows
  time.sleep(.4)
 raise ValueError('visible ranking rows do not match the accepted source')

def choose_cell(r,allowed,pending):
 rows=prepare_scope(r,allowed)
 target=min(pending.values(),key=lambda p:p['rank']);wanted=target['sourceRowIndex']
 seen_ranges={}
 for _ in range(20):
  available=[c for c in rows if c['playerId'] in pending]
  if available:return min(available,key=lambda c:c['rank'])
  if not rows:raise ValueError('no safely tappable verified ranking rows')
  low=min(c['index'] for c in rows);high=max(c['index'] for c in rows)
  key=(low,high);seen_ranges[key]=seen_ranges.get(key,0)+1
  if seen_ranges[key]>3:raise ValueError('ranking scroll stopped making progress')
  down=wanted<low;gap=low-wanted if down else wanted-high
  if gap>15:
   command('shell','input','swipe',620,300 if down else 550,620,560 if down else 270,130)
   time.sleep(1.15)
  else:
   command('shell','input','swipe',620,310 if down else 510,620,470 if down else 350,650)
   time.sleep(.65)
  rows=visible_cells(r)
  if any(c['playerId'] not in allowed for c in rows):raise ValueError('ranking source changed during scrolling')
 raise ValueError('bounded ranking scroll limit')

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--snapshot',required=True);parser.add_argument('--top',type=int,default=200);parser.add_argument('--max-seconds',type=int,default=3600);a=parser.parse_args()
 if not 1<=a.top<=200 or not 30<=a.max_seconds<=3600:parser.error('bounded top/time required')
 ranking=load_snapshot(a.snapshot)
 if ranking['scope']['label']!='傳奇':raise ValueError('only the observed Legend dropdown route is verified')
 allowed={p['playerId']:p for p in ranking['players']};targets={uid:p for uid,p in allowed.items() if p['rank']<=a.top}
 if '1280x720' not in command('shell','wm','size').decode():raise ValueError('unverified physical UI size')
 started=time.monotonic();failed=set();consecutive_failures=0;state={'snapshotId':a.snapshot,'top':a.top,'startedAt':datetime.now(timezone.utc).isoformat(),'stopReason':None,'capturedThisRun':0}
 STATE.mkdir(parents=True,exist_ok=True)
 try:
  while time.monotonic()-started<a.max_seconds:
   if (STATE/'stop').exists():state['stopReason']='user_stop';break
   attempts=latest_attempts(a.snapshot)
   cached={uid for uid,row in attempts.items() if row['status'] in ('success','partial')}
   pending={uid:p for uid,p in targets.items() if uid not in cached and uid not in failed}
   if not pending:state['stopReason']='all_target_players_attempted';break
   with Reader(ADB,SERIAL,180) as r:
    r.expected_module_sha=NEW_SHA;r.refresh();cell=choose_cell(r,allowed,pending)
    tap(283,cell['tapY']);wait_scene(r,0x1eee558)
   uid=cell['playerId'];target=allowed[uid]
   out=ROOT/'data/research/runtime.private'/('ranked-defense-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:6])
   try:
    with Reader(ADB,SERIAL,180) as r:
     r.expected_module_sha=NEW_SHA;r.refresh();ctx=visible_context(r,True)
     if ctx['playerId']!=uid:raise ValueError('visible native UID differs from tapped ranking cell')
     meta=capture(r,out,True,ctx)
    doc=parse_capture(out,all_teams=True)
    (out/'observations.private.json').write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf8')
    link={'rankingSnapshotId':a.snapshot,'rankingSourceCaptureSha256':ranking['sourceCaptureSha256'],'rank':target['rank'],'playerId':uid,'defenseCaptureSha256':hashlib.sha256((out/'capture.json').read_bytes()).hexdigest(),'snapshotIds':[t['snapshotId'] for t in doc['snapshots']],'identityMatch':'exact-native-uid','purpose':'pvp_defense'}
    (out/'ranking-link.private.json').write_text(json.dumps(link,indent=2),encoding='utf8')
    saved=save_capture(a.snapshot,out);state['capturedThisRun']+=1;consecutive_failures=0
    print(json.dumps({'event':'captured','rank':target['rank'],'teams':saved['teams'],'status':saved['status'],'cachedOrCaptured':len(cached&set(targets))+1,'targetPlayers':len(targets)}),flush=True)
   except Exception:
    failed.add(uid);consecutive_failures+=1;(STATE/('capture-error-'+uuid.uuid4().hex[:6]+'.private.txt')).write_text(traceback.format_exc(),encoding='utf8');save_failure(a.snapshot,uid,'capture_validation_failed')
    print(json.dumps({'event':'capture_failed','rank':target['rank'],'previousSuccessPreserved':True}),flush=True)
   (STATE/'progress.private.json').write_text(json.dumps(state,indent=2),encoding='utf8')
   if consecutive_failures>=3:state['stopReason']='repeated_capture_failure';break
   time.sleep(.5)
  else:state['stopReason']='time_limit'
 except Exception:
  (STATE/'stopped-error.private.txt').write_text(traceback.format_exc(),encoding='utf8');state['stopReason']='unexpected_ui_or_source_state'
 finally:
  attempts=latest_attempts(a.snapshot);state.update(finishedAt=datetime.now(timezone.utc).isoformat(),successfulPlayers=sum(attempts.get(uid,{}).get('status')=='success' for uid in targets),partialPlayers=sum(attempts.get(uid,{}).get('status')=='partial' for uid in targets),failedPlayers=sum(attempts.get(uid,{}).get('status')=='failed' for uid in targets),unreadPlayers=sum(uid not in attempts for uid in targets),wholeRankingComplete=False)
  (STATE/'progress.private.json').write_text(json.dumps(state,indent=2),encoding='utf8');print(json.dumps(state),flush=True)

if __name__=='__main__':main()
