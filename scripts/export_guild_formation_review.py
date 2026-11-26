"""Sanitized Chinese review copy of one real public attack formation.

Contains no native account/unit/equipment instance identities, tokens or raw
memory. It is a review artifact, never an accepted guild-war tower defense.
"""
import hashlib,json,sqlite3
from pathlib import Path
from local_game_database import ROOT

def export():
 db=sqlite3.connect((ROOT/'data/local/lr.private.sqlite').as_uri()+'?mode=ro',uri=True)
 try:
  def document(name):return json.loads(db.execute('SELECT d.payload FROM current_documents c JOIN documents d USING(sha256) WHERE c.filename=?',(name,)).fetchone()[0])
  equipment={r['itemCode']:r for r in document('verified-equipment.json')['records']};characters={r['characterId']:r for r in document('verified-characters.json')['records']}
  doc=json.loads(db.execute('SELECT s.payload FROM current_guild_public_formations c JOIN guild_public_formation_sources s USING(source_id) ORDER BY s.captured_at DESC LIMIT 1').fetchone()[0])
  ranking=json.loads(db.execute('SELECT payload FROM guild_rank_sources WHERE snapshot_id=?',(doc['rankingSnapshotId'],)).fetchone()[0]);guild=next(g for g in ranking['guilds'] if g['guildId']==doc['guildId'])
 finally:db.close()
 teams=[]
 for team in doc['teams']:
  units=[]
  for u in team['units']:
   template=characters.get(u['characterId']);slots={}
   for slot,e in u['equipment'].items():
    g=equipment.get(e['equipmentId']);slots[slot]={'state':e['state'],'equipmentId':e['equipmentId'],'name':g['names'].get('zh-Hant') if g else None,
     'stars':g['starCount'] if g else None,'actualEnhancement':e.get('enhancement'),'actualNumericalEffects':'not_exported_for_unverified_defense_purpose'}
   units.append({'position':u['position']+1,'characterId':u['characterId'],'characterName':template.get('name') if template else None,'actualLevel':u['level'],'equipment':slots})
  teams.append({'teamNo':team['teamNo'],'units':units})
 result={'guildName':guild['name'],'guildRank':guild['rank'],'publicMemberName':doc['playerName'],'capturedAt':doc['capturedAt'],'sourceId':doc['sourceId'],
  'purpose':'公會戰出戰編隊','defenseVerified':False,'towerNumber':None,'note':'正常公開回應的 guildwar 群組為出戰用途（0x0c）。防禦快照為另一群組（0x0b）；此檔不可算成已取得其他公會防禦。',
  'teams':teams,'nativeInstanceIdentifiersIncluded':False,'credentialsIncluded':False}
 path=ROOT/'reports/guild-public-formation-review.json';path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 return {'path':path.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'unitCount':sum(len(t['units']) for t in teams),'equipmentCount':sum(e['state']=='equipped' for t in teams for u in t['units'] for e in u['equipment'].values()),'defenseVerified':False}

if __name__=='__main__':print(json.dumps(export()))
