"""Offline enrichment of accepted PVP/guild-war character INSTANCE observations.

Reads only source copies already associated with accepted teams. Never performs
requests, changes templates or substitutes template max levels/training values.
"""
import argparse,hashlib,json,re,sqlite3
from collections import Counter,OrderedDict
from contextlib import closing
from datetime import datetime,timezone
from pathlib import Path
from local_game_database import ROOT,DEFAULT_DB,connect,encoded
from native_layouts import NEW_SHA

VERSION='character-instance-progress-v1'
LANG=ROOT/'data/research/runtime.private/guild-session-20261123/lang_unit.ndb'
SCHEMA='''
CREATE TABLE IF NOT EXISTS character_instance_sources(source_id TEXT PRIMARY KEY,payload TEXT NOT NULL CHECK(json_valid(payload)));
CREATE TABLE IF NOT EXISTS current_character_instance_sources(scope TEXT PRIMARY KEY,source_id TEXT NOT NULL REFERENCES character_instance_sources(source_id));
CREATE TABLE IF NOT EXISTS character_instance_progress(source_id TEXT NOT NULL REFERENCES character_instance_sources(source_id),observation_id TEXT NOT NULL,payload TEXT NOT NULL CHECK(json_valid(payload)),PRIMARY KEY(source_id,observation_id));
'''


def digest(value):return hashlib.sha256(encoded(value).encode()).hexdigest()
def observation_key(scope,source,owner,team,position,tower=None):return digest([scope,source,tower,owner,str(team),position])
def instance_hash(owner,instance):return digest([owner,'player-owned-unit',str(instance)])


def integer_field(raw,key,minimum=0):
 if key not in raw or raw[key] is None:return None
 v=raw[key]
 if type(v) is not int or not minimum<=v<=0xffffffff:raise ValueError('invalid instance field '+key)
 return v


def parse_progress(raw,labels):
 """Missing awakening is unknown; an explicit empty string is distinct."""
 code=raw.get('awakeAbilityCode');state='not_returned'
 if 'awakeAbilityCode' in raw and code is not None:
  if not isinstance(code,str) or (code and not re.fullmatch('[A-Za-z0-9_-]{1,160}',code)):raise ValueError('invalid actual awakening code')
  state='present' if code else 'empty_observed'
 def clean(text):return re.sub(r'<[^>]*>','',text.replace('\\n','\n')).strip() if text else None
 return {'level':integer_field(raw,'unitLevel',1),'maxLevel':integer_field(raw,'playerUnitMaxLevel',1),
         'leonardPoints':integer_field(raw,'leonardPoint'),'talentGrade':integer_field(raw,'talentGrade'),
         'awakening':{'state':state,'abilityCode':code or None,'name':clean(labels.get((code or '')+'_nm')) if code else None,
                      'description':clean(labels.get((code or '')+'_desc')) if code else None},
         'fieldEvidence':{'level':'unitLevel','maxLevel':'playerUnitMaxLevel','leonardPoints':'leonardPoint','talentGrade':'talentGrade','awakening':'awakeAbilityCode'},
         'recordScope':'player-character-instance','templateTrainingSubstituted':False,'visuallyVerified':False}


def safe_progress(value):
 """Shared cloud whitelist; no owner/instance IDs, paths or raw response data."""
 if not value:return None
 a=value['awakening']
 return {k:value[k] for k in ['level','maxLevel','leonardPoints','talentGrade','recordScope','templateTrainingSubstituted','visuallyVerified']}|{
  'awakening':{k:a[k] for k in ['state','abilityCode','name','description']},'retrievedAt':value['retrievedAt']}


def match_progress(row,code,owner,instance,retrieved_at):
 if not row or row['characterId']!=code or row['instanceHash']!=instance_hash(owner,instance) or row['retrievedAt']!=retrieved_at:return None
 return safe_progress(row)


