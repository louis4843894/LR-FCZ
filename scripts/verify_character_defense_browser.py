"""Local browser checks for actual native characters and one real defense snapshot."""
import argparse,base64,hashlib,json,subprocess,sys,time,urllib.request,urllib.parse,sqlite3,uuid
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'data/research/runtime.private/python'))
from websockets.sync.client import connect
BASE='http://127.0.0.1:3101';OUT=ROOT/'data/research/runtime.private/character-defense-browser';OUT.mkdir(exist_ok=True)
character_source=json.loads((ROOT/'data/normalized/verified-characters.json').read_text(encoding='utf8'))
guild_source=json.loads((ROOT/'data/normalized/guild-roster.private.json').read_text(encoding='utf8'))
parser=argparse.ArgumentParser();parser.add_argument('--scope',choices=['all','characters','rankings','guild-defense','source-routing'],default='all');parser.add_argument('--case',action='append',help='Run only named affected cases');args=parser.parse_args()
target_guild=guild_source['name']
if (ROOT/'data/local/lr.private.sqlite').exists():
    with sqlite3.connect((ROOT/'data/local/lr.private.sqlite').resolve().as_uri()+'?mode=ro',uri=True) as db:
        row=db.execute("SELECT target_name FROM collection_targets WHERE module='guild'").fetchone()
        if row:target_guild=row[0]
target_pending=target_guild!=guild_source['name']

defense_source=json.loads((ROOT/'data/normalized/defense-teams.private.json').read_text(encoding='utf8'))
ranked_keys=set();ranking_ids=[];ranked_player=None;ranking_snapshot=None;current_ranking_players=0;bronze_valid_top10=0;ranking_scopes=[]
ranked_name=None;bronze_name=None;ranked_members=[];enhancement_sample=None
with sqlite3.connect((ROOT/'data/local/lr.private.sqlite').resolve().as_uri()+'?mode=ro',uri=True) as db:
    if db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ranking_snapshots'").fetchone():
        for uid,payload in db.execute('SELECT player_id,payload FROM ranking_defense_attempts'):
            row=json.loads(payload)
            if row['status'] in ('success','partial'):ranked_keys.update((uid,sid) for sid in row['defenseSnapshotIds'])
        for payload, in db.execute('SELECT payload FROM ranking_snapshots'):
            ranking_ids.extend(p['playerId'] for p in json.loads(payload)['players'])
        current_ranking_players=sum(len(json.loads(p)["players"]) for p, in db.execute("SELECT r.payload FROM current_rankings c JOIN ranking_snapshots r USING(snapshot_id)"))
        ranking_scopes=[r[0] for r in db.execute('SELECT scope_label FROM current_rankings')]
        for source_id,payload in db.execute('SELECT r.snapshot_id,r.payload FROM current_rankings c JOIN ranking_snapshots r USING(snapshot_id)'):
            source=json.loads(payload)
            for player in source['players']:
                row=db.execute('SELECT payload FROM ranking_defense_attempts WHERE ranking_snapshot_id=? AND player_id=? ORDER BY attempted_at DESC LIMIT 1',(source_id,player['playerId'])).fetchone()
                if not row:continue
                ids=set(json.loads(row[0])['defenseSnapshotIds'])
                members=[m for t in defense_source['snapshots'] if t['playerId']==player['playerId'] and t['snapshotId'] in ids for m in (t['members'] or [])]
                if any(g.get('state')=='equipped' and g.get('enhancement')==2 for m in members for g in m['equipment'].values()):
                    enhancement_sample={'alias':hashlib.sha256(player['playerId'].encode()).hexdigest()[:12],'snapshot':source_id,'scope':source['scope']['label'],'rank':player['rank'],'members':members};break
            if enhancement_sample:break
        current=db.execute("SELECT r.payload FROM current_rankings c JOIN ranking_snapshots r USING(snapshot_id) WHERE c.scope_label='傳奇'").fetchone()
        if current:
            ranking=json.loads(current[0]);ranking_snapshot=ranking['snapshotId']
            candidate=ranking['players'][0];ranked_player=hashlib.sha256(candidate['playerId'].encode()).hexdigest()[:12]
            ranked_name=candidate['displayName']
            row=db.execute('SELECT payload FROM ranking_defense_attempts WHERE ranking_snapshot_id=? AND player_id=? ORDER BY attempted_at DESC LIMIT 1',(ranking_snapshot,candidate['playerId'])).fetchone()
            if row:
                ids=set(json.loads(row[0])['defenseSnapshotIds'])
                ranked_members=[m for t in defense_source['snapshots'] if t['playerId']==candidate['playerId'] and t['snapshotId'] in ids for m in (t['members'] or [])]
