"""Prepare/resume an insert-only private Supabase audit snapshot. Never publishes.

Uses the existing research/equipment schema, validates frozen local audit exports,
and reads back every inserted payload. Existing versions and rows are preserved.
"""
import argparse,hashlib,json
from datetime import datetime
from pathlib import Path
from audit_equipment_reference import AUDIT_SCHEMA,digest
from local_game_database import ROOT,DEFAULT_DB,connect,encoded,stamp
from supabase_local_connection import existing_service_client,existing_anon_client
from import_supabase import SupabaseApiError,ImportInputError

RESEARCH_COLUMNS='snapshot_id,module,source_record_identity,source_file,source_file_sha256,source_record_locator,raw_record,normalized_record,record_sha256,validation_status,parse_warnings'
EQUIPMENT_COLUMNS='snapshot_id,module,game_id,language,source_record_identity,source_file,source_file_sha256,payload,validation_status'

def prepare(path,database=DEFAULT_DB):
    path=Path(path).resolve();allowed=(ROOT/'data/research/runtime.private/equipment-audits').resolve()
    if not path.is_relative_to(allowed):raise ValueError('use a private frozen equipment audit export')
    data=json.loads(path.read_text(encoding='utf8'));audit=data['report'];audit_id=data['auditId']
    if audit_id!=audit['auditId'] or audit.get('method')!='native-instance-vs-rangerbook-v1':raise ValueError('invalid audit identity/method')
    db=connect(database)
    try:
        record=db.execute('SELECT content_sha256 FROM equipment_audit_exports WHERE audit_id=?',(audit_id,)).fetchone()
        if not record or record[0]!=digest(data):raise ValueError('export differs from the accepted local audit')
    finally:db.close()
    source=str(path.relative_to(ROOT)).replace('\\','/');source_sha=hashlib.sha256(path.read_bytes()).hexdigest()
    records=[];equipment=[]
    def add(identity,payload,locator,validated):
        row={'snapshot_id':audit_id,'module':'equipment','source_record_identity':identity,'source_file':source,
            'source_file_sha256':source_sha,'source_record_locator':locator,'raw_record':{'recordScope':payload['recordScope'],'frozenExportSha256':source_sha},
            'normalized_record':payload,'validation_status':'source-record-verified' if validated else 'schema-validated','parse_warnings':[]}
        row['record_sha256']=digest(row);records.append(row);return row
    checks={r['itemCode']:r for r in audit['templateChecks']}
    for i,item in enumerate(data['templates']):
        check=checks[item['itemCode']]
        if check['status']!='identity_match':raise ValueError('conflicting template cannot be uploaded')
        payload={**item,'referenceIdentityCheck':check,'numericSource':'local-native-template','externalEffectsRemainSeparate':True}
        identity={'scope':'native-template','itemCode':item['itemCode']};r=add(identity,payload,f'$.templates[{i}]',True)
        equipment.append({'snapshot_id':audit_id,'module':'equipment','game_id':item['itemCode'],'language':None,
            'source_record_identity':identity,'source_file':source,'source_file_sha256':source_sha,'payload':payload,'validation_status':r['validation_status']})
    for i,item in enumerate(data['references']):
        payload={**item,'recordScope':'external-equipment-reference','sourceKind':'external-user-confirmed','sourceUrl':audit['referenceUrl'],
                 'publicationAllowed':False,'nativeParsed':False,'referenceSources':audit['referenceSources']}
        add({'scope':'external-reference','itemCode':item['itemCode']},payload,f'$.references[{i}]',False)
    for i,item in enumerate(data['observations']):
        # Aliases are owner-scoped; no native player/unit/equipment IDs or raw memory.
        if any(k in item for k in ['playerId','guildId','moduleBase','objectAddress']):raise ValueError('unexpected private identity/memory fields')
        add({'scope':'equipment-observation','observationId':item['observationId']},item,f'$.observations[{i}]',True)
    counts={'research_records':len(records),'equipment':len(equipment)}
    manifest={'auditId':audit_id,'exportSha256':source_sha,'referenceManifestSha256':audit['referenceManifestSha256'],
        'nativeSourceHashes':audit['sourceHashes'],'expectedCounts':counts}
    manifest_file=path.with_name('upload-manifest.private.json');raw=encoded(manifest).encode('utf8')
    if manifest_file.exists() and manifest_file.read_bytes()!=raw:raise ValueError('existing upload manifest differs; preserve it')
    if not manifest_file.exists():manifest_file.write_bytes(raw)
    content=digest({'research':records,'equipment':equipment})
    snapshot={'snapshot_id':audit_id,'module':'equipment','source_kind':'dynamic','source_version':'native-with-attributed-reference-audit-v1',
        'captured_at':audit['checkedAt'],'source_manifest_sha256':hashlib.sha256(raw).hexdigest(),'content_sha256':content,'record_count':len(records),
        'source_metadata':{'auditMethod':audit['method'],'referenceUrl':audit['referenceUrl'],'referenceFetchedAt':audit['referenceFetchedAt'],
            'comparisonCounts':audit['summary'],'unknownValuesRemainUnknown':True,'rangeAgreementDoesNotVerifyExactRoll':True,
            'draftOnly':True,'containsRawMemoryOrCredentials':False},'expected_counts':counts,'is_complete':False,'status':'draft'}
    if 'externalMappingSummary' in audit:snapshot['source_metadata']['externalMappingCounts']=audit['externalMappingSummary']
    plan={'snapshot':snapshot,'researchRows':records,'equipmentRows':equipment}
    prepared=path.with_name('supabase-upload.private.json');payload=encoded(plan).encode('utf8')
    if prepared.exists() and json.loads(prepared.read_bytes())!=plan:raise ValueError('existing upload plan differs; preserve it')
    if not prepared.exists():prepared.write_bytes(payload)
    return plan

