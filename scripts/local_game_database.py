"""Transactional local storage for validated website snapshots. No network access."""
import hashlib
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / 'data/local/lr.private.sqlite'
TAIPEI = timezone(timedelta(hours=8), 'Asia/Taipei')
FILES = {
    'equipment': 'verified-equipment.json',
    'equipment_reference': 'equipment-reference-preview.json',
    'characters': 'verified-characters.json',
    'guild': 'guild-roster.private.json',
    'pvp': 'defense-teams.private.json',
}
KINDS = dict(zip(FILES, ['verified-equipment-template', 'external-user-confirmed',
                        'verified-character-template', 'validated-native-guild-roster',
                        'validated-player-team-snapshots']))
SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS documents (
 sha256 TEXT PRIMARY KEY, module TEXT NOT NULL, filename TEXT NOT NULL,
 imported_at TEXT NOT NULL, payload TEXT NOT NULL CHECK(json_valid(payload))
);
CREATE TABLE IF NOT EXISTS current_documents (
 filename TEXT PRIMARY KEY, sha256 TEXT NOT NULL REFERENCES documents(sha256)
);
CREATE TABLE IF NOT EXISTS equipment_templates (
 document_sha256 TEXT NOT NULL REFERENCES documents(sha256), item_code TEXT NOT NULL,
 stars INTEGER NOT NULL CHECK(stars BETWEEN 1 AND 9), kind TEXT NOT NULL,
 payload TEXT NOT NULL CHECK(json_valid(payload)), PRIMARY KEY(document_sha256,item_code)
);
CREATE TABLE IF NOT EXISTS equipment_references (
 document_sha256 TEXT NOT NULL REFERENCES documents(sha256), item_code TEXT NOT NULL,
 source_kind TEXT NOT NULL CHECK(source_kind='external-user-confirmed'),
 payload TEXT NOT NULL CHECK(json_valid(payload)), PRIMARY KEY(document_sha256,item_code)
);
CREATE TABLE IF NOT EXISTS defense_snapshots (
 document_sha256 TEXT NOT NULL REFERENCES documents(sha256), snapshot_id TEXT NOT NULL,
 player_id TEXT NOT NULL, purpose TEXT NOT NULL, team_id TEXT, retrieved_at TEXT NOT NULL,
 status TEXT NOT NULL, payload TEXT NOT NULL CHECK(json_valid(payload)),
 PRIMARY KEY(document_sha256,player_id,snapshot_id)
);
CREATE INDEX IF NOT EXISTS defense_owner_time ON defense_snapshots(player_id,purpose,team_id,retrieved_at);
CREATE TABLE IF NOT EXISTS equipment_observations (
 document_sha256 TEXT NOT NULL, snapshot_id TEXT NOT NULL, member_index INTEGER NOT NULL,
 slot TEXT NOT NULL CHECK(slot IN ('weapon','armor','accessory')), player_id TEXT NOT NULL,
 character_instance_id TEXT, instance_namespace TEXT, equipment_instance_id TEXT,
 equipment_id TEXT, state TEXT NOT NULL, enhancement INTEGER,
 attribute_read_state TEXT, payload TEXT NOT NULL CHECK(json_valid(payload)),
 PRIMARY KEY(document_sha256,player_id,snapshot_id,member_index,slot),
 FOREIGN KEY(document_sha256,player_id,snapshot_id) REFERENCES defense_snapshots(document_sha256,player_id,snapshot_id)
);
CREATE INDEX IF NOT EXISTS gear_owner_instance ON equipment_observations(player_id,instance_namespace,equipment_instance_id);
CREATE TABLE IF NOT EXISTS guild_memberships (
 document_sha256 TEXT NOT NULL REFERENCES documents(sha256), guild_id TEXT NOT NULL,
 player_id TEXT NOT NULL, retrieved_at TEXT NOT NULL, payload TEXT NOT NULL CHECK(json_valid(payload)),
 PRIMARY KEY(document_sha256,guild_id,player_id)
);
CREATE TABLE IF NOT EXISTS update_policies (
 module TEXT PRIMARY KEY, mode TEXT NOT NULL, timezone TEXT NOT NULL,
 weekday INTEGER, hour INTEGER, minute INTEGER
);
CREATE TABLE IF NOT EXISTS update_attempts (
 id INTEGER PRIMARY KEY, module TEXT NOT NULL, started_at TEXT NOT NULL,
 finished_at TEXT, status TEXT NOT NULL CHECK(status IN ('running','success','failed','skipped')),
 reason_code TEXT
);
CREATE TABLE IF NOT EXISTS collection_targets (
 module TEXT PRIMARY KEY CHECK(module IN ('guild','pvp')),
 target_name TEXT NOT NULL, source TEXT NOT NULL CHECK(source='user'), selected_at TEXT NOT NULL
);
"""


def stamp():
    return datetime.now(timezone.utc).isoformat()


def get_collection_target(database=DEFAULT_DB,module='guild'):
    db=connect(database)
    try:
        row=db.execute('SELECT target_name FROM collection_targets WHERE module=?',(module,)).fetchone()
        return row[0] if row else None
    finally:db.close()


def require_selected_guild(name,database=DEFAULT_DB):
    selected=get_collection_target(database,'guild')
    if selected and selected!=name:raise ValueError('visible guild differs from the user-selected target')


def latest_guild_boundary(now):
    local = now.astimezone(TAIPEI)
    boundary = (local - timedelta(days=(local.weekday()-1) % 7)).replace(hour=12, minute=0, second=0, microsecond=0)
    return boundary if local >= boundary else boundary-timedelta(days=7)


def guild_update_due(captured_at, now=None):
    return datetime.fromisoformat(captured_at.replace('Z', '+00:00')) < latest_guild_boundary(now or datetime.now(timezone.utc))


def connect(path=DEFAULT_DB):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=30)
    db.executescript(SCHEMA)
    if not next(row[5] for row in db.execute('PRAGMA table_info(defense_snapshots)') if row[1]=='player_id'):
        # Upgrade the first local schema without merging equal snapshot IDs across owners.
        db.executescript("""
        PRAGMA foreign_keys=OFF;
        BEGIN IMMEDIATE;
        ALTER TABLE equipment_observations RENAME TO gear_before_owner_key;
        ALTER TABLE defense_snapshots RENAME TO defense_before_owner_key;
        """ + SCHEMA.replace('PRAGMA foreign_keys=ON;', '') + """
        INSERT INTO defense_snapshots SELECT * FROM defense_before_owner_key;
        INSERT INTO equipment_observations SELECT * FROM gear_before_owner_key;
        DROP TABLE gear_before_owner_key;
        DROP TABLE defense_before_owner_key;
        COMMIT;
        PRAGMA foreign_keys=ON;
        """)
        db.executescript(SCHEMA)  # recreate indexes after dropping their legacy owners
    db.execute('PRAGMA user_version=1')
    with db:
        db.execute("INSERT INTO update_policies VALUES ('guild','weekly','Asia/Taipei',1,12,0) ON CONFLICT(module) DO NOTHING")
        db.execute("INSERT INTO update_policies VALUES ('pvp','on_demand','Asia/Taipei',NULL,NULL,NULL) ON CONFLICT(module) DO NOTHING")
    return db


def encoded(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def validate(module, doc):
    if doc.get('schemaVersion') != 1 or doc.get('sourceKind') != KINDS[module]:
        raise ValueError('unexpected normalized source: '+module)
    if module in ('equipment', 'characters'):
        rows = doc['records']
        key = 'itemCode' if module == 'equipment' else 'characterId'
        if not rows or doc['recordCount'] != len(rows) or len({r[key] for r in rows}) != len(rows):
            raise ValueError('invalid template count/identities')
        if module == 'equipment':
            for row in rows:
                if row.get('recordScope') != 'equipment-template' or type(row.get('starCount')) is not int or not 1 <= row['starCount'] <= 9 or row.get('equipType') not in ('ARMOR','WEAPON','ACC') or row.get('effects') is not None or row.get('effectsStatus') != 'unparsed':
                    raise ValueError('unverified equipment template')
        else:
            for row in rows:
                stars=row.get('starCount')
                if stars is not None and (type(stars) is not int or not 1<=stars<=9 or row.get('recordScope')!='character-template' or row.get('fieldStatus',{}).get('starCount')!='verified-native-ui-relation'):
                    raise ValueError('character star count lacks verified native UI evidence')
    elif module == 'equipment_reference':
        if doc.get('publicationAllowed') is not False or len({r['itemCode'] for r in doc['records']}) != len(doc['records']):
            raise ValueError('invalid research-only equipment reference')
    elif module == 'guild':
        rows = doc['members']
        if not doc.get('membershipComplete') or not rows or len(rows) != doc['membersRetrieved'] or len(rows) != doc['observedMemberTotal'] or len({r['playerId'] for r in rows}) != len(rows):
            raise ValueError('incomplete guild roster; keep previous snapshot')
    elif module == 'pvp':
        if doc.get('recordScope') != 'player-team' or not doc.get('snapshots'):
            raise ValueError('invalid defense snapshots')
        for row in doc['snapshots']:
            if row['status'] not in ('success', 'failed', 'unavailable') or row['purpose'] not in ('pvp_defense','guild_battle_defense'):
                raise ValueError('invalid defense status/purpose')
            if row['status'] == 'success' and not isinstance(row.get('members'), list):
                raise ValueError('missing team contents')
            indices = set()
            for member in row.get('members') or []:
                if member['memberIndex'] in indices or set(member['equipment']) != {'weapon','armor','accessory'}:
                    raise ValueError('duplicate position or missing equipment slots')
                indices.add(member['memberIndex'])


def sync_database(root=ROOT, database=DEFAULT_DB, modules=None,*,verify_integrity=True):
    """Validate the entire selected batch before writing; old versions are never deleted."""
    pending = []
    for module in modules or FILES:
        file = Path(root) / 'data/normalized' / FILES[module]
        raw = file.read_bytes()
        doc = json.loads(raw)
        validate(module, doc)
        pending.append((module, hashlib.sha256(raw).hexdigest(), doc))
    db = connect(database)
    try:
        with db:
            for module, sha, doc in pending:
                filename = FILES[module]
                # A failed/partial PVP refresh must retain previously valid team observations.
                previous = db.execute('SELECT d.payload FROM current_documents c JOIN documents d USING(sha256) WHERE c.filename=?', (filename,)).fetchone()
                if module == 'pvp' and previous:
                    old = json.loads(previous[0])
                    signatures = {encoded(r) for r in doc['snapshots']}
                    for row in old['snapshots']:
                        if row['status'] == 'success' and encoded(row) not in signatures:
                            same = next((r for r in doc['snapshots'] if r['snapshotId']==row['snapshotId'] and r['playerId']==row['playerId']), None)
                            # Enriching a saved observation is allowed; removing a success is not.
                            if not same or same['status'] != 'success' or same['playerId'] != row['playerId']:
                                raise ValueError('refresh would discard a valid defense snapshot')
                db.execute('INSERT OR IGNORE INTO documents VALUES (?,?,?,?,?)', (sha,module,filename,stamp(),encoded(doc)))
                if module == 'equipment':
                    db.executemany('INSERT OR IGNORE INTO equipment_templates VALUES (?,?,?,?,?)', [(sha,r['itemCode'],r['starCount'],r['equipType'],encoded(r)) for r in doc['records']])
                elif module == 'equipment_reference':
                    db.executemany('INSERT OR IGNORE INTO equipment_references VALUES (?,?,?,?)', [(sha,r['itemCode'],'external-user-confirmed',encoded(r)) for r in doc['records']])
                elif module == 'guild':
                    db.executemany('INSERT OR IGNORE INTO guild_memberships VALUES (?,?,?,?,?)', [(sha,doc['guildId'],r['playerId'],r['retrievedAt'],encoded(r)) for r in doc['members']])
                elif module == 'pvp':
                    for row in doc['snapshots']:
                        db.execute('INSERT OR IGNORE INTO defense_snapshots VALUES (?,?,?,?,?,?,?,?)', (sha,row['snapshotId'],row['playerId'],row['purpose'],row.get('teamId'),row['retrievedAt'],row['status'],encoded(row)))
                        for m in row.get('members') or []:
                            for slot, gear in m['equipment'].items():
                                identity = gear.get('equipmentInstanceIdentity') or {}
                                db.execute('INSERT OR IGNORE INTO equipment_observations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)', (sha,row['snapshotId'],m['memberIndex'],slot,row['playerId'],(m.get('characterInstanceIdentity') or {}).get('value'),identity.get('namespace'),identity.get('value'),gear.get('equipmentId'),gear['state'],gear.get('enhancement'),gear.get('attributeReadState'),encoded(gear)))
                db.execute('INSERT INTO current_documents VALUES (?,?) ON CONFLICT(filename) DO UPDATE SET sha256=excluded.sha256', (filename,sha))
        return counts(db,verify_integrity=verify_integrity)
    finally:
        db.close()


def counts(db,verify_integrity=True):
    # Counts refer to the active source documents, not accumulated historical rows.
    active = ' document_sha256 IN (SELECT sha256 FROM current_documents)'
    result = {table: db.execute('SELECT count(*) FROM '+table+' WHERE'+active).fetchone()[0] for table in ('equipment_templates','equipment_references','defense_snapshots','equipment_observations','guild_memberships')}
    result['databaseIntegrity'] = db.execute('PRAGMA quick_check').fetchone()[0] if verify_integrity else 'not_rechecked'
    return result
