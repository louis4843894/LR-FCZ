"""Versioned public guild-war rankings and rosters; no credentials or PVP teams."""
import hashlib
import json
import math
import sqlite3
from datetime import datetime
from pathlib import Path
from local_game_database import ROOT,DEFAULT_DB,connect,encoded,stamp
from ranking_database import private_directory
from native_layouts import NEW_SHA

SCHEMA='''
CREATE TABLE IF NOT EXISTS guild_rank_sources (
 snapshot_id TEXT PRIMARY KEY,captured_at TEXT NOT NULL,status TEXT NOT NULL,
 payload TEXT NOT NULL CHECK(json_valid(payload))
);
CREATE TABLE IF NOT EXISTS current_guild_rankings (
 scope TEXT PRIMARY KEY,snapshot_id TEXT NOT NULL REFERENCES guild_rank_sources(snapshot_id)
);
CREATE TABLE IF NOT EXISTS guild_ranking_checks (
 snapshot_id TEXT NOT NULL REFERENCES guild_rank_sources(snapshot_id),checked_at TEXT NOT NULL,
 source_sha256 TEXT NOT NULL,PRIMARY KEY(snapshot_id,checked_at)
);
CREATE TABLE IF NOT EXISTS guild_roster_sources (
 source_id TEXT PRIMARY KEY,guild_id TEXT NOT NULL,captured_at TEXT NOT NULL,
 status TEXT NOT NULL,payload TEXT NOT NULL CHECK(json_valid(payload))
);
CREATE TABLE IF NOT EXISTS current_ranked_guild_rosters (
 guild_id TEXT PRIMARY KEY,source_id TEXT NOT NULL REFERENCES guild_roster_sources(source_id)
);
CREATE TABLE IF NOT EXISTS guild_fetch_attempts (
 attempt_id TEXT PRIMARY KEY,guild_id TEXT NOT NULL,part TEXT NOT NULL,
 checked_at TEXT NOT NULL,status TEXT NOT NULL,reason TEXT,
 payload TEXT NOT NULL CHECK(json_valid(payload))
);
CREATE INDEX IF NOT EXISTS ranked_guild_fetch ON guild_fetch_attempts(guild_id,part,checked_at);
'''
LABELS={1:'傳奇',2:'大師'}


def connection(database=DEFAULT_DB):
    db=connect(database);db.executescript(SCHEMA);return db


def integer(value,minimum=0,maximum=0x7fffffff):
    if type(value) not in (int,float) or not math.isfinite(value) or int(value)!=value or not minimum<=value<=maximum:
        raise ValueError('invalid guild integer')
    return int(value)


def identifier(value):
    if not isinstance(value,str) or not 1<=len(value)<=256 or any(ord(c)<32 for c in value):raise ValueError('invalid guild identity')
    return value


def label(value,limit=200):
    if not isinstance(value,str) or len(value)>limit:raise ValueError('invalid guild label')
    return value


def parse_rankings(directories,top=100):
    if not 1<=top<=100:raise ValueError('guild rank bound')
    rows=[];sources=[];totals=set();times=[]
    for directory in directories:
        directory=private_directory(directory);raw=(directory/'rank-response.private.json').read_bytes();meta=json.loads(raw)
        if meta['moduleSha256']!=NEW_SHA or meta['sourceKind']!='normal-guildwar-ranking-response':raise ValueError('guild rank source differs')
        grade=integer(meta['gradeId'],1,2);result=meta['result']['totalRank'];total=integer(result['totalCount']);totals.add(total)
        listing=result['rankingList']
        if not isinstance(listing,list) or len(listing)>500:raise ValueError('guild list bound')
        times.append(datetime.fromisoformat(meta['capturedAt']));source_ranks=set();source_ids=set()
        for row in listing:
            rank=integer(row['rank'],1);gid=identifier(row['uid'])
            if rank in source_ranks or gid in source_ids:raise ValueError('duplicate guild ranking identity')
            source_ranks.add(rank);source_ids.add(gid)
            if rank>top:continue
            members=integer(row['curMemberCount'],0,1000);capacity=integer(row['maxMemberCount'],1,1000)
            if members>capacity:raise ValueError('guild member count exceeds capacity')
            rows.append({'guildId':gid,'rank':rank,'score':integer(row['score']),'name':label(row['displayName']),
                         'gradeId':grade,'gradeLabel':LABELS[grade],'memberCount':members,'memberCapacity':capacity,
                         'level':integer(row['level']),'nationalFlag':label(row.get('nationalFlag',''),10),
                         'retrievedAt':meta['capturedAt']})
        sources.append({'directory':directory.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(raw).hexdigest(),'gradeId':grade,'capturedAt':meta['capturedAt'],'returned':len(listing),'totalCount':total})
    rows.sort(key=lambda r:r['rank']);complete=len(rows)==top and [r['rank'] for r in rows]==list(range(1,top+1)) and len({r['guildId'] for r in rows})==len(rows)
    if len(totals)!=1 or (max(times)-min(times)).total_seconds()>120:raise ValueError('guild ranking sources differ in time/count')
    content=hashlib.sha256(encoded([{k:v for k,v in r.items() if k!='retrievedAt'} for r in rows]).encode()).hexdigest()
    return {'schemaVersion':1,'sourceKind':'verified-normal-guildwar-top-ranking','snapshotId':'guild-ranking-'+content[:24],
            'capturedAt':max(times).isoformat(),'gameVersion':'12.4.2','moduleSha256':NEW_SHA,
            'top':top,'observedTotal':next(iter(totals)),'status':'success' if complete else 'partial','sources':sources,'guilds':rows,
            'rankingPurpose':'guild_war','wholeGameComplete':False}


