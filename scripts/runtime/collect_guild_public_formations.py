"""Bounded, resumable public guildwar formation copies, not claimed defenses.

Explicit user request to keep candidates for independent review. Uses accepted
top-100 rosters; two workers, >=0.5s between starts, stop on denial/rate-limit.
Only the guildwar branch is retained. No PVP, tower guesses or saved-team POST.
"""
import argparse,hashlib,json,sqlite3,time,threading,urllib.parse,uuid
from concurrent.futures import ThreadPoolExecutor,wait,FIRST_COMPLETED
from datetime import datetime,timezone
from pvp_session import Reader,NEW_SHA,ROOT,load_session
from fetch_ranked_pvp_response import normal_json,AcquisitionStopped
from collect_ranked_pvp_http import acquisition_lock
from probe_ranked_guild_member_groups import selected_group
from guild_public_formations import accept,attempt,SCHEMA
from local_game_database import connect

def collect(args):
 if not 1<=args.max_guilds<=100 or not 1<=args.max_members<=5000 or not 30<=args.max_seconds<=3600:raise ValueError('bounded acquisition parameters required')
 state=ROOT/'data/research/runtime.private/guild-public-formations-session';state.mkdir(exist_ok=True)
 prior=state/'progress.private.json'
 if prior.exists() and json.loads(prior.read_bytes()).get('stopReason') in ('http_access_denied','http_error_429','response_owner_differs'):
  raise AcquisitionStopped('previous_refusal_requires_manual_access_review')
 db=connect();db.executescript(SCHEMA)
 try:
  rank=json.loads(db.execute("SELECT s.payload FROM current_guild_rankings c JOIN guild_rank_sources s USING(snapshot_id) WHERE c.scope='top100'").fetchone()[0])
  rosters={gid:json.loads(p) for gid,p in db.execute('SELECT c.guild_id,s.payload FROM current_ranked_guild_rosters c JOIN guild_roster_sources s USING(source_id)')}
  cached={(gid,uid):at for gid,uid,at in db.execute('SELECT c.guild_id,c.player_id,s.captured_at FROM current_guild_public_formations c JOIN guild_public_formation_sources s USING(source_id)')}
 finally:db.close()
 guilds=sorted(rank['guilds'],key=lambda g:g['rank'])[:args.max_guilds];targets=[];hit=0
 for g in guilds:
  roster=rosters.get(g['guildId'])
  if not roster:continue
  for member in roster['members']:
   prior=cached.get((g['guildId'],member['playerId']))
   if prior and not args.force and (datetime.now(timezone.utc)-datetime.fromisoformat(prior)).total_seconds()<6*3600:hit+=1;continue
   targets.append((g,roster,member))
 targets=targets[:args.max_members];begun=time.monotonic();stop=threading.Event();lock=threading.Lock();next_start=[0.0]
 progress={'startedAt':datetime.now(timezone.utc).isoformat(),'guildsSelected':len(guilds),'targetMembers':len(targets),'cachedMembers':hit,'success':0,'unavailable':0,'failed':0,'units':0,'equipment':0,
  'stopReason':None,'defensesVerified':0,'purpose':'guildwar_attack_formation','pvpImported':False,'credentialsPersisted':False}
 with Reader(r'C:\LDPlayer\LDPlayer9\adb.exe','emulator-5554',100) as r:
  r.expected_module_sha=NEW_SHA;r.refresh();session=load_session(r,authorized=True)
 def one(target):
  guild,roster,member=target
  with lock:
   delay=max(0,next_start[0]-time.monotonic())
   if delay:time.sleep(delay)
   if stop.is_set() or time.monotonic()-begun>args.max_seconds:raise AcquisitionStopped('bounded_collection_stopped')
   next_start[0]=time.monotonic()+.5
  raw,response=normal_json(session,'/player/units/team/equip/uid/'+urllib.parse.quote(member['playerId'],safe=''),purpose='guild-war-member-groups')
  result=response.get('result') or {}
  if result.get('player',{}).get('uid')!=member['playerId']:raise AcquisitionStopped('response_owner_differs')
  if result.get('guild',{}).get('gid')!=guild['guildId']:raise AcquisitionStopped('response_guild_differs_from_roster')
  group=selected_group(result.get('playerUnitTeamGroupMap') or {});at=datetime.now(timezone.utc)
  folder=ROOT/'data/research/runtime.private'/('ranked-guild-war-group-'+at.strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:6]);folder.mkdir()
  saved={'schemaVersion':1,'sourceKind':'normal-public-member-guildwar-group','capturedAt':at.isoformat(),'moduleSha256':NEW_SHA,'gameVersion':'12.4.2',
   'guildId':guild['guildId'],'playerId':member['playerId'],'playerName':member['name'],'rankingSnapshotId':rank['snapshotId'],'rosterSourceId':roster['sourceId'],
   'responseSha256':hashlib.sha256(raw).hexdigest(),'playerUnitTeamGroupMap':{'guildwar':group},'deploymentConfirmed':False,'pvpTeamsIncluded':False,'credentialsIncluded':False}
  (folder/'response.private.json').write_text(json.dumps(saved,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
  return folder
 with ThreadPoolExecutor(max_workers=2) as pool:
  pending={};iterator=iter(targets)
  def submit():
   if stop.is_set():return
   target=next(iterator,None)
   if target:pending[pool.submit(one,target)]=target
  submit();submit()
  while pending:
   done,_=wait(pending,timeout=1,return_when=FIRST_COMPLETED)
   for future in done:
    guild,roster,member=pending.pop(future)
    try:
     folder=future.result();doc=accept(folder);attempt(guild['guildId'],member['playerId'],'success',source_id=doc['sourceId'])
     progress['success']+=1;progress['units']+=sum(len(t['units']) for t in doc['teams']);progress['equipment']+=sum(e['state']=='equipped' for t in doc['teams'] for u in t['units'] for e in u['equipment'].values())
    except Exception as e:
     reason=str(e) if isinstance(e,AcquisitionStopped) else 'public_formation_validation_failed'
     status='unavailable' if reason in ('guildwar_group_shape_unverified','public_team_groups_missing','response_guild_differs_from_roster') else 'failed'
     attempt(guild['guildId'],member['playerId'],status,reason);progress[status]+=1
     if reason in ('http_access_denied','http_error_429','response_owner_differs'):stop.set();progress['stopReason']=reason
    if time.monotonic()-begun>args.max_seconds:stop.set();progress['stopReason']=progress['stopReason'] or 'time_bound'
    progress['elapsedSeconds']=round(time.monotonic()-begun,2)
    (state/'progress.private.json').write_text(json.dumps(progress,indent=2)+'\n',encoding='utf8')
    if (progress['success']+progress['failed']+progress['unavailable'])%10==0:print(json.dumps(progress),flush=True)
    submit()
 progress['finishedAt']=datetime.now(timezone.utc).isoformat();(state/'progress.private.json').write_text(json.dumps(progress,indent=2)+'\n',encoding='utf8');return progress

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--max-guilds',type=int,default=1);p.add_argument('--max-members',type=int,default=50);p.add_argument('--max-seconds',type=int,default=300);p.add_argument('--force',action='store_true');a=p.parse_args()
 try:
  with acquisition_lock():
   result=collect(a);print(json.dumps(result))
   if result['stopReason']:raise SystemExit(1)
 except Exception as e:
  print(json.dumps({'completed':False,'reason':str(e) if isinstance(e,AcquisitionStopped) else type(e).__name__,'oldDataPreserved':True,'credentialsPersisted':False}));raise SystemExit(1)
