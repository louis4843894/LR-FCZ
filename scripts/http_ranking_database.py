"""Immutable HTTP source cache and one-write normalized ranking import."""
import hashlib,json,sqlite3
from datetime import datetime,timezone
from pathlib import Path
from local_game_database import ROOT,DEFAULT_DB,encoded,stamp,sync_database
from ranking_database import connection,load_snapshot,private_directory
from parse_http_defense import parse_response
from import_defense_teams import import_many

SCHEMA='''CREATE TABLE IF NOT EXISTS pvp_http_sources (
 capture_id TEXT PRIMARY KEY, ranking_snapshot_id TEXT NOT NULL REFERENCES ranking_snapshots(snapshot_id),
 player_id TEXT NOT NULL, captured_at TEXT NOT NULL, source_sha256 TEXT NOT NULL,
 private_directory TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS pvp_http_cache ON pvp_http_sources(ranking_snapshot_id,player_id,captured_at);
CREATE TABLE IF NOT EXISTS pvp_http_checks (
 capture_id TEXT PRIMARY KEY REFERENCES pvp_http_sources(capture_id), checked_at TEXT NOT NULL
);'''


def connect(database=DEFAULT_DB):
    db=connection(database);db.executescript(SCHEMA);return db


def remember(directory,database=DEFAULT_DB):
    directory=private_directory(directory);raw=(directory/'response.private.json').read_bytes();meta=json.loads(raw)
    ranking=load_snapshot(meta['rankingSnapshotId'],database)
    uid=meta['result']['player']['uid']
    if (ranking['sourceCaptureSha256']!=meta['rankingSourceCaptureSha256']
            or not any(p['playerId']==uid and p['rank']==meta['rank'] for p in ranking['players'])):raise ValueError('HTTP source owner/rank differs')
    parse_response(directory) # Reject malformed/owner-conflicting branches before caching.
    sha=hashlib.sha256(raw).hexdigest();row=(directory.name,ranking['snapshotId'],uid,meta['capturedAt'],sha,directory.relative_to(ROOT).as_posix())
    db=connect(database)
    try:
        with db:
            old=db.execute('SELECT * FROM pvp_http_sources WHERE capture_id=?',(directory.name,)).fetchone()
            if old and tuple(old)!=row:raise ValueError('immutable HTTP source differs')
            db.execute('INSERT OR IGNORE INTO pvp_http_sources VALUES (?,?,?,?,?,?)',row)
    finally:db.close()
    return directory


def checked(directory,checked_at,database=DEFAULT_DB):
    datetime.fromisoformat(checked_at)
    db=connect(database)
    try:
        with db:
            db.execute('INSERT INTO pvp_http_checks VALUES (?,?) ON CONFLICT(capture_id) DO UPDATE SET checked_at=max(checked_at,excluded.checked_at)',(directory.name,checked_at))
            source=db.execute('SELECT ranking_snapshot_id,player_id,source_sha256 FROM pvp_http_sources WHERE capture_id=?',(directory.name,)).fetchone()
            if not source:raise ValueError('checked source is not accepted')
            sid,uid,sha=source
            latest=db.execute('SELECT status FROM ranking_defense_attempts WHERE ranking_snapshot_id=? AND player_id=? ORDER BY attempted_at DESC LIMIT 1',(sid,uid)).fetchone()
            if latest and latest[0]=='failed':
                for payload, in db.execute("SELECT payload FROM ranking_defense_attempts WHERE ranking_snapshot_id=? AND player_id=? AND status IN ('success','partial','unavailable') ORDER BY attempted_at DESC",(sid,uid)):
                    previous=json.loads(payload)
                    if previous.get('captureSha256')!=sha:continue
                    previous['attemptedAt']=checked_at
                    identity=hashlib.sha256(encoded([sid,uid,sha,checked_at,'confirmed-unchanged']).encode()).hexdigest()
                    db.execute('INSERT OR IGNORE INTO ranking_defense_attempts VALUES (?,?,?,?,?,?)',(identity,sid,uid,checked_at,previous['status'],encoded(previous)))
                    break
    finally:db.close()


def recent(snapshot_id,age_seconds,database=DEFAULT_DB,*,player_ids=None,for_comparison=False):
    members={p['playerId'] for p in load_snapshot(snapshot_id,database)['players']}
    if player_ids is not None:members.intersection_update(player_ids)
    db=connect(database);result={};now=datetime.now(timezone.utc)
    try:
        # A later failed read follows the owner across ranking versions. An
        # older successful copy is eligible only for a real response comparison,
        # never as a fresh accepted cache merely because the ranking ID changed.
        failures=dict(db.execute("SELECT player_id,max(attempted_at) FROM ranking_defense_attempts WHERE status='failed' GROUP BY player_id"))
        for uid,at,sha,path in db.execute('SELECT s.player_id,coalesce(c.checked_at,s.captured_at),s.source_sha256,s.private_directory FROM pvp_http_sources s LEFT JOIN pvp_http_checks c USING(capture_id) ORDER BY s.captured_at'):
            if uid not in members:continue
            age=(now-datetime.fromisoformat(at)).total_seconds()
            if not for_comparison and uid in failures and datetime.fromisoformat(at)<=datetime.fromisoformat(failures[uid]):continue
            directory=private_directory(ROOT/path);file=directory/'response.private.json'
            if 0<=age and (age_seconds is None or age<=age_seconds) and file.exists() and hashlib.sha256(file.read_bytes()).hexdigest()==sha:result[uid]=directory
    finally:db.close()
    return result


