"""Offline, versioned guild-war observations; saved configurations are not deployments.

Only reviewed normal GET response copies are accepted. No authentication or UI
operations here. Instance fields are independent of equipment template ranges.
"""
import argparse, hashlib, json, re
from datetime import datetime
from pathlib import Path
from guild_rank_database import connection as guild_connection, integer, identifier, label
from local_game_database import ROOT, DEFAULT_DB, encoded
from ranking_database import private_directory
from native_layouts import NEW_SHA
from import_defense_teams import observed_equipment

PARSER_VERSION='guildwar-normal-v1'
SLOTS={'WEAPON':'weapon','ARMOR':'armor','ACC':'accessory'}
SCHEMA='''
CREATE TABLE IF NOT EXISTS guild_war_sources (
 source_id TEXT PRIMARY KEY,guild_id TEXT NOT NULL,kind TEXT NOT NULL,
 captured_at TEXT NOT NULL,status TEXT NOT NULL,payload TEXT NOT NULL CHECK(json_valid(payload))
);
CREATE TABLE IF NOT EXISTS current_guild_war_sources (
 guild_id TEXT NOT NULL,kind TEXT NOT NULL,source_id TEXT NOT NULL REFERENCES guild_war_sources(source_id),
 PRIMARY KEY(guild_id,kind)
);
CREATE TABLE IF NOT EXISTS guild_war_equipment_instances (
 source_id TEXT NOT NULL REFERENCES guild_war_sources(source_id),player_id TEXT NOT NULL,
 instance_id TEXT NOT NULL,unit_instance_id TEXT NOT NULL,slot TEXT NOT NULL,
 item_code TEXT NOT NULL,enhancement INTEGER NOT NULL,payload TEXT NOT NULL CHECK(json_valid(payload)),
 PRIMARY KEY(source_id,player_id,instance_id)
);
'''


def connection(database=DEFAULT_DB):
    db=guild_connection(database);db.executescript(SCHEMA);return db


def battle_number(status):
    # 0133c470 maps native season status 2/3 -> 1, 4/5 -> 2, 6/7 -> 3.
    # JSON name -> enum is confirmed in 01349f3c (see parameter evidence).
    return {'first_standby':1,'first_battle':1,
            'second_standby':2,'second_battle':2,
            'third_standby':3,'third_battle':3}.get(status)


def units_from_json(units,team_no):
    if not isinstance(units,list) or len(units)>20:raise ValueError('guild-war unit bound')
    positions=set();instances=set();equipment_ids=set();rows=[]
    for unit in units:
        position=integer(unit['slot'],0,19);instance=integer(unit['invenId'],1,0xffffffffffffffff)
        if position in positions or instance in instances or unit['teamNo']!=team_no:raise ValueError('duplicate or inconsistent guild-war placement')
        positions.add(position);instances.add(instance);code=identifier(unit['unitCode'])
        if not re.fullmatch('[A-Za-z0-9_-]+',code):raise ValueError('invalid unit code')
        mapping=unit.get('equipMap');equipment={}
        if mapping is not None and (not isinstance(mapping,dict) or set(mapping)-set(SLOTS)):raise ValueError('unknown guild-war equipment slot')
        for native,slot in SLOTS.items():
            if mapping is None:equipment[slot]={'state':'unknown','equipmentId':None};continue
            if native not in mapping:equipment[slot]={'state':'not_equipped','equipmentId':None};continue
            g=mapping[native]
            if not isinstance(g,dict) or not g:equipment[slot]={'state':'unknown','equipmentId':None};continue
            item=identifier(g['equipItemCode'])
            if not re.fullmatch('eq_[A-Za-z0-9_]+',item) or g['itemCode']!=item or g['equipType']!=native:raise ValueError('guild-war equipment template/slot differs')
            eid=integer(g['invenId'],1,0xffffffffffffffff);owner=integer(g['unitInvenId'],0,0xffffffffffffffff)
            if eid in equipment_ids or (owner and owner!=instance):raise ValueError('guild-war equipment instance owner/duplicate differs')
            equipment_ids.add(eid);enhancement=integer(g['currentEnchant']);grade=integer(g['currentGrade'])
            entries=[]
            for prefix in ('attr1','attr2','attr3','attr4','attr5','skillPlusAttr1'):
                field=prefix+'No'
                if field not in g:continue
                attr=integer(g[field]);value_grade=integer(g[prefix+'ValueGrade'])
                if attr:entries.append({'index':len(entries),'attributeId':attr,'valueGradeRaw':value_grade,'attributeTypeRaw':None,'sourceField':field})
            observed={'state':'equipped','equipmentId':item,'enhancement':enhancement,'instanceGrade':grade,
                'equipmentInstanceIdentity':{'value':str(eid),'namespace':'player-owned-equipment','sourceField':'equipMap.*.invenId'},
                'ownerAssociationStatus':'verified-native' if owner else 'unknown',
                'actualEffects':{'status':'identifiers_only','entries':entries,'numericalValuesVerified':False} if entries else None,
                'attributeReadState':'captured' if entries else 'empty_observed_semantics_unknown',
                'fieldEvidence':{'enhancement':'normal guild-war response equipMap.*.currentEnchant; instance, not template maxEnchant',
                    'instanceGrade':'normal guild-war response currentGrade; not template stars',
                    'equipmentInstanceIdentity':'normal guild-war response invenId, scoped to response player',
                    'actualEffects':'instance attrNNo/attrNValueGrade; numeric value, unit and activation unconfirmed'}}
            equipment[slot]={'state':'equipped','equipmentId':item,**observed_equipment(observed)}
        rows.append({'position':position,'characterId':code,'characterInstanceId':str(instance),
                     'level':integer(unit['unitLevel'],1),'equipment':equipment})
    return sorted(rows,key=lambda u:u['position'])


