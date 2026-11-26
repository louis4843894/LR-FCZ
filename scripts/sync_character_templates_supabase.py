"""Freeze accepted native character templates and insert a private Supabase draft.

Reuses the verified insert-only uploader. No credentials, instance/account data,
raw memory, schema migrations, or publication. Default is prepare-only.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from local_game_database import ROOT, DEFAULT_DB, encoded, validate
from native_layouts import NEW_SHA
from parse_runtime_characters import STAR_EVIDENCE
from supabase_local_connection import existing_service_client, existing_anon_client
from sync_equipment_audit_supabase import upload, digest
from import_supabase import SupabaseApiError, ImportInputError


def freeze(path, data):
    serialized=encoded(data).encode('utf8')
    if path.exists() and path.read_bytes()!=serialized:
        raise ValueError('frozen character export differs; preserve existing version')
    if not path.exists():path.write_bytes(serialized)
    return hashlib.sha256(serialized).hexdigest()


def prepare(database=DEFAULT_DB):
    import sqlite3
    source=ROOT/'data/normalized/verified-characters.json'
    raw=source.read_bytes();source_sha=hashlib.sha256(raw).hexdigest();doc=json.loads(raw)
    validate('characters',doc)
    with sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro',uri=True) as db:
        accepted=db.execute('SELECT sha256 FROM current_documents WHERE filename=?',('verified-characters.json',)).fetchone()
    if not accepted or accepted[0]!=source_sha:
        raise ValueError('character source is not the currently accepted local document')
    native_file=ROOT/'data/research/rangers-native-2405.json'
    native_bytes=native_file.read_bytes();native=json.loads(native_bytes)
    if (doc.get('localVerification') is not True or doc.get('sourceSha256')!=hashlib.sha256(native_bytes).hexdigest()
            or native.get('sourceKind')!='verified-native-unit-definitions'):
        raise ValueError('character export lacks its verified native source')
    originals={r['characterId']:r for r in native['records']}
    if len(originals)!=len(doc['records']):raise ValueError('character native/export count differs')
    for row in doc['records']:
        original=originals[row['characterId']]
        if (original['provenance']['moduleSha256']!=NEW_SHA
                or row.get('starCount')!=original.get('gradeRaw')
                or row.get('fieldStatus',{}).get('starCount')!='verified-native-ui-relation'
                or row.get('skills') is not None or row.get('imageMapping') is not None):
            raise ValueError('character template evidence or unknown fields differ')
        if any(row.get(k)!=original.get(k) for k in row):
            raise ValueError('character whitelist differs from native source')
    snapshot_id='characters-native-'+source_sha[:24]
    folder=ROOT/'data/research/runtime.private/character-exports'/snapshot_id
    folder.mkdir(parents=True,exist_ok=True)
    frozen=folder/'templates.private.json';frozen_sha=freeze(frozen,doc)
    manifest={'snapshotId':snapshot_id,'localDocumentSha256':source_sha,
              'nativeSourceSha256':hashlib.sha256(native_bytes).hexdigest(),
              'moduleSha256':NEW_SHA,'starEvidenceSha256':hashlib.sha256((ROOT/STAR_EVIDENCE).read_bytes()).hexdigest(),
              'templateCount':len(doc['records']),'coverage':doc['fieldCoverage']}
    manifest_sha=freeze(folder/'manifest.private.json',manifest)
    source_name=frozen.relative_to(ROOT).as_posix()
    rows=[]
    for index,row in enumerate(doc['records']):
        record={'snapshot_id':snapshot_id,'module':'characters',
                'source_record_identity':{'scope':'character-template','characterId':row['characterId']},
                'source_file':source_name,'source_file_sha256':frozen_sha,'source_record_locator':f'$.records[{index}]',
                'raw_record':{'recordScope':'character-template','nativeRecordSha256':originals[row['characterId']]['provenance']['rawRecordSha256']},
                'normalized_record':row,'validation_status':'source-record-verified','parse_warnings':[]}
        record['record_sha256']=digest(record);rows.append(record)
    snapshot={'snapshot_id':snapshot_id,'module':'characters','source_kind':'dynamic',
              'source_version':native['parserVersion'],
              'captured_at':datetime.fromtimestamp(doc['capturedAt'],timezone.utc).isoformat(),
              'source_manifest_sha256':manifest_sha,'content_sha256':digest(rows),'record_count':len(rows),
              'source_metadata':{'gameVersion':doc['gameVersion'],'moduleSha256':NEW_SHA,'fieldCoverage':doc['fieldCoverage'],
                                 'draftOnly':True,'containsRawMemoryOrCredentials':False,'wholeGameCoverageConfirmed':False},
              'expected_counts':{'research_records':len(rows)},'is_complete':False,'status':'draft'}
    plan={'snapshot':snapshot,'researchRows':rows,'equipmentRows':[]}
    freeze(folder/'supabase-upload.private.json',plan)
    return folder,plan


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    folder,plan=prepare()
    if not args.apply:
        print(json.dumps({'prepared':True,'snapshotId':plan['snapshot']['snapshot_id'],'templates':len(plan['researchRows']),'status':'draft'}))
    else:
        try:receipt=upload(plan,existing_service_client(),existing_anon_client())
        except (SupabaseApiError,ImportInputError,ValueError) as error:
            (folder/'upload-error.private.txt').write_text(str(error),encoding='utf8')
            print(json.dumps({'uploaded':False,'reason':'remote_connection_schema_or_readback_failed','localDataPreserved':True}))
            raise SystemExit(1)
        (folder/'supabase-receipt.private.json').write_text(json.dumps(receipt,indent=2),encoding='utf8')
        (ROOT/'reports/character-templates-supabase-receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf8')
        print(json.dumps(receipt))
