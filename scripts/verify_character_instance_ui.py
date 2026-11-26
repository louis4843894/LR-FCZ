"""Browser checks for skill startup and real PVP/guild character progress."""
import argparse,hashlib,json,sqlite3
from contextlib import closing
from datetime import datetime,timezone
from browser_session import Browser,ROOT
from character_instance_progress import read_progress,observation_key,match_progress
INSTANCE_DISPLAY_FILES=['lib/character-instance-progress.ts','lib/local-game-data.ts','lib/defense-teams.ts','lib/guild-war.ts','app/_components/character-instance-panel.tsx','app/_components/character-instance-panel.css','app/_components/defense-teams-panel.tsx','app/_components/guild-war-panel.tsx']


def startup_only():
 """Reuse unaffected instance checks only with identical source and code hashes."""
 path=ROOT/'reports/character-instance-ui-validation.json';previous=json.loads(path.read_bytes())
 if not previous['passed'] or not previous.get('instanceDisplaySourceHashes'):raise ValueError('accepted instance display evidence required')
 for name,sha in previous['instanceDisplaySourceHashes'].items():
  if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=sha:raise ValueError('instance display changed; full UI validation required')
 with closing(sqlite3.connect((ROOT/'data/local/lr.private.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
  sid=db.execute("SELECT source_id FROM current_character_instance_sources WHERE scope='accepted-defense'").fetchone()[0]
  detail_sid=db.execute("SELECT source_id FROM current_character_details WHERE scope='native-matched-reference'").fetchone()[0]
  details={code:json.loads(db.execute('SELECT payload FROM character_template_details WHERE source_id=? AND character_id=?',(detail_sid,code)).fetchone()[0]) for code in ('u1618e-ka','u1216e-towa')}
 if sid!=previous['instanceSourceId']:raise ValueError('instance source changed; full UI validation required')
 cases=[c for c in previous['cases'] if c['case'] in ('ranked-pvp-instances','guild-tower-instances')]
 if len(cases)!=4 or not all(all(c['checks'].values()) for c in cases):raise ValueError('four accepted instance cases required')
 with Browser('character-startup-final') as b:
  for code,row in details.items():
   for width in (1440,390):
    b.navigate('http://127.0.0.1:3101/characters/'+code,width,'document.querySelector(".character-skill-card")!==null')
    timings=b.evaluate('Array.from(document.querySelectorAll(".character-skill-card")).map(c=>Array.from(c.querySelectorAll("dt")).find(d=>d.textContent==="技能前搖")?.nextElementSibling?.textContent)')
    checks={'startupMatchesSavedAnimationSeconds':timings==[f"{s['startupSeconds']:.2f} 秒" for s in row['skills']],'notProjectileTravel':'不含投射物飛行時間' in b.evaluate('document.body.innerText'),'noHorizontalOverflow':b.evaluate('document.documentElement.scrollWidth<=innerWidth')}
    b.evaluate('document.querySelector("#character-skills").scrollIntoView()');b.screenshot(code+'-'+str(width));cases.append({'case':'skill-startup','characterId':code,'width':width,'timings':timings,'checks':checks})
  result={'verifiedAt':datetime.now(timezone.utc).isoformat(),'instanceSourceId':sid,'detailSourceId':detail_sid,'passed':len(cases)==8 and all(all(c['checks'].values()) for c in cases) and not b.errors,
          'cases':cases,'runtimeErrors':b.errors,'instanceDisplaySourceHashes':previous['instanceDisplaySourceHashes'],'unchangedInstanceCasesReused':4,'previousInstanceAcceptanceAt':previous['verifiedAt']}
 path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(result,ensure_ascii=False))
 if not result['passed']:raise SystemExit(1)


def expected_fields(progress):
 p=progress;a=p['awakening']
 return {'實際等級':f"Lv.{p['level']} / {p['maxLevel']}" if p['maxLevel'] is not None else f"Lv.{p['level']}",
         '雷納德點數':str(p['leonardPoints'])+' 點','才能階段':f"第 {p['talentGrade']} 階",
         '實際覺醒能力':a['name'] if a['state']=='present' else '來源回傳空值' if a['state']=='empty_observed' else '來源未提供'}


def main():
 sid,progress=read_progress();cases=[]
 with closing(sqlite3.connect((ROOT/'data/local/lr.private.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
  detail_sid=db.execute("SELECT source_id FROM current_character_details WHERE scope='native-matched-reference'").fetchone()[0]
  detail=json.loads(db.execute('SELECT payload FROM character_template_details WHERE source_id=? AND character_id=?',(detail_sid,'u1618e-ka')).fetchone()[0])
  ranking=json.loads(db.execute("SELECT r.payload FROM current_rankings c JOIN ranking_snapshots r USING(snapshot_id) WHERE c.scope_label='傳奇'").fetchone()[0])
  for player in ranking['players']:
   found=db.execute("SELECT payload FROM ranking_defense_attempts WHERE ranking_snapshot_id=? AND player_id=? ORDER BY attempted_at DESC LIMIT 1",(ranking['snapshotId'],player['playerId'])).fetchone()
   attempt=json.loads(found[0]) if found else None
   if attempt and attempt['status'] in ('success','partial'):break
  else:raise ValueError('no accepted current ranked player')
  document=json.loads(db.execute("SELECT d.payload FROM current_documents c JOIN documents d USING(sha256) WHERE c.filename='defense-teams.private.json'").fetchone()[0])
  teams=[t for t in document['snapshots'] if t['playerId']==player['playerId'] and t['snapshotId'] in attempt['defenseSnapshotIds']]
  war=json.loads(db.execute("SELECT s.payload FROM current_guild_war_sources c JOIN guild_war_sources s USING(source_id) WHERE s.kind='deployed_defense' AND s.status='success'").fetchone()[0])
 expected_pvp={t['teamId']:[expected_fields(match_progress(progress[observation_key('pvp',t['snapshotId'],t['playerId'],t['teamId'].split('/')[-1],m['memberIndex'])],m['characterId'],t['playerId'],m['characterInstanceIdentity']['value'],t['retrievedAt'])) for m in t['members']] for t in teams}
 tower=next(t for t in war['towers'] if t['code']==11)
 expected_guild=[expected_fields(match_progress(progress[observation_key('guildwar',war['sourceId'],d['playerId'],t['teamNo'],u['position'],tower['code'])],u['characterId'],d['playerId'],u['characterInstanceId'],d['retrievedAt'])) for d in tower['defenders'] for t in d['teams'] for u in t['units']]
 pvp_url=f"http://127.0.0.1:3101/pvp/players/{hashlib.sha256(player['playerId'].encode()).hexdigest()[:12]}?snapshot={ranking['snapshotId']}"
 guild_url=f"http://127.0.0.1:3101/guild/{hashlib.sha256(war['guildId'].encode()).hexdigest()[:20]}?tower=1"
 with Browser('character-instances-acceptance') as b:
  for width in (1440,390):
   b.navigate('http://127.0.0.1:3101/characters/u1618e-ka',width,'document.querySelector(".character-skill-card")!==null')
   timings=b.evaluate('Array.from(document.querySelectorAll(".character-skill-card")).map(c=>Array.from(c.querySelectorAll("dt")).find(d=>d.textContent==="技能前搖")?.nextElementSibling?.textContent)')
   expected=[f"{s['startupSeconds']:.2f} 秒" for s in detail['skills']]
   checks={'startupMatchesSavedAnimationSeconds':timings==expected,'notProjectileTravel':'不含投射物飛行時間' in b.evaluate('document.body.innerText'),'noHorizontalOverflow':b.evaluate('document.documentElement.scrollWidth<=innerWidth')}
   b.evaluate('document.querySelector("#character-skills").scrollIntoView()');b.screenshot('startup-'+str(width));cases.append({'case':'skill-startup','width':width,'timings':timings,'checks':checks})
   b.navigate(pvp_url,width,'document.querySelector(".defense-member .instance-character-facts")!==null')
   actual=b.evaluate('Array.from(document.querySelectorAll("article.reference-panel")).filter(a=>a.querySelector(".defense-member")).map(a=>({team:a.innerText.includes("pvpteam/1")?"pvpteam/1":"pvpteam/2",members:Array.from(a.querySelectorAll(".defense-member .instance-character-facts")).map(dl=>Object.fromEntries(Array.from(dl.querySelectorAll("dt")).map(dt=>[dt.textContent,dt.nextElementSibling.textContent])))}))')
   checks={'actualLevelPointsTalentAwakeningMatchSource':{a['team']:a['members'] for a in actual}==expected_pvp,'noHorizontalOverflow':b.evaluate('document.documentElement.scrollWidth<=innerWidth')}
   b.evaluate('document.querySelector(".defense-member").scrollIntoView()');b.screenshot('pvp-instance-'+str(width));cases.append({'case':'ranked-pvp-instances','width':width,'characters':sum(len(v) for v in expected_pvp.values()),'checks':checks})
   b.navigate(guild_url,width,'document.querySelector(".war-selected-tower .instance-character-facts")!==null')
   actual=b.evaluate('Array.from(document.querySelectorAll(".war-selected-tower .instance-character-facts")).map(dl=>Object.fromEntries(Array.from(dl.querySelectorAll("dt")).map(dt=>[dt.textContent,dt.nextElementSibling.textContent])))')
   checks={'allTowerInstancesMatchSource':actual==expected_guild,'unknownAwakeningNotInvented':sum(a['實際覺醒能力']=='來源未提供' for a in actual)==sum(a['實際覺醒能力']=='來源未提供' for a in expected_guild),'noHorizontalOverflow':b.evaluate('document.documentElement.scrollWidth<=innerWidth')}
   b.evaluate('document.querySelector(".war-selected-tower .war-unit").scrollIntoView()');b.screenshot('guild-instance-'+str(width));cases.append({'case':'guild-tower-instances','width':width,'characters':len(expected_guild),'checks':checks})
   if not all(all(c['checks'].values()) for c in cases):break
  report={'verifiedAt':datetime.now(timezone.utc).isoformat(),'instanceSourceId':sid,'detailSourceId':detail_sid,'passed':len(cases)==6 and all(all(c['checks'].values()) for c in cases) and not b.errors,'cases':cases,'runtimeErrors':b.errors,'instanceDisplaySourceHashes':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in INSTANCE_DISPLAY_FILES}}
 (ROOT/'reports/character-instance-ui-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(report,ensure_ascii=False))
 if not report['passed']:raise SystemExit(1)


if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--startup-only',action='store_true');args=parser.parse_args()
 if args.startup_only:startup_only()
 else:main()
