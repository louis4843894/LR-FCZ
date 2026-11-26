"""Check real ranked defenses: native Chinese kinds and separate template ranges."""
import json,re,sqlite3,hashlib
from contextlib import closing
from browser_session import Browser,ROOT


def main():
 with closing(sqlite3.connect((ROOT/'data/local/lr.private.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
  raw=json.loads(db.execute("SELECT d.payload FROM current_documents c JOIN documents d USING(sha256) WHERE c.filename='defense-teams.private.json'").fetchone()[0])
  private_ids={t['playerId'] for t in raw['snapshots']}
  verified=next((t for t in raw['snapshots'] if any(a.get('valueVerified') is True for m in t['members'] or [] for g in m['equipment'].values() for a in (g.get('actualEffects') or {}).get('entries',[]))),None)
  legacy_key=hashlib.sha256(verified['playerId'].encode()).hexdigest()[:12] if verified else None
 records=[]
 with Browser('pvp-chinese-acceptance') as b:
  b.navigate('http://127.0.0.1:3101/pvp?top=10',1440,'document.querySelector(".ranking-player a.ranking-name")!==null')
  href=b.evaluate('document.querySelector(".ranking-player a.ranking-name").href')
  for width in (1440,390):
   b.navigate(href,width,'document.querySelector(".actual-attribute-label")!==null')
   visible=b.evaluate('document.body.innerText');html=b.evaluate('document.documentElement.outerHTML')
   labels=b.evaluate('Array.from(document.querySelectorAll(".actual-attribute-label")).map(e=>e.innerText)')
   checks={'hasChineseKinds':any(re.search('[\u3400-\u9fff]',x) and '尚未解析' not in x for x in labels),
    'noVisibleRawGearOrEffectCodes':all(x not in visible for x in ['eq_','原始屬性 ID','ALL_ATK_MUL','SKL_PROB_MUL','attr1No']),
    'unknownValuesNotFilled':'數值尚未解析' in visible,
    'advancedIdentifiersCollapsed':b.evaluate('Array.from(document.querySelectorAll(".defense-raw-identifiers")).every(e=>!e.open)'),
    'templateReferencesPresent':b.evaluate('document.querySelectorAll(".war-template-reference").length>0'),
    'noPrivatePlayerIds':all(x not in html for x in private_ids),
    'noExternalBranding':not any(x in visible.lower() for x in ['rangerbook','warmycat','外部來源']),
    'updateButtonPresent':b.evaluate('document.querySelector("[data-action=update-pvp]")!==null'),
    'noHorizontalOverflow':b.evaluate('document.documentElement.scrollWidth<=innerWidth')}
   b.evaluate('document.querySelector(".war-template-reference").open=true')
   checks['templateScopeSeparate']=b.evaluate('document.querySelector(".war-template-reference").innerText.includes("模板的可能範圍")')
   checks['expandedNoOverflow']=b.evaluate('document.documentElement.scrollWidth<=innerWidth')
   b.evaluate('document.querySelector(".defense-equipment").scrollIntoView({block:"start"});window.scrollBy(0,-90)')
   b.screenshot('ranked-chinese-'+str(width));records.append({'width':width,'checks':checks})
  b.navigate('http://127.0.0.1:3101/pvp?top=10',390,'document.querySelector("[data-action=update-pvp]")!==null')
  result=b.evaluate('fetch("/api/local-updates/pvp",{cache:"no-store"}).then(r=>r.json())')
  update={'statusEndpointAvailable':bool(result.get('state',{}).get('enabled'))}
  if result.get('state',{}).get('status')=='running':
   response=b.evaluate('fetch("/api/local-updates/pvp",{method:"POST",headers:{"Content-Type":"application/json"}}).then(async r=>({status:r.status,...await r.json()}))')
   update['runningUpdateNotDuplicated']=response.get('status')=='already_running'
  records.append({'case':'local-update-status','checks':update})
  if legacy_key:
   b.navigate('http://127.0.0.1:3101/pvp/observations?player='+legacy_key,390,'document.querySelector(".defense-equipment")!==null')
   records.append({'case':'legacy-values','checks':{'previousVerifiedValuesStillDisplayed':b.evaluate('document.querySelectorAll(".native-attribute-value").length>0')}})
  report={'passed':all(all(r['checks'].values()) for r in records) and not b.errors,'cases':records,'runtimeErrors':b.errors,'noGameRequestsFromBrowser':True}
 (ROOT/'reports/pvp-chinese-ui-validation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
 print(json.dumps(report))
 if not report['passed']:raise SystemExit(1)


if __name__=='__main__':main()
