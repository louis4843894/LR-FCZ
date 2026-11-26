"""Validate actual team observations and export only supported private local fields.
No fetching, authentication, templates promoted to instances, or fixture auto-import.
"""
import argparse,dataclasses,hashlib,json,tempfile,math,re
from pathlib import Path
from data_contracts import (TeamSnapshot,TeamMember,GuildMembership,TeamPurpose,RetrievalStatus,
    ValueState,EquipmentSlot,EquipmentState,EquipmentReference,validate_guild_team_links,validate_unique_source_records)
ROOT=Path(__file__).resolve().parents[1]
MAX_BYTES=2*1024*1024

def observed_equipment(source):
    extra={'enhancement':None,'instanceGrade':None,'equipmentInstanceIdentity':None,'actualEffects':None,'ownerAssociationStatus':source.get('ownerAssociationStatus','unknown')}
    if extra['ownerAssociationStatus'] not in ('verified-native','unknown'):raise ValueError('unknown equipment owner association status')
    evidence=source.get('fieldEvidence',{})
    for key in ['enhancement','instanceGrade']:
        value=source.get(key)
        if value is not None:
            if source.get('state')!='equipped' or type(value) is not int or not 0<=value<=0xffffffff or not isinstance(evidence.get(key),str) or not evidence[key]:raise ValueError('unverified equipment '+key)
            extra[key]=value
    identity=source.get('equipmentInstanceIdentity')
    if identity is not None:
        if source.get('state')!='equipped' or not isinstance(identity,dict) or any(not isinstance(identity.get(k),str) or not identity[k] for k in ['value','sourceField','namespace']) or not evidence.get('equipmentInstanceIdentity'):raise ValueError('unverified equipment instance identity')
        extra['equipmentInstanceIdentity']={k:identity[k] for k in ['value','sourceField','namespace']}
    effects=source.get('actualEffects')
    if effects is not None:
        if source.get('state')!='equipped' or not isinstance(effects,dict) or effects.get('status') not in ('identifiers_only','partial_values') or not evidence.get('actualEffects'):raise ValueError('unverified actual effects')
        partial=effects['status']=='partial_values'
        if partial and (not evidence.get('actualEffectValues') or effects.get('valueMethod')!='native-ordinary-gearstat-v1' or effects.get('valueModuleSha256')!='1185e119efeb6a67d30d289f8a183b36aebe53126a4765698509cd7a822a42a0'):raise ValueError('unverified native attribute value method')
        entries=effects.get('entries')
        if not isinstance(entries,list) or not 1<=len(entries)<=16:raise ValueError('invalid actual attribute bounds')
        safe=[]
        for i,e in enumerate(entries):
            if e.get('index')!=i or any(type(e.get(k)) is not int or not 0<=e[k]<=0xffffffff for k in ['attributeId','valueGradeRaw']):raise ValueError('invalid actual attribute identifiers')
            # The verified HTTP response exposes attrNo/valueGrade, but does not
            # expose GearStat's native type enum. Preserve that field as unknown.
            kind=e.get('attributeTypeRaw')
            if kind is not None and (type(kind) is not int or not 0<=kind<=0xffffffff):raise ValueError('invalid actual attribute type')
            row={k:e[k] for k in ['index','attributeId','valueGradeRaw','attributeTypeRaw']}
            if isinstance(e.get('sourceField'),str):row['sourceField']=e['sourceField']
            row.update(value=None,unit=None,valueVerified=False,enhancementIncluded=False,valueVisuallyVerified=False)
            if partial:
                row.update(attributeCode=e.get('attributeCode') if isinstance(e.get('attributeCode'),str) else None,attributeLabel=e.get('attributeLabel') if isinstance(e.get('attributeLabel'),str) else None)
                if e.get('value') is not None:
                    value=e['value'];proof=e.get('valueEvidence',{})
                    if type(e.get('attributeTypeRaw')) is not int or not 1<=e['attributeTypeRaw']<=45:raise ValueError('numeric attribute requires a verified native type')
                    if type(value) not in (int,float) or not math.isfinite(value) or e.get('unit') not in ('PERCENT','FLAT') or e.get('enhancementIncluded') is not True:raise ValueError('invalid native attribute value/unit')
                    if proof.get('method')!='native-ordinary-gearstat-v1' or proof.get('moduleSha256')!=effects['valueModuleSha256'] or proof.get('enhancement')!=extra['enhancement'] or proof.get('attributeId')!=e['attributeId'] or proof.get('attributeTypeRaw')!=e['attributeTypeRaw'] or any(not re.fullmatch('[a-f0-9]{64}',str(proof.get(k,''))) for k in ['attributeSha256','factorSha256','uiReviewSha256']):raise ValueError('native attribute value evidence mismatch')
                    row.update(value=value,unit=e['unit'],valueVerified=True,enhancementIncluded=True,valueVisuallyVerified=e.get('valueVisuallyVerified') is True)
            safe.append(row)
        extra['actualEffects']={'status':effects['status'],'entries':safe,'numericalValuesVerified':False,'verifiedValueCount':sum(e['valueVerified'] for e in safe),'valueFactorRetrievedAt':effects.get('valueFactorRetrievedAt') if partial else None}
    extra['attributeReadState']=source.get('attributeReadState','not_captured')
    if extra['attributeReadState'] not in ('not_captured','captured','read_failed','empty_observed_semantics_unknown'):raise ValueError('invalid attribute read state')
    return extra