def player_teams(doc):
    if doc['kind']=='saved_configuration':
        for team in doc['teams']:yield doc['playerId'],team
    elif doc['kind']=='deployed_defense':
        for tower in doc['towers']:
            for defender in tower.get('defenders') or []:
                for team in defender['teams']:yield defender['playerId'],team


def parse_towers(directory,main,base,main_raw):
    files=list(directory.glob('tower-*.private.json'));records=[]
    if not files:return records
    expected_main=hashlib.sha256(main_raw).hexdigest()
    for side,key,mapkey in [('ally','myGuildInfo','fortressCount'),('opponent','enemyGuildInfo','enemyFortressCount')]:
        if not main.get(key) or not main.get(mapkey):continue
        gid=main[key]['gid'];towers=[];sources=[];times=[]
        for code in sorted(int(k) for k in main[mapkey]):
            source=directory/f'tower-{side}-{code}.private.json'
            if not source.exists():
                towers.append({'code':code,'readState':'not_read','defenders':None});continue
            raw=source.read_bytes()
            if len(raw)>8*1024*1024:raise ValueError('tower source size bound')
            data=json.loads(raw)
            if (data.get('sourceKind')!='normal-visible-guildwar-tower' or data.get('moduleSha256')!=NEW_SHA
                or data.get('mainCopySha256')!=expected_main or data.get('guildId')!=gid or data.get('side')!=side
                or data.get('towerCode')!=code or data.get('seasonNo')!=base['seasonNo'] or data.get('battleNo')!=base['battleNo']):raise ValueError('tower source context differs')
            listing=data['result']['guildWarDefenceDeckResponses']
            if not isinstance(listing,list) or len(listing)>8:raise ValueError('tower defender bound')
            defenders=[];seen=set()
            for row in listing:
                player=row['mergedGuildPlayer'];uid=identifier(player['uid'])
                if uid in seen or row['fortressCode']!=code:raise ValueError('duplicate defender or wrong fortress')
                seen.add(uid);is_ai=row.get('isAIUser')
                if type(is_ai) is not bool or (not is_ai and player['gid']!=gid):raise ValueError('defender guild or AI state unverified')
                groups=row['deckInfo']['playerUnitTeams']
                if not isinstance(groups,dict) or not 1<=len(groups)<=4:raise ValueError('defender group bound')
                teams=[]
                for group,units in groups.items():
                    if not re.fullmatch('[1-9][0-9]?',group):raise ValueError('defender team key unverified')
                    teams.append({'teamNo':int(group),'units':units_from_json(units,int(group))})
                defenders.append({'playerId':uid,'playerName':label(player.get('userName') or player.get('name') or ''),
                                  'deckId':str(integer(row['deckId'],1,0xffffffffffffffff)),
                                  'retrievedAt':data['capturedAt'],'isAI':is_ai,
                                  'withdrawal':row.get('withdrawal') if type(row.get('withdrawal')) is bool else None,
                                  'membershipEvidence':'tower response mergedGuildPlayer.gid and uid; not inferred from PVP',
                                  'teams':teams})
            towers.append({'code':code,'readState':'success','retrievedAt':data['capturedAt'],'defenders':defenders})
            sources.append({'file':source.name,'sha256':hashlib.sha256(raw).hexdigest()});times.append(data['capturedAt'])
        if not sources:continue
        complete=all(t['readState']=='success' for t in towers)
        records.append({**base,'sourceKind':'verified-guildwar-tower-deployments','kind':'deployed_defense','guildId':gid,
                        'capturedAt':max(times),'status':'success' if complete else 'partial','side':side,
                        'towers':towers,'towerSources':sources,'sourceSha256':hashlib.sha256(encoded([expected_main,sources]).encode()).hexdigest(),
                        'fieldEvidence':{'deployment':'0133c388/0133c590 normal fortress GET -> result.guildWarDefenceDeckResponses[].fortressCode',
                                         'membership':'same response mergedGuildPlayer.gid/uid',
                                         'equipment':'deckInfoJson.playerUnitTeams[].equipMap instance fields; no template range substituted'}})
    return records


