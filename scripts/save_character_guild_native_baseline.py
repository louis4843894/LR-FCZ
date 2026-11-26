"""Freeze this character/guild phase only; exclude PVP data and the live DB."""
import hashlib,json,shutil,sqlite3,zipfile
from contextlib import closing
from datetime import datetime,timezone
from pathlib import Path
from local_game_database import ROOT,DEFAULT_DB
from build_character_native_details import build,CAPTURE,LANG


def main():
 def report(name):return json.loads((ROOT/'reports'/name).read_bytes())
 ui=report('character-guild-native-ui-validation.json');engineering=report('character-guild-native-engineering.json')
 if not ui['passed'] or engineering['buildExitCode']!=0:raise ValueError('final UI/build acceptance required')
 receipts={m:report(f) for m,f in [('characters','character-details-supabase-receipt.json'),('guild','guild-top100-supabase-receipt.json')]}
 if not all(r['allPayloadsReadBack'] and r['publishedVersionsPreserved'] and r['anonymousAccessBlocked'] for r in receipts.values()):raise ValueError('cloud readback required')
 folder=ROOT/'data/research/runtime.private/baselines'/('character-guild-native-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'));folder.mkdir(parents=True,exist_ok=False)
 with closing(sqlite3.connect(DEFAULT_DB.resolve().as_uri()+'?mode=ro',uri=True)) as db:
  sid,p=db.execute("SELECT s.source_id,s.payload FROM current_character_native_sources c JOIN character_native_sources s USING(source_id) WHERE c.scope='native-templates'").fetchone();meta=json.loads(p)
  if sid!=ui['nativeSourceId']:raise ValueError('accepted native source changed')
  docs=[json.loads(p) for p, in db.execute("SELECT s.payload FROM current_guild_war_sources c JOIN guild_war_sources s USING(source_id)")]
  if ui['guildSourceId'] not in [d['sourceId'] for d in docs]:raise ValueError('accepted guild source changed')
  with closing(sqlite3.connect(folder/'accepted-inputs.private.sqlite')) as frozen:
   selectors={
    'documents':("SELECT * FROM documents WHERE sha256 IN (SELECT sha256 FROM current_documents WHERE filename='verified-characters.json')",()),
    'current_documents':("SELECT * FROM current_documents WHERE filename='verified-characters.json'",()),
    'character_detail_sources':("SELECT * FROM character_detail_sources WHERE source_id IN (SELECT source_id FROM current_character_details)",()),
    'current_character_details':('SELECT * FROM current_character_details',()),
    'character_native_sources':('SELECT * FROM character_native_sources WHERE source_id=?',(sid,)),
    'current_character_native_sources':('SELECT * FROM current_character_native_sources',()),
    'character_native_details':('SELECT * FROM character_native_details WHERE source_id=?',(sid,)),
    'character_instance_sources':('SELECT * FROM character_instance_sources WHERE source_id=?',(ui['progressSourceId'],)),
    'current_character_instance_sources':('SELECT * FROM current_character_instance_sources',()),
    'character_instance_progress':("SELECT * FROM character_instance_progress WHERE source_id=? AND json_extract(payload,'$.scope') IN ('guildwar','guildwar-saved')",(ui['progressSourceId'],)),
    'guild_war_sources':('SELECT * FROM guild_war_sources WHERE source_id IN (SELECT source_id FROM current_guild_war_sources)',()),
    'current_guild_war_sources':('SELECT * FROM current_guild_war_sources',())}
   for table,(query,args) in selectors.items():
    columns=[r[1] for r in db.execute('PRAGMA table_info('+table+')')];frozen.execute('CREATE TABLE '+table+'('+','.join(columns)+')')
    frozen.executemany('INSERT INTO '+table+' VALUES ('+','.join('?' for _ in columns)+')',db.execute(query,args).fetchall())
   frozen.execute('CREATE TABLE baseline_scope(note TEXT)');frozen.execute("INSERT INTO baseline_scope VALUES ('Selected character/guild inputs only; not an operational database; PVP instances excluded')");frozen.commit()
 source=ROOT/'data/research/runtime.private/character-native-exports'/sid/'details.private.json';doc=json.loads(source.read_bytes())
 rebuilt=build(ROOT/meta['definitionCapture'],database=folder/'accepted-inputs.private.sqlite',thumbnails=ROOT/meta['thumbnailCapture']['directory'])
 if rebuilt!=doc:raise ValueError('frozen SQLite inputs do not reproduce native details')
 for name,subdir in [('characters','character-detail-exports'),('guild','guild-exports')]:
  plan=json.loads((ROOT/'data/research/runtime.private'/subdir/receipts[name]['auditId']/'supabase-upload.private.json').read_bytes());m=plan['snapshot']['source_metadata']
  if m.get('nativeEnrichmentSourceId',m.get('nativeCharacterEnrichmentSourceId'))!=sid:raise ValueError('cloud native source differs')
 files=['scripts/build_character_native_details.py','scripts/runtime/read_character_talent_definitions.py','scripts/runtime/read_character_thumbnails.py','scripts/runtime/guildwar_visible_towers.py','scripts/runtime/collect_guildwar_http.py','scripts/sync_character_details_supabase.py','scripts/sync_guild_rankings_supabase.py','scripts/verify_character_guild_native_ui.py','scripts/browser_session.py','scripts/save_character_guild_native_baseline.py',
        'lib/character-native.ts','lib/character-reference.ts','lib/local-game-data.ts','lib/guild-war.ts','app/characters/page.tsx','app/characters/[characterId]/page.tsx','app/guild/[guildAlias]/page.tsx','app/api/local-research-assets/characters/[assetId]/route.ts','app/_components/character-detail-panels.tsx','app/_components/character-portrait.tsx','app/_components/character-portrait.css','app/_components/character-instance-panel.tsx','app/_components/guild-war-panel.tsx','app/data-status/page.tsx',
        'tests/character-native.test.ts','tests/character-asset-reader.test.ts','tests/guild-war.test.ts','tests/test_character_native_details.py','tests/test_guildwar_visibility.py',
        'reports/character-native-details-validation.json','reports/character-guild-native-ui-validation.json','reports/character-guild-native-engineering.json','reports/character-details-supabase-receipt.json','reports/guild-top100-supabase-receipt.json','reports/guildwar-current-validation.json','reports/guild-render-profile.json','reports/guild-render-profile-selected.json','docs/current-state.md','package.json','package-lock.json','tsconfig.json']
 hashes={}
 for name in files:
  target=folder/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,target);hashes[name]=hashlib.sha256(target.read_bytes()).hexdigest()
 inputs={source.relative_to(ROOT).as_posix(),'data/normalized/verified-characters.json',LANG.relative_to(ROOT).as_posix(),(CAPTURE/'capture.json').relative_to(ROOT).as_posix()}
 raw_meta=json.loads((CAPTURE/'capture.json').read_bytes());inputs.update((CAPTURE/r['files']['record']['file']).relative_to(ROOT).as_posix() for r in raw_meta['records'])
 for r in doc['records']:
  if r['image']:inputs.add(r['image']['path'])
 for p in (ROOT/meta['definitionCapture']).iterdir():
  if p.is_file():inputs.add(p.relative_to(ROOT).as_posix())
 thumbs=ROOT/meta['thumbnailCapture']['directory'];inputs.update((thumbs/name).relative_to(ROOT).as_posix() for name in ('capture.json','base-reuse-verification.private.json'))
 for d in docs:
  directory=ROOT/d['sourceDirectory'];inputs.add((directory/d['sourceFile']).relative_to(ROOT).as_posix())
  inputs.update((directory/s['file']).relative_to(ROOT).as_posix() for s in d.get('towerSources',[]))
 with closing(sqlite3.connect(folder/'accepted-inputs.private.sqlite')) as db:reference=json.loads(db.execute('SELECT payload FROM character_detail_sources LIMIT 1').fetchone()[0])['referenceDirectory']
 for name in ('rangers.json','official-locales.json','custom-locales.json','datasets-source.json'):inputs.add((Path(reference)/name).as_posix())
 evidence=['character-talents-and-thumbnails-1242.txt','character-talents-mapping-1242.txt','character-talents-fields-1242.txt','character-talent-stage-selection-1242.txt','character-talent-unlock-rule-1242.txt','character-talent-unlocked-vector-1242.txt','character-talent-real-grade-1242.txt','guildwar-visible-tower-objects-1242.txt','guildwar-mode-request-branch-1242.txt']
 inputs.update('reports/ghidra/'+f for f in evidence)
 archive=folder/'parser-inputs.private.zip'
 with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=2) as z:
  for i,name in enumerate(sorted(inputs),1):
   z.write(ROOT/name,name)
   if i%1000==0:print(json.dumps({'archivedFiles':i,'totalFiles':len(inputs)}),flush=True)
 with zipfile.ZipFile(archive) as z:
  if z.testzip() is not None:raise ValueError('baseline archive integrity differs')
 manifest={'nativeSourceId':sid,'guildSourceId':ui['guildSourceId'],'gameVersion':meta['gameVersion'],'moduleSha256':meta['moduleSha256'],
           'reproducedFromFrozenDatabase':True,'imageAndSourceFilesArchived':len(inputs),'archiveSha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'codeAndReportHashes':hashes,
           'cloudDrafts':{m:r['auditId'] for m,r in receipts.items()},'pvpInstancesCopied':False,'liveDatabaseCopied':False,'credentialsCopied':False,'deployed':False}
 (folder/'manifest.private.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 result={'baselineDirectory':folder.relative_to(ROOT).as_posix(),'nativeSourceId':sid,'guildSourceId':ui['guildSourceId'],'reproducedFromFrozenDatabase':True,'archivedInputs':len(inputs),'uiPassed':True,'cloudReadback':True,'deployed':False}
 (ROOT/'reports/character-guild-native-success-baseline.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8');print(json.dumps(result))


if __name__=='__main__':main()
