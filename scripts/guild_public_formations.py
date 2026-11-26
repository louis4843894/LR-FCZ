"""Versioned public guildwar attack formations; never counts as tower defense."""
import hashlib,json,re,sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from local_game_database import ROOT,DEFAULT_DB,encoded,stamp,connect
from native_layouts import NEW_SHA
from guild_war_database import units_from_json
from ranking_database import private_directory

SCHEMA='''CREATE TABLE IF NOT EXISTS guild_public_formation_sources(source_id TEXT PRIMARY KEY,guild_id TEXT NOT NULL,player_id TEXT NOT NULL,captured_at TEXT NOT NULL,status TEXT NOT NULL,payload TEXT NOT NULL CHECK(json_valid(payload)));
CREATE TABLE IF NOT EXISTS current_guild_public_formations(guild_id TEXT NOT NULL,player_id TEXT NOT NULL,source_id TEXT NOT NULL REFERENCES guild_public_formation_sources,PRIMARY KEY(guild_id,player_id));
CREATE TABLE IF NOT EXISTS guild_public_formation_attempts(attempt_id TEXT PRIMARY KEY,guild_id TEXT NOT NULL,player_id TEXT NOT NULL,checked_at TEXT NOT NULL,status TEXT NOT NULL,reason TEXT,payload TEXT NOT NULL CHECK(json_valid(payload)));'''

def parse(directory,database=DEFAULT_DB):
 directory=private_directory(Path(directory));p=directory/'response.private.json';raw=p.read_bytes()
 if len(raw)>2*1024*1024:raise ValueError('public formation copy size bound')
 data=json.loads(raw)
 if data.get('sourceKind')!='normal-public-member-guildwar-group' or data.get('moduleSha256')!=NEW_SHA or data.get('credentialsIncluded') is not False or data.get('pvpTeamsIncluded') is not False:raise ValueError('unverified public formation source')
 if datetime.fromisoformat(data['capturedAt']).tzinfo is None:raise ValueError('formation time requires timezone')
 with closing(sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro',uri=True)) as db:
  row=db.execute('SELECT payload FROM guild_roster_sources WHERE source_id=?',(data['rosterSourceId'],)).fetchone()
  if not row:raise ValueError('accepted source roster missing')
  roster=json.loads(row[0])
  if roster['guildId']!=data['guildId'] or not any(m['playerId']==data['playerId'] and m['name']==data['playerName'] for m in roster['members']):raise ValueError('formation owner is not in its accepted roster')
 group=data['playerUnitTeamGroupMap']
 if set(group)!= {'guildwar'} or not isinstance(group['guildwar'],dict) or len(group['guildwar'])>4:raise ValueError('formation group boundary differs')
 teams=[]
 for number,units in group['guildwar'].items():
  if not re.fullmatch('[1-9][0-9]?',number):raise ValueError('invalid formation team number')
  teams.append({'teamNo':int(number),'units':units_from_json(units,int(number))})
 result={'schemaVersion':1,'sourceKind':'verified-public-guildwar-attack-formation','parserVersion':'guild-public-formation-v1','moduleSha256':NEW_SHA,
  'guildId':data['guildId'],'playerId':data['playerId'],'playerName':data['playerName'],'capturedAt':data['capturedAt'],
  'rosterSourceId':data['rosterSourceId'],'rankingSnapshotId':data['rankingSnapshotId'],'sourceDirectory':directory.relative_to(ROOT).as_posix(),
  'sourceSha256':hashlib.sha256(raw).hexdigest(),'status':'success','purpose':'guildwar_attack_formation','deploymentState':'not_established',
  'towerCode':None,'teams':teams,'defenseVerified':False,'visualVerification':False,
  'purposeEvidence':{'parser':'00f96454 guildwar -> group0x0c','battleConsumer':'01328cac -> /guildwar/battle/enter','defenseUsesDifferentGroup':'0133c6c8 -> group0x0b'}}
 result['sourceId']='guild-public-formation-'+hashlib.sha256(encoded(result).encode()).hexdigest()[:24];return result

def accept(directory,database=DEFAULT_DB):
 doc=parse(directory,database);db=connect(database);db.executescript(SCHEMA)
 try:
  with db:
   db.execute('INSERT OR IGNORE INTO guild_public_formation_sources VALUES (?,?,?,?,?,?)',(doc['sourceId'],doc['guildId'],doc['playerId'],doc['capturedAt'],doc['status'],encoded(doc)))
   old=db.execute('SELECT s.captured_at FROM current_guild_public_formations c JOIN guild_public_formation_sources s USING(source_id) WHERE c.guild_id=? AND c.player_id=?',(doc['guildId'],doc['playerId'])).fetchone()
   if not old or datetime.fromisoformat(old[0])<=datetime.fromisoformat(doc['capturedAt']):
    db.execute('INSERT INTO current_guild_public_formations VALUES (?,?,?) ON CONFLICT(guild_id,player_id) DO UPDATE SET source_id=excluded.source_id',(doc['guildId'],doc['playerId'],doc['sourceId']))
 finally:db.close()
 return doc

def attempt(gid,uid,status,reason=None,source_id=None,database=DEFAULT_DB):
 at=stamp();payload={'sourceId':source_id,'defenseVerified':False,'deploymentState':'not_established'};key=hashlib.sha256(encoded([gid,uid,at,status,reason]).encode()).hexdigest()
 db=connect(database);db.executescript(SCHEMA)
 try:
  with db:db.execute('INSERT OR IGNORE INTO guild_public_formation_attempts VALUES (?,?,?,?,?,?,?)',(key,gid,uid,at,status,reason,encoded(payload)))
 finally:db.close()
