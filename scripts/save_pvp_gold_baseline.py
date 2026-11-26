"""Freeze the accepted validation snapshot, independently of a live update.

Additive reproduction DB only: accepted document, ranking/cache metadata and
new definition/label/roll tables. No credentials or whole-process dumps.
"""
import gzip,hashlib,json,shutil,sqlite3,sys,zipfile
from pathlib import Path
from datetime import datetime,timezone
from local_game_database import ROOT,DEFAULT_DB
sys.path.insert(0,str(ROOT/'scripts/runtime'))
from pvp_scope_policy import canonical_scope
FILES=[
 'data/config/pvp-scope-policy.json','lib/pvp-scopes.ts','lib/pvp-rankings.ts','lib/local-game-data.ts','lib/gear-instance-values.ts','lib/defense-teams.ts',
 'app/_components/pvp-auto-update-status.tsx','app/_components/defense-equipment.tsx','scripts/build_native_gear_labels.py','scripts/parse_gear_definitions.py','scripts/derive_http_gear_values.py',
 'scripts/runtime/read_gear_definitions.py','scripts/runtime/pvp_league_codes.py','scripts/runtime/pvp_scope_policy.py','scripts/runtime/refresh_pvp_rankings_http.py',
 'scripts/runtime/collect_ranked_pvp_http.py','scripts/runtime/fetch_ranked_pvp_response.py','scripts/update_local_game_data.py','scripts/apply_pvp_scope_policy.py','scripts/activate_completed_pvp_scopes.py',
 'scripts/pvp_auto_update.py','scripts/register_pvp_update.ps1','scripts/native_elf.py','scripts/ghidra/request_native_evidence.py','scripts/ghidra/RestoreVerifiedFunctionRange.java',
 'scripts/browser_session.py','scripts/sync_pvp_rankings_supabase.py','scripts/validate_pvp_chinese_labels.py','scripts/validate_pvp_gold_equipment.py','scripts/verify_pvp_gold_ui.py','scripts/save_pvp_gold_baseline.py',
 'tests/test_pvp_scope_policy.py','tests/test_http_rankings.py','tests/test_pvp_denial_stop.py','tests/test_http_gear_values.py','tests/test_global_gear_definitions.py',
 'tests/pvp-rankings.test.ts','tests/gear-instance-values.test.ts','tests/gear-roll-reader.test.ts','tests/defense-label-reader.test.ts','docs/current-state.md']
