"""One visible ranked-guild member: normal public GET, guildwar branch only.

Does not guess endpoints or group selectors. Unknown response bodies stay in
RAM; only bounded structural evidence is retained. PVP is not imported.
"""
import argparse,hashlib,json,sqlite3,sys,urllib.parse,uuid,re
from datetime import datetime,timezone
from pathlib import Path
from pvp_session import Reader,NEW_SHA,ROOT,load_session,SessionUnavailable
from equipment_memory import GBASE,u64
from read_defense_team import typed
from fetch_ranked_pvp_response import normal_json,AcquisitionStopped
from collect_ranked_pvp_http import acquisition_lock
from probe_guildwar_normal import shape

def selected_group(groups):
 from guild_war_database import units_from_json
 selected=groups.get('guildwar')
 if not isinstance(selected,dict) or len(selected)>4:raise AcquisitionStopped('guildwar_group_shape_unverified')
 unit_fields=['teamNo','slot','invenId','unitCode','unitLevel'];gear_fields=['invenId','equipItemCode','currentGrade','currentEnchant','currentAdvancedEnchant','currentSkillPlusEnchant','currentSpecialEnchant','unitInvenId','itemCode','equipType','specialOptionCode','specialOptionAttrValueGrade','specialOptionTalentValueGrade']
 gear_fields += [prefix+suffix for prefix in [*[f'attr{i}' for i in range(1,6)],'skillPlusAttr1','skillPlusAttr2'] for suffix in ['No','ValueGrade']]
 safe={}
 for key,units in selected.items():
  if not re.fullmatch('[1-9][0-9]?',key) or not isinstance(units,list) or len(units)>20:raise AcquisitionStopped('guildwar_team_bounds_unverified')
  rows=[]
  for unit in units:
   row={k:unit[k] for k in unit_fields if k in unit}
   if 'equipMap' in unit:
    mapping=unit['equipMap']
    if mapping is not None and (not isinstance(mapping,dict) or set(mapping)-{'WEAPON','ARMOR','ACC'}):raise AcquisitionStopped('guildwar_slot_unverified')
    row['equipMap']={slot:({k:g[k] for k in gear_fields if k in g} if isinstance(g,dict) else g) for slot,g in mapping.items()} if mapping is not None else None
   rows.append(row)
  units_from_json(rows,int(key)) # same verified slot/instance/type checks as tower data
  safe[key]=rows
 return safe