def save_batch(snapshot_id,directories,database=DEFAULT_DB):
    ranking=load_snapshot(snapshot_id,database);sources=[];attempts=[]
    normalized=ROOT/'data/normalized/defense-teams.private.json'
    db=connect(database)
    try:
        existing=set(db.execute("SELECT player_id,snapshot_id FROM defense_snapshots WHERE document_sha256=(SELECT sha256 FROM current_documents WHERE filename='defense-teams.private.json')"))
        cached={name:(uid,sha) for name,uid,sha in db.execute('SELECT capture_id,player_id,source_sha256 FROM pvp_http_sources')}
        accepted={};latest_target={}
        for sid,uid,payload in db.execute('SELECT ranking_snapshot_id,player_id,payload FROM ranking_defense_attempts ORDER BY attempted_at'):
            row=json.loads(payload)
            if sid==snapshot_id:latest_target[uid]=row
            if row['status'] in ('success','partial','unavailable') and row.get('cacheState')=='normal-native-http-response':
                accepted[(uid,row['captureSha256'])]=row
        checked_times={path:at for path,at in db.execute('SELECT s.private_directory,c.checked_at FROM pvp_http_checks c JOIN pvp_http_sources s USING(capture_id)')}
    finally:db.close()
    reused=0
    target_members={p['playerId'] for p in ranking['players']}
    for directory in directories:
        directory=private_directory(directory)
        sha=hashlib.sha256((directory/'response.private.json').read_bytes()).hexdigest()
        owner=cached.get(directory.name)
        if owner and owner[0] not in target_members:raise ValueError('cached HTTP owner is outside target ranking')
        prior=accepted.get((owner[0],sha)) if owner and owner[1]==sha else None
        if prior and all((owner[0],sid) in existing for sid in prior['defenseSnapshotIds']):
            # The exact source bytes, accepted parser result and active snapshot
            # keys still match. Do not reparse/rewrite already-validated copies.
            uid=owner[0];current=latest_target.get(uid);verified_at=checked_times.get(prior['captureDirectory'])
            recovered=bool(current and current['status']=='failed' and verified_at and datetime.fromisoformat(verified_at)>datetime.fromisoformat(current['attemptedAt']))
            if current and current['status']=='failed' and not recovered:
                raise ValueError('failed target needs a newer successful source check')
            if current is None or current.get('captureSha256')!=sha or recovered:
                payload={**prior,'attemptedAt':stamp()}
                identity=hashlib.sha256(encoded([snapshot_id,uid,sha,verified_at if recovered else None]).encode()).hexdigest()
                attempts.append((identity,snapshot_id,uid,payload['attemptedAt'],payload['status'],encoded(payload)))
            reused+=1;continue
        directory=remember(directory,database)
        meta=json.loads((directory/'response.private.json').read_bytes());doc=parse_response(directory)
        uid=meta['result']['player']['uid'];ids=[t['snapshotId'] for t in doc['snapshots']]
        if not any(p['playerId']==uid for p in ranking['players']):raise ValueError('HTTP defense owner is outside target ranking')
        source=directory/'observations.private.json'
        if ids and not all((uid,sid) in existing for sid in ids):
            source.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf8');sources.append(source)
        state=doc['captureEvidence']['teamReadState']
        status='unavailable' if not ids else 'partial' if state!='returned' or any(t['unobservedPositionIndices'] for t in doc['snapshots']) else 'success'
        payload={'status':status,
                 'attemptedAt':stamp(),'failureReason':'normal_response_no_team_records' if not ids else None,'defenseRetrievedAt':meta['capturedAt'],'defenseSnapshotIds':ids,
                 'sourceRankingSnapshotId':meta['rankingSnapshotId'],'cacheState':'normal-native-http-response',
                 'captureDirectory':directory.relative_to(ROOT).as_posix(),'captureSha256':hashlib.sha256((directory/'response.private.json').read_bytes()).hexdigest(),
                 'identityMatch':'exact-native-uid','teams':len(ids),
                 'selectedTeamId':next((t['teamId'] for t in doc['snapshots'] if t['isSelected']),None)}
        identity=hashlib.sha256(encoded([snapshot_id,uid,payload['captureSha256']]).encode()).hexdigest()
        attempts.append((identity,snapshot_id,uid,payload['attemptedAt'],payload['status'],encoded(payload)))
    if sources:
        import_many(sources,normalized)
        # Transactions, field validation and source checks still run. A full
        # historical-database quick_check belongs to delivery, not every league.
        sync_database(database=database,modules=['pvp'],verify_integrity=False)
    db=connect(database)
    try:
        with db:db.executemany('INSERT OR IGNORE INTO ranking_defense_attempts VALUES (?,?,?,?,?,?)',attempts)
    finally:db.close()
    return {'acceptedPlayers':len(directories),'acceptedCopiesReused':reused,'newSourceImports':len(sources),'normalizedWrites':1 if sources else 0}
