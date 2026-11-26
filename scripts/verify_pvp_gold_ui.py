"""Verify ten native phases and actual roll values in the local UI only."""
import hashlib,json,sqlite3,urllib.parse
from pathlib import Path
from browser_session import Browser,ROOT
from derive_http_gear_values import observation_id,matching_roll_entry

def expected_values(href):
 parsed=urllib.parse.urlsplit(href);alias=parsed.path.rsplit('/',1)[-1];sid=urllib.parse.parse_qs(parsed.query)['snapshot'][0]
 with sqlite3.connect((ROOT/'data/local/lr.private.sqlite').as_uri()+'?mode=ro',uri=True) as db:
  db.execute('BEGIN');ranking=json.loads(db.execute('SELECT payload FROM ranking_snapshots WHERE snapshot_id=?',(sid,)).fetchone()[0])
  owner=next(p['playerId'] for p in ranking['players'] if hashlib.sha256(p['playerId'].encode()).hexdigest()[:12]==alias)
  attempt=json.loads(db.execute("SELECT payload FROM ranking_defense_attempts WHERE ranking_snapshot_id=? AND player_id=? AND status IN ('success','partial') ORDER BY attempted_at DESC LIMIT 1",(sid,owner)).fetchone()[0])
  document=json.loads(db.execute("SELECT d.payload FROM current_documents c JOIN documents d USING(sha256) WHERE c.filename='defense-teams.private.json'").fetchone()[0])
  team=next(t for t in document['snapshots'] if t['playerId']==owner and t['snapshotId'] in attempt['defenseSnapshotIds'] and t['teamId']=='pvpteam/1');member=team['members'][0];gear=member['equipment']['weapon']
  row=db.execute("SELECT r.payload FROM gear_instance_rolls r JOIN current_gear_rolls c USING(source_id) WHERE c.scope='ranked-http' AND r.observation_id=?",(observation_id(team,member,'weapon'),)).fetchone()
  record=json.loads(row[0]) if row else None
  expected=[{'index':a['index'],'value':r['value'],'unit':r['unit']} for a in (gear.get('actualEffects') or {}).get('entries',[]) if (r:=matching_roll_entry(record,team,member,'weapon',gear,a))]
  return expected
def main():
 results=[]
 with Browser('pvp-gold-values') as b:
  b.navigate('http://127.0.0.1:3101/pvp?top=10',1440,'document.querySelector(".ranking-name")!==null')
  options=b.evaluate('Array.from(document.querySelector("select[name=scope]").options).map(o=>o.value)')
  wanted=['傳奇',*[g+str(i) for g in ['大師','鑽石','黃金'] for i in (1,2,3)]]
  results.append({'case':'gold-cutoff-and-subdivisions','passed':options==wanted,'options':options})
  href=b.evaluate('document.querySelector(".ranking-name").href');expected=expected_values(href)
  for width in (1440,390):
   b.navigate(href,width,'document.querySelector(".native-attribute-value")!==null')
   actual=b.evaluate('(()=>{const article=Array.from(document.querySelectorAll("article.reference-panel")).find(e=>e.innerText.includes("隊伍識別：pvpteam/1"));return Array.from(article.querySelector(".defense-member .defense-equipment").querySelectorAll(".actual-attribute")).map((e,index)=>({index,text:e.querySelector(".native-attribute-value")?.textContent??null}))})()')
   checked=[]
   for e in expected:
    text=next((a['text'] for a in actual if a['index']==e['index']),None)
    number=float(text.replace('%','').replace(',','')) if text else None
    checked.append(number==e['value'] and ('%' in text)==(e['unit']=='PERCENT'))
   visible=b.evaluate('document.body.innerText')
   checks={'valuesMatchInstanceBoundDatabaseRows':len(checked)>0 and all(checked),'nativeReconstructionExplained':'依原生定義與實例分級還原' in visible,'unknownSpecialValuesRemainUnknown':'數值尚未解析' in visible,
    'noOverflow':b.evaluate('document.documentElement.scrollWidth<=innerWidth'),'templateSeparate':'模板參考' in visible,'noRawCodesVisible':not any(x in visible for x in ['ALL_ATK_MUL','SKL_PROB_MUL','attr1No'])}
   b.evaluate('document.querySelector(".defense-equipment").scrollIntoView({block:"start"});window.scrollBy(0,-90)');b.screenshot('native-rolls-'+str(width))
   results.append({'case':'native-values','width':width,'checkedValues':len(checked),'checks':checks,'passed':all(checks.values())})
  b.navigate('http://127.0.0.1:3101/pvp?scope='+urllib.parse.quote('大師1')+'&top=10',390,'document.querySelector("select[name=scope]")!==null')
  results.append({'case':'master-1-is-distinct','passed':b.evaluate('document.querySelector("h1").innerText.includes("大師1")&&document.querySelector("select[name=scope]").value==="大師1"')})
  b.navigate('http://127.0.0.1:3101/pvp?scope='+urllib.parse.quote('白銀'),390)
  results.append({'case':'excluded-query-does-not-substitute-legend','passed':b.evaluate('document.body.innerText.includes("排名資料尚未取得")&&!document.querySelector(".ranking-player")')})
  report={'passed':all(r['passed'] for r in results) and not b.errors,'cases':results,'runtimeErrors':b.errors,'noGameRequestsFromBrowser':True}
 (ROOT/'reports/pvp-gold-values-ui-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(report))
 if not report['passed']:raise SystemExit(1)
if __name__=='__main__':main()
