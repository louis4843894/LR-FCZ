"""Read only the currently visible ally/opponent guild war, never arbitrary GIDs.

Unreviewed tower response bodies remain in RAM. Probe mode saves only shapes
and hashes until field identities/deployment relationships have been verified.
"""
import argparse,hashlib,json,sys,time,uuid
from datetime import datetime,timezone
from pathlib import Path
from pvp_session import Reader,NEW_SHA,ROOT,load_session,SessionUnavailable
from fetch_ranked_pvp_response import normal_json,AcquisitionStopped
from probe_guildwar_normal import shape
sys.path.insert(0,str(ROOT/'scripts'))
from guild_war_database import battle_number,accept_directory
from collect_ranked_pvp_http import acquisition_lock
from ranking_database import private_directory
from guildwar_visible_towers import inspect as visible_opponent_towers,recheck as recheck_visible_tower,public_proof,VisibilityUnavailable


def tower_paths(main,side):
    if side not in ('ally','opponent'):raise ValueError('unsupported war side')
    season=main['currentSeason'];no=season['seasonNo'];battle=battle_number(season['status'])
    if type(no) is not int or not 1<=no<=9999999 or battle is None:raise AcquisitionStopped('war_season_not_in_verified_battle')
    key='fortressCount' if side=='ally' else 'enemyFortressCount';codes=main.get(key)
    if not isinstance(codes,dict) or not 1<=len(codes)<=32:raise AcquisitionStopped('current_war_tower_map_missing')
    result=[]
    for code in codes:
        if not isinstance(code,str) or not code.isdigit() or not 1<=int(code)<=9999:raise AcquisitionStopped('current_war_tower_code_unverified')
        result.append((int(code),f'/guildwar/fortress/{side}/{no}/{battle}/{int(code)}'))
    return sorted(result)


def reviewed_tower(doc,main,side,code):
    result=doc.get('result')
    listing=result.get('guildWarDefenceDeckResponses') if isinstance(result,dict) else None
    if not isinstance(listing,list) or len(listing)>8:raise AcquisitionStopped('normal_tower_defenders_shape_unverified')
    gid=main['myGuildInfo' if side=='ally' else 'enemyGuildInfo']['gid'];selected=[]
    for row in listing:
        if row.get('fortressCode')!=code:raise AcquisitionStopped('normal_tower_code_differs')
        player=row.get('mergedGuildPlayer')
        if not isinstance(player,dict):raise AcquisitionStopped('normal_tower_player_missing')
        if player.get('gid')!=gid and row.get('isAIUser') is not True:raise AcquisitionStopped('normal_tower_guild_differs')
        deck=row.get('deckInfoJson')
        if not isinstance(deck,str) or len(deck)>2*1024*1024:raise AcquisitionStopped('normal_tower_deck_unverified')
        parsed=json.loads(deck)
        if not isinstance(parsed,dict):raise AcquisitionStopped('normal_tower_deck_object_missing')
        # Player upgrades, unrelated machine stats, activity history and profile
        # links are not needed for the equipment display and are not retained.
        subset={k:parsed[k] for k in ('playerUnitTeams','useTeamNo') if k in parsed}
        if not subset:raise AcquisitionStopped('normal_tower_unit_groups_missing')
        selected.append({**{k:row[k] for k in ('fortressCode','remainDefenceCount','winCount','deckId','withdrawal','progressInBattle','isAIUser') if k in row},
                         'mergedGuildPlayer':{k:player[k] for k in ('gid','uid','name','userName','guildAuthority') if k in player},
                         'deckInfo':subset})
    return {'guildWarDefenceDeckResponses':selected}


def historical_request(previous,current):
    if previous.get('moduleSha256')!=NEW_SHA or previous.get('sourceKind') not in ('normal-visible-guildwar-bootstrap','normal-visible-guildwar-main'):raise AcquisitionStopped('unverified_previous_war_context')
    old=previous.get('main',previous.get('result'));season=old.get('currentSeason',{})
    if not old.get('myGuildInfo',{}).get('gid') or old['myGuildInfo']['gid']!=current.get('myGuildInfo',{}).get('gid'):raise AcquisitionStopped('previous_context_not_this_guild')
    if season.get('seasonNo')!=current.get('currentSeason',{}).get('seasonNo') or battle_number(season.get('status')) is None:raise AcquisitionStopped('previous_context_outside_known_current_season')
    return f"/guildwar/main?status={season['status']}&seasonNo={season['seasonNo']}",old