def read_progress(database=DEFAULT_DB):
 with closing(sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro',uri=True)) as db:
  if not db.execute("SELECT name FROM sqlite_master WHERE name='current_character_instance_sources'").fetchone():return None,{}
  found=db.execute("SELECT source_id FROM current_character_instance_sources WHERE scope='accepted-defense'").fetchone()
  if not found:return None,{}
  return found[0],{k:json.loads(p) for k,p in db.execute('SELECT observation_id,payload FROM character_instance_progress WHERE source_id=?',found)}


def build(database=DEFAULT_DB):
 with closing(sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro',uri=True)) as db:
  defense_sha,payload=db.execute("SELECT c.sha256,d.payload FROM current_documents c JOIN documents d USING(sha256) WHERE c.filename='defense-teams.private.json'").fetchone()
  teams=json.loads(payload)['snapshots']
  wars=[json.loads(p) for p, in db.execute("SELECT s.payload FROM current_guild_war_sources c JOIN guild_war_sources s USING(source_id) WHERE s.kind IN ('deployed_defense','saved_configuration')")] if db.execute("SELECT name FROM sqlite_master WHERE name='current_guild_war_sources'").fetchone() else []
 with closing(sqlite3.connect(LANG.resolve().as_uri()+'?mode=ro',uri=True)) as db:labels=dict(db.execute("SELECT dataCode,msg FROM lang_unit WHERE language='zh-Hant'"))
 records={};counts=Counter();sources={};cache=OrderedDict()
 def read(path):
  path=path.resolve()
  if not path.is_relative_to((ROOT/'data/research/runtime.private').resolve()):raise ValueError('source path outside accepted private root')
  if path not in cache:
   raw=path.read_bytes()
   if len(raw)>8*1024*1024:raise ValueError('source exceeds bound')
   name=path.relative_to(ROOT).as_posix();sha=hashlib.sha256(raw).hexdigest()
   if name in sources and sources[name]!=sha:raise ValueError('source changed while parsing')
   cache[path]=json.loads(raw);sources[name]=sha
   if len(cache)>8:cache.popitem(last=False)
  cache.move_to_end(path)
  return cache[path]
 def add(scope,source,owner,team,pos,tower,code,instance,at,raw,source_file):
  if raw['unitCode']!=code or str(raw['invenId'])!=str(instance) or raw['slot']!=pos or raw['teamNo']!=int(team):raise ValueError('instance association differs')
  p=parse_progress(raw,labels);key=observation_key(scope,source,owner,team,pos,tower)
  if key in records:raise ValueError('duplicate instance observation')
  records[key]={**p,'observationId':key,'scope':scope,'characterId':code,'instanceHash':instance_hash(owner,instance),
                'retrievedAt':at,'sourceFile':source_file,'sourceFileSha256':sources[source_file]}
  counts[scope+'Instances']+=1
  for field in ('level','maxLevel','leonardPoints','talentGrade'):
   if p[field] is not None:counts[scope+'.'+field]+=1
  counts[scope+'.awakening.'+p['awakening']['state']]+=1
  if p['awakening']['state']=='present' and p['awakening']['name'] and p['awakening']['description']:counts[scope+'.awakening.localized']+=1
 for t in teams:
  if t['purpose']!='pvp_defense' or t['status']!='success':continue
  path=ROOT/'data/research/runtime.private'/t['sourceId']/'response.private.json'
  if not t['sourceId'].startswith('pvp-http-') or not path.exists():
   counts['pvpInstancesWithoutHTTPSource']+=len(t.get('members') or []);continue
  data=read(path)
  if data.get('moduleSha256')!=NEW_SHA or data.get('sourceKind')!='verified-normal-pvp-http-branch' or data.get('identityMatch')!='exact-native-ranking-uid':raise ValueError('PVP source not accepted')
  if data['result']['player']['uid']!=t['playerId'] or data['capturedAt']!=t['retrievedAt']:raise ValueError('PVP source owner/time differs')
  group=t['teamId'].split('/')[-1];units=data['result']['playerUnitTeamGroupMap']['pvpteam'][group]
  mapped={u['slot']:u for u in units}
  if len(mapped)!=len(units) or len(units)!=len(t['members']):raise ValueError('PVP slot count differs')
  for m in t['members']:
   add('pvp',t['snapshotId'],t['playerId'],group,m['memberIndex'],None,m['characterId'],m['characterInstanceIdentity']['value'],t['retrievedAt'],mapped[m['memberIndex']],path.relative_to(ROOT).as_posix())
 for w in wars:
  directory=ROOT/w['sourceDirectory']
  if w['kind']=='deployed_defense':
   from guild_war_database import parse_directory
   rebuilt=next((d for d in parse_directory(directory) if d['kind']==w['kind'] and d['guildId']==w['guildId']),None)
   if rebuilt is None or any(rebuilt[k]!=w[k] for k in ('towers','sourceSha256')):raise ValueError('accepted guild deployment differs from source')
   for tower in w['towers']:
    if tower['readState']!='success':continue
    path=directory/f"tower-{w['side']}-{tower['code']}.private.json";data=read(path)
    raw_defenders={d['mergedGuildPlayer']['uid']:d for d in data['result']['guildWarDefenceDeckResponses']}
    for d in tower['defenders']:
     groups=raw_defenders[d['playerId']]['deckInfo']['playerUnitTeams']
     for t in d['teams']:
      mapped={u['slot']:u for u in groups[str(t['teamNo'])]}
      for u in t['units']:add('guildwar',w['sourceId'],d['playerId'],t['teamNo'],u['position'],tower['code'],u['characterId'],u['characterInstanceId'],d['retrievedAt'],mapped[u['position']],path.relative_to(ROOT).as_posix())
  else:
   path=directory/w['sourceFile'];data=read(path);groups=json.loads(data['savedDeck']['deckInfoJson'])['playerUnitTeams']
   if data['savedDeck']['uid']!=w['playerId'] or data['capturedAt']!=w['capturedAt']:raise ValueError('saved guild owner/time differs')
   for t in w['teams']:
    mapped={u['slot']:u for u in groups[str(t['teamNo'])]}
    for u in t['units']:add('guildwar-saved',w['sourceId'],w['playerId'],t['teamNo'],u['position'],None,u['characterId'],u['characterInstanceId'],w['capturedAt'],mapped[u['position']],path.relative_to(ROOT).as_posix())
 doc={'parserVersion':VERSION,'sourceKind':'accepted-response-character-instances','defenseDocumentSha256':defense_sha,
      'guildSourceIds':sorted(w['sourceId'] for w in wars),'localTranslationSha256':hashlib.sha256(LANG.read_bytes()).hexdigest(),
      'sources':sources,'summary':dict(counts),'records':list(records.values()),'templateTrainingSubstituted':False,'credentialsRead':False}
 doc['sourceId']='character-instances-'+digest(doc)[:24];return doc


def save(doc,database=DEFAULT_DB):
 from sync_character_templates_supabase import freeze
 folder=ROOT/'data/research/runtime.private/character-instance-exports'/doc['sourceId'];folder.mkdir(parents=True,exist_ok=True)
 freeze(folder/'instances.private.json',doc)
 with closing(connect(database)) as db:
  db.executescript(SCHEMA)
  with db:
   # Refuse to activate against a concurrently changed defense snapshot.
   current=db.execute("SELECT sha256 FROM current_documents WHERE filename='defense-teams.private.json'").fetchone()[0]
   if current!=doc['defenseDocumentSha256']:raise ValueError('accepted defenses changed during enrichment')
   guild_ids=sorted(r[0] for r in db.execute("SELECT c.source_id FROM current_guild_war_sources c JOIN guild_war_sources s USING(source_id) WHERE s.kind IN ('deployed_defense','saved_configuration')")) if db.execute("SELECT name FROM sqlite_master WHERE name='current_guild_war_sources'").fetchone() else []
   if guild_ids!=doc['guildSourceIds']:raise ValueError('accepted guild defenses changed during enrichment')
   db.execute('INSERT OR IGNORE INTO character_instance_sources VALUES (?,?)',(doc['sourceId'],encoded({k:v for k,v in doc.items() if k!='records'})))
   db.executemany('INSERT OR IGNORE INTO character_instance_progress VALUES (?,?,?)',[(doc['sourceId'],r['observationId'],encoded(r)) for r in doc['records']])
   db.execute("INSERT INTO current_character_instance_sources VALUES ('accepted-defense',?) ON CONFLICT(scope) DO UPDATE SET source_id=excluded.source_id",(doc['sourceId'],))
 return folder


def validate(doc,database=DEFAULT_DB):
 sid,rows=read_progress(database)
 if sid!=doc['sourceId'] or rows!={r['observationId']:r for r in doc['records']}:raise ValueError('stored progress does not reproduce')
 current={};attempts={}
 with closing(sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro',uri=True)) as db:
  for rank,owner,p in db.execute('SELECT ranking_snapshot_id,player_id,payload FROM ranking_defense_attempts ORDER BY attempted_at'):attempts[(rank,owner)]=json.loads(p)
  for p, in db.execute('SELECT r.payload FROM current_rankings c JOIN ranking_snapshots r USING(snapshot_id)'):
   ranking=json.loads(p)
   for player in ranking['players']:
    attempt=attempts.get((ranking['snapshotId'],player['playerId']))
    if attempt and attempt['status'] in ('success','partial'):
     for t in attempt['defenseSnapshotIds']:current[(player['playerId'],t)]=True
  teams=json.loads(db.execute("SELECT d.payload FROM current_documents c JOIN documents d USING(sha256) WHERE c.filename='defense-teams.private.json'").fetchone()[0])['snapshots']
 active=Counter()
 for t in teams:
  if (t['playerId'],t['snapshotId']) not in current:continue
  active['teams']+=1
  for m in t.get('members') or []:
   active['instances']+=1;r=rows.get(observation_key('pvp',t['snapshotId'],t['playerId'],t['teamId'].split('/')[-1],m['memberIndex']))
   if match_progress(r,m['characterId'],t['playerId'],(m.get('characterInstanceIdentity') or {}).get('value'),t['retrievedAt']):
    active['progressMatched']+=1
    active['actualAwakeningPresent']+=r['awakening']['state']=='present'
 report={'verifiedAt':datetime.now(timezone.utc).isoformat(),'sourceId':sid,'passed':True,'records':len(rows),'summary':doc['summary'],'currentRankedPvp':dict(active),
         'offlineSourceReproduction':True,'associationChecks':['source','owner','team','slot','character-template','character-instance','capture-time'],
         'templateTrainingSubstituted':False,'visualVerification':False,'networkRequests':0}
 (ROOT/'reports/character-instance-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8');return report


if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--apply',action='store_true');p.add_argument('--validate',action='store_true');a=p.parse_args();doc=build()
 if a.apply:save(doc)
 if a.validate:report=validate(doc)
 else:report={'sourceId':doc['sourceId'],'records':len(doc['records']),'summary':doc['summary'],'saved':a.apply}
 print(json.dumps(report,ensure_ascii=False))
