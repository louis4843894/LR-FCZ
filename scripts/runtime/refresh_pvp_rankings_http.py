"""Refresh the proven normal league ranking request; never guesses league codes.

0174d004 -> 01750af0 -> /pvp/league/rank/%s; response 01750c2c reads
result.pvpLeaguePhase / result.league.rankingList, then 0175113c/00fc4d78.
Credentials stay in the existing in-memory session. Partial responses cannot
replace a previously accepted complete source.
"""
import argparse,hashlib,json,sqlite3,time,uuid,math
from datetime import datetime,timezone
from pathlib import Path
from pvp_session import Reader,NEW_SHA,ROOT,load_session
from fetch_ranked_pvp_response import normal_json,AcquisitionStopped
from pvp_league_codes import OUTPUT as PHASE_CODES,verified_mappings
from pvp_scope_policy import canonical_scope,matches_scope,CLI_SCOPES
from ranking_database import connection
from local_game_database import encoded

KIND='verified-normal-pvp-league-ranking'
SCHEMA='''CREATE TABLE IF NOT EXISTS pvp_ranking_checks (
 snapshot_id TEXT NOT NULL REFERENCES ranking_snapshots(snapshot_id), checked_at TEXT NOT NULL,
 source_directory TEXT NOT NULL, source_sha256 TEXT NOT NULL,
 PRIMARY KEY(snapshot_id,checked_at)
);'''


def native_integer(value):
    # 00fc4d78 uses 01a15bfc (integral JSON number predicate), followed by
    # 01a15244 (signed 32-bit conversion). Scores arrive as e.g. 199.0.
    if type(value) not in (int,float) or not math.isfinite(value) or int(value)!=value or not -0x80000000<=value<=0x7fffffff:
        raise ValueError('nonintegral or out-of-range native ranking number')
    return int(value)


def parse_source(directory):
    directory=Path(directory).resolve()
    if not directory.is_relative_to((ROOT/'data/research/runtime.private').resolve()):raise ValueError('ranking response must remain private')
    source=directory/'ranking-response.private.json';raw=source.read_bytes();meta=json.loads(raw)
    proof=json.loads(PHASE_CODES.read_bytes())
    mapping=next((m for m in proof['mappings'] if canonical_scope(m['label'])==canonical_scope(meta['scopeLabel']) and m['phaseCode']==meta['phaseCode']),None)
    if not mapping or proof['moduleSha256']!=NEW_SHA or meta['moduleSha256']!=NEW_SHA:raise ValueError('unverified league-code mapping')
    result=meta['result']
    if result['pvpLeaguePhase']!=mapping['phaseCode']:raise ValueError('response league differs from the normal request')
    rows=result['league']['rankingList']
    if not isinstance(rows,list) or len(rows)>256:raise ValueError('ranking response bounds')
    players=[];uids=set();ranks=set();failed=0
    for index,row in enumerate(rows):
        uid=row.get('uid')
        try:rank=native_integer(row.get('rank'));score=native_integer(row.get('score'))
        except ValueError:failed+=1;continue
        if (not isinstance(uid,str) or not 1<=len(uid)<=256 or '\0' in uid or uid in uids
                or type(rank) is not int or not 1<=rank<=10000 or rank in ranks
                or type(score) is not int or not 0<=score<=0x7fffffff):
            failed+=1;continue
        name=row.get('displayName');phase=row.get('leaguePhase')
        if name is not None and (not isinstance(name,str) or len(name)>100):failed+=1;continue
        if phase is not None and (not isinstance(phase,str) or len(phase)>100):failed+=1;continue
        uids.add(uid);ranks.add(rank)
        players.append({'playerId':uid,'rank':rank,'score':score,'displayName':name,'leaguePhase':phase,
                        'retrievedAt':meta['capturedAt'],'sourceRowIndex':index,
                        'sourceRecordSha256':hashlib.sha256(encoded(row).encode()).hexdigest(),
                        'defenseState':'not_read','defenseSnapshotIds':[],'defenseRetrievedAt':None,'failureReason':None})
    players.sort(key=lambda p:p['rank'])
    minimum=mapping.get('minimumPlayers',mapping.get('count'))
    identity={'phase':mapping['phaseCode'],'loadedCount':len(rows),'failedRows':failed,
              'expectedMinimumPlayers':minimum,
              'players':[{k:p[k] for k in ['playerId','rank','score','displayName','leaguePhase']} for p in players]}
    content=hashlib.sha256(encoded(identity).encode()).hexdigest()
    complete=not failed and len(players)>=minimum and ranks==set(range(1,len(players)+1))
    return {'schemaVersion':1,'sourceKind':KIND,'parserVersion':'normal-pvp-league-ranking-v1',
            'snapshotId':'pvp-ranking-http-'+content[:24],'contentIdentitySha256':content,
            'capturedAt':meta['capturedAt'],'gameVersion':'12.4.2','moduleSha256':NEW_SHA,
            'sourceCaptureSha256':hashlib.sha256(raw).hexdigest(),'sourceDirectory':directory.relative_to(ROOT).as_posix(),
            'scope':{'kind':'normal-pvp-league-ranking-response','label':mapping['label'],'phaseCode':mapping['phaseCode'],'wholeRankingComplete':False},
            'rankRange':{'minimum':min(ranks) if ranks else None,'maximum':max(ranks) if ranks else None},
            'loadedCount':len(rows),'retrievedPlayerCount':len(players),'loadedArrayFullyCaptured':True,
            'status':'success' if complete else 'partial','failedRowCount':failed,'players':players}


