"""Bounded normal-request collection: two workers, at most two starts/second.

No game UI, injection, endpoint guessing, credential files, TLS changes, or
retry after access denial. Cache and raw source copies allow interruption/resume.
"""
import argparse,json,threading,time,os
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor,wait,FIRST_COMPLETED
from datetime import datetime,timezone
from pathlib import Path
from pvp_session import Reader,NEW_SHA,ROOT,load_session,SessionUnavailable
from fetch_ranked_pvp_response import fetch,ranked_player,AcquisitionStopped
from http_ranking_database import remember,recent,save_batch,checked
from ranking_database import save_failure


@contextmanager
def acquisition_lock(path=None):
    path=path or ROOT/'data/research/runtime.private/pvp-http.lock'
    with open(path,'a+b') as handle:
        if handle.tell()==0:handle.write(b'0');handle.flush()
        handle.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:raise AcquisitionStopped('update_already_running') from None
        try:yield
        finally:
            handle.seek(0)
            if os.name=='nt':msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(handle.fileno(),fcntl.LOCK_UN)


def main(arguments=None,session=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot',required=True);parser.add_argument('--top',type=int,default=200)
    parser.add_argument('--max-age-seconds',type=int,default=300);parser.add_argument('--force',action='store_true')
    parser.add_argument('--use-authorized-runtime-session',action='store_true');args=parser.parse_args(arguments)
    if not args.use_authorized_runtime_session:parser.error('explicit session authorization flag is required')
    if not 1<=args.top<=200 or not 0<=args.max_age_seconds<=3600:parser.error('bounded top/age required')
    started=time.monotonic()
    ranking,_=ranked_player(args.snapshot,1);players=[p for p in ranking['players'] if p['rank']<=args.top]
    from pvp_scope_policy import matches_scope
    if not matches_scope(ranking['scope']['label'],'all'):raise AcquisitionStopped('scope_excluded_by_user')
    cache=recent(args.snapshot,0 if args.force else args.max_age_seconds,player_ids={p['playerId'] for p in players})
    targets=[p for p in players if p['playerId'] not in cache];directories=[cache[p['playerId']] for p in players if p['playerId'] in cache]
    # Body comparison only needs expired/missing players. A cache-only update
    # must not hash every copy a second time merely to prepare unused requests.
    previous=recent(args.snapshot,None,player_ids={p['playerId'] for p in targets},for_comparison=True) if targets else {}
    progress_dir=ROOT/'data/research/runtime.private/pvp-http-session-20261125';progress_dir.mkdir(exist_ok=True)
    progress={'rankingSnapshotId':args.snapshot,'targetPlayers':len(players),'cached':len(directories),
              'fetched':0,'unchanged':0,'failed':0,'stopReason':None,'credentialsPersisted':False,'uiNavigation':False}
    lock=threading.Lock();next_start=[0.0];stop=threading.Event()
    if targets and session is None:
        reader=Reader(r'C:\LDPlayer\LDPlayer9\adb.exe','emulator-5554',120);reader.expected_module_sha=NEW_SHA
        try:
            reader.refresh();session=load_session(reader,authorized=True)
        finally:reader.close()
    def one(player):
        with lock:
            delay=max(0,next_start[0]-time.monotonic())
            if delay:time.sleep(delay)
            if stop.is_set():raise AcquisitionStopped('batch_stopped_before_request')
            next_start[0]=time.monotonic()+.5
        return fetch(session,ranking,player,previous=previous.get(player['playerId']))
    iterator=iter(targets);failures=[]
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending={}
        def submit():
            if stop.is_set():return
            player=next(iterator,None)
            if player is not None:pending[pool.submit(one,player)]=player
        submit();submit()
        while pending:
            if (progress_dir/'stop').exists() or time.monotonic()-started>900:
                progress['stopReason']='local_stop_or_time_bound';stop.set()
            done,_=wait(pending,timeout=1,return_when=FIRST_COMPLETED)
            for future in done:
                player=pending.pop(future)
                try:
                    folder,result=future.result();remember(folder);checked(folder,result['checkedAt']);directories.append(folder);progress['fetched']+=1
                    progress['unchanged']+=int(result['unchanged'])
                except Exception as error:
                    reason=str(error) if isinstance(error,(AcquisitionStopped,SessionUnavailable)) else 'source_validation_failed'
                    if reason!='batch_stopped_before_request':
                        failures.append((player['playerId'],reason));progress['failed']+=1
                    # No repeated denial/protection/auth probing. Other unexpected
                    # server shapes also stop so existing valid data is preserved.
                    if reason!='batch_stopped_before_request' or not progress['stopReason']:progress['stopReason']=reason
                    stop.set()
                progress['elapsedSeconds']=round(time.monotonic()-started,3)
                (progress_dir/'progress.private.json').write_text(json.dumps(progress,indent=2),encoding='utf8')
                if (progress['fetched']+progress['failed'])%10==0:print(json.dumps(progress),flush=True)
                submit()
    imported=save_batch(args.snapshot,directories) if directories else {'acceptedPlayers':0,'normalizedWrites':0}
    for uid,reason in failures:save_failure(args.snapshot,uid,'normal_http_source_failed')
    progress.update(imported);progress['elapsedSeconds']=round(time.monotonic()-started,3)
    progress['notRetrieved']=len(players)-len(directories);progress['stopReason']=progress['stopReason'] or 'requested_rank_range_complete'
    (progress_dir/'progress.private.json').write_text(json.dumps(progress,indent=2),encoding='utf8')
    print(json.dumps(progress),flush=True)
    if progress['failed'] or progress['stopReason']!='requested_rank_range_complete':raise AcquisitionStopped(progress['stopReason'] or 'normal_http_batch_incomplete')
    return progress


if __name__=='__main__':
    try:
        with acquisition_lock():main()
    except (AcquisitionStopped,SessionUnavailable) as error:
        print(json.dumps({'collectionStarted':False,'stopReason':str(error),'credentialsPersisted':False}))
        raise SystemExit(0 if str(error)=='update_already_running' else 1)
    except Exception as error:
        print(json.dumps({'collectionStarted':False,'stopReason':'unexpected_context_or_storage_failure','errorType':type(error).__name__,'credentialsPersisted':False}))
        raise SystemExit(1)