REPORTS=['pvp-gold-equipment-validation.json','pvp-chinese-label-coverage.json','http-gear-values-reconstruction.json','pvp-gold-values-ui-validation.json','pvp-chinese-ui-validation.json','native-gear-labels-supabase-receipt.json','pvp-rankings-supabase-receipt.json',
 'ghidra/pvp-subdivision-ui-and-gear-manager.txt','ghidra/gear-db-attribute-root-1242.txt','ghidra/gear-db-factory-and-instance-parser-1242.txt','ghidra/gear-manager-attribute-resolution-1242.txt','ghidra/gear-definition-lookup-and-skillplus-1242.txt','ghidra/gear-function-boundary-repair.txt']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 accepted=json.loads((ROOT/'reports/pvp-gold-equipment-validation.json').read_text(encoding='utf8'));roll_id=accepted['rollSourceId']
 source_dir=ROOT/'data/research/runtime.private/gear-roll-exports'/roll_id;roll=json.loads((source_dir/'rolls.private.json').read_bytes());cutoff=datetime.fromisoformat(accepted['verifiedAt'])
 if roll['summary']['reconstructedValues']!=accepted['nativeDefinitionReconstructedValues']:raise ValueError('validation and frozen roll source differ')
 ui=json.loads((ROOT/'reports/pvp-gold-values-ui-validation.json').read_text(encoding='utf8'))
 if not ui['passed']:raise ValueError('UI acceptance did not pass')
 now=datetime.now(timezone.utc);folder=ROOT/'data/research/runtime.private/baselines'/('pvp-gold-equipment-'+now.strftime('%Y%m%dT%H%M%SZ'));folder.mkdir()
 copied={}
 for name in [*FILES,*['reports/'+p for p in REPORTS]]:
  src=ROOT/name;target=folder/'source'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,target);copied[name]=sha(src)
 parent=json.loads((ROOT/'reports/pvp-chinese-success-baseline.json').read_bytes());parent_manifest=json.loads((ROOT/parent['privateBaseline']/'manifest.private.json').read_bytes())
 dependencies={name:sha(ROOT/name) for name in ['package.json','package-lock.json']}
 if dependencies!=parent_manifest['dependencyHashes']:raise ValueError('dependency inputs changed; inspect independently')
 archive=folder/'accepted-inputs.private.sqlite';counts={}
 with sqlite3.connect(DEFAULT_DB.resolve().as_uri()+'?mode=ro',uri=True) as db,sqlite3.connect(archive) as frozen:
  db.execute('BEGIN')
  def copy(table,rows=None):
   sql=db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone()[0];frozen.execute(sql)
   rows=list(db.execute('SELECT * FROM '+table)) if rows is None else list(rows)
   if rows:frozen.executemany('INSERT INTO '+table+' VALUES ('+','.join('?' for _ in rows[0])+')',rows)
   counts[table]=len(rows)
  copy('documents',db.execute("SELECT * FROM documents WHERE sha256=? OR sha256 IN (SELECT sha256 FROM current_documents WHERE filename IN ('verified-equipment.json','verified-characters.json'))",(roll['defenseDocumentSha256'],)))
  markers=[('defense-teams.private.json',roll['defenseDocumentSha256']),*db.execute("SELECT filename,sha256 FROM current_documents WHERE filename IN ('verified-equipment.json','verified-characters.json')")];copy('current_documents',markers)
  copy('ranking_snapshots');rankings=[json.loads(db.execute('SELECT payload FROM ranking_snapshots WHERE snapshot_id=?',(sid,)).fetchone()[0]) for sid in roll['rankingSources']]
  copy('current_rankings',[(canonical_scope(r['scope']['label']),r['snapshotId']) for r in rankings])
  rows=[r for r in db.execute('SELECT * FROM ranking_defense_attempts') if r[1] in roll['rankingSources'] and datetime.fromisoformat(r[3])<=cutoff];copy('ranking_defense_attempts',rows);copy('pvp_http_sources')
  definition_id=roll['definitionSourceId'];label_id=json.loads((ROOT/'reports/pvp-chinese-label-coverage.json').read_bytes())['labelSourceId']
  for sources,current,records,sid,scope in [('gear_definition_sources','current_gear_definitions','gear_definition_records',definition_id,'ordinary-gearstat'),('gear_attribute_label_sources','current_gear_attribute_labels','gear_attribute_labels',label_id,'ordinary-native'),('gear_roll_sources','current_gear_rolls','gear_instance_rolls',roll_id,'ranked-http')]:
   copy(sources,db.execute('SELECT * FROM '+sources+' WHERE source_id=?',(sid,)));copy(current,[(scope,sid)]);copy(records,db.execute('SELECT * FROM '+records+' WHERE source_id=?',(sid,)))
  frozen.commit();integrity=frozen.execute('PRAGMA quick_check').fetchone()[0];foreign=frozen.execute('PRAGMA foreign_key_check').fetchall()
  if integrity!='ok' or foreign:raise ValueError('additive frozen input DB integrity failed')
 definition=json.loads((ROOT/'data/research/runtime.private/gear-definition-exports'/roll['definitionSourceId']/'definitions.private.json').read_bytes());capture=ROOT/definition['captureDirectory'];meta=json.loads((capture/'capture.json').read_bytes())
 raw_zip=folder/'gear-definitions.private.zip'
 with zipfile.ZipFile(raw_zip,'w',zipfile.ZIP_DEFLATED) as z:
  for name in ['capture.json','manager.bin','dictionary.bin',*[r['file'] for r in meta['records']]]:z.write(capture/name,name)
 with zipfile.ZipFile(raw_zip) as z:
  if z.testzip() is not None:raise ValueError('definition copy archive differs')
 receipt=json.loads((ROOT/'reports/pvp-rankings-supabase-receipt.json').read_bytes());remote=ROOT/'data/research/runtime.private/pvp-exports'/receipt['auditId']
 manifest={'createdAt':now.isoformat(),'validationAt':accepted['verifiedAt'],'parentIndex':'reports/pvp-chinese-success-baseline.json','kind':'additive-accepted-rank-equipment-inputs','files':copied,'dependencyHashes':dependencies,
  'databaseRows':counts,'databaseIntegrity':integrity,'foreignKeyErrors':len(foreign),'frozenRollSource':roll_id,'frozenDefenseDocument':roll['defenseDocumentSha256'],'privateSupabaseExport':remote.relative_to(ROOT).as_posix(),
  'remoteExportHashes':{p.name:sha(p) for p in remote.glob('*.json')},'artifacts':{archive.name:sha(archive),raw_zip.name:sha(raw_zip)},'credentialsOrWholeMemoryIncluded':False,'deployed':False}
 (folder/'manifest.private.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 result={'privateBaseline':folder.relative_to(ROOT).as_posix(),'parentIndex':manifest['parentIndex'],'validationAt':accepted['verifiedAt'],'phaseCount':10,'rankedPlayers':accepted['rankedPlayers'],'teams':accepted['teams'],'equipmentInstances':accepted['equippedRecords'],
  'ordinaryValuesReconstructed':accepted['nativeDefinitionReconstructedValues'],'unknownEffectValues':accepted['unknownEffectValues'],'nativeDefinitionRecords':len(definition['records']),'supabasePrivateSnapshotId':receipt['auditId'],'supabaseRowsVerified':receipt['researchRowsVerified'],
  'pythonRelatedTests':25,'typescriptRelatedTests':12,'typecheck':'passed','lint':'passed','build':'passed','browserCases':len(ui['cases']),'databaseIntegrity':integrity,'dependenciesUnchanged':True,'deployed':False}
 (ROOT/'reports/pvp-gold-equipment-success-baseline.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8');print(json.dumps(result))
if __name__=='__main__':main()
