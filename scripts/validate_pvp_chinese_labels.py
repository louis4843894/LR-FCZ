"""Measure label coverage of current accepted rank sources, without new fetching."""
import json,sqlite3,math
from collections import Counter
from datetime import datetime,timezone
from local_game_database import ROOT,DEFAULT_DB
from derive_http_gear_values import observation_id,matching_roll_entry


def validate():
 db=sqlite3.connect(DEFAULT_DB.resolve().as_uri()+'?mode=ro',uri=True)
 try:
  db.execute('BEGIN')
  source=db.execute("SELECT d.sha256,d.payload FROM current_documents c JOIN documents d USING(sha256) WHERE c.filename='defense-teams.private.json'").fetchone();data=json.loads(source[1])
  label_source=db.execute("SELECT source_id FROM current_gear_attribute_labels WHERE scope='ordinary-native'").fetchone()[0]
  labels={r[0]:r[1:] for r in db.execute('SELECT attribute_id,type_enum,label FROM gear_attribute_labels WHERE source_id=?',(label_source,))}
  current={r[0] for r in db.execute('SELECT snapshot_id FROM current_rankings')};attempts={}
  for rank,uid,payload in db.execute('SELECT ranking_snapshot_id,player_id,payload FROM ranking_defense_attempts ORDER BY attempted_at'):
   r=json.loads(payload)
   if rank in current and r['status'] in ('success','partial'):attempts[(rank,uid)]=r
  keys={(uid,sid) for (_,uid),r in attempts.items() for sid in r.get('defenseSnapshotIds',[])}
  teams=[t for t in data['snapshots'] if (t['playerId'],t['snapshotId']) in keys];gear=[e for t in teams for u in t['members'] or [] for e in u['equipment'].values() if e['state']=='equipped'];entries=[a for e in gear for a in (e.get('actualEffects') or {}).get('entries',[])]
  coverage=Counter()
  for a in entries:
   kind=a.get('attributeTypeRaw')
   if a.get('attributeLabel') and kind and 1<=kind<=45:coverage['nativeInstanceLabel']+=1
   elif kind is not None and any(r[0]==kind for r in labels.values()):coverage['nativeKindLabel']+=1
   elif a.get('sourceField') in ['attr1No','attr2No','attr3No','attr4No','attr5No'] and a['attributeId'] in labels:coverage['nativeIdLabel']+=1
   else:coverage['unknownKind']+=1
  reconstructed=0
  if db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='gear_roll_sources'").fetchone():
   roll_source=db.execute("SELECT source_id FROM current_gear_rolls WHERE scope='ranked-http'").fetchone()
   rolls={r[0]:json.loads(r[1]) for r in db.execute('SELECT observation_id,payload FROM gear_instance_rolls WHERE source_id=?',(roll_source[0],))} if roll_source else {}
   reconstructed=sum(bool(matching_roll_entry(rolls.get(observation_id(t,m,slot)),t,m,slot,g,a)) for t in teams for m in t['members'] or [] for slot,g in m['equipment'].items() for a in (g.get('actualEffects') or {}).get('entries',[]) if a.get('valueVerified') is not True)
  raw_numeric=sum(a.get('valueVerified') is True and type(a.get('value')) in (int,float) and math.isfinite(a['value']) for a in entries)
  integrity={t:db.execute('PRAGMA quick_check('+t+')').fetchone()[0] for t in ['gear_attribute_label_sources','current_gear_attribute_labels','gear_attribute_labels']}
  if any(v!='ok' for v in integrity.values()):raise ValueError('native label table integrity differs')
  report={'verifiedAt':datetime.now(timezone.utc).isoformat(),'defenseDocumentSha256':source[0],'labelSourceId':label_source,'nativeDictionaryIds':len(labels),
          'rankSources':len(current),'rankedPlayersWithTeams':len({t['playerId'] for t in teams}),'rankedTeams':len(teams),'equippedRecords':len(gear),'effectEntries':len(entries),
          'chineseKindEntries':len(entries)-coverage['unknownKind'],'unknownKindEntries':coverage['unknownKind'],'labelCoverage':dict(coverage),
          'verifiedNumericalEntries':raw_numeric+reconstructed,'rawVerifiedNumericalEntries':raw_numeric,'calibratedReconstructedNumericEntries':reconstructed,
          'newNumericValuesDerived':reconstructed,'tableIntegrity':integrity,'rawMemoryOrCredentialsIncluded':False}
 finally:db.close()
 (ROOT/'reports/pvp-chinese-label-coverage.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');return report


if __name__=='__main__':print(json.dumps(validate()))