def probe(save_group=False,compare_own=False):
 with sqlite3.connect((ROOT/'data/local/lr.private.sqlite').as_uri()+'?mode=ro',uri=True) as db:
  rank=json.loads(db.execute("SELECT s.payload FROM current_guild_rankings c JOIN guild_rank_sources s USING(snapshot_id) WHERE c.scope='top100'").fetchone()[0])
  rosters={gid:json.loads(p) for gid,p in db.execute('SELECT c.guild_id,s.payload FROM current_ranked_guild_rosters c JOIN guild_roster_sources s USING(source_id)')}
 with acquisition_lock():
  with Reader(r'C:\LDPlayer\LDPlayer9\adb.exe','emulator-5554',100) as r:
   r.expected_module_sha=NEW_SHA;r.refresh()
   director=u64(r.read(r.base+0x204e2f0-GBASE,8));controller=u64(r.read(director+0xf0,8))
   scene=typed(r,controller,0x170,0x1eee558)
   profile=typed(r,u64(scene,0x138),0x220,0x1e7d650)
   uid=r.string(profile,0x90).decode();name=r.string(profile,0x48).decode()
   guild=typed(r,u64(profile,0x150),0x40,0x1eadb48);text=typed(r,u64(guild,0x30),0x30,0x1f6a7a8);gid=r.string(text,0x18).decode()
   matches=[g for g in rank['guilds'] if g['guildId']==gid]
   roster=rosters.get(gid)
   if len(matches)!=1 or not roster or not any(m['playerId']==uid and m['name']==name for m in roster['members']):raise AcquisitionStopped('visible_player_not_verified_ranked_guild_member')
   session=load_session(r,authorized=True)
  raw,response=normal_json(session,'/player/units/team/equip/uid/'+urllib.parse.quote(uid,safe=''),purpose='guild-war-member-groups')
 result=response.get('result');groups=result.get('playerUnitTeamGroupMap') if isinstance(result,dict) else None
 if not isinstance(result,dict) or not isinstance(result.get('player'),dict) or result['player'].get('uid')!=uid:raise AcquisitionStopped('response_owner_differs')
 if not isinstance(groups,dict):raise AcquisitionStopped('public_team_groups_missing')
 selected=groups.get('guildwar');at=datetime.now(timezone.utc).isoformat()
 report={'checkedAt':at,'moduleSha256':NEW_SHA,'normalPathFunction':'015eab84','publicGuildRank':matches[0]['rank'],'publicGuildName':matches[0]['name'],
  'visibleOwnerMatchedRoster':True,'responseOwnerMatched':True,'groupKeys':sorted(groups),'guildwarBranchPresent':'guildwar' in groups,
  'resultKeys':sorted(result),'relatedBranchShapes':{key:shape(value) for key,value in result.items() if key!='playerUnitTeamGroupMap' and any(word in key.lower() for word in ['guild','defen','deck','battle'])},
  'guildwarShape':shape(selected),'responseSha256':hashlib.sha256(raw).hexdigest(),'deploymentConfirmed':False,
  'pvpTeamsImported':False,'credentialsPersisted':False,'rawResponsePersisted':False}
 if save_group:
  safe=selected_group(groups);folder=ROOT/'data/research/runtime.private'/('ranked-guild-war-group-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:6]);folder.mkdir()
  saved={'schemaVersion':1,'sourceKind':'normal-public-member-guildwar-group','capturedAt':at,'moduleSha256':NEW_SHA,'gameVersion':'12.4.2',
   'guildId':gid,'playerId':uid,'playerName':name,'rankingSnapshotId':rank['snapshotId'],'rosterSourceId':roster['sourceId'],'responseSha256':report['responseSha256'],
   'playerUnitTeamGroupMap':{'guildwar':safe},'deploymentConfirmed':False,'pvpTeamsIncluded':False,'credentialsIncluded':False}
  (folder/'response.private.json').write_text(json.dumps(saved,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
  report.update(savedCopy=folder.relative_to(ROOT).as_posix(),teamNumbers=list(safe),units=sum(map(len,safe.values())),equipped=sum(len(u.get('equipMap') or {}) for units in safe.values() for u in units))
 if compare_own:
  import time
  # Existing own-session UID is used verbatim; no identity substitution. Only
  # compare guildwar with the same owner's normal saved-defense endpoint.
  with acquisition_lock():
   time.sleep(.5);_,own=normal_json(session,'/player/units/team/equip/uid/'+urllib.parse.quote(session.headers['uid'],safe=''),purpose='guild-war-member-groups')
   time.sleep(.5);_,deck=normal_json(session,'/guildwar/defencedeck',purpose='guild-war-bootstrap')
  own_result=own.get('result') or {}
  if own_result.get('player',{}).get('uid')!=session.headers['uid']:raise AcquisitionStopped('own_comparison_identity_differs')
  own_groups=selected_group(own_result.get('playerUnitTeamGroupMap') or {})
  result=deck.get('result') or {};candidates=[]
  def find(value,depth=0):
   if depth>3:return
   if isinstance(value,dict):
    if 'deckInfoJson' in value:candidates.append(value)
    else:
     for v in value.values():find(v,depth+1)
  find(result)
  if len(candidates)!=1 or candidates[0].get('uid')!=session.headers['uid']:raise AcquisitionStopped('own_saved_defense_shape_differs')
  saved=json.loads(candidates[0]['deckInfoJson']);saved_groups=saved.get('playerUnitTeams') or {}
  def placements(group):
   return sorted((u['slot'],str(u['invenId']),u['unitCode'],sorted((slot,str(g['invenId']),g['itemCode'],g['currentEnchant']) for slot,g in (u.get('equipMap') or {}).items())) for units in group.values() for u in units)
  left,right=placements(own_groups),placements(saved_groups)
  report['ownSavedDefenseComparison']={'sameOwnerVerified':True,'groupUnits':len(left),'savedDefenseUnits':len(right),'exactPlacementsAndInstancesMatch':left==right,
   'groupTeamNumbers':list(own_groups),'savedDefenseTeamNumbers':list(saved_groups),'comparisonAt':datetime.now(timezone.utc).isoformat(),'bothCopiesKeptInRamOnly':True}
 (ROOT/'reports/ranked-guild-member-war-groups-probe.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 return report

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--save-group',action='store_true');p.add_argument('--compare-own',action='store_true');args=p.parse_args()
 try:print(json.dumps(probe(args.save_group,args.compare_own),ensure_ascii=False))
 except Exception as e:
  print(json.dumps({'completed':False,'reason':str(e) if isinstance(e,(AcquisitionStopped,SessionUnavailable)) else type(e).__name__,'credentialsPersisted':False}));raise SystemExit(1)
