"""Rebuild only new guild-war records from saved copies and check template links."""
import json
from collections import Counter
from datetime import datetime,timezone
from guild_war_database import ROOT,connection,parse_directory,player_teams
from derive_guildwar_gear_values import read_rolls,observations,observation_id,matching_value


def validate():
 db=connection()
 try:
  docs=[json.loads(r[0]) for r in db.execute('SELECT s.payload FROM current_guild_war_sources c JOIN guild_war_sources s USING(source_id)')]
  by_source={}
  for doc in docs:
   path=doc['sourceDirectory']
   if path not in by_source:by_source[path]={r['sourceId']:r for r in parse_directory(ROOT/path)}
   if by_source[path].get(doc['sourceId'])!=doc:raise ValueError('guild-war source rebuild differs')
  def normalized(filename):
   row=db.execute('SELECT d.payload FROM current_documents c JOIN documents d USING(sha256) WHERE c.filename=?',(filename,)).fetchone()
   if not row:raise ValueError('accepted template document missing')
   return json.loads(row[0])['records']
  equipment={r['itemCode'] for r in normalized('verified-equipment.json')};characters={r['characterId'] for r in normalized('verified-characters.json')}
  gear=[];units=[];deployed=[];saved=[];rosters={gid:json.loads(p) for gid,p in db.execute('SELECT c.guild_id,r.payload FROM current_ranked_guild_rosters c JOIN guild_roster_sources r USING(source_id)')};roster_matches=0;observed_players=0
  for doc in docs:
   if doc['kind']=='deployed_defense':
    defenders=[d for t in doc['towers'] for d in t.get('defenders') or []];roster_ids={m['playerId'] for m in rosters.get(doc['guildId'],{}).get('members',[])}
    observed_players+=len(defenders);roster_matches+=sum(d['playerId'] in roster_ids for d in defenders)
   for _,team in player_teams(doc):
    units+=team['units'];gear.extend(e for u in team['units'] for e in u['equipment'].values() if e['state']=='equipped')
    (deployed if doc['kind']=='deployed_defense' else saved).extend(team['units'])
  stored=db.execute('SELECT count(*) FROM guild_war_equipment_instances WHERE source_id IN (SELECT source_id FROM current_guild_war_sources)').fetchone()[0]
  if stored!=len(gear):raise ValueError('guild-war equipment relational rows differ')
  roll_source,rolls=read_rolls(db);derived=0;unknown_values=0;known_labels=0;unmatched=[];calculation_kinds=Counter();unparsed_special=0;resolved_special=0
  labels={r[0] for r in db.execute('SELECT attribute_id FROM gear_attribute_labels WHERE source_id IN (SELECT source_id FROM current_gear_attribute_labels)')}
  for doc in docs:
   for tower,owner,team,unit,slot,e in observations(doc):
    if doc['kind']!='deployed_defense' or e['state']!='equipped':continue
    record=rolls.get(observation_id(doc,tower,owner,team,unit,slot));hits=0
    special=record.get('supplementarySpecial') if record else None
    resolved_special+=int(bool(special and special.get('state')=='values_reconstructed'))
    unparsed_special+=int(bool(special and special.get('state')!='values_reconstructed'))
    if record and record.get('sourceObservationSha256')!=doc['sourceSha256']:raise ValueError('roll source differs from actual tower copy')
    for a in (e.get('actualEffects') or {}).get('entries',[]):
     value=matching_value(record,owner,e,a)
     derived+=int(value is not None);hits+=int(value is not None);unknown_values+=int(value is None)
     known_labels+=int((a.get('sourceField') in ['attr1No','attr2No','attr3No','attr4No','attr5No'] and a['attributeId'] in labels) or bool(value and value.get('labelTemplate')))
     if value:calculation_kinds[value.get('calculationKind','ordinary')]+=1
     if a.get('value') is not None:raise ValueError('raw tower instance was overwritten with derived values')
    if record and hits!=len(record['entries']):unmatched.append(record['observationId'])
  if unmatched:raise ValueError('derived guild values no longer match their actual instance')
  integrity={t:db.execute('PRAGMA quick_check('+t+')').fetchone()[0] for t in ['guild_war_sources','current_guild_war_sources','guild_war_equipment_instances']}
  foreign=sum(len(db.execute('PRAGMA foreign_key_check('+t+')').fetchall()) for t in ['current_guild_war_sources','guild_war_equipment_instances'])
  if foreign or any(v!='ok' for v in integrity.values()):raise ValueError('guild-war storage integrity failed')
  report={'verifiedAt':datetime.now(timezone.utc).isoformat(),'overviewGuilds':sum(d['kind']=='overview' for d in docs),
   'towerIdentifiers':sum(len(d.get('towers',[])) for d in docs if d['kind']=='overview'),'savedConfigurations':sum(d['kind']=='saved_configuration' for d in docs),
   'savedConfigurationUnits':len(saved),'deployedUnits':len(deployed),'deployedPlayers':observed_players,'deployedRosterMatches':roster_matches,
   'deployedTowersRead':sum(t['readState']=='success' for d in docs if d['kind']=='deployed_defense' for t in d['towers']),
   'deployedEquipmentInstances':sum(e['state']=='equipped' for u in deployed for e in u['equipment'].values()),
   'deployedVerifiedEquipmentOwners':sum(e.get('ownerAssociationStatus')=='verified-native' for u in deployed for e in u['equipment'].values() if e['state']=='equipped'),
   'deployedEnhancementDistribution':dict(Counter(e['enhancement'] for u in deployed for e in u['equipment'].values() if e['state']=='equipped')),
   'deployedEffectsIdentifierEntries':sum(len(e['actualEffects']['entries']) for u in deployed for e in u['equipment'].values() if e.get('actualEffects')),
   'confirmedEmptyDeploymentEquipmentSlots':sum(e['state']=='not_equipped' for u in deployed for e in u['equipment'].values()),
   'equippedInstances':len(gear),'equipmentTemplateMatches':sum(e['equipmentId'] in equipment for e in gear),
   'unknownEquipmentIds':sorted({e['equipmentId'] for e in gear if e['equipmentId'] not in equipment}),
   'characterTemplateMatches':sum(u['characterId'] in characters for u in units),'unknownCharacterIds':sorted({u['characterId'] for u in units if u['characterId'] not in characters}),
   'effectsIdentifierEntries':sum(len(e.get('actualEffects',{}).get('entries',[])) for e in gear if e.get('actualEffects')),
   'verifiedEffectNumericalValues':0,'nativeReconstructedValues':derived,'unknownDeployedValues':unknown_values,'chineseDeployedEffectKinds':known_labels,'gearReconstructionSourceId':roll_source,
   'calculationKinds':dict(calculation_kinds),'activationConditionsVerified':False,'specialOptionAndTalentEffectsCovered':False,
   'specialOptionAndTalentDisplayCovered':resolved_special>0 and unparsed_special==0,'reconstructedSpecialEquipmentInstances':resolved_special,'unparsedSpecialEquipmentInstances':unparsed_special,
   'activeDeployedTeams':sum(1 for d in docs if d['kind']=='deployed_defense' for _ in player_teams(d)),'visualEquipmentChecks':0,
   'tableIntegrity':integrity,'foreignKeyErrors':foreign,'oldRankingAndRosterDataModified':False}
 finally:db.close()
 (ROOT/'reports/guildwar-current-validation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
 return report


if __name__=='__main__':print(json.dumps(validate()))
