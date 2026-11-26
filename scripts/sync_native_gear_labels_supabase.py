"""Insert only a verified native Chinese-kind lookup as a private draft."""
import argparse,json,sqlite3
from datetime import datetime,timezone
from pathlib import Path
from local_game_database import ROOT,DEFAULT_DB
from sync_character_templates_supabase import freeze
from sync_equipment_audit_supabase import upload,digest
from supabase_local_connection import existing_service_client,existing_anon_client


def prepare(database=DEFAULT_DB):
    with sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro',uri=True) as db:
        row=db.execute("SELECT s.payload FROM current_gear_attribute_labels c JOIN gear_attribute_label_sources s USING(source_id) WHERE scope='ordinary-native'").fetchone()
    if not row:raise ValueError('accepted native label source missing')
    doc=json.loads(row[0])
    if doc['sourceKind']!='verified-native-gearstat-labels' or doc['numericValuesDerived'] is not False:raise ValueError('native label contract differs')
    records=[{k:r[k] for k in ['attributeId','typeEnum','code','label','evidenceRecordHashes']} for r in doc['records']]
    sid='equipment-native-labels-'+digest(records)[:24];folder=ROOT/'data/research/runtime.private/gear-label-exports'/sid;folder.mkdir(exist_ok=True)
    source=folder/'labels.private.json';sha=freeze(source,{'sourceKind':doc['sourceKind'],'moduleSha256':doc['moduleSha256'],'records':records})
    manifest={'sourceId':doc['sourceId'],'moduleSha256':doc['moduleSha256'],'labels':len(records),'nativeCaptures':len(doc['evidence']['sources']),
              'translationSha256':doc['evidence']['translationSha256'],'numericValuesDerived':False,'rawMemoryOrCredentialsIncluded':False}
    manifest_sha=freeze(folder/'manifest.private.json',manifest);rows=[]
    for i,record in enumerate(records):
        data={'recordScope':'ordinary-gearstat-kind','sourceKind':doc['sourceKind'],'idNamespace':doc['idNamespace'],**record,'numericValue':None}
        r={'snapshot_id':sid,'module':'equipment','source_record_identity':{'scope':'ordinary-gearstat-kind','attributeId':record['attributeId']},'source_file':source.relative_to(ROOT).as_posix(),
           'source_file_sha256':sha,'source_record_locator':f'$.records[{i}]','raw_record':{'recordScope':'ordinary-gearstat-kind','evidenceRecordHashes':record['evidenceRecordHashes']},
           'normalized_record':data,'validation_status':'source-record-verified','parse_warnings':[]}
        r['record_sha256']=digest(r);rows.append(r)
    times=[s['capturedAt'] for s in doc['evidence']['sources']]
    at=max(datetime.fromtimestamp(t,timezone.utc) if isinstance(t,(int,float)) else datetime.fromisoformat(t) for t in times).isoformat()
    plan={'snapshot':{'snapshot_id':sid,'module':'equipment','source_kind':'dynamic','source_version':'native-gearstat-chinese-kind-v1','captured_at':at,
          'source_manifest_sha256':manifest_sha,'content_sha256':digest(rows),'record_count':len(rows),'source_metadata':{**manifest,'draftOnly':True,'wholeGameCoverageConfirmed':False},
          'expected_counts':{'research_records':len(rows),'ranger_equipment':0},'is_complete':False,'status':'draft'},'researchRows':rows,'equipmentRows':[]}
    freeze(folder/'supabase-upload.private.json',plan);return folder,plan


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--apply',action='store_true');a=p.parse_args();folder,plan=prepare()
    if not a.apply:print(json.dumps({'prepared':True,'snapshotId':plan['snapshot']['snapshot_id'],'labels':len(plan['researchRows'])}))
    else:
        try:receipt=upload(plan,existing_service_client(),existing_anon_client())
        except Exception:print(json.dumps({'uploaded':False,'reason':'native_label_connection_or_readback_failed','localDataPreserved':True}));raise SystemExit(1)
        receipt['nativeGearKindLabelsVerified']=len(plan['researchRows'])
        (folder/'supabase-receipt.private.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf8')
        (ROOT/'reports/native-gear-labels-supabase-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf8');print(json.dumps(receipt))