with sqlite3.connect((ROOT/'data/local/lr.private.sqlite').resolve().as_uri()+'?mode=ro',uri=True) as db:
    bronze=db.execute("SELECT r.payload FROM current_rankings c JOIN ranking_snapshots r USING(snapshot_id) WHERE c.scope_label='青銅'").fetchone()
    if bronze:
        source=json.loads(bronze[0]);latest={};bronze_name=source['players'][0]['displayName']
        for uid,payload in db.execute('SELECT player_id,payload FROM ranking_defense_attempts WHERE ranking_snapshot_id=? ORDER BY attempted_at',(source['snapshotId'],)):latest[uid]=json.loads(payload)
        for player in source['players']:
            attempt=latest.get(player['playerId'])
            if player['rank']>10 or not attempt or attempt['status'] not in ('success','partial'):continue
            selected=[t for t in defense_source['snapshots'] if t['playerId']==player['playerId'] and t['snapshotId'] in attempt['defenseSnapshotIds'] and t['isSelected'] is True]
            if len(selected)==1 and selected[0]['status']=='success' and not selected[0].get('unobservedPositionIndices') and selected[0]['members'] is not None and all(m['characterState']=='present' and m['characterId'] for m in selected[0]['members']):bronze_valid_top10+=1

defense_source['snapshots']=[t for t in defense_source['snapshots'] if (t['playerId'],t['snapshotId']) not in ranked_keys]
latest={}
for row in defense_source['snapshots']:
    if row['purpose']!='pvp_defense':continue
    key=(row.get('guildId'),row['playerId'],row['teamId']);before=latest.get(key)
    if before is None or datetime.fromisoformat(row['retrievedAt'])>datetime.fromisoformat(before['retrievedAt']):latest[key]=row
