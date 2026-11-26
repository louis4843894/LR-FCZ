"""Insert a sanitized top-100 guild/roster draft; preserve all remote versions."""
import argparse,hashlib,json,sqlite3
from copy import deepcopy
from datetime import datetime,timezone
from pathlib import Path
from local_game_database import ROOT,DEFAULT_DB,encoded
from sync_equipment_audit_supabase import upload,digest
from sync_character_templates_supabase import freeze
from supabase_local_connection import existing_service_client,existing_anon_client
from import_supabase import SupabaseApiError,ImportInputError
from derive_guildwar_gear_values import read_rolls,observation_id,matching_value
from character_instance_progress import read_progress,observation_key,match_progress
from build_character_native_details import read_native_details,talent_stages


def alias(value):return hashlib.sha256(value.encode()).hexdigest()[:24]


def public_war_record(doc,rolls=None,progress=None,native=None):
    """No native player/unit/equipment identities or raw response bodies."""
    base={k:doc[k] for k in ['sourceKind','sourceId','parserVersion','seasonNo','battleNo','seasonStatus','capturedAt','gameVersion','status']}
    base.update(recordScope='guild-war-observation',guildAlias=alias(doc['guildId']),kind=doc['kind'],visualVerification=False)
    def safe_gear(e,owner,tower,team,unit,slot):
        safe={k:e.get(k) for k in ['state','equipmentId','enhancement','instanceGrade','attributeReadState']}
        effects=deepcopy(e.get('actualEffects'))
        if effects:
            record=(rolls or {}).get(observation_id(doc,tower,owner,team,unit,slot))
            if record and record.get('sourceObservationSha256')!=doc.get('sourceSha256'):record=None
            if record and not any(matching_value(record,owner,e,a) for a in effects['entries']):record=None
            if record and record.get('supplementarySpecial',{}):
                extra=record['supplementarySpecial']
                safe['supplementarySpecial']={'state':'observed_unparsed','numericalValuesVerified':False}
                if (extra.get('state')=='values_reconstructed' and extra.get('valueVerified') is True and extra.get('enhancementIncluded') is True
                    and extra.get('activationState')=='not_verified' and type(extra.get('specialEnhancement')) is int and 0<=extra['specialEnhancement']<=100
                    and all(isinstance(extra.get(k),str) and 0<len(extra[k])<=1000 for k in ['name','normalText','description'])):
                    safe['supplementarySpecial']={k:extra[k] for k in ['state','name','normalText','description','specialEnhancement','enhancementIncluded','activationState']}
                    safe['supplementarySpecial'].update(numericalValuesVerified=True,valueVisuallyVerified=False,duplicateOptionPriorityVerified=False)
            for entry in effects['entries']:
                result=matching_value(record,owner,e,entry)
                if result and entry.get('value') is None:
                    entry.update({k:result[k] for k in ['value','unit','enhancementIncluded','valueVerified']},valueSource='native-definition-reconstruction',valueVisuallyVerified=False,factorCapturedAt=record['factorCapturedAt'])
                    entry.update({k:result[k] for k in ['calculationKind','appliedEnhancementLevel','conditionState','labelTemplate','modifierOperator'] if k in result})
            if any(a.get('value') is not None for a in effects['entries']):effects['status']='partially_verified_values'
        safe['actualEffects']=effects
        return safe
    if doc['kind']=='overview':
        base.update(defenseState='not_read',towers=[{'code':t['code'],'defendersState':'not_read','defenders':None} for t in doc['towers']])
    elif doc['kind']=='deployed_defense':
        base.update(deploymentState='returned-by-fortress',towers=[])
        for tower in doc['towers']:
            defenders=None if tower['defenders'] is None else []
            for defender in tower['defenders'] or []:
                safe={'memberAlias':alias(encoded([doc['guildId'],defender['playerId']])),
                      **{k:defender[k] for k in ['playerName','retrievedAt','isAI','withdrawal']},'teams':[]}
                for team in defender['teams']:
                    units=[]
                    for unit in team['units']:
                        gear={slot:safe_gear(e,defender['playerId'],tower['code'],team,unit,slot) for slot,e in unit['equipment'].items()}
                        p=match_progress((progress or {}).get(observation_key('guildwar',doc['sourceId'],defender['playerId'],team['teamNo'],unit['position'],tower['code'])),unit['characterId'],defender['playerId'],unit['characterInstanceId'],defender['retrievedAt'])
                        units.append({k:unit[k] for k in ['position','characterId','level']}|{'equipment':gear,'characterProgress':p,'talentProgress':talent_stages((native or {}).get(unit['characterId']),p['talentGrade'] if p else None)})
                    safe['teams'].append({'teamNo':team['teamNo'],'units':units})
                defenders.append(safe)
            base['towers'].append({'code':tower['code'],'readState':tower['readState'],'defenders':defenders})
    elif doc['kind']=='saved_configuration':
        base.update(playerAlias=alias(encoded([doc['guildId'],doc['playerId']])),deploymentState='unconfirmed',configuredTeamNo=doc['configuredTeamNo'],teams=[])
        for team in doc['teams']:
            units=[]
            for unit in team['units']:
                gear={}
                for slot,e in unit['equipment'].items():
                    gear[slot]=safe_gear(e,doc['playerId'],None,team,unit,slot)
                p=match_progress((progress or {}).get(observation_key('guildwar-saved',doc['sourceId'],doc['playerId'],team['teamNo'],unit['position'])),unit['characterId'],doc['playerId'],unit['characterInstanceId'],doc['capturedAt'])
                units.append({k:unit[k] for k in ['position','characterId','level']}|{'equipment':gear,'characterProgress':p,'talentProgress':talent_stages((native or {}).get(unit['characterId']),p['talentGrade'] if p else None)})
            base['teams'].append({'teamNo':team['teamNo'],'units':units})
    else:raise ValueError('unsupported guild-war public record')
    return base


