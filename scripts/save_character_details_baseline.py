"""Freeze accepted character inputs, code and checks without account data."""
import hashlib,json,shutil,sqlite3
from pathlib import Path
from contextlib import closing
from datetime import datetime,timezone
from build_character_details import ROOT,DEFAULT_DB,LANG,build


def save():
 ui=json.loads((ROOT/'reports/character-detail-ui-validation.json').read_bytes());receipt=json.loads((ROOT/'reports/character-details-supabase-receipt.json').read_bytes());build_status=json.loads((ROOT/'reports/build-local-validation-status.json').read_text(encoding='utf-8-sig'));validation=json.loads((ROOT/'reports/character-detail-validation.json').read_bytes())
 if ui.get('passed') is not True or ui.get('sourceId')!=validation.get('sourceId') or receipt.get('allPayloadsReadBack') is not True or receipt.get('researchRowsVerified')!=validation.get('storedRows') or build_status.get('exitCode')!=0:raise ValueError('final character acceptance checks not complete')
 folder=ROOT/'data/research/runtime.private/baselines'/('character-details-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'));folder.mkdir()
 with closing(sqlite3.connect(DEFAULT_DB.resolve().as_uri()+'?mode=ro',uri=True)) as db:
  sid,payload=db.execute("SELECT s.source_id,s.payload FROM current_character_details c JOIN character_detail_sources s USING(source_id) WHERE c.scope='native-matched-reference'").fetchone();meta=json.loads(payload)
  records={code:json.loads(p) for code,p in db.execute('SELECT character_id,payload FROM character_template_details WHERE source_id=?',(sid,))}
  if sid!=validation['sourceId'] or len(records)!=validation['storedRows']:raise ValueError('character source changed after acceptance')
  with closing(sqlite3.connect(folder/'accepted-inputs.private.sqlite')) as dst:
   for table,where,args in [('documents',"sha256=?",(meta['nativeDocumentSha256'],)),('current_documents',"filename='verified-characters.json'",()),
                            ('character_detail_sources','source_id=?',(sid,)),('current_character_details',"scope='native-matched-reference'",()),('character_template_details','source_id=?',(sid,))]:
    dst.execute(db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone()[0]);rows=db.execute('SELECT * FROM '+table+' WHERE '+where,args).fetchall()
    if rows:dst.executemany('INSERT INTO '+table+' VALUES ('+','.join('?' for _ in rows[0])+')',rows)
   dst.commit()
   if dst.execute('PRAGMA foreign_key_check').fetchall() or dst.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise ValueError('frozen character DB integrity failed')
 reference=(ROOT/meta['referenceDirectory']).resolve()
 if not reference.is_relative_to(ROOT/'data/research/external-reference'):raise ValueError('reference source outside scope')
 manifest=json.loads((reference/'datasets-source.json').read_bytes());inputs=folder/'inputs';inputs.mkdir();reference_copy=inputs/'reference';reference_copy.mkdir()
 for name in ['datasets-source.json','public-sources.json','v2-data.js','ranger.js','ranger-page.html','ability-page.html',*[r['file'] for r in manifest['files']]]:
  if Path(name).name!=name:raise ValueError('invalid reference basename')
  shutil.copyfile(reference/name,reference_copy/name)
 native=inputs/'verified-characters.json';shutil.copyfile(ROOT/'data/normalized/verified-characters.json',native)
 translation=inputs/'lang_unit.ndb';shutil.copyfile(LANG,translation)
 if hashlib.sha256(native.read_bytes()).hexdigest()!=meta['nativeDocumentSha256'] or hashlib.sha256(translation.read_bytes()).hexdigest()!=meta['localTranslationSha256'] or hashlib.sha256((reference_copy/'datasets-source.json').read_bytes()).hexdigest()!=meta['referenceManifestSha256']:raise ValueError('frozen input provenance hash differs')
 reproduced=build(reference_copy,native,translation)
 if {r['characterId']:r for r in reproduced['records']}!=records or reproduced['summary']!=meta['summary']:raise ValueError('copied character inputs do not reproduce records')
 files=['scripts/build_character_details.py','scripts/fetch_character_details_reference.py','scripts/validate_character_details.py','scripts/sync_character_details_supabase.py','scripts/verify_character_details_ui.py','scripts/save_character_details_baseline.py',
        'lib/character-details.ts','lib/character-reference.ts','lib/local-game-data.ts','app/_components/character-detail-panels.tsx','app/_components/character-detail-panels.css',
        'app/characters/page.tsx','app/characters/[characterId]/page.tsx','app/data-status/page.tsx','tests/test_character_details.py','tests/character-details.test.ts','tests/character-detail-reader.test.ts',
        'reports/character-detail-validation.json','reports/character-detail-ui-validation.json','reports/character-details-supabase-receipt.json','reports/build-local-validation-status.json','docs/current-state.md','package.json','package-lock.json','tsconfig.json']
 hashes={}
 for name in files:
  target=folder/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target);hashes[name]=hashlib.sha256(target.read_bytes()).hexdigest()
 for p in inputs.rglob('*'):
  if p.is_file():hashes[p.relative_to(folder).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
 details={'sourceId':sid,'summary':meta['summary'],'recordsReproducedFromCopiedInputs':True,'sourcePathDiffersInFrozenCopy':True,
          'frozenDatabaseSha256':hashlib.sha256((folder/'accepted-inputs.private.sqlite').read_bytes()).hexdigest(),'files':hashes,
          'credentialsOrRawMemoryIncluded':False,'playerInstanceTablesCopied':False,'deployed':False}
 (folder/'manifest.private.json').write_text(json.dumps(details,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 report={'baselineDirectory':folder.relative_to(ROOT).as_posix(),'sourceId':sid,'recordsReproducedFromCopiedInputs':True,'summary':meta['summary'],'deployed':False}
 (ROOT/'reports/character-details-success-baseline.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8');return report


if __name__=='__main__':print(json.dumps(save(),ensure_ascii=False))
