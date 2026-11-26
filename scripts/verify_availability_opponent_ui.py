"""Affected local pages: explicit template absence and a real ranked-guild defense."""
import hashlib,json,sqlite3,time
from contextlib import closing
from datetime import datetime,timezone
from browser_session import Browser,ROOT


def main():
 audit=json.loads((ROOT/'reports/reference-availability-audit.json').read_text(encoding='utf8'))
 none=next(r['characterId'] for r in audit['characters'] if set(r['referenceAvailability'].values())=={'absent'})
 empty_gear=next(r['itemCode'] for r in audit['equipment'] if all(r['referenceAvailability'][k]=='absent' for k in ['advanced','skillPlus','specPlus']))
 skill_gear=next(r['itemCode'] for r in audit['equipment'] if r['referenceAvailability']['skillPlus']=='present')
 spec_gear=next(r['itemCode'] for r in audit['equipment'] if r['referenceAvailability']['specPlus']=='present')
 with closing(sqlite3.connect((ROOT/'data/local/lr.private.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
  wars=[json.loads(p) for p, in db.execute('SELECT s.payload FROM current_guild_war_sources c JOIN guild_war_sources s USING(source_id)')]
  war=next(w for w in wars if w['kind']=='deployed_defense' and w.get('side')=='opponent' and w['seasonStatus']=='second_battle')
  overview=next(w for w in wars if w['kind']=='overview' and w['guildId']==war['guildId']);alias=hashlib.sha256(war['guildId'].encode()).hexdigest()[:20]
 cases=[]
 pages=[('character-none','/characters/'+none),('character-present','/characters/u1618e-ka'),('character-unlisted','/characters/u0004u-leonard'),('gear-none','/gear/'+empty_gear+'_nm'),('gear-skill','/gear/'+skill_gear+'_nm'),('gear-spec','/gear/'+spec_gear+'_nm'),('opponent','/guild/'+alias+'?tower=1'),('opponent-unread','/guild/'+alias+'?tower=7')]
 with Browser('availability-opponent-acceptance',protocol_timeout=180) as b:
  for case,path in pages:
   for width in (1440,390):
    b.navigate('http://127.0.0.1:3101'+path,width,'document.querySelector("main h1")?.getBoundingClientRect().height>0')
    if case.startswith(('character','gear')):
     for _ in range(60):
      if b.evaluate('Array.from(document.querySelectorAll(".collapse-controls button")).some(e=>Object.keys(e).some(k=>k.startsWith("__reactProps$")))'):break
      time.sleep(.1)
     b.evaluate('document.querySelectorAll("main .collapse-controls button:first-child").forEach(b=>b.click())')
    text=b.evaluate('document.querySelector("main").innerText');checks={'noHorizontalOverflow':b.evaluate('document.documentElement.scrollWidth<=innerWidth'),'noExternalBranding':all(s not in text.lower() for s in ['rangerbook','warmycat'])}
    if case=='character-none':checks['explicitAbsenceNotMissing']=all(s in text for s in ['此角色沒有技能','此角色沒有角色能力','此角色沒有覺醒能力候選','此角色未設定才能'])
    if case=='character-present':checks['realSkillsAndStartupRetained']='技能前搖' in text and '我正在卯足全力啊' in text and '四階段對照' in text
    if case=='character-unlisted':checks['unlistedDoesNotMeanAbsent']='未收錄此模板' in text and '技能詳細資料尚未取得' in text and '此角色未設定才能' in text
    if case=='gear-none':checks['explicitGearAbsence']=all(s in text for s in ['此裝備沒有高級效果','此裝備沒有 Skill+','此裝備沒有 Spec+']) and '模板參考基本效果' in text and '已對照 3 項' in text
    if case=='gear-skill':checks['skillPlusStillPresent']='此裝備沒有 Skill+' not in text and 'Skill+' in text
    if case=='gear-spec':checks['specPlusStillPresent']='此裝備沒有 Spec+' not in text and 'Spec+' in text
    if case.startswith('opponent'):
     checks['correctGuild']=overview['guildName'] in text;checks['partialCoverageVisible']='6／10' in text
     if case=='opponent-unread':checks['unreadNotEmpty']='此塔尚未讀取' in text and '此次正常回應確認沒有駐防配置' not in text
     else:
      count=sum(len(t['units']) for d in war['towers'][0]['defenders'] for t in d['teams'])
      checks['positionCount']=b.evaluate('document.querySelectorAll(".war-selected-tower .dv-card").length')==count
      b.evaluate('document.querySelector(".war-selected-tower .dv-card").click()')
      for _ in range(60):
       if b.evaluate('!!document.querySelector(".war-selected-tower .dv-unit-detail")'):break
       time.sleep(.1)
      actual=b.evaluate('document.querySelector(".war-selected-tower .dv-unit-detail").textContent')
      checks['actualGearAndCharacterFields']='實際強化 +5' in actual and 'Lv.' in actual and '雷納德點數' in actual and '數值尚未解析' not in actual
      if width==390:b.evaluate('document.querySelector(".war-selected-tower .dv-details").scrollIntoView()')
    if case.startswith('character'):b.evaluate('document.querySelector("#character-skills").scrollIntoView()')
    b.evaluate('new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))');b.screenshot(case+'-'+str(width));cases.append({'case':case,'width':width,'checks':checks});print(case,width,checks,flush=True)
  report={'verifiedAt':datetime.now(timezone.utc).isoformat(),'opponentSourceId':war['sourceId'],'passed':all(all(c['checks'].values()) for c in cases) and not b.errors,'cases':cases,'runtimeErrors':b.errors,'gameRequests':0}
 (ROOT/'reports/availability-opponent-ui-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 if not report['passed']:raise SystemExit(1)


if __name__=='__main__':main()