def normalize(doc,source_sha):
    if doc.get('schemaVersion')!=1 or doc.get('recordScope')!='player-team-observations':raise ValueError('expected observed player-team schema v1')
    source_id=doc.get('sourceId')
    if not isinstance(source_id,str) or not source_id.strip() or len(source_id)>200:raise ValueError('sourceId is required')
    raw_teams=doc.get('snapshots',[]);raw_memberships=doc.get('memberships',[])
    if not isinstance(raw_teams,list) or not isinstance(raw_memberships,list) or max(len(raw_teams),len(raw_memberships))>1000:raise ValueError('observation bounds exceeded')
    teams=[];memberships=[]
    for r in raw_memberships:
        memberships.append(GuildMembership(r['snapshotId'],r['guildId'],r['playerId'],r['observedAt'],r['sourceRecordIdentity']))
    for r in raw_teams:
        raw_members=r.get('members');members=None
        if r['status']=='success' and (not isinstance(r.get('teamId'),str) or not r['teamId'].strip()):raise ValueError('successful observation requires the actual team identifier')
        if raw_members is not None:
            if not isinstance(raw_members,list) or len(raw_members)>20:raise ValueError('team member bound exceeded')
            for m in raw_members:
                if m['characterState']=='present':
                    identity=m.get('characterInstanceIdentity')
                    if not isinstance(identity,dict) or any(not isinstance(identity.get(k),str) or not identity[k].strip() for k in ['value','sourceField','namespace']):raise ValueError('present character requires an observed instance identity and its source namespace')
            members=tuple(TeamMember(r['snapshotId'],r['playerId'],m['memberIndex'],ValueState(m['characterState']),m.get('characterId'),
                {EquipmentSlot(slot):EquipmentReference(EquipmentState(e['state']),e.get('equipmentId')) for slot,e in m['equipment'].items()}) for m in raw_members)
        missing=r.get('unobservedPositionIndices')
        if missing is not None and (not isinstance(missing,list) or any(type(n) is not int or not 0<=n<100 for n in missing) or len(set(missing))!=len(missing) or (raw_members and set(missing)&{m['memberIndex'] for m in raw_members})):raise ValueError('invalid unobserved position indices')
        teams.append(TeamSnapshot(r['snapshotId'],r['playerId'],TeamPurpose(r['purpose']),r['retrievedAt'],RetrievalStatus(r['status']),members,r.get('guildId'),r.get('membershipSnapshotId')))
    validate_guild_team_links(memberships,teams)
    validate_unique_source_records((source_id,t.snapshot_id) for t in teams)
    rows=[]
    for t,source_row in zip(teams,raw_teams):
        rows.append({'snapshotId':t.snapshot_id,'sourceId':source_id,'sourceSha256':source_sha,'playerId':t.player_id,'purpose':t.purpose.value,'retrievedAt':t.retrieved_at,'status':t.status.value,
            'playerDisplayName':source_row.get('playerDisplayName') if isinstance(source_row.get('playerDisplayName'),str) and len(source_row['playerDisplayName'])<=100 else None,
            'teamId':source_row.get('teamId'),'guildId':t.guild_id,'membershipSnapshotId':t.membership_snapshot_id,
            'isSelected':source_row.get('isSelected') if type(source_row.get('isSelected')) is bool else None,
            'unobservedPositionIndices':source_row.get('unobservedPositionIndices'),
            'gameVersion':source_row.get('gameVersion') if isinstance(source_row.get('gameVersion'),str) else None,
            'verification':{k:source_row['verification'].get(k) for k in ['checkedAt','method','purposeConfirmed','visibleRangerCount','selectedTeamNo','equipmentValuesVisuallyVerified']} if isinstance(source_row.get('verification'),dict) else None,
            'members':None if t.members is None else [{'memberIndex':m.member_index,'characterState':m.character_state.value,'characterId':m.character_id,
                'characterInstanceIdentity':None if m.character_state is not ValueState.PRESENT else {k:raw_member['characterInstanceIdentity'][k] for k in ['value','sourceField','namespace']},
                'identityOwnerPlayerId':t.player_id,
                'equipment':{slot.value:{'state':e.state.value,'equipmentId':e.equipment_id,**observed_equipment(raw_member['equipment'][slot.value])} for slot,e in m.equipment.items()}} for m,raw_member in zip(t.members,source_row['members'])]})
    return {'schemaVersion':1,'normalizerVersion':'defense-import-v4-partial-values','sourceKind':'validated-player-team-snapshots','recordScope':'player-team','sourceId':source_id,'sourceSha256':source_sha,
            'snapshots':rows,'memberships':[dataclasses.asdict(m) for m in memberships],'counts':{'snapshots':len(rows),'successful':sum(t.status is RetrievalStatus.SUCCESS for t in teams),'failedOrUnavailable':sum(t.status is not RetrievalStatus.SUCCESS for t in teams)}}

