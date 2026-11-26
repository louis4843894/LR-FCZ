"""Compare returned guildwar groups with actual tower/saved-defense copies.

At most three public member GETs and the own saved-defense GET. No PVP import,
arbitrary identity substitution, tower access change or game-state write.
"""
import hashlib,json,sqlite3,time,urllib.parse,uuid
from datetime import datetime,timezone
from pvp_session import Reader,ROOT,NEW_SHA,load_session
from fetch_ranked_pvp_response import normal_json,AcquisitionStopped
from collect_ranked_pvp_http import acquisition_lock
from probe_ranked_guild_member_groups import selected_group

def canonical(groups):
 units={};gear={}
 for rows in groups.values():
  for u in rows:
   key=u['slot'];units[key]=(str(u['invenId']),u['unitCode'])
   for slot,g in (u.get('equipMap') or {}).items():gear[key,slot]=(str(g['invenId']),g['itemCode'],g['currentEnchant'])
 return units,gear

def comparison(left,right):
 a,x=canonical(left);b,y=canonical(right)
 return {'publicGroupUnits':len(a),'defenseUnits':len(b),'sameUnitInstancesAtSameSlots':sum(a[k]==b[k] for k in a.keys()&b.keys()),
  'overlappingUnitInstances':len({v[0] for v in a.values()}&{v[0] for v in b.values()}),'sameTemplateAtSameSlots':sum(a[k][1]==b[k][1] for k in a.keys()&b.keys()),
  'publicGroupGear':len(x),'defenseGear':len(y),'sameGearInstancesAndEnhancement':sum(x[k]==y[k] for k in x.keys()&y.keys()),'exactMatch':a==b and x==y}

def verify():
 with sqlite3.connect((ROOT/'data/local/lr.private.sqlite').as_uri()+'?mode=ro',uri=True) as db:
  doc=json.loads(db.execute("SELECT s.payload FROM current_guild_war_sources c JOIN guild_war_sources s USING(source_id) WHERE c.kind='deployed_defense' AND s.status='success' ORDER BY s.captured_at DESC LIMIT 1").fetchone()[0])
  roster=json.loads(db.execute('SELECT s.payload FROM current_ranked_guild_rosters c JOIN guild_roster_sources s USING(source_id) WHERE c.guild_id=?',(doc['guildId'],)).fetchone()[0])
 allowed={m['playerId'] for m in roster['members']};folder=ROOT/'data/research/runtime.private'/('guildwar-purpose-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:6]);folder.mkdir()
 with acquisition_lock():
  with Reader(r'C:\LDPlayer\LDPlayer9\adb.exe','emulator-5554',100) as r:
   r.expected_module_sha=NEW_SHA;r.refresh();session=load_session(r,authorized=True)
  own=session.headers['uid'];targets=[]
  for tower in doc['towers']:
   source=json.loads((ROOT/doc['sourceDirectory']/f"tower-{doc['side']}-{tower['code']}.private.json").read_bytes())
   for defender in source['result']['guildWarDefenceDeckResponses']:
    uid=defender['mergedGuildPlayer']['uid']
    if uid in allowed and uid!=own:targets.append((uid,defender['deckInfo']['playerUnitTeams']))
  targets=targets[:2];results=[]
  for index,(uid,groups) in enumerate([(own,None),*targets]):
   time.sleep(.5);raw,response=normal_json(session,'/player/units/team/equip/uid/'+urllib.parse.quote(uid,safe=''),purpose='guild-war-member-groups')
   result=response.get('result') or {}
   if result.get('player',{}).get('uid')!=uid:raise AcquisitionStopped('comparison_owner_differs')
   public=selected_group(result.get('playerUnitTeamGroupMap') or {})
   if groups is None:
    time.sleep(.5);_,saved=normal_json(session,'/guildwar/defencedeck',purpose='guild-war-bootstrap')
    value=saved['result'];candidates=[value] if 'deckInfoJson' in value else [v for v in value.values() if isinstance(v,dict) and 'deckInfoJson' in v]
    if len(candidates)!=1 or candidates[0].get('uid')!=uid:raise AcquisitionStopped('own_saved_defense_identity_differs')
    groups=json.loads(candidates[0]['deckInfoJson'])['playerUnitTeams'];kind='own-saved-defense-same-time'
   else:kind='reviewed-actual-tower-earlier-snapshot'
   safe={'sourceKind':'guildwar-purpose-comparison-copy','moduleSha256':NEW_SHA,'capturedAt':datetime.now(timezone.utc).isoformat(),
    'comparisonKind':kind,'responseSha256':hashlib.sha256(raw).hexdigest(),'publicGuildwar':public,'defense':groups,'credentialsIncluded':False}
   # Unit and equipment copies only; UID and authentication remain in RAM.
   p=folder/f'comparison-{index}.private.json';p.write_text(json.dumps(safe,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
   results.append({'kind':kind,**comparison(public,groups),'copySha256':hashlib.sha256(p.read_bytes()).hexdigest()})
 report={'checkedAt':datetime.now(timezone.utc).isoformat(),'sourceDirectory':folder.relative_to(ROOT).as_posix(),'comparisons':results,
  'guildwarNameAloneEstablishesDefense':False,'pvpImported':False,'credentialsPersisted':False}
 (ROOT/'reports/guildwar-public-group-purpose-comparison.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');return report

if __name__=='__main__':
 try:print(json.dumps(verify()))
 except Exception as e:
  print(json.dumps({'completed':False,'reason':str(e) if isinstance(e,AcquisitionStopped) else type(e).__name__,'credentialsPersisted':False}));raise SystemExit(1)
