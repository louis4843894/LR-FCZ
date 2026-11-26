"""Collect the game's actual guild-war ranks 1-100 and visible rosters.

Explicitly authorized local session only; no UI navigation or PVP acquisition.
Known normal GETs: 012a386c, 0125386c, 01259a0c. Guild-player session,
admission, help, online timestamps and response headers are never persisted.
"""
import argparse,hashlib,json,sys,time,uuid,threading,urllib.parse
from concurrent.futures import ThreadPoolExecutor,wait,FIRST_COMPLETED
from datetime import datetime,timezone
from pathlib import Path
from pvp_session import Reader,NEW_SHA,ROOT,load_session
from fetch_ranked_pvp_response import normal_json,AcquisitionStopped
from collect_ranked_pvp_http import acquisition_lock
sys.path.insert(0,str(ROOT/'scripts'))
from guild_rank_database import accept_rankings,current_ranking,accept_roster,connection,attempt
from local_game_database import latest_guild_boundary


def rank_copy(session,grade):
    raw,doc=normal_json(session,f'/guildwar/rank/total?gradeId={grade}',purpose='guild-ranking')
    data=doc['result']['totalRank'];fields=['uid','rank','score','displayName','nationalFlag','curMemberCount','maxMemberCount','level']
    selected=[{k:r[k] for k in fields} for r in data['rankingList']]
    now=datetime.now(timezone.utc);folder=ROOT/'data/research/runtime.private'/('guild-ranking-http-'+now.strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:6]);folder.mkdir()
    saved={'sourceKind':'normal-guildwar-ranking-response','gameVersion':'12.4.2','moduleSha256':NEW_SHA,'gradeId':grade,'capturedAt':now.isoformat(),'responseSha256':hashlib.sha256(raw).hexdigest(),'result':{'totalRank':{'totalCount':data['totalCount'],'rankingList':selected}}}
    (folder/'rank-response.private.json').write_text(json.dumps(saved,ensure_ascii=False,indent=2)+'\n',encoding='utf8');return folder