def fetch_rows(client,table,snapshot_id,columns,module='equipment'):
    rows=[];offset=0
    while True:
        page=client.request('GET','/rest/v1/'+table,params={'select':columns,'snapshot_id':'eq.'+snapshot_id,'module':'eq.'+module,'order':'source_record_identity','limit':'250','offset':str(offset)})
        if not isinstance(page,list):raise ValueError('invalid remote row response')
        rows.extend(page)
        if len(page)<250:return rows
        offset+=len(page)

def key(row):return json.dumps(row['source_record_identity'],sort_keys=True,separators=(',',':'),ensure_ascii=False)
def compare_existing(actual,expected):
    wanted={key(r):r for r in expected};seen=set()
    for row in actual:
        k=key(row)
        if k in seen or k not in wanted or row!=wanted[k]:raise ValueError('existing remote rows differ; no overwrites allowed')
        seen.add(k)
    return [r for r in expected if key(r) not in seen]

def same_snapshot(row,proposed):
    for k,v in proposed.items():
        if k=='status':continue
        actual=row.get(k)
        if k=='captured_at':
            if datetime.fromisoformat(actual.replace('Z','+00:00'))!=datetime.fromisoformat(v.replace('Z','+00:00')):raise ValueError('remote snapshot time differs')
        elif actual!=v:raise ValueError('existing remote snapshot differs at '+k)
    if row.get('status')!='draft':raise ValueError('only this private draft can be resumed')

