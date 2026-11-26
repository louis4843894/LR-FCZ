"""Private, versioned ranking sources and independently resumable defense attempts."""
import hashlib,json,re,sqlite3
from datetime import datetime
from pathlib import Path
from local_game_database import ROOT,DEFAULT_DB,connect,encoded,stamp,sync_database
from parse_runtime_rankings import parse_capture as parse_rankings
from parse_runtime_defense import parse_capture as parse_defense
from import_defense_teams import import_file

PRIVATE_ROOT=(ROOT/'data/research/runtime.private').resolve()

SCHEMA='''
CREATE TABLE IF NOT EXISTS ranking_snapshots (
 snapshot_id TEXT PRIMARY KEY, scope_label TEXT NOT NULL, captured_at TEXT NOT NULL,
 status TEXT NOT NULL, source_capture_sha256 TEXT NOT NULL,
 payload TEXT NOT NULL CHECK(json_valid(payload))
);
CREATE TABLE IF NOT EXISTS current_rankings (
 scope_label TEXT PRIMARY KEY, snapshot_id TEXT NOT NULL REFERENCES ranking_snapshots(snapshot_id)
);
CREATE TABLE IF NOT EXISTS ranking_defense_attempts (
 attempt_id TEXT PRIMARY KEY, ranking_snapshot_id TEXT NOT NULL REFERENCES ranking_snapshots(snapshot_id),
 player_id TEXT NOT NULL, attempted_at TEXT NOT NULL, status TEXT NOT NULL,
 payload TEXT NOT NULL CHECK(json_valid(payload))
);
CREATE INDEX IF NOT EXISTS ranking_attempt_owner ON ranking_defense_attempts(ranking_snapshot_id,player_id,attempted_at);
'''


def connection(database=DEFAULT_DB):
    db=connect(database);db.executescript(SCHEMA);return db


def private_directory(path):
    path=Path(path).resolve()
    if not path.is_relative_to(PRIVATE_ROOT):
        raise ValueError('ranking sources must remain private')
    return path


def save_snapshot(directory,database=DEFAULT_DB):
    directory=private_directory(directory);doc=parse_rankings(directory)
    review=json.loads((directory/'screen-observation.private.json').read_text(encoding='utf8'))
    if (review.get('sourceCaptureSha256')!=doc['sourceCaptureSha256'] or review.get('scopeLabel')!=doc['scope']['label']
            or review.get('purpose')!='pvp-ranking' or review.get('screenSha256')!=hashlib.sha256((directory/'screen.private.png').read_bytes()).hexdigest()):
        raise ValueError('ranking scope screen evidence differs')
    if not doc['scope']['label']:raise ValueError('visible ranking scope label is required')
    payload=encoded(doc);db=connection(database)
    try:
        with db:
            previous=db.execute('SELECT payload FROM ranking_snapshots WHERE snapshot_id=?',(doc['snapshotId'],)).fetchone()
            if previous and previous[0]!=payload:raise ValueError('immutable ranking source differs')
            db.execute('INSERT OR IGNORE INTO ranking_snapshots VALUES (?,?,?,?,?,?)',(doc['snapshotId'],doc['scope']['label'],doc['capturedAt'],doc['status'],doc['sourceCaptureSha256'],payload))
            current=db.execute('SELECT r.captured_at,r.status FROM current_rankings c JOIN ranking_snapshots r USING(snapshot_id) WHERE c.scope_label=?',(doc['scope']['label'],)).fetchone()
            newer=not current or datetime.fromisoformat(doc['capturedAt'])>=datetime.fromisoformat(current[0])
            if newer and (not current or current[1]!='success' or doc['status']=='success'):
                db.execute('INSERT INTO current_rankings VALUES (?,?) ON CONFLICT(scope_label) DO UPDATE SET snapshot_id=excluded.snapshot_id',(doc['scope']['label'],doc['snapshotId']))
    finally:db.close()
    return doc


def load_snapshot(snapshot_id,database=DEFAULT_DB):
    db=connection(database)
    try:
        row=db.execute('SELECT payload FROM ranking_snapshots WHERE snapshot_id=?',(snapshot_id,)).fetchone()
        if not row:raise ValueError('ranking source has not been accepted')
        return json.loads(row[0])
    finally:db.close()


def latest_attempts(snapshot_id,database=DEFAULT_DB):
    db=connection(database)
    try:
        result={}
        for uid,payload in db.execute('SELECT player_id,payload FROM ranking_defense_attempts WHERE ranking_snapshot_id=? ORDER BY attempted_at',(snapshot_id,)):
            result[uid]=json.loads(payload)
        return result
    finally:db.close()