teams=list(latest.values());players=len({t['playerId'] for t in teams})
def members_of(rows):return [m for t in rows if t['status']=='success' for m in t['members']]
owner=defense_source['snapshots'][0]['playerId']
owner_key=hashlib.sha256(owner.encode()).hexdigest()[:12]
all_members=members_of([t for t in teams if t['playerId']==owner])
enhancement5=sum(e.get('enhancement')==5 for m in all_members for e in m['equipment'].values())
member=guild_source['members'][0];member_alias=hashlib.sha256(json.dumps([guild_source['guildId'],member['playerId']],separators=(',',':'),ensure_ascii=False).encode()).hexdigest()[:20]
member_teams=[t for t in teams if t['playerId']==member['playerId']]
private_ids=[guild_source['guildId'],*[m['playerId'] for m in guild_source['members']],*[t['playerId'] for t in teams],*ranking_ids]
owner=defense_source['snapshots'][0]['playerId']
debug_profile=OUT/('profile-'+uuid.uuid4().hex[:10])
process=subprocess.Popen([r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe','--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--remote-debugging-port=0','--remote-debugging-address=127.0.0.1','--user-data-dir='+str(debug_profile),'about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=0x08000000)
results=[];errors=[];sequence=0;passed=False
try:
    for _ in range(40):
        try:
            port=int((debug_profile/'DevToolsActivePort').read_text().splitlines()[0])
            tabs=json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json',timeout=1));break
        except Exception:time.sleep(.5)
    else:raise RuntimeError('Edge did not start')
    tab=next(t for t in tabs if t['type']=='page');ws=connect(tab['webSocketDebuggerUrl'],max_size=20*1024*1024)
    def call(method,params=None):
        global sequence
        sequence+=1;target=sequence;ws.send(json.dumps({'id':target,'method':method,'params':params or {}}))
        while True:
            msg=json.loads(ws.recv(timeout=45))
            if msg.get('method')=='Runtime.exceptionThrown':errors.append(msg['params']['exceptionDetails'].get('text','exception'))
            if msg.get('id')==target:
                if 'error' in msg:raise RuntimeError(str(msg['error']))
                return msg.get('result',{})
    def evaluate(js):
        result=call('Runtime.evaluate',{'expression':js,'returnByValue':True,'awaitPromise':True})
        if 'exceptionDetails' in result:raise RuntimeError(str(result['exceptionDetails']))
        return result['result'].get('value')
    call('Runtime.enable');call('Page.enable')
    cases=[('characters-desktop','/characters',1440,f"{len(character_source['records'])} 筆結果"),('characters-search','/characters?q=u1618e-ka',390,'1 筆結果'),('character-detail','/characters/u1618e-ka',390,'日比野卡夫卡'),('defense-desktop','/pvp/observations?player='+owner_key,1440,'PVP 防禦隊伍'),('defense-mobile','/pvp/observations?player='+owner_key,390,'PVP 防禦隊伍'),('characters-last-page','/characters?page=101',390,'第 101／101 頁'),('guild-desktop','/guild',1440,target_guild+' 公會'),('guild-mobile','/guild',390,target_guild+' 公會'),('guild-search','/guild?q=nat2',390,'1 位成員')]
    cases.extend((name,'/guild/members/'+member_alias,width,member['name']+' 的 PVP 防禦') for name,width in [('member-desktop',1440),('member-mobile',390)])
    if target_pending:cases=[c for c in cases if c[0]!='guild-search']
    if args.scope in ('guild-defense','source-routing'):cases=[c for c in cases if not c[0].startswith('character')]
    cases.extend([('ranking-desktop','/pvp',1440,'PVP 排行與防禦'),('ranking-mobile','/pvp',390,'PVP 排行與防禦'),('status-desktop','/data-status',1440,'完成度與尚未完成項目'),('status-mobile','/data-status',390,'完成度與尚未完成項目')])
    if args.scope=='characters':
        cases=[c for c in cases if c[0].startswith('character')]
        star_rows=[r for r in character_source['records'] if r.get('starCount')==9]
        if star_rows:cases.append(('characters-star-filter','/characters?star=9',390,f'{len(star_rows)} 筆結果'))
        stars_known=sum(r.get('starCount') is not None for r in character_source['records'])
        cases.append(('character-coverage-status','/data-status',390,f"角色星等已確認 {stars_known}／{len(character_source['records'])}"))
    if args.scope=='rankings':
        if not ranked_player:raise RuntimeError('real ranking defense source required')
        cases=[('rank-list-desktop','/pvp?scope='+urllib.parse.quote('傳奇')+'&top=10',1440,'傳奇排行榜'),('rank-list-mobile','/pvp?scope='+urllib.parse.quote('傳奇')+'&top=10',390,'傳奇排行榜'),('rank-bronze','/pvp?scope='+urllib.parse.quote('青銅')+'&top=10',390,'青銅排行榜'),('rank-player-desktop',f'/pvp/players/{ranked_player}?snapshot={ranking_snapshot}',1440,ranked_name),('rank-player-mobile',f'/pvp/players/{ranked_player}?snapshot={ranking_snapshot}',390,ranked_name),('rank-status','/data-status',390,f'真實排行榜已取得 {current_ranking_players} 位玩家')]
        cases.extend(('rank-scope-'+str(i),'/pvp?scope='+urllib.parse.quote(scope)+'&top=100',390,scope+'排行榜') for i,scope in enumerate(ranking_scopes) if scope not in ('傳奇','青銅'))
    if args.scope=='rankings':cases.append(('rank-full-range','/pvp?scope='+urllib.parse.quote('傳奇')+'&top=200',1440,'傳奇排行榜'))
    if args.scope=='rankings' and enhancement_sample:
        cases.append(('rank-enhancement-sample',f"/pvp/players/{enhancement_sample['alias']}?snapshot={enhancement_sample['snapshot']}",390,f"{enhancement_sample['scope']}排行榜第 {enhancement_sample['rank']} 名"))
    if args.case:cases=[case for case in cases if case[0] in args.case]
    if not cases:raise RuntimeError('requested browser cases unavailable')
    for name,path,width,text in cases:
        call('Emulation.setDeviceMetricsOverride',{'width':width,'height':900,'deviceScaleFactor':1,'mobile':width<700})
        call('Page.navigate',{'url':BASE+path})
        for _ in range(160):
            if evaluate('document.readyState==="complete" && document.body.innerText.includes('+json.dumps(text)+')'):break
            time.sleep(.2)
        else:raise RuntimeError('page readiness: '+name)
        evaluate('document.fonts.ready.then(()=>true)')
        visible=evaluate('document.body.innerText');html=evaluate('document.documentElement.outerHTML')
        checks={'expectedText':text in visible,'noHorizontalOverflow':evaluate('document.documentElement.scrollWidth<=innerWidth'),'noRawOwnerId':owner not in html,'noRawMemoryFields':not any(x in html for x in ['runtime.private','objectAddress','moduleBase','gradeCipherFile','rawRecordSha256'])}
        if name.startswith('guild') and target_pending:
            checks.update({'targetGuildHonest':target_guild in visible and '尚未取得' in visible,'noOldGuildMemberCards':evaluate('document.querySelectorAll(".guild-member").length')==0,'noRawIds':all(value not in html for value in private_ids)})
        if name.startswith('ranking'):
            checks.update({'rankingSourceRequired':('傳奇排行榜' in visible if ranking_snapshot else '排名樣本為 0' in visible),'historySeparate':'非排名歷史觀察' in visible,'noUnrankedTeamsOnRanking':evaluate('document.querySelectorAll(".defense-member").length')==0})
        if name.startswith('status'):
            checks.update({'targetAndUnknownHonest':target_guild in visible and '尚未完成' in visible,'rankedSampleCountHonest':(f'真實排行榜已取得 {current_ranking_players} 位玩家' in visible if ranking_snapshot else '排名樣本 0 筆' in visible),'noRawIds':all(value not in html for value in private_ids)})
        if name.startswith('guild') and not target_pending:
            checks.update({'noRawGuildOrPlayerId':all(value not in html for value in private_ids),'realRosterCount':f"實際取得 {guild_source['membersRetrieved']} 位" in visible,'capacityNotTotal':f"{guild_source['observedMemberTotal']}／{guild_source['memberCapacity']}" in visible,'unknownDefense':'配置未知' in visible,'weeklyUpdateRule':'每週二 12:00' in visible,'noInventedEnhancement':'強化 +5' not in visible,'memberCards':evaluate('document.querySelectorAll(".guild-member").length')==(1 if name=='guild-search' else len(guild_source['members']))})
        if name=='characters-last-page':checks['fiveRemaining']=evaluate('document.querySelectorAll(".verified-gear-card").length===5')
        if name.startswith('defense'):
            checks.update({'actualMemberCount':evaluate('document.querySelectorAll(".defense-member").length')==len(all_members),'actualSlotCount':evaluate('document.querySelectorAll(".defense-slots > div").length')==len(all_members)*3,'actualEnhancementCount':visible.count('強化 +5')==enhancement5,'bothDefenseTeams':'防禦 A 隊' in visible and '防禦 B 隊' in visible,'BVisualReviewUnknown':'尚未目視核對此隊' in visible,'captureVersionShown':'12.4.0' in visible,'allNativeNames':all(n in visible for n in ['日比野卡夫卡','山參熊大','始皇帝','太陽巨蟹座莎莉','旅館老闆娘潔西卡']),'actualEffectsUnknown':'詞條尚未解析' in visible,'playerCountHonest':f'已取得 {players} 位玩家' in visible and '單一玩家樣本' in visible,'onDemandUpdateRule':'PVP 防禦可隨時' in visible})
        if name.startswith('member'):
            checks.update({'exactOwnerMemberCount':evaluate('document.querySelectorAll(".defense-member").length')==len(members_of(member_teams)),'noRawIds':all(value not in html for value in private_ids),'noOwnTeamFallback':'u1618e-ka' not in html if not member_teams else True,'separatePvpPurpose':'PVP 防禦隊伍' in visible,'unknownNotEmpty':'尚無此用途的隊伍快照' in visible if not member_teams else True,'nativeValuesNotMultipliedTwice':evaluate('document.querySelectorAll(".native-attribute-value").length')==90 and '+444.0%' in visible and '-30.0%' in visible and '+50.4%' in visible if member_teams else True,'unparsedSpecialsRemainUnknown':'數值尚未解析' in visible if member_teams else True})
        if name.startswith('member') and member_teams:
            checks.update({'externalMappingShown':evaluate('document.querySelectorAll(".external-attribute-mapping").length')>0,'mappingNotActualValue':'效果種類已對上，實際數值尚未確認' in visible,'candidateNotConfirmed':'同裝備模板候選，尚未確認實例對應' in visible,'externalBaseRangeSeparated':'模板 +0 範圍' in visible})
        if name=='character-detail':
            actual=next(r for r in character_source['records'] if r['characterId']=='u1618e-ka')
            checks.update({'starsMatchNativeTemplate':(f"{actual['starCount']} 星" in visible and '星等尚未確認' not in visible) if actual.get('starCount') is not None else '星等尚未確認' in visible,'nativeSkillReference':'sk1617_ka' in visible,'skillDetailsUnknown':'技能描述與數值尚未解析' in visible})
        if name=='characters-star-filter':checks.update({'starFilterEnabled':evaluate('!document.querySelector("select[name=star]").disabled'),'onlyRequestedStarCards':evaluate('Array.from(document.querySelectorAll(".verified-gear-card")).every(el=>el.innerText.includes("9 星"))'),'selectedStarPreserved':evaluate('document.querySelector("select[name=star]").value==="9"')})
        if name.startswith('rank-'):
            checks['noPrivateRankingPlayerIds']=all(value not in html for value in private_ids)
        if name.startswith('rank-list'):
            checks.update({'tenActualRanks':evaluate('document.querySelectorAll(".ranking-player").length')==10,'nativeLeader':f'第 1 名 · {ranked_name}' in visible,'actualRankScope':'Top N 指玩家排名範圍' in visible,'sampleOnly':'不代表整體環境' in visible,'noWinRate':'未計算勝率' in visible,'noUnrankedProfiles':evaluate('document.querySelectorAll(".defense-member").length')==0,'allCapturedScopesSelectable':set(evaluate('Array.from(document.querySelectorAll("select[name=scope] option")).map(el=>el.value)'))==set(ranking_scopes)})
        if name=='rank-full-range':checks.update({'twoHundredActualRanks':evaluate('document.querySelectorAll(".ranking-player").length')==200,'selectedTeamDenominator':'角色分母：200 位' in visible,'equipmentDenominator':'裝備分母：200 位' in visible})
        if name.startswith('rank-scope-'):checks.update({'oneHundredActualRanks':evaluate('document.querySelectorAll(".ranking-player").length')==100,'rankingTimeShown':'名單最近核對' in visible,'noUnrankedProfiles':evaluate('document.querySelectorAll(".defense-member").length')==0})
        if name=='rank-status':checks['allScopesInCoverageTable']=all(scope in visible for scope in ranking_scopes)
        if name=='rank-bronze':checks.update({'bronzeDefenseCount':f'防禦有效樣本 {bronze_valid_top10} 位' in visible,'tenBronzePlayers':evaluate('document.querySelectorAll(".ranking-player").length')==10,'bronzeLeader':bronze_name in visible})
        if name.startswith('rank-player'):
            checks.update({'exactRankOne':'傳奇排行榜第 1 名' in visible,'actualUnitCount':evaluate('document.querySelectorAll(".defense-member").length')==len(ranked_members),'actualSlotCount':evaluate('document.querySelectorAll(".defense-slots > div").length')==len(ranked_members)*3,'actualEnhancement':visible.count('強化 +5')==sum(g.get('enhancement')==5 for m in ranked_members for g in m['equipment'].values()),'exactOwnerName':f'玩家：{ranked_name}' in visible,'rankingBackLink':evaluate('Array.from(document.querySelectorAll("a")).some(a=>a.innerText==="返回排行榜")'),'noFalseNoRanking':'尚無排名樣本' not in visible,'notFalselyVisuallyReviewed':'已核對遊戲防禦畫面' not in visible,'checkedTimeSeparated':'防禦最近核對' in visible,'unknownActualValuesPreserved':evaluate('document.querySelectorAll(".native-attribute-value").length')==0})
        if name=='rank-enhancement-sample':
            sample=enhancement_sample['members'];counts={}
            for m in sample:
                for g in m['equipment'].values():
                    if g['state']=='equipped':counts[g['enhancement']]=counts.get(g['enhancement'],0)+1
            checks.update({'actualUnitCount':evaluate('document.querySelectorAll(".defense-member").length')==len(sample),'actualSlotCount':evaluate('document.querySelectorAll(".defense-slots > div").length')==len(sample)*3,'allEnhancementValuesMatchSource':all(visible.count(f'強化 +{value}')==count for value,count in counts.items()),'observedPlusTwoNotReplacedWithFive':'強化 +2' in visible,'noInventedNumericEffects':evaluate('document.querySelectorAll(".native-attribute-value").length')==0})
        png=call('Page.captureScreenshot',{'format':'png','captureBeyondViewport':True});(OUT/(name+'.png')).write_bytes(base64.b64decode(png['data']))
        results.append({'case':name,'width':width,'checks':checks})
        if not all(checks.values()):raise RuntimeError('failed case: '+json.dumps(results[-1]))
    ws.close();passed=not errors
finally:
    report='rankings-browser-validation.json' if args.scope=='rankings' else 'character-stars-browser-validation.json' if args.scope=='characters' else 'source-routing-browser-validation.json' if args.scope=='source-routing' else 'member-defense-browser-validation.json' if args.scope=='guild-defense' else 'character-defense-browser-validation.json'
    if args.case:report='rankings-enhancement-browser-validation.json'
    (ROOT/'reports'/report).write_text(json.dumps({'passed':passed,'cases':results,'runtimeErrors':errors},indent=2),encoding='utf8')
    process.terminate()
    try:process.wait(timeout=5)
    except subprocess.TimeoutExpired:process.kill()
print(json.dumps({'passed':passed,'cases':len(results),'runtimeErrors':errors}))
if not passed:raise SystemExit(1)