def accept_rankings(directories,database=DEFAULT_DB):
    doc=parse_rankings(directories);db=connection(database)
    try:
        with db:
            db.execute('INSERT OR IGNORE INTO guild_rank_sources VALUES (?,?,?,?)',(doc['snapshotId'],doc['capturedAt'],doc['status'],encoded(doc)))
            db.execute('INSERT OR IGNORE INTO guild_ranking_checks VALUES (?,?,?)',(doc['snapshotId'],doc['capturedAt'],hashlib.sha256(encoded(doc['sources']).encode()).hexdigest()))
            if doc['status']=='success':db.execute("INSERT INTO current_guild_rankings VALUES ('top100',?) ON CONFLICT(scope) DO UPDATE SET snapshot_id=excluded.snapshot_id",(doc['snapshotId'],))
    finally:db.close()
    return doc


def current_ranking(database=DEFAULT_DB):
    db=connection(database)
    try:
        row=db.execute("SELECT r.payload FROM current_guild_rankings c JOIN guild_rank_sources r USING(snapshot_id) WHERE scope='top100'").fetchone()
        if not row:return None
        doc=json.loads(row[0]);checked=db.execute('SELECT max(checked_at) FROM guild_ranking_checks WHERE snapshot_id=?',(doc['snapshotId'],)).fetchone()[0]
        return {**doc,'lastCheckedAt':checked or doc['capturedAt']}
    finally:db.close()


def parse_roster(directory):
    directory=private_directory(directory);raw=(directory/'guild-response.private.json').read_bytes();data=json.loads(raw)
    if data['moduleSha256']!=NEW_SHA or data['sourceKind']!='normal-public-guild-profile-roster':raise ValueError('guild roster source differs')
    guild=data['guild'];gid=identifier(guild['gid']);seen=set();members=[]
    for row in data['guildMemberList']:
        uid=identifier(row['uid'])
        if row['gid']!=gid or uid in seen:raise ValueError('guild roster owner/duplicate differs')
        seen.add(uid);members.append({'playerId':uid,'name':label(row.get('userName') or row['name']),
                                     'level':integer(row['level']),'role':label(row['guildAuthority'],50)})
    if len(members)>1000:raise ValueError('guild roster bound')
    total=integer(guild['currentMemberCount'],0,1000);capacity=integer(guild['guildLevelInfo']['maxMemberCount'],1,1000)
    if len(members)>capacity or total>capacity:raise ValueError('guild roster exceeds capacity')
    return {'schemaVersion':1,'sourceKind':'verified-normal-ranked-guild-roster','sourceId':'guild-roster-'+hashlib.sha256(raw).hexdigest()[:24],
            'guildId':gid,'name':label(guild['name']),'level':integer(guild['level']),
            'nationalFlag':label(guild.get('nationalFlag',''),10),'capturedAt':data['capturedAt'],
            'profileRetrievedAt':data['profileRetrievedAt'],'gameVersion':'12.4.2','moduleSha256':NEW_SHA,
            'observedMemberTotal':total,'memberCapacity':capacity,'membersRetrieved':len(members),
            'membershipComplete':len(members)==total,'status':'success' if len(members)==total else 'partial',
            'members':members,'sourceDirectory':directory.relative_to(ROOT).as_posix(),
            'sourceSha256':hashlib.sha256(raw).hexdigest()}


def attempt(gid,part,status,reason=None,payload=None,database=DEFAULT_DB):
    if part not in ('roster','defense') or status not in ('success','partial','failed','unavailable','not_read'):raise ValueError('guild attempt status differs')
    at=stamp();identity=hashlib.sha256(encoded([gid,part,at,status]).encode()).hexdigest();db=connection(database)
    try:
        with db:db.execute('INSERT INTO guild_fetch_attempts VALUES (?,?,?,?,?,?,?)',(identity,gid,part,at,status,reason,encoded(payload or {})))
    finally:db.close()


def accept_roster(directory,database=DEFAULT_DB):
    doc=parse_roster(directory);db=connection(database)
    try:
        with db:
            db.execute('INSERT OR IGNORE INTO guild_roster_sources VALUES (?,?,?,?,?)',(doc['sourceId'],doc['guildId'],doc['capturedAt'],doc['status'],encoded(doc)))
            previous=db.execute('SELECT r.status FROM current_ranked_guild_rosters c JOIN guild_roster_sources r USING(source_id) WHERE c.guild_id=?',(doc['guildId'],)).fetchone()
            if doc['membershipComplete'] or not previous or previous[0]!='success':
                db.execute('INSERT INTO current_ranked_guild_rosters VALUES (?,?) ON CONFLICT(guild_id) DO UPDATE SET source_id=excluded.source_id',(doc['guildId'],doc['sourceId']))
    finally:db.close()
    attempt(doc['guildId'],'roster',doc['status'],payload={'sourceId':doc['sourceId'],'retrieved':doc['membersRetrieved'],'observed':doc['observedMemberTotal']},database=database)
    return doc
