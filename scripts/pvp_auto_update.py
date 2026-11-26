"""Local periodic PVP worker. Uses no saved cookie and never performs login.

Windows task timing is separate. This bounded worker executes the existing
normal request pipeline once, supports its OS lock/cache, and pauses automatic
network work after a denial/rate limit until the operator explicitly resumes.
"""
import argparse,json,os,subprocess,sys,tempfile
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts/runtime'))
from collect_ranked_pvp_http import acquisition_lock
from fetch_ranked_pvp_response import AcquisitionStopped
STATE=ROOT/'data/research/runtime.private/pvp-auto-state.private.json'
INTERVAL=10
PAUSE_REASONS={'http_access_denied','http_error_429','normal_result_object_missing','response_owner_differs','pvpteam_object_missing','response_is_not_json',
               'normal_ranking_shape_differs','normal_ranking_row_shape_differs','unexpected_sensitive_response_field'}


def stamp():return datetime.now(timezone.utc).isoformat()


def load(path=STATE):
    if not path.exists():return {'schemaVersion':1,'enabled':False,'paused':False,'intervalMinutes':INTERVAL,'lastStatus':'not_started'}
    doc=json.loads(path.read_text(encoding='utf8'))
    if doc.get('schemaVersion')!=1:raise ValueError('automatic update state format differs')
    return doc


def save(doc,path=STATE):
    path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w',encoding='utf8',dir=path.parent,suffix='.tmp',delete=False) as f:
        tmp=Path(f.name);json.dump(doc,f,ensure_ascii=False);f.write('\n')
    tmp.replace(path)


def classify(stdout,returncode):
    rows=[]
    for line in stdout.splitlines():
        try:doc=json.loads(line)
        except ValueError:continue
        if isinstance(doc,dict):rows.append(doc)
    reason=next((r.get('reason') or r.get('stopReason') for r in rows if (r.get('reason') or r.get('stopReason')) in PAUSE_REASONS),None)
    if reason:return {'lastStatus':'paused','paused':True,'reason':reason}
    final=next((r for r in reversed(rows) if r.get('status') in ('success','failed','skipped')),None)
    if final and final['status']=='success' and returncode==0:return {'lastStatus':'success','paused':False,'reason':None}
    if final and final['status']=='skipped':return {'lastStatus':'skipped','paused':False,'reason':'update_already_running'}
    return {'lastStatus':'failed','paused':False,'reason':'game_session_or_update_unavailable'}


def _run_once(path=STATE):
    state=load(path)
    if not state.get('enabled'):return {'status':'skipped','reason':'automatic_update_disabled'}
    if state.get('paused'):return {'status':'paused','reason':state.get('reason'),'networkRequests':0}
    state.update(lastStatus='running',lastStartedAt=stamp());save(state,path)
    command=[sys.executable,str(ROOT/'scripts/update_local_game_data.py'),'--module','pvp','--capture','--scope','all',
             '--use-authorized-runtime-session','--sync-supabase']
    try:
        result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf8',errors='replace',timeout=2400,
                              env={**os.environ,'PYTHONUTF8':'1'},creationflags=0x08000000 if os.name=='nt' else 0)
        outcome=classify(result.stdout,result.returncode)
    except subprocess.TimeoutExpired:outcome={'lastStatus':'failed','paused':False,'reason':'automatic_update_time_bound'}
    # A user may disable the schedule while the child finishes. Keep that
    # current configuration rather than restoring the worker's initial copy.
    state=load(path)
    state.update(outcome,lastFinishedAt=stamp());save(state,path)
    return {'status':state['lastStatus'],'reason':state.get('reason'),'intervalMinutes':state['intervalMinutes'],'previousDataPreserved':True}


def run_once(path=STATE):
    path.parent.mkdir(parents=True,exist_ok=True)
    try:
        with acquisition_lock(path.parent/'pvp-auto-worker.lock'):return _run_once(path)
    except AcquisitionStopped:
        return {'status':'skipped','reason':'automatic_worker_already_running','networkRequests':0}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--enable',action='store_true');p.add_argument('--disable',action='store_true');p.add_argument('--resume',action='store_true');p.add_argument('--status',action='store_true');a=p.parse_args()
    state=load()
    if a.enable or a.disable or a.resume:
        if a.enable:
            state.update(enabled=True,configuredAt=stamp())
            if not state.get('paused') and state.get('lastStatus')!='running':state.update(lastStatus='ready',reason=None)
        if a.disable:state['enabled']=False
        if a.resume:state.update(paused=False,reason=None,lastStatus='ready')
        save(state);print(json.dumps(state))
    elif a.status:print(json.dumps(state))
    else:print(json.dumps(run_once()))