def parse_directory(directory):
    directory=private_directory(directory)
    filename='bootstrap.private.json' if (directory/'bootstrap.private.json').exists() else 'main.private.json'
    raw=(directory/filename).read_bytes()
    if len(raw)>8*1024*1024:raise ValueError('guild-war source size bound')
    data=json.loads(raw)
    if data.get('moduleSha256')!=NEW_SHA or data.get('sourceKind') not in ('normal-visible-guildwar-bootstrap','normal-visible-guildwar-main'):raise ValueError('unverified guild-war source')
    at=data['capturedAt']
    if datetime.fromisoformat(at).tzinfo is None:raise ValueError('guild-war timestamp requires timezone')
    main=data.get('main',data.get('result'));season=main['currentSeason'];no=integer(season['seasonNo'],1)
    status=label(season['status']);battle=battle_number(status)
    base={'schemaVersion':1,'parserVersion':PARSER_VERSION,'capturedAt':at,'gameVersion':'12.4.2','moduleSha256':NEW_SHA,
          'seasonNo':no,'battleNo':battle,'seasonStatus':status,'sourceDirectory':directory.relative_to(ROOT).as_posix(),
          'sourceFile':filename,'sourceSha256':hashlib.sha256(raw).hexdigest(),'visualVerification':False}
    if data.get('historicalContext'):base['historicalContext']=True
    result=[]
    for side,key,mapkey in [('ally','myGuildInfo','fortressCount'),('opponent','enemyGuildInfo','enemyFortressCount')]:
        guild=main.get(key);counts=main.get(mapkey)
        if not guild or not counts:continue
        gid=identifier(guild['gid'])
        if not isinstance(counts,dict) or not 1<=len(counts)<=32:raise ValueError('guild-war tower map bound')
        towers=[]
        for code,counters in counts.items():
            if not re.fullmatch('[1-9][0-9]{0,3}',code) or not isinstance(counters,list) or not 1<=len(counters)<=8:raise ValueError('guild-war tower counters bound')
            towers.append({'code':int(code),'countersRaw':[integer(n) for n in counters],
                           'defendersState':'not_read','defenders':None})
        result.append({**base,'sourceKind':'verified-guildwar-overview','kind':'overview','guildId':gid,
                       'guildName':label(guild['guildName']),'side':side,'rankObserved':integer(guild['guildWarRank']),
                       'registered':main.get('registered') if side=='ally' and type(main.get('registered')) is bool else None,
                       'towers':sorted(towers,key=lambda t:t['code']),'status':'success','defenseState':'not_read'})
    deck=data.get('savedDeck')
    if deck:
        gid=identifier(deck['gid']);uid=identifier(deck['uid'])
        if gid!=main['myGuildInfo']['gid']:raise ValueError('saved deck guild mismatch')
        configuration=json.loads(deck['deckInfoJson']);groups=configuration['playerUnitTeams']
        if not isinstance(groups,dict) or not 1<=len(groups)<=4:raise ValueError('guild-war saved group bound')
        teams=[]
        for key,units in groups.items():
            if not re.fullmatch('[1-9][0-9]?',key):raise ValueError('invalid guild-war team key')
            teams.append({'teamNo':int(key),'units':units_from_json(units,int(key))})
        result.append({**base,'sourceKind':'verified-guildwar-saved-configuration','kind':'saved_configuration',
                       'guildId':gid,'playerId':uid,'deckId':str(integer(deck['deckId'],1,0xffffffffffffffff)),
                       'configuredTeamNo':integer(configuration['useTeamNo'],1),
                       'deploymentState':'unconfirmed','status':'success','teams':teams,
                       'fieldEvidence':{'purpose':'GET /guildwar/defencedeck 0133c678; saved configuration only',
                                        'positions':'deckInfoJson.playerUnitTeams.*[].slot; actual 0-based slots; not PVP five-slot assumption'}})
    result.extend(parse_towers(directory,main,base,raw))
    for doc in result:
        doc['sourceId']='guildwar-'+hashlib.sha256(encoded(doc).encode()).hexdigest()[:24]
    return result