def accept(directory,database=None,*,activate=True):
    directory=Path(directory).resolve()
    from local_game_database import DEFAULT_DB
    db=connection(database or DEFAULT_DB);db.executescript(SCHEMA);doc=parse_source(directory)
    try:
        with db:
            row=db.execute('SELECT payload FROM ranking_snapshots WHERE snapshot_id=?',(doc['snapshotId'],)).fetchone()
            if row:
                previous=json.loads(row[0])
                if previous.get('contentIdentitySha256')!=doc['contentIdentitySha256']:raise ValueError('immutable ranking content differs')
            else:
                db.execute('INSERT INTO ranking_snapshots VALUES (?,?,?,?,?,?)',(doc['snapshotId'],doc['scope']['label'],doc['capturedAt'],doc['status'],doc['sourceCaptureSha256'],encoded(doc)))
            db.execute('INSERT OR IGNORE INTO pvp_ranking_checks VALUES (?,?,?,?)',(doc['snapshotId'],doc['capturedAt'],directory.relative_to(ROOT).as_posix(),doc['sourceCaptureSha256']))
            if activate and doc['status']=='success':
                db.execute('INSERT INTO current_rankings VALUES (?,?) ON CONFLICT(scope_label) DO UPDATE SET snapshot_id=excluded.snapshot_id',(doc['scope']['label'],doc['snapshotId']))
    finally:db.close()
    return doc


def refresh(session,scope,*,apply=False,activate=True):
    proof=json.loads(PHASE_CODES.read_bytes())
    mappings=[m for m in verified_mappings() if matches_scope(m['label'],scope)]
    if proof['moduleSha256']!=NEW_SHA or not mappings:raise ValueError('verified ranking scope missing')
    results=[];next_request=0.0
    for mapping in mappings:
        delay=max(0,next_request-time.monotonic())
        if delay:time.sleep(delay)
        next_request=time.monotonic()+.5
        started=time.monotonic();payload,doc=normal_json(session,'/pvp/league/rank/'+mapping['phaseCode'])
        result=doc.get('result') if isinstance(doc,dict) else None
        if (not isinstance(result,dict) or result.get('pvpLeaguePhase')!=mapping['phaseCode']
                or not isinstance(result.get('league'),dict) or not isinstance(result['league'].get('rankingList'),list)):
            raise AcquisitionStopped('normal_ranking_shape_differs')
        rows=result['league']['rankingList']
        # Whitelist only the exact public ranking fields consumed by 00fc4d78.
        selected=[{k:r[k] for k in ['uid','rank','score','displayName','leaguePhase'] if k in r} for r in rows if isinstance(r,dict)]
        if len(selected)!=len(rows):raise AcquisitionStopped('normal_ranking_row_shape_differs')
        data={'sourceKind':'normal-pvp-ranking-response-copy','moduleSha256':NEW_SHA,'scopeLabel':mapping['label'],
              'phaseCode':mapping['phaseCode'],'capturedAt':datetime.now(timezone.utc).isoformat(),
              'responseSha256':hashlib.sha256(payload).hexdigest(),
              'result':{'pvpLeaguePhase':result['pvpLeaguePhase'],'league':{'rankingList':selected}}}
        directory=ROOT/'data/research/runtime.private'/('pvp-ranking-http-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:6]);directory.mkdir()
        (directory/'ranking-response.private.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        parsed=accept(directory,activate=activate) if apply else parse_source(directory)
        (directory/'rankings.private.json').write_text(json.dumps(parsed,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        results.append({'scope':mapping['label'],'players':len(parsed['players']),'status':parsed['status'],
                        'snapshotId':parsed['snapshotId'],'acceptedAsCurrent':apply and activate and parsed['status']=='success',
                        'seconds':round(time.monotonic()-started,3),'privateCopy':directory.name,'credentialsPersisted':False})
    return results


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--scope',choices=CLI_SCOPES,default='all')
    parser.add_argument('--apply',action='store_true');parser.add_argument('--use-authorized-runtime-session',action='store_true');args=parser.parse_args()
    if not args.use_authorized_runtime_session:parser.error('explicit session authorization required')
    try:
        with Reader(r'C:\LDPlayer\LDPlayer9\adb.exe','emulator-5554',120) as reader:
            reader.expected_module_sha=NEW_SHA;reader.refresh();session=load_session(reader,authorized=True)
        print(json.dumps(refresh(session,args.scope,apply=args.apply),ensure_ascii=True))
    except (ValueError,AcquisitionStopped) as error:
        print(json.dumps({'rankingRefreshed':False,'stopReason':str(error),'credentialsPersisted':False}));raise SystemExit(1)
    except Exception as error:
        print(json.dumps({'rankingRefreshed':False,'stopReason':'context_or_transport_failure','errorType':type(error).__name__,'credentialsPersisted':False}));raise SystemExit(1)
