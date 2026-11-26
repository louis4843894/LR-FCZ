"""Validate the accepted character detail overlay against immutable inputs."""
import argparse,hashlib,json,sqlite3
from collections import Counter
from contextlib import closing
from datetime import datetime,timezone
from pathlib import Path
from build_character_details import build
from local_game_database import ROOT,DEFAULT_DB


def validate():
 with closing(sqlite3.connect(DEFAULT_DB.resolve().as_uri()+'?mode=ro',uri=True)) as db:
  source,payload=db.execute("SELECT s.source_id,s.payload FROM current_character_details c JOIN character_detail_sources s USING(source_id) WHERE c.scope='native-matched-reference'").fetchone();meta=json.loads(payload)
  rebuilt=build(ROOT/meta['referenceDirectory'],startup_folder=ROOT/meta['startupSource']['directory'] if meta.get('startupSource') else None)
  if rebuilt['sourceId']!=source or {k:v for k,v in rebuilt.items() if k!='records'}!=meta:raise ValueError('character detail metadata does not reproduce')
  rows={code:json.loads(p) for code,p in db.execute('SELECT character_id,payload FROM character_template_details WHERE source_id=?',(source,))}
  if rows!={r['characterId']:r for r in rebuilt['records']}:raise ValueError('stored character details differ from source')
  accepted=db.execute("SELECT sha256 FROM current_documents WHERE filename='verified-characters.json'").fetchone()[0]
  if accepted!=rebuilt['nativeDocumentSha256']:raise ValueError('native basic version differs')
  for table in ['character_detail_sources','current_character_details','character_template_details']:
   if db.execute('PRAGMA quick_check('+table+')').fetchone()[0]!='ok' or db.execute('PRAGMA foreign_key_check('+table+')').fetchall():raise ValueError('character detail database integrity failed')
  samples=[]
  for code in ['u1618e-ka','u1535e-brown','u1646e-jessica','u0004u-leonard']:
   row=rows.get(code)
   if row:samples.append({'characterId':code,'status':row['status'],'skillNames':[s['name'] for s in row['skills'] or []],
                          'abilityNames':[a['name'] for a in row['abilities'] or []],'awakeningNames':[a['name'] for a in row['awakeningAbilities'] or []],
                          'hasTalents':row['talents'] is not None})
 report={'verifiedAt':datetime.now(timezone.utc).isoformat(),'sourceId':source,'nativeBasicVersionUnchanged':True,'nativeDocumentSha256':accepted,
         'offlineReproductionVerified':True,'storedRows':len(rows),'summary':meta['summary'],'referenceDetailsAreNativeParsed':False,
         'skillDescriptionSources':dict(Counter(s['textSource'] for r in rows.values() for s in r['skills'] or [])),
         'candidateProbabilityIsActivationRate':False,'samples':samples}
 (ROOT/'reports/character-detail-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8');return report


if __name__=='__main__':print(json.dumps(validate(),ensure_ascii=False))
