"""Local browser acceptance for real character details and unknown/empty states."""
import json,sqlite3
from contextlib import closing
from datetime import datetime,timezone
from browser_session import Browser,ROOT


def main():
 with closing(sqlite3.connect((ROOT/'data/local/lr.private.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
  sid=db.execute("SELECT source_id FROM current_character_details WHERE scope='native-matched-reference'").fetchone()[0]
  data={code:json.loads(p) for code,p in db.execute('SELECT character_id,payload FROM character_template_details WHERE source_id=?',(sid,))}
 cases=[]
 with Browser('character-details-acceptance') as b:
  for code,width in [('u1618e-ka',1440),('u1618e-ka',390),('u1535e-brown',390),('u1646e-jessica',1440),('u0004u-leonard',390),('u001e-bella',390)]:
   b.navigate('http://127.0.0.1:3101/characters/'+code,width,'document.querySelector("#character-skills")!==null')
   r=data[code];text=b.evaluate('document.body.innerText');html=b.evaluate('document.documentElement.outerHTML')
   checks={'templateNotPlayerState':'未套用玩家等級、裝備與培養' in text,'awakeningCandidatesNotClaimedOwned':'不代表玩家已取得或啟用' in text,
           'noExternalBranding':not any(s in text.lower() for s in ['rangerbook','warmycat','外部來源']),
           'noVisibleEffectCodes':not any(s in text for s in ['SKILLEFF_','aab233_','sk1617_ka','ab701_team_2608']),
           'noRawDiagnostics':all(s not in html for s in ['candidateProbabilityRaw','probabilityMeaning','moduleBase','nativeDocumentSha256']),
           'noHorizontalOverflow':b.evaluate('document.documentElement.scrollWidth<=innerWidth'),
           'fiveSections':b.evaluate('document.querySelectorAll(".character-section").length')==5}
   if r['status']=='matched-reference':
    checks['skillCount']=b.evaluate('document.querySelectorAll(".character-skill-card").length')==len(r['skills'])
    checks['effectCount']=b.evaluate('document.querySelectorAll(".character-effect").length')==sum(len(s['effects']) for s in r['skills'])
    checks['skillNamesAndRates']=all(s['name'] in text and (str(s['activationRatePercent']).removesuffix('.0')+'%') in text and (str(s['cooldownSeconds']).removesuffix('.0')+' 秒') in text for s in r['skills'])
    checks['abilities']=b.evaluate('document.querySelectorAll("#character-abilities .character-ability-card").length')==len(r['abilities'])
    checks['awakeningCount']=b.evaluate('document.querySelectorAll("#character-awakening .character-ability-card").length')==len(r['awakeningAbilities'])
    checks['talents']=('主要才能' in text and '強化才能' in text) if r['talents'] else '本次模板資料未列技能' in text
    if code=='u1618e-ka':checks['actualKnownEffects']=all(s in text for s in ['+500%','攻擊力的 4500%','10 秒','350 點','毅力+','誘惑抗性','複製分身'])
   else:checks['unknownNotEmpty']='技能詳細資料尚未取得' in text and '角色能力尚未取得' in text and b.evaluate('document.querySelectorAll(".character-skill-card").length')==0
   b.evaluate('document.querySelector("#character-skills").scrollIntoView({block:"start"})');b.screenshot(code+'-'+str(width)+'-skills')
   if r.get('awakeningAbilities'):
    b.evaluate('document.querySelector("#character-awakening").scrollIntoView({block:"start"})');b.screenshot(code+'-'+str(width)+'-awakening')
   cases.append({'characterId':code,'width':width,'checks':checks})
   if not all(checks.values()):break
  b.navigate('http://127.0.0.1:3101/characters?details=awakening',390,'document.querySelector("select[name=details]")!==null')
  text=b.evaluate('document.body.innerText');cases.append({'page':'awakening-filter','width':390,'checks':{'realCandidateCharacters':'201 筆結果' in text,'filterSelected':b.evaluate('document.querySelector("select[name=details]").value')=='awakening','noHorizontalOverflow':b.evaluate('document.documentElement.scrollWidth<=innerWidth')}})
  report={'verifiedAt':datetime.now(timezone.utc).isoformat(),'sourceId':sid,'passed':len(cases)==7 and all(all(c['checks'].values()) for c in cases) and not b.errors,'cases':cases,'runtimeErrors':b.errors}
 (ROOT/'reports/character-detail-ui-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(report,ensure_ascii=False))
 if not report['passed']:raise SystemExit(1)


if __name__=='__main__':main()
