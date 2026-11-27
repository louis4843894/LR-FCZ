"""Local UI acceptance against accepted SQLite observations; no game requests."""
import argparse,hashlib,json,re,sqlite3,time
from contextlib import closing
from datetime import datetime,timezone
from browser_session import Browser,ROOT
from character_instance_progress import observation_key


def digest(value):
 return hashlib.sha256(json.dumps(value,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def inputs():
 with closing(sqlite3.connect((ROOT/'data/local/lr.private.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
  def payload(sql,args=()):return json.loads(db.execute(sql,args).fetchone()[0])
  war=payload("SELECT s.payload FROM current_guild_war_sources c JOIN guild_war_sources s USING(source_id) WHERE s.kind='deployed_defense'")
  ranking=payload("SELECT s.payload FROM current_rankings c JOIN ranking_snapshots s USING(snapshot_id) WHERE c.scope_label LIKE '%大師%' ORDER BY c.scope_label LIMIT 1")
  player=ranking['players'][0]
  attempt=payload('SELECT payload FROM ranking_defense_attempts WHERE ranking_snapshot_id=? AND player_id=? ORDER BY attempted_at DESC LIMIT 1',(ranking['snapshotId'],player['playerId']))
  document=payload("SELECT d.payload FROM current_documents c JOIN documents d USING(sha256) WHERE c.filename='defense-teams.private.json'")
  pvps=[t for t in document['snapshots'] if t['playerId']==player['playerId'] and t['snapshotId'] in attempt['defenseSnapshotIds']]
  progress_id=db.execute("SELECT source_id FROM current_character_instance_sources WHERE scope='accepted-defense'").fetchone()[0]
  progress={key:json.loads(p) for key,p in db.execute('SELECT observation_id,payload FROM character_instance_progress WHERE source_id=?',(progress_id,))}
  rolls={}
  for scope in ('guildwar','ranked-http'):
   source=db.execute('SELECT source_id FROM current_gear_rolls WHERE scope=?',(scope,)).fetchone()[0]
   rolls[scope]={key:json.loads(p) for key,p in db.execute('SELECT observation_id,payload FROM gear_instance_rolls WHERE source_id=?',(source,))}
 chars={r['characterId']:r for r in json.loads((ROOT/'data/normalized/verified-characters.json').read_text(encoding='utf8'))['records']}
 guild_alias=hashlib.sha256(war['guildId'].encode()).hexdigest()[:20]
 pvp_alias=hashlib.sha256(player['playerId'].encode()).hexdigest()[:12]
 expected={}
 defender=war['towers'][0]['defenders'][0]
 for mode,teams in [('pvp',pvps),('guild',defender['teams'])]:
  rows=[]
  for t in teams:
   for u in t.get('members',t.get('units',[])):
    pos=u.get('memberIndex',u.get('position'));owner=player['playerId'] if mode=='pvp' else defender['playerId']
    source=t['snapshotId'] if mode=='pvp' else war['sourceId'];team_no=t['teamId'].split('/')[-1] if mode=='pvp' else t['teamNo'];tower=None if mode=='pvp' else war['towers'][0]['code']
    p=progress.get(observation_key('pvp' if mode=='pvp' else 'guildwar',source,owner,team_no,pos,tower))
    gear=[]
    for slot in ('weapon','armor','accessory'):
     g=u['equipment'][slot]
     key=digest([source,owner,pos,slot]) if mode=='pvp' else digest(['guildwar',source,tower,owner,team_no,pos,slot])
     roll=rolls['ranked-http' if mode=='pvp' else 'guildwar'].get(key);values=[]
     for a in (g.get('actualEffects') or {}).get('entries',[]):
      v=a if a.get('valueVerified') and a.get('enhancementIncluded') else next((r for r in (roll or {}).get('entries',[]) if all(r.get(k)==a.get(k) for k in ['index','attributeId','valueGradeRaw','sourceField']) and r.get('valueVerified') and r.get('enhancementIncluded')),None)
      values.append(v)
     gear.append({'slot':slot,'state':g['state'],'equipmentId':g.get('equipmentId'),'enhancement':g.get('enhancement'),'values':values})
    rows.append({'id':u['characterId'],'position':pos,'stars':chars[u['characterId']]['starCount'],'progress':p,'gear':gear})
  expected[mode]=rows
 return {'pvp':f"/pvp/players/{pvp_alias}?snapshot={ranking['snapshotId']}",'guild':f'/guild/{guild_alias}?tower=1'},expected,{'guildSourceId':war['sourceId'],'rankingSnapshotId':ranking['snapshotId'],'progressSourceId':progress_id},[player['playerId'],defender['playerId']]


def wait_for(b,js):
 for _ in range(80):
  if b.evaluate(js):return
  time.sleep(.1)
 raise AssertionError('UI state did not settle')


def main():
 parser=argparse.ArgumentParser();parser.add_argument('--only',help='Comma-separated affected case names; retain unaffected theme checks.');parser.add_argument('--resume',action='store_true');args=parser.parse_args()
 only=set(args.only.split(',')) if args.only else None
 urls,expected,sources,private_ids=inputs();cases=[]
 if only:
  previous=json.loads((ROOT/('reports/defense-viewer-ui-validation.json' if args.resume else 'reports/defense-viewer-theme-validation.json')).read_text(encoding='utf8'))
  if previous['sources']!=sources:raise ValueError('Cannot reuse checks from a different data version')
  cases=[dict(c,retainedFrom=previous['verifiedAt']) for c in previous['cases'] if c['case'] not in only]
  if not all(all(c['checks'].values()) for c in cases):raise ValueError('Cannot retain failed cases')
 def checkpoint():
  (ROOT/'reports/defense-viewer-ui-validation.json').write_text(json.dumps({'verifiedAt':datetime.now(timezone.utc).isoformat(),'sources':sources,'passed':False,'inProgress':True,'cases':cases},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 with Browser('defense-viewer-acceptance',protocol_timeout=180) as b:
  for mode in ('pvp','guild'):
   if only and mode+'-team-viewer' not in only:continue
   for width in (1440,390):
    root='.defense-player-view .team-viewer:not(dialog)' if mode=='pvp' else '.war-selected-tower .team-viewer:not(dialog)'
    b.navigate('http://127.0.0.1:3101'+urls[mode],width,'document.querySelector('+json.dumps(root+' .dv-card')+')!==null')
    wait_for(b,'Object.keys(document.querySelector('+json.dumps(root+' .dv-expand')+')).some(k=>k.startsWith("__reactProps$"))')
    if width==390:
     b.evaluate('document.querySelector('+json.dumps(root)+').scrollIntoView()');b.screenshot(mode+'-cards-mobile')
    b.evaluate('document.querySelector('+json.dumps(root+' .dv-expand')+').click()');wait_for(b,'!!document.querySelector("dialog[open]")')
    card_count=b.evaluate('document.querySelectorAll("dialog[open] .dv-card").length')
    checks={'actualPositionCount':card_count==len(expected[mode]),'emptyDetailBeforeSelection':b.evaluate('!!document.querySelector("dialog[open] .dv-detail-empty")'),'modalFocusContained':b.evaluate('!!document.activeElement.closest("dialog[open]")')}
    # Exercise each position, including repeated character/equipment templates.
    verified_values=0;binding_ok=True;star_ok=True;slot_ok=True;talent_ok=True
    for i,row in enumerate(expected[mode]):
     b.evaluate(f'document.querySelectorAll("dialog[open] .dv-card")[{i}].click()')
     wait_for(b,'document.querySelector("dialog[open] .dv-unit-detail")?.dataset.unitKey===document.querySelector("dialog[open] .dv-card[aria-pressed=true]")?.dataset.unitKey')
     actual=b.evaluate('(()=>{const d=document.querySelector("dialog[open] .dv-unit-detail");return {href:d.querySelector(".dv-detail-hero h3 a")?.getAttribute("href"),hero:d.querySelector(".dv-detail-hero").textContent,talents:d.querySelector(".dv-talents summary").textContent,stars:d.querySelector(".dv-portrait .dv-stars")?.title,gear:Array.from(d.querySelectorAll(".dv-equipment")).map(e=>({slot:e.getAttribute("aria-label"),state:e.querySelector(".dv-gear-preview").dataset.state,href:e.querySelector(".dv-equipment-name a")?.getAttribute("href"),text:e.querySelector(".dv-equipment-heading").textContent,values:Array.from(e.querySelectorAll(".dv-effects li>strong")).map(v=>v.textContent)}))}})()')
     binding_ok &= actual['href']=='/characters/'+row['id']
     star_ok &= actual['stars']==str(row['stars'])+' 星'
     p=row['progress']
     if p:
      binding_ok &= f"Lv. {p['level']}" in actual['hero'] and f"{p['leonardPoints']} 點" in actual['hero']
      talent_ok &= f"第 {p['talentGrade']} 階" in actual['talents']
     for a,g in zip(actual['gear'],row['gear']):
      slot_ok &= a['slot']=={'weapon':'武器','armor':'防具','accessory':'飾品'}[g['slot']] and a['state']==g['state']
      if g['state']=='equipped':
       slot_ok &= a.get('href','').split('?')[0]=='/gear/'+g['equipmentId']+'_nm' and f"+{g['enhancement']}" in a['text']
      for text,v in zip(a['values'],g['values']):
       if v:
        number=float(re.sub('[^0-9.\\-]','',text));target=float(v['value'])
        if v.get('modifierOperator'):target=-abs(target) if v['modifierOperator']=='-' else abs(target)
        binding_ok &= abs(number-target)<.00051
        verified_values+=1
    checks.update({'everyCharacterProgressBound':bool(binding_ok),'actualStarsPreserved':bool(star_ok),'threeSlotsAndEnhancementBound':bool(slot_ok),'actualTalentGradesBound':bool(talent_ok),'knownEffectsCompared':verified_values>0,'noHorizontalOverflow':b.evaluate('document.documentElement.scrollWidth<=innerWidth && document.querySelector("dialog[open]").scrollWidth<=document.querySelector("dialog[open]").clientWidth')})
    # Team switch must clear the prior selection and must use observed team options.
    options=b.evaluate('Array.from(document.querySelector("dialog[open] select")?.options??[], o=>o.value)')
    if len(options)>1:
     b.evaluate('(()=>{const s=document.querySelector("dialog[open] select");s.value=s.options[1].value;s.dispatchEvent(new Event("change",{bubbles:true}))})()')
     wait_for(b,'!!document.querySelector("dialog[open] .dv-detail-empty")')
     checks['teamSwitchClearsSelection']=b.evaluate('!document.querySelector("dialog[open] .dv-card[aria-pressed=true]")')
     b.evaluate('(()=>{const s=document.querySelector("dialog[open] select");s.value="all";s.dispatchEvent(new Event("change",{bubbles:true}))})()')
    b.evaluate('document.querySelector("dialog[open] .dv-card").click()');wait_for(b,'!!document.querySelector("dialog[open] .dv-unit-detail")')
    checks['abilityAndGearInitiallyCollapsed']=b.evaluate('Array.from(document.querySelectorAll("dialog[open] .dv-awakening,dialog[open] .dv-equipment,dialog[open] .dv-talents")).every(d=>!d.open)')
    b.evaluate('document.querySelector("dialog[open] .dv-equipment>summary").click()')
    checks['individualEquipmentOpens']=b.evaluate('document.querySelector("dialog[open] .dv-equipment").open')
    b.evaluate('document.querySelector("dialog[open]>.collapse-controls button:last-child").click()')
    checks['collapseAllWorks']=b.evaluate('Array.from(document.querySelectorAll("dialog[open] details")).every(d=>!d.open)')
    b.evaluate('document.querySelector("dialog[open]>.collapse-controls button:first-child").click()')
    checks['expandAllWorks']=b.evaluate('Array.from(document.querySelectorAll("dialog[open] details")).every(d=>d.open)')
    # Return to a compact readable screenshot without losing selection.
    b.evaluate('document.querySelectorAll("dialog[open] .dv-awakening,dialog[open] .dv-equipment,dialog[open] .dv-talents,dialog[open] .dv-reference,dialog[open] .catalog-fold").forEach(d=>d.open=false)')
    if width==1440:
     checks['fiveDesktopColumns']=b.evaluate('getComputedStyle(document.querySelector("dialog[open] .dv-character-grid")).gridTemplateColumns.split(" ").length===5')
     b.evaluate('document.querySelector("dialog[open]").scrollTop=0')
    else:
     checks['stackedMobilePanels']=b.evaluate('document.querySelector("dialog[open] .dv-details").getBoundingClientRect().top>=document.querySelector("dialog[open] .dv-roster").getBoundingClientRect().bottom')
     b.evaluate('document.querySelector("dialog[open] .dv-details").scrollIntoView()')
    b.screenshot(mode+'-selected-'+str(width))
    b.call('Input.dispatchKeyEvent',{'type':'keyDown','key':'Escape','code':'Escape','windowsVirtualKeyCode':27});b.call('Input.dispatchKeyEvent',{'type':'keyUp','key':'Escape','code':'Escape','windowsVirtualKeyCode':27})
    wait_for(b,'!document.querySelector("dialog[open]")')
    checks['escapeRestoresFocus']=b.evaluate('document.activeElement.classList.contains("dv-expand") && document.body.style.overflow!=="hidden"')
    html=b.evaluate('document.documentElement.outerHTML')
    checks['privateIdsAbsent']=not any(uid in html for uid in private_ids)
    checks['researchFieldsAbsent']=all(s not in html for s in ['characterInstanceIdentity','equipmentInstanceIdentity','moduleSha256','valueGradeRaw','sourceFile'])
    cases.append({'case':mode+'-team-viewer','width':width,'positionsCompared':len(expected[mode]),'knownValuesCompared':verified_values,'checks':checks});checkpoint();print(mode,width,checks,flush=True)
  # The same shared theme must cover the existing independent workflows.
  pages=[('/', 'home'),('/characters','characters'),('/gear','gear'),('/characters/u1616e-brown','character-detail'),('/gear/eq_2202_amr_06_nm','gear-detail'),('/guild','guild-ranking'),('/pvp?scope='+__import__('urllib.parse',fromlist=['quote']).quote('大師1')+'&top=10','pvp-ranking'),('/data-status','data-status')]
  for path,label in pages:
   if only and label not in only:continue
   for width in (1440,390):
    b.navigate('http://127.0.0.1:3101'+path,width,'document.querySelector("main h1")?.getBoundingClientRect().height>0 && document.querySelector(".site-header")?.getBoundingClientRect().height>0')
    checks={'darkTheme':b.evaluate('getComputedStyle(document.body).backgroundColor==="rgb(13, 23, 30)"'),'noHorizontalOverflow':b.evaluate('document.documentElement.scrollWidth<=innerWidth'),'noExternalBranding':not re.search('rangerbook|warmycat',b.evaluate('document.body.innerText'),re.I)}
    if label in ('characters','gear'):
     checks['realCards']=b.evaluate('document.querySelectorAll(".catalog-grid .verified-gear-card").length===24')
     checks['advancedFilterInitiallyCollapsed']=b.evaluate('!document.querySelector(".catalog-advanced").open')
     b.evaluate('document.querySelector(".catalog-advanced summary").click()');checks['advancedFilterOpens']=b.evaluate('document.querySelector(".catalog-advanced").open')
     b.evaluate('document.querySelector(".catalog-advanced summary").click()')
    if label in ('character-detail','gear-detail'):
     selector='[data-collapse-scope] .collapse-controls' if label=='character-detail' else '.reference-panel[data-collapse-scope] .collapse-controls'
     wait_for(b,'Object.keys(document.querySelector('+json.dumps(selector+' button')+')).some(k=>k.startsWith("__reactProps$"))')
     b.evaluate('document.querySelector('+json.dumps(selector+' button:first-child')+').click()')
     checks['expandAllSections']=b.evaluate('Array.from(document.querySelector('+json.dumps(selector)+').closest("[data-collapse-scope]").querySelectorAll("details")).every(d=>d.open)')
     b.evaluate('document.querySelector('+json.dumps(selector+' button:last-child')+').click()')
     checks['collapseAllSections']=b.evaluate('Array.from(document.querySelector('+json.dumps(selector)+').closest("[data-collapse-scope]").querySelectorAll("details")).every(d=>!d.open)')
    if label=='character-detail':
     b.evaluate('document.querySelector('+json.dumps('a[href="#character-talents"]')+').click()');wait_for(b,'document.querySelector("#character-talents").open');checks['anchorRevealsCollapsedSection']=True
    if label in ('guild-ranking','pvp-ranking'):
     checks['rankingCanCollapse']=b.evaluate('(()=>{const d=document.querySelector(".ranking-list");d.querySelector("summary").click();return !d.open})()')
    if width==390:
     wait_for(b,'Object.keys(document.querySelector(".nav-toggle")).some(k=>k.startsWith("__reactProps$"))')
     b.evaluate('document.querySelector(".nav-toggle").click()');wait_for(b,'document.querySelector(".nav-toggle").getAttribute("aria-expanded")==="true"');checks['mobileNavigationWorks']=b.evaluate('getComputedStyle(document.querySelector(".site-navigation")).display!=="none"');b.evaluate('document.querySelector(".nav-toggle").click()')
    checks['pageActuallyVisible']=b.evaluate('document.querySelector("main h1").getBoundingClientRect().height>0')
    decoded=b.evaluate('Promise.all(Array.from(document.querySelectorAll("main img")).filter(i=>{const r=i.getBoundingClientRect();return r.height>0&&r.top<innerHeight&&r.bottom>0}).map(i=>i.decode().then(()=>true).catch(()=>false)))')
    checks['visibleImagesDecoded']=all(decoded)
    b.evaluate('new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
    b.screenshot(label+'-'+str(width));cases.append({'case':label,'width':width,'checks':checks});checkpoint();print(label,width,checks,flush=True)
  report={'verifiedAt':datetime.now(timezone.utc).isoformat(),'sources':sources,'passed':all(all(c['checks'].values()) for c in cases) and not b.errors,'cases':cases,'runtimeErrors':b.errors,'networkScope':'localhost only; no game or Supabase requests'}
 (ROOT/'reports/defense-viewer-ui-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 print('passed',report['passed'])
 if not report['passed']:raise SystemExit(1)


if __name__=='__main__':main()