def upload(plan,client,anonymous=None):
    snapshot=plan['snapshot'];sid=snapshot['snapshot_id'];module=snapshot['module']
    if module not in ('equipment','characters','pvp','guild'):raise ValueError('unsupported private research upload module')
    if module!='equipment' and plan.get('equipmentRows'):raise ValueError('non-equipment import must not contain equipment rows')
    batch_size=plan.get('uploadBatchSize',100)
    if type(batch_size) is not int or not 1<=batch_size<=100:raise ValueError('invalid private upload batch size')
    tables=[('ranger_research_records',plan['researchRows'],RESEARCH_COLUMNS)]
    if module=='equipment':tables.append(('ranger_equipment',plan['equipmentRows'],EQUIPMENT_COLUMNS))
    before=client.request('GET','/rest/v1/ranger_research_snapshots',params={'select':'snapshot_id,module,content_sha256,status','status':'eq.published','order':'snapshot_id,module'})
    if anonymous:
        for table,_,_ in tables:
            try:anonymous.request('GET','/rest/v1/'+table,params={'select':'snapshot_id','limit':'0'})
            except SupabaseApiError as e:
                if e.status not in (401,403):raise
            else:raise ValueError('private-table access restrictions must be verified before uploading')
    existing=client.request('GET','/rest/v1/ranger_research_snapshots',params={'select':','.join(snapshot),'snapshot_id':'eq.'+sid,'module':'eq.'+module})
    if len(existing)>1:raise ValueError('ambiguous remote snapshot')
    if existing:same_snapshot(existing[0],snapshot)
    # Check all target tables and existing contents before making any mutation.
    batches=[]
    for table,rows,columns in tables:
        actual=fetch_rows(client,table,sid,columns,module);batches.append((table,rows,columns,compare_existing(actual,rows)))
    if not existing:client.request('POST','/rest/v1/ranger_research_snapshots',payload=snapshot,prefer='return=minimal')
    for table,rows,columns,missing in batches:
        for i in range(0,len(missing),batch_size):
            client.request('POST','/rest/v1/'+table,payload=missing[i:i+batch_size],prefer='resolution=ignore-duplicates,return=minimal')
        actual=fetch_rows(client,table,sid,columns,module)
        if compare_existing(actual,rows):raise ValueError('remote payload readback incomplete')
    current=client.request('GET','/rest/v1/ranger_research_snapshots',params={'select':','.join(snapshot),'snapshot_id':'eq.'+sid,'module':'eq.'+module})
    if len(current)!=1:raise ValueError('remote snapshot missing after import')
    same_snapshot(current[0],snapshot)
    after=client.request('GET','/rest/v1/ranger_research_snapshots',params={'select':'snapshot_id,module,content_sha256,status','status':'eq.published','order':'snapshot_id,module'})
    if before!=after:raise ValueError('published versions changed during import; inspect independently')
    private_verified=False
    if anonymous:
        for table,_,_ in tables:
            try:
                result=anonymous.request('GET','/rest/v1/'+table,params={'select':'snapshot_id','snapshot_id':'eq.'+sid,'limit':'1'})
            except SupabaseApiError as e:
                if e.status not in (401,403):raise
            else:
                if result!=[]:raise ValueError('private draft is anonymously readable')
        private_verified=True
    result={'auditId':sid,'status':'draft','researchRowsVerified':len(plan['researchRows']),
            'allPayloadsReadBack':True,'publishedVersionsPreserved':True,'anonymousAccessBlocked':private_verified,'verifiedAt':stamp()}
    count_key={'equipment':'equipmentTemplatesVerified','characters':'characterTemplatesVerified','pvp':'pvpRecordsVerified','guild':'guildRecordsVerified'}[module]
    result[count_key]=len(plan['equipmentRows'] if module=='equipment' else plan['researchRows'])
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--export',type=Path,required=True);p.add_argument('--apply',action='store_true');a=p.parse_args()
    plan=prepare(a.export)
    if not a.apply:
        print(json.dumps({'prepared':True,'auditId':plan['snapshot']['snapshot_id'],'counts':plan['snapshot']['expected_counts'],'status':'draft','existingDataPreserved':True}));return
    try:receipt=upload(plan,existing_service_client(),existing_anon_client())
    except (SupabaseApiError,ImportInputError,ValueError) as error:
        # API wrapper redacts credentials. Keep diagnostics local; do not print payloads.
        a.export.with_name('upload-error.private.txt').write_text(str(error),encoding='utf8')
        print(json.dumps({'uploaded':False,'reason':'remote_connection_schema_or_readback_failed','localAuditPreserved':True}));raise SystemExit(1)
    db=connect()
    try:
        with db:db.execute("UPDATE equipment_audit_exports SET remote_status='verified',remote_verified_at=? WHERE audit_id=?",(receipt['verifiedAt'],receipt['auditId']))
    finally:db.close()
    a.export.with_name('supabase-receipt.private.json').write_text(json.dumps(receipt,indent=2),encoding='utf8')
    (ROOT/'reports/equipment-audit-supabase-receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf8')
    print(json.dumps(receipt))

if __name__=='__main__':main()