def import_many(sources,output):
    """Validate bounded per-player inputs, then write the combined version once."""
    results=[]
    for source in sources:
        raw=source.read_bytes()
        if len(raw)>MAX_BYTES:raise ValueError('source exceeds 2MB limit')
        results.append(normalize(json.loads(raw),hashlib.sha256(raw).hexdigest()))
    if not results:raise ValueError('no observation sources')
    result=results[-1]
    result['snapshots']=[row for doc in results for row in doc['snapshots']]
    result['memberships']=[row for doc in results for row in doc['memberships']]
    if output.exists():
        previous=json.loads(output.read_text(encoding='utf8'))
        if previous.get('sourceKind')!='validated-player-team-snapshots':raise ValueError('existing output has an unexpected source kind; preserve it')
        # Keep previous successes and unrelated members when importing a partial
        # batch. A newer failed attempt remains a failure, not an empty team.
        key=lambda r:(r.get('guildId'),r['playerId'],r['purpose'],r.get('teamId'),r['snapshotId'])
        rows={key(r):r for r in previous['snapshots']}
        rows.update({key(r):r for r in result['snapshots']})
        result['snapshots']=list(rows.values())
        member_key=lambda r:(r['guild_id'],r['player_id'],r['snapshot_id'])
        memberships={member_key(r):r for r in previous.get('memberships',[])}
        memberships.update({member_key(r):r for r in result['memberships']});result['memberships']=list(memberships.values())
    result['counts']={'snapshots':len(result['snapshots']),'successful':sum(r['status']=='success' for r in result['snapshots']),'failedOrUnavailable':sum(r['status']!='success' for r in result['snapshots'])}
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w',encoding='utf8',dir=output.parent,suffix='.tmp',delete=False) as f:
        temporary=Path(f.name);json.dump(result,f,ensure_ascii=False,separators=(',',':'),allow_nan=False);f.write('\n')
    try:temporary.replace(output)
    finally:temporary.unlink(missing_ok=True)
    return result

def import_file(source,output):return import_many([source],output)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,default=ROOT/'data/normalized/defense-teams.private.json');a=p.parse_args()
    print(json.dumps(import_file(a.input,a.output)['counts']))
