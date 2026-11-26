"""Freeze the accepted startup/progress inputs and code; never copy the live DB."""
import hashlib,json,shutil,sqlite3,zipfile
from contextlib import closing
from datetime import datetime,timezone
from pathlib import Path
from local_game_database import ROOT,DEFAULT_DB
from native_layouts import NEW_SHA


def main():
 def report(name):return json.loads((ROOT/'reports'/name).read_bytes())
 ui=report('character-instance-ui-validation.json');validated=report('character-instance-validation.json');build=report('character-instance-build-validation.json')
 if not ui['passed'] or not validated['passed'] or ui['instanceSourceId']!=validated['sourceId'] or build['exitCode']!=0:raise ValueError('final local acceptance required')
 receipts={name:report(filename) for name,filename in [('characters','character-details-supabase-receipt.json'),('pvp','pvp-rankings-supabase-receipt.json'),('guild','guild-top100-supabase-receipt.json')]}
 if not all(r['allPayloadsReadBack'] and r['publishedVersionsPreserved'] and r['anonymousAccessBlocked'] for r in receipts.values()):raise ValueError('cloud full readback required')
 sid=validated['sourceId'];detail_sid=ui['detailSourceId']
 for name,part in [('characters','character-detail-exports'),('pvp','pvp-exports'),('guild','guild-exports')]:
  plan=json.loads((ROOT/'data/research/runtime.private'/part/receipts[name]['auditId']/'supabase-upload.private.json').read_bytes())
  meta=plan['snapshot']['source_metadata']
  if (name=='characters' and meta['detailSourceId']!=detail_sid) or (name!='characters' and meta['characterInstanceProgressSourceId']!=sid):raise ValueError('cloud draft source differs from accepted local source')
 source=ROOT/'data/research/runtime.private/character-instance-exports'/sid/'instances.private.json';doc=json.loads(source.read_bytes())
 detail_path=ROOT/'data/research/runtime.private/character-detail-exports'/detail_sid/'details.private.json';details=json.loads(detail_path.read_bytes())
 with closing(sqlite3.connect(DEFAULT_DB.resolve().as_uri()+'?mode=ro',uri=True)) as db:
  if db.execute("SELECT source_id FROM current_character_instance_sources WHERE scope='accepted-defense'").fetchone()[0]!=sid:raise ValueError('progress source changed')
  if db.execute("SELECT source_id FROM current_character_details WHERE scope='native-matched-reference'").fetchone()[0]!=detail_sid:raise ValueError('character detail source changed')
  sha,payload=db.execute("SELECT c.sha256,d.payload FROM current_documents c JOIN documents d USING(sha256) WHERE c.filename='defense-teams.private.json'").fetchone()
  if sha!=doc['defenseDocumentSha256']:raise ValueError('defense source changed')
  defense_payload=payload
  war_payloads=[p for p, in db.execute("SELECT s.payload FROM current_guild_war_sources c JOIN guild_war_sources s USING(source_id) WHERE s.kind IN ('deployed_defense','saved_configuration')")]
 folder=ROOT/'data/research/runtime.private/baselines'/('character-instances-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'));folder.mkdir(parents=True,exist_ok=False)
 (folder/'accepted-defense-document.private.json').write_text(defense_payload,encoding='utf8')
 (folder/'accepted-guild-documents.private.json').write_text('['+','.join(war_payloads)+']',encoding='utf8')
 files=['scripts/character_skill_startup.py','scripts/character_instance_progress.py','scripts/build_character_details.py','scripts/validate_character_details.py','scripts/sync_character_details_supabase.py','scripts/sync_pvp_rankings_supabase.py','scripts/sync_guild_rankings_supabase.py','scripts/update_local_game_data.py','scripts/runtime/collect_guildwar_http.py','scripts/verify_character_instance_ui.py','scripts/save_character_instance_baseline.py',
        'lib/character-instance-progress.ts','lib/character-details.ts','lib/local-game-data.ts','lib/defense-teams.ts','lib/guild-war.ts',
        'app/_components/character-detail-panels.tsx','app/_components/character-instance-panel.tsx','app/_components/character-instance-panel.css','app/_components/defense-teams-panel.tsx','app/_components/guild-war-panel.tsx',
        'tests/test_character_instance_progress.py','tests/character-instance-progress.test.ts','tests/defense-label-reader.test.ts','tests/guild-war.test.ts',
        'reports/character-instance-validation.json','reports/character-instance-ui-validation.json','reports/character-instance-build-validation.json','reports/character-detail-validation.json','reports/character-details-supabase-receipt.json','reports/pvp-rankings-supabase-receipt.json','reports/guild-top100-supabase-receipt.json','docs/current-state.md','package.json','package-lock.json','tsconfig.json']
 hashes={}
 for name in files:
  target=folder/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target);hashes[name]=hashlib.sha256(target.read_bytes()).hexdigest()
 # A bounded archive contains only the exact source copies used by this parser,
 # translations and animation/reference data. No process dump/session files.
 normalized_defense=ROOT/'data/normalized/defense-teams.private.json'
 if hashlib.sha256(normalized_defense.read_bytes()).hexdigest()!=doc['defenseDocumentSha256']:raise ValueError('original normalized defense file hash differs')
 inputs=set(doc['sources'])|{source.relative_to(ROOT).as_posix(),detail_path.relative_to(ROOT).as_posix(),'data/normalized/verified-characters.json','data/normalized/defense-teams.private.json','data/research/runtime.private/guild-session-20261123/lang_unit.ndb'}
 for payload in war_payloads:
  war=json.loads(payload);inputs.add((Path(war['sourceDirectory'])/war['sourceFile']).as_posix())
 for source_path in [details['referenceDirectory'],details['startupSource']['directory']]:
  inputs.update(p.relative_to(ROOT).as_posix() for p in (ROOT/source_path).iterdir() if p.suffix in ('.json','.js','.html'))
 archive=folder/'parser-inputs.private.zip'
 with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=2) as z:
  for name in sorted(inputs):
   p=ROOT/name
   if name in doc['sources'] and hashlib.sha256(p.read_bytes()).hexdigest()!=doc['sources'][name]:raise ValueError('input copy changed')
   z.write(p,name)
 details={'sourceId':sid,'detailSourceId':detail_sid,'gameVersion':'12.4.2','moduleSha256':NEW_SHA,'summary':doc['summary'],'currentRankedPvp':validated['currentRankedPvp'],
          'codeAndReportHashes':hashes,'archivedInputFiles':len(inputs),'archiveSha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
          'sourceCopyHashes':doc['sources'],'cloudDrafts':{k:r['auditId'] for k,r in receipts.items()},'noLiveDatabaseOrProcessDumpCopied':True,'deployed':False}
 (folder/'manifest.private.json').write_text(json.dumps(details,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 summary={'baselineDirectory':folder.relative_to(ROOT).as_posix(),'sourceId':sid,'detailSourceId':detail_sid,'inputsArchived':len(inputs),'uiPassed':True,'cloudFullyReadBack':True,'deployed':False}
 (ROOT/'reports/character-instance-success-baseline.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(summary))


if __name__=='__main__':main()