def accept_directory(directory,database=DEFAULT_DB):
    documents=parse_directory(directory);db=connection(database)
    try:
        with db:
            for doc in documents:
                db.execute('INSERT OR IGNORE INTO guild_war_sources VALUES (?,?,?,?,?,?)',
                           (doc['sourceId'],doc['guildId'],doc['kind'],doc['capturedAt'],doc['status'],encoded(doc)))
                previous=db.execute('SELECT s.captured_at,s.status,s.payload FROM current_guild_war_sources c JOIN guild_war_sources s USING(source_id) WHERE c.guild_id=? AND c.kind=?',(doc['guildId'],doc['kind'])).fetchone()
                def context_order(d):return (d['seasonNo'],4 if d['seasonStatus']=='settlement' else d['battleNo'] or 0,datetime.fromisoformat(d['capturedAt']))
                if (not previous or context_order(doc)>=context_order(json.loads(previous[2]))) and not (previous and previous[1]=='success' and doc['status']=='partial'):
                    db.execute('INSERT INTO current_guild_war_sources VALUES (?,?,?) ON CONFLICT(guild_id,kind) DO UPDATE SET source_id=excluded.source_id',(doc['guildId'],doc['kind'],doc['sourceId']))
                for player_id,team in player_teams(doc):
                    for unit in team['units']:
                        for slot,e in unit['equipment'].items():
                            if e['state']!='equipped':continue
                            db.execute('INSERT OR IGNORE INTO guild_war_equipment_instances VALUES (?,?,?,?,?,?,?,?)',
                                (doc['sourceId'],player_id,e['equipmentInstanceIdentity']['value'],unit['characterInstanceId'],slot,e['equipmentId'],e['enhancement'],encoded(e)))
                if doc['kind']=='deployed_defense':
                    identity=hashlib.sha256(encoded([doc['sourceId'],'defense']).encode()).hexdigest()
                    db.execute('INSERT OR IGNORE INTO guild_fetch_attempts VALUES (?,?,?,?,?,?,?)',
                        (identity,doc['guildId'],'defense',doc['capturedAt'],doc['status'],None,
                         encoded({'sourceId':doc['sourceId'],'towersRead':sum(t['readState']=='success' for t in doc['towers']),'towersObserved':len(doc['towers'])})))
    finally:db.close()
    return documents


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture',type=Path,required=True);p.add_argument('--database',type=Path,default=DEFAULT_DB);a=p.parse_args()
    docs=accept_directory(a.capture,a.database)
    print(json.dumps({'accepted':len(docs),'overviewGuilds':sum(d['kind']=='overview' for d in docs),
        'savedConfigurationUnits':sum(len(t['units']) for d in docs for t in d.get('teams',[])),
        'deployedDefenderTeams':sum(1 for d in docs if d['kind']=='deployed_defense' for _ in player_teams(d)),
        'credentialsPersisted':False}))