def prepare(database=DEFAULT_DB):
    db=sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro',uri=True)
    try:
        db.execute('BEGIN')
        row=db.execute("SELECT r.payload FROM current_guild_rankings c JOIN guild_rank_sources r USING(snapshot_id) WHERE c.scope='top100'").fetchone()
        if not row:raise ValueError('accepted guild ranking missing')
        ranking=json.loads(row[0]);rosters={gid:json.loads(p) for gid,p in db.execute('SELECT c.guild_id,r.payload FROM current_ranked_guild_rosters c JOIN guild_roster_sources r USING(source_id)')}
        attempts={}
        for gid,part,at,status,reason in db.execute('SELECT guild_id,part,checked_at,status,reason FROM guild_fetch_attempts ORDER BY checked_at'):attempts[(gid,part)]={'checkedAt':at,'status':status,'reason':reason}
        wars=[]
        if db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='guild_war_sources'").fetchone():
            wars=[json.loads(r[0]) for r in db.execute('SELECT s.payload FROM current_guild_war_sources c JOIN guild_war_sources s USING(source_id)')]
        roll_source,rolls=read_rolls(db)
    finally:db.close()
    progress_source,progress=read_progress(database)
    native_source,native=read_native_details(database)
    records=[];private_ids=set();members=0;complete=0
    records.append({'identity':{'scope':'guild-ranking','sourceId':ranking['snapshotId']},'data':{'recordScope':'guild-war-ranking','sourceId':ranking['snapshotId'],'capturedAt':ranking['capturedAt'],'rankRange':[1,100],'guilds':len(ranking['guilds']),'observedTotal':ranking['observedTotal']}})
    for guild in ranking['guilds']:
        gid=guild['guildId'];private_ids.add(gid);roster=rosters.get(gid);public_members=None
        deployed=next((w for w in wars if w['guildId']==gid and w['kind']=='deployed_defense'),None)
        placements={}
        if deployed:
            for tower in deployed['towers']:
                for defender in tower.get('defenders') or []:placements.setdefault(defender['playerId'],[]).append(tower['code'])
        if roster:
            private_ids.update(m['playerId'] for m in roster['members']);members+=len(roster['members']);complete+=int(roster['membershipComplete'])
            public_members=[{'memberAlias':alias(encoded([gid,m['playerId']])),'name':m['name'],'levelRaw':m['level'],'levelDisplayVerified':False,'role':m['role'],
                'guildWarDefense':{'status':'captured','towerCodes':placements[m['playerId']],'sourceId':deployed['sourceId']} if m['playerId'] in placements else {'status':'not_read','teams':None}} for m in roster['members']]
        record={'recordScope':'ranked-guild-roster','guildAlias':alias(gid),**{k:guild[k] for k in ['rank','score','name','gradeId','gradeLabel','level','nationalFlag','memberCount','memberCapacity']},
                'rankingRetrievedAt':guild['retrievedAt'],'rosterRetrievedAt':roster['capturedAt'] if roster else None,
                'membershipComplete':roster['membershipComplete'] if roster else False,'membersRetrieved':len(public_members) if public_members is not None else None,
                'members':public_members,'rosterAttempt':attempts.get((gid,'roster')),
                'guildWarDefense':{'status':deployed['status'],'capturedAt':deployed['capturedAt'],'sourceId':deployed['sourceId']} if deployed else attempts.get((gid,'defense')) or {'status':'not_read','teams':None}}
        records.append({'identity':{'scope':'ranked-guild','guildAlias':alias(gid)},'data':record})
    target_ids={g['guildId'] for g in ranking['guilds']};wars=[w for w in wars if w['guildId'] in target_ids]
    for war in wars:
        private_ids.add(war['guildId'])
        if war.get('playerId'):private_ids.add(war['playerId'])
        for tower in war.get('towers',[]):
            for defender in tower.get('defenders') or []:private_ids.add(defender['playerId'])
        records.append({'identity':{'scope':'guild-war-observation','sourceId':war['sourceId']},'data':public_war_record(war,rolls,progress,native)})
    content=digest(records);sid='guild-top100-'+content[:24];folder=ROOT/'data/research/runtime.private/guild-exports'/sid;folder.mkdir(parents=True,exist_ok=True)
    source=folder/'records.private.json';sha=freeze(source,{'records':records})
    deployments=[w for w in wars if w['kind']=='deployed_defense']
    deployed_players=[d for w in deployments for t in w['towers'] for d in t.get('defenders') or []]
    manifest={'snapshotId':sid,'rankingSnapshotId':ranking['snapshotId'],'guilds':len(ranking['guilds']),'completeRosters':complete,'members':members,'researchRecords':len(records),'guildWarDefenseState':'partial_coverage' if deployments else 'not_read',
              'warOverviewGuilds':sum(w['kind']=='overview' for w in wars),'savedWarConfigurations':sum(w['kind']=='saved_configuration' for w in wars),
              'savedConfigurationUnits':sum(len(t['units']) for w in wars for t in w.get('teams',[])),
              'completeDefenseGuilds':sum(w['status']=='success' for w in deployments),'deployedDefenseTeams':sum(len(d['teams']) for d in deployed_players),
              'deployedUnits':sum(len(t['units']) for d in deployed_players for t in d['teams']),
              'nativeGearReconstructionSourceId':roll_source,'characterInstanceProgressSourceId':progress_source,'nativeCharacterEnrichmentSourceId':native_source,
              'credentialsOrRawMemoryIncluded':False,'nativeIdentifiersAnonymized':True}
    manifest_sha=freeze(folder/'manifest.private.json',manifest);rows=[]
    for index,record in enumerate(records):
        row={'snapshot_id':sid,'module':'guild','source_record_identity':record['identity'],'source_file':source.relative_to(ROOT).as_posix(),'source_file_sha256':sha,'source_record_locator':f'$.records[{index}]','raw_record':{'recordScope':record['data']['recordScope'],'sanitizedExportSha256':sha},'normalized_record':record['data'],'validation_status':'source-record-verified','parse_warnings':[]}
        row['record_sha256']=digest(row);rows.append(row)
    plan={'snapshot':{'snapshot_id':sid,'module':'guild','source_kind':'dynamic','source_version':'normal-guild-top100-war-v2','captured_at':max([ranking['capturedAt']]+[r['capturedAt'] for gid,r in rosters.items() if gid in target_ids]+[w['capturedAt'] for w in wars]),'source_manifest_sha256':manifest_sha,'content_sha256':digest(rows),'record_count':len(rows),'source_metadata':{**manifest,'draftOnly':True,'wholeGameCoverageConfirmed':False},'expected_counts':{'research_records':len(rows)},'is_complete':False,'status':'draft'},'researchRows':rows,'equipmentRows':[],'uploadBatchSize':20}
    def values(v):
        if isinstance(v,dict):return [x for item in v.values() for x in values(item)]
        if isinstance(v,list):return [x for item in v for x in values(item)]
        return [v] if isinstance(v,str) else []
    if private_ids.intersection(values(plan)):raise ValueError('native identity leaked into guild export')
    freeze(folder/'supabase-upload.private.json',plan);return folder,plan,manifest


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--apply',action='store_true');args=p.parse_args();folder,plan,manifest=prepare()
    if not args.apply:print(json.dumps({'prepared':True,**manifest}))
    else:
        try:receipt=upload(plan,existing_service_client(),existing_anon_client())
        except (SupabaseApiError,ImportInputError,ValueError):
            print(json.dumps({'uploaded':False,'reason':'remote_connection_or_readback_failed','localDataPreserved':True}));raise SystemExit(1)
        (folder/'supabase-receipt.private.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf8')
        (ROOT/'reports/guild-top100-supabase-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf8');print(json.dumps(receipt))
