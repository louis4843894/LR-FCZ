"""Check two normal ranked-guild profile/roster responses during an actual battle.

The previous public player-team 403 pause is untouched. No player-team, saved
deck POST, invented query parameter, battle action, or arbitrary tower request.
Only key/type shapes and hashes are retained; credentials remain in RAM.
"""
import argparse,hashlib,json,re,sqlite3,time,urllib.parse
from collections import Counter
from datetime import datetime,timezone
from contextlib import closing
from pvp_session import Reader,NEW_SHA,ROOT,load_session,SessionUnavailable
from fetch_ranked_pvp_response import normal_json,AcquisitionStopped
from collect_ranked_pvp_http import acquisition_lock
from probe_guildwar_normal import shape


def candidates(value,path='$',depth=0):
 if depth>8:return []
 rows=[]
 if isinstance(value,dict):
  for key,v in list(value.items())[:100]:
   if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,60}',key):continue
   child=path+'.'+key
   if re.search(r'defen|fortress|tower|guildwar(?!rank)',key,re.I):rows.append({'path':child,'shape':shape(v),'nonempty':v not in (None,[],{})})
   rows+=candidates(v,child,depth+1)
 elif isinstance(value,list):
  for i,v in enumerate(value[:50]):rows+=candidates(v,path+'['+str(i)+']',depth+1)
 return rows


def history_types(result):
 counts=Counter();examples={}
 if not isinstance(result,list):return {'types':{},'schemas':{}}
 for day in result[:7]:
  if not isinstance(day,dict):continue
  for event in (day.get('history') or [])[:500]:
   if not isinstance(event,dict):continue
   code=event.get('historyType')
   if not isinstance(code,str) or not re.fullmatch('[A-Za-z0-9_:-]{1,100}',code):continue
   counts[code]+=1;values=event.get('data');schemas=[]
   for value in values if isinstance(values,list) else []:
    parsed=None
    if isinstance(value,str) and len(value)<=100000 and value[:1] in ('{','['):
     try:parsed=json.loads(value)
     except ValueError:pass
    schemas.append({'type':type(value).__name__,'encodedJsonShape':shape(parsed) if parsed is not None else None})
   examples.setdefault(code,schemas)
 return {'types':dict(counts),'schemas':examples}


def run(ranking_only=False,history_only=False,contribution_only=False):
 folder=ROOT/'data/research/runtime.private/guild-battle-profile-probe';folder.mkdir(exist_ok=True)
 state=folder/('contribution-progress.private.json' if contribution_only else 'history-progress.private.json' if history_only else 'ranking-progress.private.json' if ranking_only else 'progress.private.json')
 if state.exists() and json.loads(state.read_bytes()).get('stopReason') in ('http_access_denied','http_error_429','guild_profile_identity_differs'):
  raise AcquisitionStopped('previous_refusal_requires_manual_access_review')
 with closing(sqlite3.connect((ROOT/'data/local/lr.private.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
  ranking=json.loads(db.execute("SELECT s.payload FROM current_guild_rankings c JOIN guild_rank_sources s USING(snapshot_id) WHERE c.scope='top100'").fetchone()[0])
  seasons=[json.loads(p)['seasonNo'] for p, in db.execute("SELECT s.payload FROM current_guild_war_sources c JOIN guild_war_sources s USING(source_id) WHERE c.kind='overview'")]
 targets=[g for g in ranking['guilds'] if g['rank'] in (1,5)];rows=[]
 progress={'startedAt':datetime.now(timezone.utc).isoformat(),'rankingSnapshotId':ranking['snapshotId'],'requests':rows,'stopReason':None,'credentialsPersisted':False,'playerTeamRequests':0}
 with Reader(r'C:\LDPlayer\LDPlayer9\adb.exe','emulator-5554',100) as reader:
  reader.expected_module_sha=NEW_SHA;reader.refresh();session=load_session(reader,authorized=True)
 try:
  if ranking_only or history_only or contribution_only:
   path='/guild/'+urllib.parse.quote(next(g['guildId'] for g in targets if g['rank']==1),safe='')+'/history' if history_only else '/guildwar/rank/total?gradeId=1'
   purpose='guild-history' if history_only else 'guild-ranking'
   if contribution_only:
    if not seasons:raise AcquisitionStopped('accepted_current_season_missing')
    path='/guildwar/contribution/'+urllib.parse.quote(next(g['guildId'] for g in targets if g['rank']==1),safe='')+'/'+str(max(seasons));purpose='guild-contribution'
   raw,response=normal_json(session,path,purpose=purpose);result=response.get('result') or {}
   row={'purpose':purpose,'capturedAt':datetime.now(timezone.utc).isoformat(),'responseSha256':hashlib.sha256(raw).hexdigest(),'responseShape':shape(result),'candidateDefenseFields':candidates(result)};rows.append(row)
   if history_only:row['historyTypes']=history_types(result)
   state.write_text(json.dumps(progress,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
   report={'checkedAt':datetime.now(timezone.utc).isoformat(),'moduleSha256':NEW_SHA,**progress}
   (ROOT/('reports/guild-contribution-battle-phase-check.json' if contribution_only else 'reports/guild-history-battle-phase-check.json' if history_only else 'reports/guild-ranking-battle-phase-check.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8');return report
  for g in targets:
   base='/guild/'+urllib.parse.quote(g['guildId'],safe='')
   for suffix,purpose in [('', 'guild-profile'),('/member/list','guild-roster')]:
    raw,response=normal_json(session,base+suffix,purpose=purpose);result=response.get('result') or {}
    if purpose=='guild-profile' and result.get('guild',{}).get('gid')!=g['guildId']:raise AcquisitionStopped('guild_profile_identity_differs')
    row={'rank':g['rank'],'guildName':g['name'],'guildAlias':hashlib.sha256(g['guildId'].encode()).hexdigest()[:20],'purpose':purpose,'capturedAt':datetime.now(timezone.utc).isoformat(),'responseSha256':hashlib.sha256(raw).hexdigest(),'responseShape':shape(result),'candidateDefenseFields':candidates(result)}
    rows.append(row);state.write_text(json.dumps(progress,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'rank':row['rank'],'purpose':purpose,'candidateFields':len(row['candidateDefenseFields'])},ensure_ascii=False),flush=True);time.sleep(.5)
 except (AcquisitionStopped,SessionUnavailable) as e:
  progress['stopReason']=str(e);state.write_text(json.dumps(progress,ensure_ascii=False,indent=2)+'\n',encoding='utf8');raise
 report={'checkedAt':datetime.now(timezone.utc).isoformat(),'moduleSha256':NEW_SHA,**progress,'scope':'Two known ranked guilds; current battle phase. Absence in these responses is not a claim about every server endpoint.'}
 (ROOT/'reports/guild-profile-battle-phase-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8');return report


if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--use-authorized-runtime-session',action='store_true');modes=p.add_mutually_exclusive_group();modes.add_argument('--ranking-only',action='store_true');modes.add_argument('--history-only',action='store_true');modes.add_argument('--contribution-only',action='store_true');args=p.parse_args()
 if not args.use_authorized_runtime_session:p.error('runtime session authorization required')
 try:
  with acquisition_lock():doc=run(args.ranking_only,args.history_only,args.contribution_only)
  print(json.dumps({'requests':len(doc['requests']),'candidateFields':sum(len(r['candidateDefenseFields']) for r in doc['requests']),'credentialsPersisted':False}))
 except (AcquisitionStopped,SessionUnavailable) as e:print(json.dumps({'completed':False,'reason':str(e),'credentialsPersisted':False}));raise SystemExit(1)