def save_failure(snapshot_id,player_id,reason,database=DEFAULT_DB):
    doc=load_snapshot(snapshot_id,database)
    if not any(p['playerId']==player_id for p in doc['players']):raise ValueError('failure owner is outside ranking source')
    if not re.fullmatch('[a-z_]{1,80}',reason):raise ValueError('failure reason must be a non-sensitive code')
    now=stamp();payload={'status':'failed','attemptedAt':now,'failureReason':reason,'defenseSnapshotIds':[],'defenseRetrievedAt':None}
    identity=hashlib.sha256(encoded([snapshot_id,player_id,now,reason]).encode()).hexdigest()
    db=connection(database)
    try:
        with db:db.execute('INSERT INTO ranking_defense_attempts VALUES (?,?,?,?,?,?)',(identity,snapshot_id,player_id,now,'failed',encoded(payload)))
    finally:db.close()


def save_capture(snapshot_id,directory,database=DEFAULT_DB):
    ranking=load_snapshot(snapshot_id,database);directory=private_directory(directory)
    link=json.loads((directory/'ranking-link.private.json').read_text(encoding='utf8'))
    if link.get('identityMatch')!='exact-native-uid' or link.get('purpose')!='pvp_defense':raise ValueError('missing exact native ranking link')
    origin=load_snapshot(link['rankingSnapshotId'],database)
    if link['rankingSourceCaptureSha256']!=origin['sourceCaptureSha256']:raise ValueError('ranking source hash differs')
    if link['defenseCaptureSha256']!=hashlib.sha256((directory/'capture.json').read_bytes()).hexdigest():raise ValueError('defense copy hash differs')
    uid=link['playerId']
    if not any(p['playerId']==uid for p in ranking['players']) or not any(p['playerId']==uid and p['rank']==link['rank'] for p in origin['players']):raise ValueError('defense owner is outside exact ranking source')
    doc=parse_defense(directory,all_teams=True)
    if any(t['playerId']!=uid or t['purpose']!='pvp_defense' for t in doc['snapshots']):raise ValueError('defense owner/purpose differs')
    if set(link['snapshotIds'])!={t['snapshotId'] for t in doc['snapshots']}:raise ValueError('defense snapshot IDs differ')
    retrieved=doc['snapshots'][0]['retrievedAt']
    cached=origin['snapshotId']!=snapshot_id
    if cached and abs((datetime.fromisoformat(ranking['capturedAt'])-datetime.fromisoformat(retrieved)).total_seconds())>900:
        raise ValueError('cross-ranking cache exceeds fifteen minutes')
    observed=directory/'observations.private.json';observed.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    normalized=ROOT/'data/normalized/defense-teams.private.json'
    accepted=json.loads(normalized.read_text(encoding='utf8')) if normalized.exists() else {'snapshots':[]}
    keys={(t['playerId'],t['snapshotId']) for t in accepted['snapshots']}
    # Do not replace enriched values when resuming the exact same successful copy.
    if not all((uid,t['snapshotId']) in keys for t in doc['snapshots']):
        import_file(observed,normalized);sync_database(database=database,modules=['pvp'])
    partial=any(t.get('unobservedPositionIndices') for t in doc['snapshots'])
    payload={'status':'partial' if partial else 'success','attemptedAt':stamp(),'failureReason':None,
             'defenseRetrievedAt':retrieved,'defenseSnapshotIds':link['snapshotIds'],
             'sourceRankingSnapshotId':origin['snapshotId'],'cacheState':'verified-earlier-session-copy' if cached else 'captured-from-this-ranking',
             'captureDirectory':directory.relative_to(ROOT).as_posix(),
             'captureSha256':link['defenseCaptureSha256'],'identityMatch':'exact-native-uid',
             'teams':len(doc['snapshots']),'selectedTeamId':next((t['teamId'] for t in doc['snapshots'] if t['isSelected']),None)}
    identity=hashlib.sha256(encoded([snapshot_id,uid,link['defenseCaptureSha256']]).encode()).hexdigest()
    db=connection(database)
    try:
        with db:
            previous=db.execute('SELECT payload FROM ranking_defense_attempts WHERE attempt_id=?',(identity,)).fetchone()
            if previous:return json.loads(previous[0])
            db.execute('INSERT INTO ranking_defense_attempts VALUES (?,?,?,?,?,?)',(identity,snapshot_id,uid,payload['attemptedAt'],payload['status'],encoded(payload)))
    finally:db.close()
    return payload
