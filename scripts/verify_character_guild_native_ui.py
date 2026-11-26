"""Affected UI checks: local portraits, native talent stages and current guild data."""
import hashlib,json,re,sqlite3
from contextlib import closing
from datetime import datetime,timezone
from browser_session import Browser,ROOT
from build_character_native_details import read_native_details,talent_stages
from character_instance_progress import observation_key


def main():
 native_id,native=read_native_details();cases=[]
 with closing(sqlite3.connect((ROOT/'data/local/lr.private.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
  war=json.loads(db.execute("SELECT s.payload FROM current_guild_war_sources c JOIN guild_war_sources s USING(source_id) WHERE s.kind='deployed_defense'").fetchone()[0])
  progress_id=db.execute("SELECT source_id FROM current_character_instance_sources WHERE scope='accepted-defense'").fetchone()[0]
  progress={key:json.loads(p) for key,p in db.execute('SELECT observation_id,payload FROM character_instance_progress WHERE source_id=?',(progress_id,))}
 tower=next(t for t in war['towers'] if t['code']==11);expected=[]
 for d in tower['defenders']:
  for team in d['teams']:
   for unit in team['units']:
    p=progress[observation_key('guildwar',war['sourceId'],d['playerId'],team['teamNo'],unit['position'],11)];t=talent_stages(native[unit['characterId']],p['talentGrade'])
    expected.append({'states':[s['state'] for s in t['steps']] if t else [],'descriptions':[s['description'] or '效果尚未對照' for s in t['steps']] if t else []})
 alias=hashlib.sha256(war['guildId'].encode()).hexdigest()[:20]
 with Browser('character-guild-native-acceptance',protocol_timeout=180) as b:
  for code,width in [('u1616e-brown',1440),('u1616e-brown',390),('u1174e-cony',390),('u0004u-leonard',390)]:
   b.navigate('http://127.0.0.1:3101/characters/'+code,width,'document.querySelector(".character-portrait img")!==null')
   decoded=b.evaluate('Promise.all(Array.from(document.querySelectorAll(".character-portrait img")).map(i=>i.decode().then(()=>i.naturalWidth>0).catch(()=>false)))')
   actual=b.evaluate('Array.from(document.querySelectorAll("#character-talents .native-talent-stages li p")).map(e=>e.textContent)')
   t=native[code]['talents'];wanted=[s['description'] or '效果尚未對照' for s in t['steps']] if t['steps'] else []
   checks={'localPortraitDecoded':len(decoded)==1 and all(decoded),'nativeStagesMatch':actual==wanted,'noHorizontalOverflow':b.evaluate('document.documentElement.scrollWidth<=innerWidth'),'noExternalBranding':not any(s in b.evaluate('document.body.innerText').lower() for s in ['rangerbook','warmycat'])}
   b.evaluate('document.querySelector(".character-portrait").scrollIntoView()');b.screenshot(code+'-'+str(width));cases.append({'case':'character-detail','characterId':code,'width':width,'checks':checks})
  for width in (1440,390):
   b.navigate(f'http://127.0.0.1:3101/guild/{alias}?tower=1',width,'document.querySelector(".war-selected-tower .war-unit")!==null')
   decoded=b.evaluate('Promise.all(Array.from(document.querySelectorAll(".war-selected-tower .character-portrait img")).map(i=>new Promise(resolve=>{const probe=new Image();probe.onload=()=>resolve(probe.naturalWidth>0);probe.onerror=()=>resolve(false);probe.src=i.src})))')
   actual=b.evaluate('Array.from(document.querySelectorAll(".war-selected-tower .war-unit")).map(u=>({states:Array.from(u.querySelectorAll(".instance-talents li")).map(l=>l.dataset.state),descriptions:Array.from(u.querySelectorAll(".instance-talents li p")).map(p=>p.textContent)}))')
   expected_time=b.evaluate('new Date('+json.dumps(war['capturedAt'])+').toLocaleString("zh-TW",{timeZone:"Asia/Taipei",hour12:false})')
   html=b.evaluate('document.documentElement.outerHTML');visible=b.evaluate('document.body.innerText')
   checks={'allVisibleTowerPortraitsDecoded':len(decoded)==len(expected) and all(decoded),'actualTalentGradeMatchesEveryPosition':actual==expected,'currentCapturedAtRetained':re.sub(r'\s+',' ',expected_time) in re.sub(r'\s+',' ',visible),'noRawFields':all(s not in html for s in ['enhanceValueRaw','enhanceTypeRaw','sourceFile','moduleSha256']),'noHorizontalOverflow':b.evaluate('document.documentElement.scrollWidth<=innerWidth')}
   b.evaluate('document.querySelector(".war-selected-tower .instance-talents").open=true;document.querySelector(".war-selected-tower .instance-talents").scrollIntoView()');b.screenshot('guild-talents-'+str(width));cases.append({'case':'guild-native-talents','width':width,'characters':len(expected),'checks':checks})
  b.navigate('http://127.0.0.1:3101/characters?q=u1616e-brown',390,'document.querySelector(".verified-gear-card")!==null')
  decoded=b.evaluate('Promise.all(Array.from(document.querySelectorAll(".verified-gear-card img")).map(i=>i.decode().then(()=>true).catch(()=>false)))');cases.append({'case':'catalogue','width':390,'checks':{'localImageOnFilteredCard':len(decoded)==1 and all(decoded),'noHorizontalOverflow':b.evaluate('document.documentElement.scrollWidth<=innerWidth')}})
  report={'verifiedAt':datetime.now(timezone.utc).isoformat(),'nativeSourceId':native_id,'guildSourceId':war['sourceId'],'progressSourceId':progress_id,'passed':len(cases)==7 and all(all(c['checks'].values()) for c in cases) and not b.errors,'cases':cases,'runtimeErrors':b.errors}
 (ROOT/'reports/character-guild-native-ui-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(report,ensure_ascii=False))
 if not report['passed']:raise SystemExit(1)


if __name__=='__main__':main()
