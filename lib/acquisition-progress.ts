import "server-only";
import {readSiteDisplay} from './site-display-data';
import { readNormalizedText,readCollectionTarget,readRankedSnapshotKeys } from "./local-game-data";
import { getCharacterReference } from "./character-reference";
import { getPvpRankings } from "./pvp-rankings";
import { getGuildRankings } from "./guild-rankings";

type Equipment={state:string;equipmentId:string|null;enhancement?:number|null;actualEffects?:{entries:{value?:number|null;valueVerified?:boolean}[]}|null};
type Snapshot={playerId:string;purpose:string;teamId:string;status:string;retrievedAt:string;unobservedPositionIndices?:number[];members:{characterId:string|null;equipment:Record<string,Equipment>}[]|null};
export function summarizeDefense(snapshots:Snapshot[], rosterIds:Set<string>, templateIds:Set<string>) {
  const latest=new Map<string,Snapshot>();
  for(const row of snapshots){
    const key=JSON.stringify([row.playerId,row.purpose,row.teamId]);const previous=latest.get(key);
    if(!previous || Date.parse(row.retrievedAt)>Date.parse(previous.retrievedAt))latest.set(key,row);
  }
  const rows=[...latest.values()];const pvp=rows.filter(t=>t.purpose==="pvp_defense");
  const valid=pvp.filter(t=>t.status==="success");const guild=valid.filter(t=>rosterIds.has(t.playerId));
  const gear=valid.flatMap(t=>t.members?.flatMap(m=>Object.values(m.equipment)) ?? []).filter(e=>e.state==="equipped");
  const entries=gear.flatMap(e=>e.actualEffects?.entries ?? []);
  const values=entries.filter(e=>e.valueVerified===true && typeof e.value==="number" && Number.isFinite(e.value)).length;
  const unknownIds=[...new Set(gear.filter(e=>e.equipmentId&&!templateIds.has(e.equipmentId)).map(e=>e.equipmentId!))].sort();
  const guildPlayers=new Set(guild.map(t=>t.playerId)).size;
  return {pvpPlayers:new Set(valid.map(t=>t.playerId)).size,pvpTeams:valid.length,guildPlayers,guildTeams:guild.length,
    guildUnread:Math.max(0,rosterIds.size-guildPlayers),partialTeams:valid.filter(t=>t.unobservedPositionIndices?.length).length,
    failedTeams:pvp.filter(t=>t.status==="failed").length,equipment:gear.length,enhancementKnown:gear.filter(e=>Number.isInteger(e.enhancement)).length,
    equipmentMatched:gear.filter(e=>e.equipmentId&&templateIds.has(e.equipmentId)).length,unknownEquipmentIds:unknownIds,
    attributeEntries:entries.length,attributeValues:values,attributeUnknown:entries.length-values,
    guildBattleTeams:rows.filter(t=>t.purpose==="guild_battle_defense"&&t.status==="success").length,
    latestDefenseAt:pvp.map(t=>t.retrievedAt).sort((a,b)=>Date.parse(b)-Date.parse(a))[0] ?? null};
}

export async function getAcquisitionProgress():Promise<Awaited<ReturnType<typeof getLocalAcquisitionProgress>>>{
  return process.env.NODE_ENV==='production'?readSiteDisplay('status'):getLocalAcquisitionProgress();
}
async function getLocalAcquisitionProgress(){
  if(process.env.NODE_ENV!=="development")return null;
  const [rosterText,defenseText,equipmentText,characters,rankedKeys,rankings,rankedGuilds]=await Promise.all([
    readNormalizedText("guild-roster.private.json"),readNormalizedText("defense-teams.private.json"),readNormalizedText("verified-equipment.json"),getCharacterReference(),readRankedSnapshotKeys(),getPvpRankings('傳奇',200),getGuildRankings(),
  ]);
  const roster=JSON.parse(rosterText);const defense=JSON.parse(defenseText);const equipment=JSON.parse(equipmentText);
  if(roster.sourceKind!=="validated-native-guild-roster"||defense.sourceKind!=="validated-player-team-snapshots"||equipment.sourceKind!=="verified-equipment-template")throw new Error("資料來源無效");
  const summary=summarizeDefense(defense.snapshots.filter((s:{playerId:string;snapshotId:string})=>!rankedKeys.has(JSON.stringify([s.playerId,s.snapshotId]))),new Set(roster.members.map((m:{playerId:string})=>m.playerId)),new Set(equipment.records.map((e:{itemCode:string})=>e.itemCode)));
  const selectedGuildName=rankedGuilds?'公會前100名':await readCollectionTarget("guild");const guildMatches=!rankedGuilds&&(!selectedGuildName||selectedGuildName===roster.name);
  return {...summary,guildBattleTeams:rankedGuilds?.defenseTeams??summary.guildBattleTeams,guildPlayers:guildMatches ? summary.guildPlayers : 0,guildTeams:guildMatches ? summary.guildTeams : 0,guildUnread:guildMatches ? summary.guildUnread : null,
    templates:equipment.records.length,guildTotal:guildMatches ? roster.members.length : null,guildRosterAt:guildMatches ? roster.capturedAt : null,selectedGuildName:selectedGuildName ?? roster.name,
    historicalGuildName:roster.name,historicalGuildPlayers:summary.guildPlayers,guildMatches,
    characters:characters?.records.length ?? 0,characterCoverage:characters?.coverage ?? null,
    rankedGuildSummary:rankedGuilds?{guilds:rankedGuilds.guilds.length,completeRosters:rankedGuilds.completeRosters,members:rankedGuilds.membersRetrieved,defenseGuilds:rankedGuilds.defenseGuilds}:null,
    guildBattleUnavailable:guildMatches && roster.guildBattleAvailability?.guildId===roster.guildId && roster.guildBattleAvailability?.source==="user-confirmed" && roster.guildBattleAvailability?.reasonCode==="not_registered",
    rankingSamples:rankings?.stats.validPlayers??0,rankingPlayers:rankings?.availableRankingPlayers??0,rankingTeams:rankings?.teamsRetrieved??0,rankingEquipment:rankings?.equipmentRetrieved??0,rankingEquipmentMatched:rankings?.equipmentMatched??0,rankingUnknownEquipmentIds:rankings?.unknownEquipmentIds??[],rankingNotRead:rankings?.stats.notReadPlayers??0,rankingFailures:rankings?.stats.failedPlayers??0,
    rankingAttributeEntries:rankings?.attributeEntries??0,rankingAttributeValues:rankings?.attributeValues??0,rankingAttributeUnknown:rankings?.attributeUnknown??0,rankingCohorts:rankings?.cohorts??[],
    storage:process.env.LR_LOCAL_DATABASE_PATH ? "本機 SQLite" : "本機標準化快照"};
}
