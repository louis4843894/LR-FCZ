"""Freeze sanitized current ranking/defense data and insert a private draft.

Reuses the insert-only, full-readback uploader. Does not publish, migrate,
overwrite earlier versions, send game credentials, or send raw game responses.
"""
import argparse,hashlib,json,sqlite3
from pathlib import Path
from local_game_database import ROOT,DEFAULT_DB,encoded
from sync_equipment_audit_supabase import upload,digest
from sync_character_templates_supabase import freeze
from supabase_local_connection import existing_service_client,existing_anon_client
from import_supabase import SupabaseApiError,ImportInputError
import sys
sys.path.insert(0,str(ROOT/'scripts/runtime'))
from pvp_scope_policy import matches_scope,canonical_scope
from derive_http_gear_values import observation_id,matching_roll_entry
from character_instance_progress import read_progress,observation_key,match_progress


def owner_alias(uid):return 'owner-'+hashlib.sha256(uid.encode()).hexdigest()[:24]
def instance_alias(uid,identity):return digest([uid,identity['namespace'],identity['value']]) if identity else None


def safe_team(team,rolls=None,progress=None):
    uid=team['playerId'];members=[]
    for member in team.get('members') or []:
        gear={}
        for slot,item in member['equipment'].items():
            effects=item.get('actualEffects')
            attrs=[{k:e.get(k) for k in ['index','attributeId','valueGradeRaw','attributeTypeRaw','attributeCode','attributeLabel','value','unit','valueVerified','enhancementIncluded','valueVisuallyVerified','sourceField']} for e in effects['entries']] if effects else None
            if attrs is not None and rolls:
                record=rolls.get(observation_id(team,member,slot))
                for entry in attrs:
                    if entry.get('valueVerified') is True:continue
                    derived=matching_roll_entry(record,team,member,slot,item,entry)
                    if derived:entry.update({k:derived[k] for k in ['value','unit','valueVerified','enhancementIncluded','valueVisuallyVerified']},valueSource='native-definition-reconstruction')
            gear[slot]={'state':item['state'],'equipmentId':item.get('equipmentId'),'enhancement':item.get('enhancement'),
                        'instanceGrade':item.get('instanceGrade'),'equipmentInstanceAlias':instance_alias(uid,item.get('equipmentInstanceIdentity')),
                        'instanceNamespace':(item.get('equipmentInstanceIdentity') or {}).get('namespace'),
                        'ownerAssociationStatus':item.get('ownerAssociationStatus','unknown'),
                        'attributeReadState':item.get('attributeReadState'),'actualEffects':attrs,
                        'templateReferenceRangesAreInstanceValues':False}
        members.append({'memberIndex':member['memberIndex'],'characterState':member['characterState'],'characterId':member.get('characterId'),
                        'characterInstanceAlias':instance_alias(uid,member.get('characterInstanceIdentity')),
                        'instanceNamespace':(member.get('characterInstanceIdentity') or {}).get('namespace'),'equipment':gear,
                        'characterProgress':match_progress((progress or {}).get(observation_key('pvp',team['snapshotId'],uid,team['teamId'].split('/')[-1],member['memberIndex'])),member.get('characterId'),uid,(member.get('characterInstanceIdentity') or {}).get('value'),team['retrievedAt'])})
    return {'recordScope':'ranked-defense-team','observationId':digest([uid,team['snapshotId']]),'ownerAlias':owner_alias(uid),
            'purpose':team['purpose'],'teamId':team['teamId'],'status':team['status'],'retrievedAt':team['retrievedAt'],
            'isSelected':team.get('isSelected'),'unobservedPositionIndices':team.get('unobservedPositionIndices'),
            'gameVersion':team.get('gameVersion'),'members':members,
            'visuallyVerified':bool((team.get('verification') or {}).get('purposeConfirmed'))}


