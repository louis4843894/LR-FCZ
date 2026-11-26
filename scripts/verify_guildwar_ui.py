"""Check actual local fortress pages, template links, unknowns and output privacy."""
import hashlib,json,sqlite3
from contextlib import closing
from browser_session import Browser,ROOT
from derive_guildwar_gear_values import read_rolls,observation_id,matching_value


def main():
 with closing(sqlite3.connect((ROOT/'data/local/lr.private.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
  documents=[json.loads(p) for (p,) in db.execute("SELECT s.payload FROM current_guild_war_sources c JOIN guild_war_sources s USING(source_id) WHERE c.kind='deployed_defense'")]
  native_ids=[g for (g,) in db.execute('SELECT guild_id FROM current_ranked_guild_rosters')]
  for (p,) in db.execute('SELECT s.payload FROM current_ranked_guild_rosters c JOIN guild_roster_sources s USING(source_id)'):native_ids.extend(m['playerId'] for m in json.loads(p)['members'])
  _,rolls=read_rolls(db)
 doc=next(d for d in documents if d['status']=='success');alias=hashlib.sha256(doc['guildId'].encode()).hexdigest()[:20]
 counts={t['code']:sum(len(team['units']) for d in t['defenders'] for team in d['teams']) for t in doc['towers']}
 records=[]
 with Browser('guildwar-options-acceptance') as b:
  for code,number,width in [(11,1,1440),(16,6,390),(31,10,390)]:
   b.navigate(f'http://127.0.0.1:3101/guild/{alias}?tower={number}',width,'document.querySelector(".war-deployment-summary")!==null')
   visible=b.evaluate('document.body.innerText');html=b.evaluate('document.documentElement.outerHTML')
   checks={'actualSummary':all(v in visible for v in ['10／10','25 位真人駐防','500 角色','1,499 件裝備']),
    'tenTowerLinks':b.evaluate('document.querySelectorAll("nav.war-tower-grid a").length')==10,
    'selectedTower':b.evaluate('document.querySelector("nav.war-tower-grid [aria-current=page]").innerText').startswith('第 '+str(number)+' 塔'),
    'actualSelectedUnits':b.evaluate('document.querySelectorAll(".war-selected-tower .war-unit").length')==counts[code],
    'realGearLinks':b.evaluate('Array.from(document.querySelectorAll(".war-selected-tower a")).filter(a=>a.getAttribute("href").startsWith("/gear/")).length')>0,
    'realCharacterLinks':b.evaluate('Array.from(document.querySelectorAll(".war-selected-tower a")).filter(a=>a.getAttribute("href").startsWith("/characters/")).length')==counts[code],
    'memberTowerLinks':b.evaluate('document.querySelectorAll(".guild-member-row a[href*=defender-]").length')==25,
    'unverifiedConditionsNotClaimedActive':'適用條件尚待核對' in visible and '觸發狀態尚待核對' in visible,
    'chineseSkillPlusModifierNotFinalSkill':'技能追加參數變化' in visible,
    'specialEffectsChineseAndActivationUnknown':'特化效果：' in visible and '觸發條件與重複效果的生效狀態尚待核對' in visible and 'SPC_' not in visible,
    'noVisibleNativeGearOrTowerCodes':'eq_' not in visible and '塔代碼' not in visible,
    'numberedTenTowers':b.evaluate('Array.from(document.querySelectorAll("nav.war-tower-grid strong")).map(n=>n.innerText)')==['第 '+str(n)+' 塔' for n in range(1,11)],
    'savedConfigurationNotCounted':'部署未確認' in visible,
    'noPrivateIdentities':all(value not in html for value in native_ids),
    'noExternalBranding':not any(value in visible.lower() for value in ('rangerbook','warmycat','外部來源')),
    'noLoginGate':'需要登入' not in visible,
    'noHorizontalOverflow':b.evaluate('document.documentElement.scrollWidth<=innerWidth')}
   first=b.evaluate('document.querySelector(".war-selected-tower .war-gear-name").innerText');href=b.evaluate('document.querySelector(".war-selected-tower .war-gear-name").href')
   tower=next(t for t in doc['towers'] if t['code']==code);defender=tower['defenders'][0];team=defender['teams'][0];unit=team['units'][0];gear=unit['equipment']['weapon']
   special_expected=[]
   for d in tower['defenders']:
    for t in d['teams']:
     for u in t['units']:
      for slot in ['weapon','armor','accessory']:
       r=rolls.get(observation_id(doc,code,d['playerId'],t,u,slot));extra=r.get('supplementarySpecial') if r else None
       if extra and extra['state']=='values_reconstructed':special_expected.append(extra)
   special_actual=b.evaluate('Array.from(document.querySelectorAll(".war-selected-tower .war-special-option")).map(e=>e.innerText)')
   checks['specialDescriptionsMatchActualInstances']=len(special_actual)==len(special_expected)>0 and all(all(s[k] in text for k in ['name','normalText','description']) and ('特化強化 +'+str(s['specialEnhancement'])) in text for text,s in zip(special_actual,special_expected))
   record=rolls.get(observation_id(doc,code,defender['playerId'],team,unit,'weapon'))
   expected=[{'index':a['index'],'value':r['value'],'unit':r['unit']} for a in gear['actualEffects']['entries'] if (r:=matching_value(record,defender['playerId'],gear,a))]
   actual=b.evaluate('Array.from(document.querySelector(".war-selected-tower .war-instance-gear").querySelectorAll(".war-effect-value")).map(e=>e.textContent)')
   checks['valuesMatchActualBoundInstances']=bool(expected) and all(float(actual[e['index']].replace('%','').replace(',','').replace(' 秒',''))==e['value'] and ('%' in actual[e['index']])==(e['unit']=='PERCENT') for e in expected)
   b.evaluate('document.querySelector(".war-selected-tower .war-value-evidence").open=true')
   checks['reconstructionNotVisualClaim']='依原生定義與此件實例分級還原' in b.evaluate('document.body.innerText') and '尚未逐項目視核對' in b.evaluate('document.body.innerText')
   b.evaluate('document.querySelector(".war-selected-tower .war-template-reference").open=true')
   checks['chineseTemplateEffects']=b.evaluate('document.querySelector(".war-selected-tower .war-template-reference").innerText.includes("基本效果")&&document.querySelector(".war-selected-tower .war-template-reference").innerText.includes("模板數值範圍")')
   checks['embeddedLevelControlsHidden']=b.evaluate('document.querySelectorAll(".war-selected-tower .reference-level").length===0')
   b.evaluate('document.querySelector(".war-selected-tower .war-instance-gear").scrollIntoView({block:"start"})');b.screenshot(f'tower-{number}-{width}')
   b.evaluate('document.querySelector(".war-selected-tower .war-special-option").scrollIntoView({block:"center"})');b.screenshot(f'special-option-tower-{number}-{width}')
   b.navigate(href,width,'document.querySelector(".detail-heading h2")!==null')
   checks['nameMatchesCataloguePage']=b.evaluate('document.querySelector(".detail-heading h2").innerText')==first
   records.append({'towerCode':code,'towerNumber':number,'width':width,'checks':checks})
   if not all(checks.values()):break
  report={'passed':len(records)==3 and all(all(r['checks'].values()) for r in records) and not b.errors,'cases':records,'runtimeErrors':b.errors}
 (ROOT/'reports/guildwar-special-option-ui-validation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
 print(json.dumps(report))
 if not report['passed']:raise SystemExit(1)


if __name__=='__main__':main()
