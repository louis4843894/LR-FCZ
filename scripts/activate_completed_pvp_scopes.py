"""Recover only fully acquired staged phases after an interrupted multi-phase run."""
import json,sqlite3,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts/runtime'))
from pvp_scope_policy import canonical_scope,matches_scope
def latest_staged(db):
 candidates={}
 for sid,payload,checked in db.execute('SELECT r.snapshot_id,r.payload,max(c.checked_at) FROM ranking_snapshots r JOIN pvp_ranking_checks c USING(snapshot_id) GROUP BY r.snapshot_id ORDER BY max(c.checked_at)'):
  doc=json.loads(payload);label=canonical_scope(doc['scope']['label'])
  if doc['status']=='success' and matches_scope(label,'all'):candidates[label]=(sid,doc,checked)
 return candidates
def phase_ready(db,sid,doc):
 attempts={uid:status for uid,status in db.execute('SELECT player_id,status FROM ranking_defense_attempts WHERE ranking_snapshot_id=? ORDER BY attempted_at',(sid,))}
 return bool(doc['players']) and all(attempts.get(p['playerId']) in ('success','partial','unavailable') for p in doc['players']),attempts
def activate(database=ROOT/'data/local/lr.private.sqlite'):
 accepted=[];incomplete=[]
 with sqlite3.connect(database) as db:
  candidates=latest_staged(db)
  for label,(sid,doc,checked) in candidates.items():
   ready,attempts=phase_ready(db,sid,doc)
   if ready:
    db.execute('INSERT INTO current_rankings VALUES (?,?) ON CONFLICT(scope_label) DO UPDATE SET snapshot_id=excluded.snapshot_id',(label,sid));accepted.append({'scope':label,'players':len(doc['players']),'sourceId':sid})
   else:incomplete.append({'scope':label,'players':len(doc['players']),'terminalResponses':sum(attempts.get(p['playerId']) in ('success','partial','unavailable') for p in doc['players'])})
 return {'completedPhasesActivated':accepted,'incompletePhasesKeptPending':incomplete,'priorValidSourcesRetainedForIncomplete':True}
if __name__=='__main__':
 result=activate();(ROOT/'reports/pvp-gold-completed-scopes.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(result))