def prepare(database=DEFAULT_DB):
    db=sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro',uri=True)
    try:
        db.execute('BEGIN')
        rankings=[json.loads(p) for label,p in db.execute('SELECT c.scope_label,r.payload FROM current_rankings c JOIN ranking_snapshots r USING(snapshot_id) ORDER BY c.scope_label') if matches_scope(label,'all')]
        rankings=[{**r,'scope':{**r['scope'],'label':canonical_scope(r['scope']['label'])}} for r in rankings]
        doc=db.execute("SELECT d.sha256,d.payload FROM current_documents c JOIN documents d USING(sha256) WHERE c.filename='defense-teams.private.json'").fetchone()
        if not rankings or not doc:raise ValueError('accepted local ranking/defense sources missing')
        defense=json.loads(doc[1]);attempts={}
        for sid,uid,payload in db.execute('SELECT ranking_snapshot_id,player_id,payload FROM ranking_defense_attempts ORDER BY attempted_at'):attempts[(sid,uid)]=json.loads(payload)
        checked={path:at for path,at in db.execute('SELECT s.private_directory,c.checked_at FROM pvp_http_checks c JOIN pvp_http_sources s USING(capture_id)')}
        roll_source=None;rolls={}
        if db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='gear_roll_sources'").fetchone():
            row=db.execute("SELECT s.source_id,s.payload FROM current_gear_rolls c JOIN gear_roll_sources s USING(source_id) WHERE scope='ranked-http'").fetchone()
            if row:
                meta=json.loads(row[1])
                if meta.get('sourceKind')!='calibrated-native-definition-http-rolls' or meta.get('externalReferenceValuesUsed') is not False or meta.get('calibration',{}).get('screenCheckedValueCount',0)<6:raise ValueError('unverified native gear reconstruction export')
                roll_source=row[0];rolls={key:json.loads(p) for key,p in db.execute('SELECT observation_id,payload FROM gear_instance_rolls WHERE source_id=?',(roll_source,))}
    finally:db.close()
    progress_source,progress=read_progress(database)
    teams={(t['playerId'],t['snapshotId']):t for t in defense['snapshots']};records=[];private_ids=[];accepted_teams=set()
    for ranking in rankings:
        sid=ranking['snapshotId'];private_ids.extend(p['playerId'] for p in ranking['players'])
        records.append({'identity':{'scope':'ranking-source','sourceId':sid},'data':{
            'recordScope':'ranking-source','sourceId':sid,'scopeLabel':ranking['scope']['label'],
            'capturedAt':ranking['capturedAt'],'loadedCount':ranking['loadedCount'],
            'retrievedPlayerCount':len(ranking['players']),'wholeRankingComplete':False}})
        for player in ranking['players']:
            uid=player['playerId'];alias=owner_alias(uid);attempt=attempts.get((sid,uid));observations=[]
            if attempt and attempt['status'] in ('success','partial'):
                for source_id in attempt['defenseSnapshotIds']:
                    team=teams.get((uid,source_id))
                    if not team or team['purpose']!='pvp_defense':raise ValueError('accepted ranked defense relation missing')
                    safe=safe_team(team,rolls,progress);observations.append(safe['observationId'])
                    if safe['observationId'] not in accepted_teams:
                        records.append({'identity':{'scope':'ranked-defense-team','observationId':safe['observationId']},'data':safe});accepted_teams.add(safe['observationId'])
            records.append({'identity':{'scope':'ranked-player','rankingSource':sid,'ownerAlias':alias},'data':{
                'recordScope':'ranked-player','rankingSourceId':sid,'scopeLabel':ranking['scope']['label'],'rankingCapturedAt':ranking['capturedAt'],
                'ownerAlias':alias,'displayName':player.get('displayName'),'rank':player['rank'],'score':player['score'],
                'defenseStatus':attempt['status'] if attempt else 'not_read','defenseRetrievedAt':attempt.get('defenseRetrievedAt') if attempt else None,
                'defenseCheckedAt':checked.get(attempt.get('captureDirectory')) if attempt else None,
                'failureReason':attempt.get('failureReason') if attempt else None,'defenseObservations':observations}})
    content=digest(records);snapshot_id='pvp-ranked-'+content[:24]
    folder=ROOT/'data/research/runtime.private/pvp-exports'/snapshot_id;folder.mkdir(parents=True,exist_ok=True)
    source=folder/'records.private.json';sha=freeze(source,{'records':records})
    manifest={'snapshotId':snapshot_id,'localDefenseDocumentSha256':doc[0],'contentSha256':content,
              'rankingSources':[{k:r[k] for k in ['snapshotId','sourceCaptureSha256','capturedAt']} for r in rankings],
              'researchRecords':len(records),'rankedPlayers':sum(len(r['players']) for r in rankings),'defenseTeams':len(accepted_teams),
              'credentialsOrRawMemoryIncluded':False,'instanceIdsOwnerScopedAndAnonymized':True,'nativeGearReconstructionSourceId':roll_source,
              'characterInstanceProgressSourceId':progress_source}
    manifest_sha=freeze(folder/'manifest.private.json',manifest);rows=[]
    for i,record in enumerate(records):
        row={'snapshot_id':snapshot_id,'module':'pvp','source_record_identity':record['identity'],
             'source_file':source.relative_to(ROOT).as_posix(),'source_file_sha256':sha,'source_record_locator':f'$.records[{i}]',
             'raw_record':{'recordScope':record['data']['recordScope'],'sanitizedExportSha256':sha},
             'normalized_record':record['data'],'validation_status':'source-record-verified','parse_warnings':[]}
        row['record_sha256']=digest(row);rows.append(row)
    times=[r['data'].get('retrievedAt') or r['data'].get('capturedAt') for r in records]
    snapshot={'snapshot_id':snapshot_id,'module':'pvp','source_kind':'dynamic','source_version':'normal-native-http-ranked-defense-v1',
              'captured_at':max(t for t in times if t),'source_manifest_sha256':manifest_sha,'content_sha256':digest(rows),
              'record_count':len(rows),'source_metadata':{**manifest,'draftOnly':True,'wholeGameCoverageConfirmed':False,
                  'rankingAndDefenseTimesKeptSeparate':True,'unknownValuesRemainUnknown':True},
              'expected_counts':{'research_records':len(rows)},'is_complete':False,'status':'draft'}
    plan_file=folder/'supabase-upload.private.json'
    batch=json.loads(plan_file.read_bytes()).get('uploadBatchSize',10) if plan_file.exists() else 25
    plan={'snapshot':snapshot,'researchRows':rows,'equipmentRows':[],'uploadBatchSize':batch}
    serialized=encoded(plan)
    if any(uid in serialized for uid in set(private_ids)):raise ValueError('private native player ID leaked into export')
    freeze(folder/'supabase-upload.private.json',plan)
    return folder,plan,manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    folder,plan,manifest=prepare()
    if not args.apply:print(json.dumps({'prepared':True,'snapshotId':manifest['snapshotId'],'records':manifest['researchRecords'],'players':manifest['rankedPlayers'],'defenseTeams':manifest['defenseTeams']}))
    else:
        try:receipt=upload(plan,existing_service_client(),existing_anon_client())
        except (SupabaseApiError,ImportInputError,ValueError) as error:
            (folder/'upload-error.private.txt').write_text(str(error),encoding='utf8')
            print(json.dumps({'uploaded':False,'reason':'remote_connection_or_readback_failed','localDataPreserved':True}));raise SystemExit(1)
        (folder/'supabase-receipt.private.json').write_text(json.dumps(receipt,indent=2),encoding='utf8')
        (ROOT/'reports/pvp-rankings-supabase-receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf8')
        print(json.dumps(receipt))