def collect(*,probe=False,capture_towers=False,previous_context=None,sides=('ally','opponent')):
    with Reader(r'C:\LDPlayer\LDPlayer9\adb.exe','emulator-5554',100) as reader:
        reader.expected_module_sha=NEW_SHA;reader.refresh();session=load_session(reader,authorized=True)
    raw,doc=normal_json(session,'/guildwar/main',purpose='guild-war-bootstrap');main=doc.get('result')
    if not isinstance(main,dict) or not main.get('currentSeason'):raise AcquisitionStopped('normal_war_main_missing')
    historical=None
    if previous_context:
        directory=private_directory(Path(previous_context));source=directory/('bootstrap.private.json' if (directory/'bootstrap.private.json').exists() else 'main.private.json')
        prior_raw=source.read_bytes()
        if len(prior_raw)>8*1024*1024:raise AcquisitionStopped('previous_war_context_exceeds_bound')
        path,old=historical_request(json.loads(prior_raw),main)
        time.sleep(.5);raw,doc=normal_json(session,path,purpose='guild-war-history-main');returned=doc.get('result',{})
        safe={'requested':{'seasonNo':old['currentSeason']['seasonNo'],'status':old['currentSeason']['status']},
              'returned':{k:returned.get('currentSeason',{}).get(k) for k in ('seasonNo','status')},
              'responseShape':shape(doc),'responseSha256':hashlib.sha256(raw).hexdigest(),
              'sameGuildReturned':returned.get('myGuildInfo',{}).get('gid')==main['myGuildInfo']['gid'],
              'credentialsPersisted':False,'checkedAt':datetime.now(timezone.utc).isoformat()}
        check=ROOT/'data/research/runtime.private/guild-top100-session/history-context-check.private.json'
        check.write_text(json.dumps(safe,indent=2)+'\n',encoding='utf8')
        if (returned.get('currentSeason',{}).get('seasonNo')!=old['currentSeason']['seasonNo']
            or battle_number(returned.get('currentSeason',{}).get('status'))!=battle_number(old['currentSeason']['status'])
            or returned.get('myGuildInfo',{}).get('gid')!=main['myGuildInfo']['gid']):raise AcquisitionStopped('historical_war_context_not_returned')
        expected=old.get('enemyGuildInfo',{}).get('gid')
        if expected and returned.get('enemyGuildInfo',{}).get('gid')!=expected:raise AcquisitionStopped('historical_opponent_differs_from_saved_context')
        main=returned;historical={'sourceSha256':hashlib.sha256(prior_raw).hexdigest(),'normalRequestPath':path}
    allowed=('myGuildInfo','enemyGuildInfo','currentSeason','fortressCount','enemyFortressCount','myFortressCode','majorFortresses','registered')
    at=datetime.now(timezone.utc);folder=ROOT/'data/research/runtime.private'/('guildwar-main-'+at.strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:6]);folder.mkdir()
    capture={'sourceKind':'normal-visible-guildwar-main','capturedAt':at.isoformat(),'gameVersion':'12.4.2','moduleSha256':NEW_SHA,
             'responseSha256':hashlib.sha256(raw).hexdigest(),'result':{k:main[k] for k in allowed if k in main}}
    if historical:capture['historicalContext']=historical
    (folder/'main.private.json').write_text(json.dumps(capture,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    accepted=accept_directory(folder);result={'overviewGuilds':len(accepted),'copy':folder.name,'deployedTeams':0,'credentialsPersisted':False}
    if probe:
        paths=tower_paths(main,'ally');own=main.get('myFortressCode');code,path=next((p for p in paths if p[0]==own),paths[0])
        time.sleep(.5);raw,response=normal_json(session,path,purpose='guild-war-tower')
        record={'side':'ally','towerCode':code,'seasonNo':main['currentSeason']['seasonNo'],'battleNo':battle_number(main['currentSeason']['status']),
                'capturedAt':datetime.now(timezone.utc).isoformat(),'responseSha256':hashlib.sha256(raw).hexdigest(),'shape':shape(response)}
        (folder/'tower-shape.private.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8');result['towerProbe']=record
    if capture_towers:
        count=0;defenders=0
        for side,key,mapkey in [('ally','myGuildInfo','fortressCount'),('opponent','enemyGuildInfo','enemyFortressCount')]:
            if side not in sides:continue
            if not main.get(key) or not main.get(mapkey):continue
            visibility_reader=None;visibility=None
            if side=='opponent':
                visibility_reader=Reader(r'C:\LDPlayer\LDPlayer9\adb.exe','emulator-5554',180);visibility_reader.expected_module_sha=NEW_SHA
                try:
                    visibility_reader.refresh();visibility=visible_opponent_towers(visibility_reader,[code for code,_ in tower_paths(main,side)])
                except (VisibilityUnavailable,ValueError,RuntimeError):
                    visibility_reader.close();result['opponentReadState']='normal_opponent_towers_not_visibly_verified';continue
                (folder/'opponent-visibility.private.json').write_text(json.dumps(public_proof(visibility),indent=2)+'\n',encoding='utf8')
            for code,path in tower_paths(main,side):
                if visibility and code not in visibility['allowedCodes']:continue
                try:
                    if visibility_reader:recheck_visible_tower(visibility_reader,visibility,code)
                    time.sleep(.5);raw,response=normal_json(session,path,purpose='guild-war-tower');selected=reviewed_tower(response,main,side,code)
                except Exception:
                    if visibility_reader:visibility_reader.close()
                    # Accept only validated response copies already saved; a
                    # partial attempt cannot replace a prior complete defense.
                    accept_directory(folder)
                    raise
                meta={'sourceKind':'normal-visible-guildwar-tower','gameVersion':'12.4.2','moduleSha256':NEW_SHA,
                      'capturedAt':datetime.now(timezone.utc).isoformat(),'responseSha256':hashlib.sha256(raw).hexdigest(),
                      'seasonNo':main['currentSeason']['seasonNo'],'battleNo':battle_number(main['currentSeason']['status']),
                      'seasonStatus':main['currentSeason']['status'],'side':side,'guildId':main[key]['gid'],'towerCode':code,
                      'mainCopySha256':hashlib.sha256((folder/'main.private.json').read_bytes()).hexdigest(),'result':selected}
                (folder/f'tower-{side}-{code}.private.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
                count+=1;defenders+=len(selected['guildWarDefenceDeckResponses'])
            if visibility_reader:
                visibility_reader.close();result['opponentReadState']='normal_visible_towers_captured' if len(visibility['allowedCodes'])==len(tower_paths(main,side)) else 'normal_visible_towers_captured_partial'
        documents=accept_directory(folder)
        from character_instance_progress import build as build_progress,save as save_progress
        save_progress(build_progress())
        result.update(towerResponsesSaved=count,defenderResponsesSaved=defenders,towerRecordsNormalized=True,
                      deployedTeams=sum(len(d['teams']) for record in documents if record['kind']=='deployed_defense' for tower in record['towers'] for d in tower.get('defenders') or []))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--use-authorized-runtime-session',action='store_true');p.add_argument('--probe-tower',action='store_true');p.add_argument('--capture-towers',action='store_true');p.add_argument('--previous-context',type=Path);p.add_argument('--side',choices=['ally','opponent']);args=p.parse_args()
    if not args.use_authorized_runtime_session:p.error('explicit authorized local guild session required')
    try:
        with acquisition_lock():result=collect(probe=args.probe_tower,capture_towers=args.capture_towers,previous_context=args.previous_context,sides=(args.side,) if args.side else ('ally','opponent'))
        print(json.dumps(result,ensure_ascii=False))
    except Exception as error:
        reason=str(error) if isinstance(error,(AcquisitionStopped,SessionUnavailable)) else 'runtime_context_or_shape_unavailable'
        print(json.dumps({'completed':False,'reason':reason,'oldDataPreserved':True,'credentialsPersisted':False}));raise SystemExit(1)