def collect(args,session=None):
    started=time.monotonic();boundary=latest_guild_boundary(datetime.now(timezone.utc));current=current_ranking()
    if args.ranking_copies:ranking=accept_rankings(args.ranking_copies)
    elif not args.force and current and datetime.fromisoformat(current.get('lastCheckedAt',current['capturedAt']))>=boundary:ranking=current
    else:
        session=session or runtime_session();copies=[]
        for grade in (1,2):copies.append(rank_copy(session,grade));time.sleep(.5)
        ranking=accept_rankings(copies)
    if ranking['status']!='success':raise AcquisitionStopped('incomplete_guild_rank_range')
    db=connection()
    try:
        cached={gid:json.loads(p) for gid,p in db.execute('SELECT c.guild_id,r.payload FROM current_ranked_guild_rosters c JOIN guild_roster_sources r USING(source_id)')}
        latest={gid:status for gid,status in db.execute("SELECT guild_id,status FROM guild_fetch_attempts WHERE part='roster' ORDER BY checked_at")}
    finally:db.close()
    targets=[g for g in ranking['guilds'] if args.force or g['guildId'] not in cached or latest.get(g['guildId']) in ('failed','partial') or not cached[g['guildId']]['membershipComplete'] or datetime.fromisoformat(cached[g['guildId']]['capturedAt'])<boundary]
    progress={'rankingSnapshotId':ranking['snapshotId'],'targetGuilds':len(ranking['guilds']),'cached':len(ranking['guilds'])-len(targets),'fetched':0,'failed':0,'partial':0,'members':sum(cached[g['guildId']]['membersRetrieved'] for g in ranking['guilds'] if g not in targets),'stopReason':None,'credentialsPersisted':False}
    if targets:session=session or runtime_session()
    stop=threading.Event();lock=threading.Lock();next_start=[0.0]
    def request(path,purpose):
        with lock:
            delay=max(0,next_start[0]-time.monotonic())
            if delay:time.sleep(delay)
            if stop.is_set():raise AcquisitionStopped('guild_batch_stopped')
            next_start[0]=time.monotonic()+.5
        return normal_json(session,path,purpose=purpose)
    def one(guild):
        gid=guild['guildId'];path='/guild/'+urllib.parse.quote(gid,safe='')
        raw,profile=request(path,'guild-profile');at=datetime.now(timezone.utc).isoformat();data=profile['result']['guild']
        if data['gid']!=gid:raise AcquisitionStopped('guild_profile_identity_differs')
        raw_members,response=request(path+'/member/list','guild-roster');listing=response['result']['guildMemberList']
        allowed_guild=['gid','name','level','nationalFlag','currentMemberCount']
        selected={k:data[k] for k in allowed_guild};selected['guildLevelInfo']={'maxMemberCount':data['guildLevelInfo']['maxMemberCount']}
        fields=['gid','uid','name','userName','level','guildAuthority']
        members=[{k:r[k] for k in fields if k in r} for r in listing]
        now=datetime.now(timezone.utc);folder=ROOT/'data/research/runtime.private'/('ranked-guild-'+now.strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:6]);folder.mkdir()
        result={'sourceKind':'normal-public-guild-profile-roster','gameVersion':'12.4.2','moduleSha256':NEW_SHA,'capturedAt':now.isoformat(),'profileRetrievedAt':at,'profileSha256':hashlib.sha256(raw).hexdigest(),'rosterSha256':hashlib.sha256(raw_members).hexdigest(),'guild':selected,'guildMemberList':members}
        (folder/'guild-response.private.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        return accept_roster(folder)
    iterator=iter(targets)
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending={}
        def submit():
            if stop.is_set():return
            guild=next(iterator,None)
            if guild:pending[pool.submit(one,guild)]=guild
        submit();submit()
        while pending:
            done,_=wait(pending,timeout=1,return_when=FIRST_COMPLETED)
            for future in done:
                guild=pending.pop(future)
                try:
                    doc=future.result();progress['fetched']+=1;progress['members']+=doc['membersRetrieved'];progress['partial']+=int(not doc['membershipComplete'])
                except Exception as error:
                    reason=str(error) if isinstance(error,AcquisitionStopped) else 'guild_response_validation_failed'
                    attempt(guild['guildId'],'roster','failed','normal_guild_read_failed');progress['failed']+=1
                    if reason=='http_access_denied' or reason.startswith(('http_error_401','http_error_403')):stop.set();progress['stopReason']='http_access_denied'
                progress['elapsedSeconds']=round(time.monotonic()-started,3)
                output=ROOT/'data/research/runtime.private/guild-top100-session';output.mkdir(exist_ok=True)
                (output/'progress.private.json').write_text(json.dumps(progress,indent=2)+'\n',encoding='utf8')
                if (progress['fetched']+progress['failed'])%10==0:print(json.dumps(progress),flush=True)
                if time.monotonic()-started>600:stop.set();progress['stopReason']='time_bound'
                submit()
    progress['elapsedSeconds']=round(time.monotonic()-started,3)
    print(json.dumps(progress),flush=True)
    if progress['stopReason']:raise AcquisitionStopped(progress['stopReason'])
    return progress


def runtime_session():
    with Reader(r'C:\LDPlayer\LDPlayer9\adb.exe','emulator-5554',120) as reader:
        reader.expected_module_sha=NEW_SHA;reader.refresh();return load_session(reader,authorized=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--use-authorized-runtime-session',action='store_true');p.add_argument('--force',action='store_true');p.add_argument('--ranking-copies',nargs=2,type=Path);args=p.parse_args()
    if not args.use_authorized_runtime_session:p.error('explicit authorized local session required')
    try:
        with acquisition_lock():collect(args)
    except Exception as error:
        print(json.dumps({'completed':False,'reason':str(error) if isinstance(error,AcquisitionStopped) else 'guild_context_or_validation_failed','credentialsPersisted':False}));raise SystemExit(1)
