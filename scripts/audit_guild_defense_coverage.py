"""Read-only Top-100 coverage and verified read/write boundaries; no game requests."""
import json,sqlite3,hashlib
from pathlib import Path
from contextlib import closing
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]


def audit():
 with closing(sqlite3.connect((ROOT/'data/local/lr.private.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
  ranking=json.loads(db.execute("SELECT s.payload FROM current_guild_rankings c JOIN guild_rank_sources s USING(snapshot_id) WHERE c.scope='top100'").fetchone()[0])
  wars=[json.loads(p) for p, in db.execute('SELECT s.payload FROM current_guild_war_sources c JOIN guild_war_sources s USING(source_id)')]
 rows=[]
 for guild in sorted(ranking['guilds'],key=lambda g:g['rank']):
  if not 1<=guild['rank']<=100:continue
  war=next((w for w in wars if w['guildId']==guild['guildId'] and w['kind']=='deployed_defense'),None)
  defenders=[d for t in (war or {}).get('towers',[]) for d in t.get('defenders') or []];units=[u for d in defenders for t in d['teams'] for u in t['units']]
  rows.append({'rank':guild['rank'],'guildAlias':hashlib.sha256(guild['guildId'].encode()).hexdigest()[:20],'guildName':guild['name'],'state':war['status'] if war else 'not_acquired',
   'sourceId':war['sourceId'] if war else None,'capturedAt':war['capturedAt'] if war else None,'towersRead':sum(t['readState']=='success' for t in war['towers']) if war else None,
   'towersObserved':len(war['towers']) if war else None,'defenderObservations':len(defenders) if war else None,'characterPositions':len(units) if war else None,
   'equipmentInstances':sum(e['state']=='equipped' for u in units for e in u['equipment'].values()) if war else None})
 report={'checkedAt':datetime.now(timezone.utc).isoformat(),'rankingSnapshotId':ranking['snapshotId'],'target':'ranked guilds #1 through #100, not only the current opponent','summary':{'targetGuilds':len(rows),'complete':sum(r['state']=='success' for r in rows),'partial':sum(r['state']=='partial' for r in rows),'notAcquired':sum(r['state']=='not_acquired' for r in rows)},'guilds':rows,
  'verifiedBoundaries':{'towerRead':{'function':'0133c590','route':'/guildwar/fortress/opponent/%d/%d/%d','parameters':['seasonNo','battleNo','towerCode'],'guildIdParameterEstablished':False,'knownCaller':'0132a808','proof':'reports/ghidra/guild-top100-war-target-references-1242.txt'},
   'writeBranchExcluded':{'function':'00f91408','group':11,'route':'/guildwar/defencedeck','otherGroupsRoute':'/player/units/save/%s','requestIssued':False,'proof':'reports/ghidra/guild-top100-defense-save-boundary-1242.txt'},
   'referencePublicInterface':{'publicScript':'data/research/external-reference/guild-read-interface-20261126T155357Z/guildwar-ranking.js','declaredTeamPurpose':'公會戰進攻隊伍','provesDefense':False,'restrictedApiRequests':0}},
  'missingCapability':'A verified read entry that selects an arbitrary ranked guild ID for actual guild-war defense. It has not been established; no guessed GID parameters or access bypass attempted.',
  'gameRequestsByThisAudit':0,'credentialsIncluded':False,'publicAttackGroupsCountedAsDefense':False}
 (ROOT/'reports/guild-top100-defense-coverage.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8');return report


if __name__=='__main__':print(json.dumps(audit()['summary'],ensure_ascii=False))
