"""Freeze only accepted guild/value inputs and successful code; no credentials."""
import hashlib,json,shutil,sqlite3
from contextlib import closing
from datetime import datetime,timezone
from pathlib import Path
from local_game_database import ROOT,DEFAULT_DB
from derive_guildwar_gear_values import build

def save():
 previous_report=ROOT/'reports/guildwar-values-success-baseline.json'
 previous=json.loads(previous_report.read_bytes()) if previous_report.exists() else {}
 folder=ROOT/'data/research/runtime.private/baselines'/('guildwar-values-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'));folder.mkdir()
 database=folder/'accepted-inputs.private.sqlite';counts={}
 with closing(sqlite3.connect(DEFAULT_DB.resolve().as_uri()+'?mode=ro',uri=True)) as src,closing(sqlite3.connect(database)) as dst:
  src.execute('BEGIN')
  def copy(table,where='',args=()):
   ddl=src.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone()
   if not ddl:return
   rows=src.execute('SELECT * FROM '+table+(' WHERE '+where if where else ''),args).fetchall();dst.execute(ddl[0]);counts[table]=len(rows)
   if rows:dst.executemany('INSERT INTO '+table+' VALUES ('+','.join('?' for _ in rows[0])+')',rows)
  # Exact accepted normalized documents, not synthetic player fixtures. Keep
  # the native calibration source index without copying the whole live DB.
  dst.executescript('CREATE TABLE documents(sha256 TEXT PRIMARY KEY,payload TEXT);CREATE TABLE current_documents(filename TEXT PRIMARY KEY,sha256 TEXT);CREATE TABLE pvp_http_sources(capture_id TEXT PRIMARY KEY);')
  for name in ['defense-teams.private.json','verified-equipment.json','verified-characters.json']:
   sha,payload=src.execute('SELECT d.sha256,d.payload FROM current_documents c JOIN documents d USING(sha256) WHERE c.filename=?',(name,)).fetchone()
   dst.execute('INSERT INTO documents VALUES (?,?)',(sha,payload));dst.execute('INSERT INTO current_documents VALUES (?,?)',(name,sha))
  dst.executemany('INSERT INTO pvp_http_sources VALUES (?)',src.execute('SELECT capture_id FROM pvp_http_sources').fetchall())
  for source,current,where in [('guild_war_sources','current_guild_war_sources',''),('gear_definition_sources','current_gear_definitions',''),
    ('gear_special_definition_sources','current_gear_special_definitions',''),('gear_attribute_label_sources','current_gear_attribute_labels',''),
    ('gear_roll_sources','current_gear_rolls',"scope='guildwar'")]:
   selected='SELECT source_id FROM '+current+(' WHERE '+where if where else '')
   copy(source,'source_id IN ('+selected+')');copy(current,where)
  for table,current in [('gear_instance_rolls','current_gear_rolls'),('gear_attribute_labels','current_gear_attribute_labels'),('guild_war_equipment_instances','current_guild_war_sources')]:
   selected='SELECT source_id FROM '+current+(" WHERE scope='guildwar'" if current=='current_gear_rolls' else '')
   copy(table,'source_id IN ('+selected+')')
  dst.commit()
  if dst.execute('PRAGMA foreign_key_check').fetchall() or dst.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise ValueError('frozen guild inputs integrity failed')
 original=json.loads((ROOT/'reports/guildwar-gear-values-reconstruction.json').read_bytes());reproduced=build(database)
 if reproduced['sourceId']!=original['sourceId'] or reproduced['summary']!=original['summary']:raise ValueError('offline guild reconstruction differs from accepted result')
 files=['scripts/derive_guildwar_gear_values.py','scripts/native_gear_special_values.py','scripts/parse_gear_special_definitions.py','scripts/runtime/read_gear_special_definitions.py',
  'scripts/guild_public_formations.py','scripts/runtime/probe_ranked_guild_member_groups.py','scripts/runtime/verify_guildwar_group_purpose.py','scripts/runtime/collect_guild_public_formations.py','scripts/export_guild_formation_review.py',
  'scripts/sync_guild_rankings_supabase.py','scripts/update_local_game_data.py','scripts/validate_current_guildwar.py','scripts/verify_guildwar_ui.py','scripts/save_guildwar_values_baseline.py',
  'lib/guild-war.ts','lib/gear-instance-values.ts','lib/local-game-data.ts','app/_components/guild-war-panel.tsx',
  'tests/test_guildwar_gear_values.py','tests/test_guild_public_formations.py','tests/test_guild_http_transport.py','tests/gear-instance-values.test.ts','tests/guild-war.test.ts',
  'reports/guildwar-gear-values-reconstruction.json','reports/guildwar-current-validation.json','reports/guildwar-ui-validation.json','reports/guild-top100-supabase-receipt.json',
  'reports/guildwar-ranked-public-defense-boundary.json','reports/guildwar-ranking-context-validation.json','reports/guildwar-public-group-purpose-comparison.json','reports/ranked-guild-member-war-groups-probe.json','reports/guild-public-formation-review.json',
  'docs/current-state.md','package.json','package-lock.json','tsconfig.json']
 files+=['scripts/native_gear_option_values.py','scripts/parse_gear_option_definitions.py','scripts/runtime/read_gear_option_definitions.py','scripts/validate_gear_option_values.py',
  'tests/test_gear_option_values.py','tests/gear-roll-reader.test.ts','scripts/native_elf.py','tests/test_native_address_references.py',
  'reports/guildwar-special-option-validation.json','reports/guildwar-special-option-ui-validation.json','reports/silver-guild-defense-investigation.json','reports/guildwar-visible-context-status.json']
 with closing(sqlite3.connect(database)) as frozen:
  row=frozen.execute("SELECT s.payload FROM current_gear_special_definitions c JOIN gear_special_definition_sources s USING(source_id) WHERE c.scope='native-option-talents'").fetchone()
  if row:
   definition=json.loads(row[0]);capture=ROOT/definition['captureDirectory'];meta=json.loads((capture/'capture.json').read_bytes())
   files.extend((capture/name).relative_to(ROOT).as_posix() for name in ['capture.json',*[t['rawFile'] for t in meta['tables']]])
 files+=['reports/ghidra/'+name for name in ['gear-special-option-talent-definitions-1242.txt','gear-special-option-instance-inputs-1242.txt','gear-special-option-format-and-enchant-1242.txt','gear-special-option-float-1242.txt']]
 hashes={}
 for name in files:
  target=folder/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target);hashes[name]=hashlib.sha256(target.read_bytes()).hexdigest()
 manifest={'capturedAt':datetime.now(timezone.utc).isoformat(),'parentBaseline':previous.get('baselineDirectory','data/research/runtime.private/baselines/guild-values-20261126T054434Z'),'sourceId':original['sourceId'],
  'frozenDatabaseSha256':hashlib.sha256(database.read_bytes()).hexdigest(),'selectedTableRows':counts,'files':hashes,'offlineReproductionVerified':True,
  'summary':reproduced['summary'],'credentialsIncluded':False,'wholeMemoryIncluded':False,'deployed':False,
  'immutableOriginalCopiesRequired':True,'originalSpecialDefinitions':[reproduced['specialDefinitionSourceId'],reproduced['skillUpgradeDefinitionSourceId'],reproduced.get('optionDefinitionSourceId')]}
 (folder/'manifest.private.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf8')
 report={'baselineDirectory':folder.relative_to(ROOT).as_posix(),'sourceId':original['sourceId'],'offlineReproductionVerified':True,'summary':reproduced['summary'],'deployed':False}
 (ROOT/'reports/guildwar-values-success-baseline.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');return report

if __name__=='__main__':print(json.dumps(save()))
