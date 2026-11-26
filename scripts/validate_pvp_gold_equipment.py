"""Validate the current ranked scope, equipment joins and independently stored rolls."""
import json,sqlite3,sys
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
from local_game_database import ROOT,DEFAULT_DB
from derive_http_gear_values import observation_id,matching_roll_entry
sys.path.insert(0,str(ROOT/'scripts/runtime'))
from pvp_scope_policy import LABELS,canonical_scope
def validate(database=DEFAULT_DB):
 with sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro',uri=True) as db:
  db.execute('BEGIN')
  docs={name:json.loads(p) for name,p in db.execute("SELECT c.filename,d.payload FROM current_documents c JOIN documents d USING(sha256) WHERE c.filename IN ('defense-teams.private.json','verified-equipment.json','verified-characters.json')")}
  defense=docs['defense-teams.private.json'];gear={r['itemCode']:r for r in docs['verified-equipment.json']['records']};characters={r['characterId'] for r in docs['verified-characters.json']['records']}
  rankings={canonical_scope(label):json.loads(p) for label,p in db.execute('SELECT c.scope_label,r.payload FROM current_rankings c JOIN ranking_snapshots r USING(snapshot_id)')}
  if set(rankings)!=set(LABELS):raise ValueError('current scopes differ from requested ten native phases')
  current={d['snapshotId'] for d in rankings.values()};attempts={}
  for sid,uid,p in db.execute('SELECT ranking_snapshot_id,player_id,payload FROM ranking_defense_attempts ORDER BY attempted_at'):
   if sid in current:attempts[sid,uid]=json.loads(p)
  keys={(uid,s) for (_,uid),a in attempts.items() if a['status'] in ('success','partial') for s in a.get('defenseSnapshotIds',[])};teams=[t for t in defense['snapshots'] if (t['playerId'],t['snapshotId']) in keys]
  source=db.execute("SELECT s.source_id,s.payload FROM current_gear_rolls c JOIN gear_roll_sources s USING(source_id) WHERE c.scope='ranked-http'").fetchone();meta=json.loads(source[1]);rolls={key:json.loads(p) for key,p in db.execute('SELECT observation_id,payload FROM gear_instance_rolls WHERE source_id=?',(source[0],))}
  label_source=db.execute("SELECT source_id FROM current_gear_attribute_labels WHERE scope='ordinary-native'").fetchone()[0];labels={k:v for k,v in db.execute('SELECT attribute_id,label FROM gear_attribute_labels WHERE source_id=?',(label_source,))}
  equipment=[];actual=0;effects=0;unmatched=set();unknown_characters=set();samples=[]
  for t in teams:
   for m in t['members'] or []:
    if m.get('characterId') and m['characterId'] not in characters:unknown_characters.add(m['characterId'])
    for slot,g in m['equipment'].items():
     if g['state']!='equipped':continue
     equipment.append(g)
     if g['equipmentId'] not in gear:unmatched.add(g['equipmentId'])
     record=rolls.get(observation_id(t,m,slot));values=[]
     for a in (g.get('actualEffects') or {}).get('entries',[]):
      effects+=1;r=matching_roll_entry(record,t,m,slot,g,a)
      if r:
       actual+=1;values.append({'attributeId':a['attributeId'],'name':labels.get(a['attributeId']),'valueGradeRaw':a['valueGradeRaw'],'value':r['value'],'unit':r['unit'],'enhancementIncluded':True,'visuallyCheckedForThisPlayer':False})
     if values and (g['equipmentId']=='eq_2202_amr_06' or len(samples)<1):
      samples.append({'equipmentId':g['equipmentId'],'enhancement':g['enhancement'],'retrievedAt':t['retrievedAt'],'coefficientCapturedAt':record['factorCapturedAt'],'values':values})
  old=sum(a.get('valueVerified') is True for t in defense['snapshots'] for m in t['members'] or [] for g in m['equipment'].values() for a in (g.get('actualEffects') or {}).get('entries',[]))
  tables=['gear_definition_sources','current_gear_definitions','gear_definition_records','gear_roll_sources','current_gear_rolls','gear_instance_rolls']
  integrity={table:db.execute('PRAGMA quick_check('+table+')').fetchone()[0] for table in tables}
  if any(v!='ok' for v in integrity.values()) or old!=2952:raise ValueError('new table integrity or retained native numeric baseline differs')
  if meta['summary']['reconstructedValues']!=actual:raise ValueError('derived source no longer covers current accepted ranking sources; rebuild before claiming completion')
  report={'verifiedAt':datetime.now(timezone.utc).isoformat(),'phasePlayers':{label:len(rankings[label]['players']) for label in LABELS},'rankedPlayers':len({p['playerId'] for d in rankings.values() for p in d['players']}),
   'defenseStates':dict(Counter(a['status'] for a in attempts.values())),'teams':len(teams),'equippedRecords':len(equipment),'equipmentTemplateMatches':sum(g['equipmentId'] in gear for g in equipment),'unknownEquipmentIds':sorted(unmatched),'unknownCharacterIds':sorted(unknown_characters),
   'effectEntries':effects,'nativeDefinitionReconstructedValues':actual,'unknownEffectValues':effects-actual,'previousNativeNumericValuesPreserved':old,'rollSourceId':source[0],'definitionSourceId':meta['definitionSourceId'],'chineseAttributeDictionaryIds':len(labels),
   'nativeCalibrationGear':meta['calibration']['screenCheckedGearCount'],'nativeCalibrationValues':meta['calibration']['screenCheckedValueCount'],'currentPlayersVisuallyVerified':False,'externalReferenceValuesUsed':False,'tableIntegrity':integrity,'samples':samples[:2]}
 (ROOT/'reports/pvp-gold-equipment-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8');return report
if __name__=='__main__':
 report=validate();print(json.dumps({k:v for k,v in report.items() if k!='samples'}))
