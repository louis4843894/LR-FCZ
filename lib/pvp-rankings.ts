import "server-only";
import {createHash} from "node:crypto";
import {readRankingStore,readNormalizedText,readLatestPvpUpdate,readNativeGearRolls} from "./local-game-data";
import {getDefenseTeams} from "./defense-teams";
import {displaySourceText} from "./display-text";
import {getCharacterReference} from "./character-reference";
import {getVerifiedEquipmentList} from "./verified-equipment";
import {equipmentName} from "./equipment-filters";
import {pvpScopeOrder,canonicalPvpScope,activePvpScope} from './pvp-scopes';
import {gearObservationId,reconstructedEffect} from './gear-instance-values';

export type RankingPlayer={playerId:string;rank:number;score:number;displayName:string|null};
type RankingDocument={sourceKind:string;snapshotId:string;capturedAt:string;lastCheckedAt?:string;status:string;loadedCount:number;retrievedPlayerCount:number;scope:{label:string;wholeRankingComplete:false};players:RankingPlayer[]};
type StoredAttempt={snapshotId:string;playerId:string;payload:unknown};
export type RankingAttempt={status:string;defenseSnapshotIds:string[];defenseRetrievedAt:string|null;failureReason:string|null;selectedTeamId?:string|null;cacheState?:string;sourceRankingSnapshotId?:string;lastCheckedAt?:string|null};
export type RankingTeam={snapshotId:string;playerId:string;purpose:string;teamId:string;status:string;isSelected?:boolean|null;unobservedPositionIndices?:number[]|null;members:{memberIndex?:number;characterState:string;characterId:string|null;equipment:Record<string,{state:string;equipmentId:string|null;enhancement?:number|null;instanceGrade?:number|null;equipmentInstanceIdentity?:{namespace:string;value:string}|null;actualEffects?:{entries:{index?:number;attributeId?:number;valueGradeRaw?:number;sourceField?:string;value?:number|null;valueVerified?:boolean}[]}|null}>}[]|null};
const slots=['weapon','armor','accessory'] as const;
const alias=(uid:string)=>createHash('sha256').update(uid).digest('hex').slice(0,12);
export const isRankingSnapshotId=(value:unknown):value is string=>typeof value==='string'&&/^pvp-ranking-(?:http-)?[a-f0-9]{24}$/.test(value);
const scopeOrder=pvpScopeOrder;

export function summarizeRankingCoverage(current:{scope:string;snapshotId:string}[],documents:RankingDocument[],rows:StoredAttempt[],teams:RankingTeam[]){
  const teamKeys=new Set(teams.filter(t=>t.purpose==='pvp_defense').map(t=>JSON.stringify([t.playerId,t.snapshotId])));
  return current.filter(c=>activePvpScope(c.scope)).map(c=>{
    const doc=documents.find(d=>d.snapshotId===c.snapshotId);if(!doc)return null;
    const attempts=new Map<string,RankingAttempt>();
    for(const row of rows)if(row.snapshotId===c.snapshotId)attempts.set(row.playerId,row.payload as RankingAttempt);
    const players=[...new Map(doc.players.map(p=>[p.playerId,p])).values()];
    let success=0,partial=0,unavailable=0,failed=0,notRead=0,teamCount=0;
    for(const player of players){
      const a=attempts.get(player.playerId);
      if(!a){notRead++;continue;}
      if(a.status==='success')success++;else if(a.status==='partial')partial++;else if(a.status==='unavailable')unavailable++;else if(a.status==='failed')failed++;else notRead++;
      if(a.status==='success'||a.status==='partial')teamCount+=a.defenseSnapshotIds.filter(id=>teamKeys.has(JSON.stringify([player.playerId,id]))).length;
    }
    return {scope:canonicalPvpScope(c.scope),players:players.length,success,partial,unavailable,failed,notRead,teams:teamCount,
      capturedAt:doc.capturedAt,lastCheckedAt:doc.lastCheckedAt??doc.capturedAt};
  }).filter(r=>r!==null).sort((a,b)=>scopeOrder.indexOf(a.scope)-scopeOrder.indexOf(b.scope));
}

export function summarizeRankedDefense(players:RankingPlayer[],attempts:Map<string,RankingAttempt>,teams:RankingTeam[]){
  const characterPlayers=new Map<string,Set<string>>(),characterAppearances=new Map<string,number>();
  const gearPlayers=new Map<string,Set<string>>(),gearAppearances=new Map<string,number>(),combinations=new Map<string,number>();
  let valid=0,gearValid=0,unknownSlots=0,failed=0,notRead=0,partial=0;
  const add=(playersMap:Map<string,Set<string>>,counts:Map<string,number>,id:string,uid:string)=>{
    const seen=playersMap.get(id)??new Set<string>();seen.add(uid);playersMap.set(id,seen);counts.set(id,(counts.get(id)??0)+1);
  };
  const unique=new Map(players.map(p=>[p.playerId,p]));
  for(const p of unique.values()){
    const a=attempts.get(p.playerId);if(!a){notRead++;continue;}
    if(a.status==='failed'||a.status==='unavailable'){failed++;continue;}
    const linked=teams.filter(t=>t.playerId===p.playerId&&t.purpose==='pvp_defense'&&a.defenseSnapshotIds.includes(t.snapshotId));
    const selected=linked.filter(t=>t.isSelected===true&&(!a.selectedTeamId||t.teamId===a.selectedTeamId));
    if(selected.length!==1||selected[0].status!=='success'||selected[0].unobservedPositionIndices?.length||selected[0].members===null||selected[0].members.some(m=>m.characterState!=='present'||!m.characterId)){partial++;continue;}
    const members=selected[0].members;valid++;
    for(const m of members)add(characterPlayers,characterAppearances,m.characterId!,p.playerId);
    const unknown=members.reduce((n,m)=>n+slots.filter(s=>{const e=m.equipment[s];return !e||!(e.state==='not_equipped'||e.state==='equipped'&&typeof e.equipmentId==='string'&&e.equipmentId.length>0);}).length,0);unknownSlots+=unknown;
    if(unknown)continue;
    gearValid++;
    for(const m of members){
      const ids=slots.map(s=>m.equipment[s].state==='equipped'?m.equipment[s].equipmentId:null);
      for(const id of ids)if(id)add(gearPlayers,gearAppearances,id,p.playerId);
      const key=JSON.stringify([m.characterId,...ids]);combinations.set(key,(combinations.get(key)??0)+1);
    }
  }
  const rows=(map:Map<string,Set<string>>,counts:Map<string,number>,denominator:number)=>[...map].map(([id,set])=>({id,playerCount:set.size,appearanceCount:counts.get(id)!,rate:denominator?set.size/denominator:null})).sort((a,b)=>b.playerCount-a.playerCount||b.appearanceCount-a.appearanceCount||a.id.localeCompare(b.id));
  return {rankedPlayers:unique.size,validPlayers:valid,equipmentValidPlayers:gearValid,failedPlayers:failed,notReadPlayers:notRead,partialPlayers:partial,unknownEquipmentSlots:unknownSlots,
    characters:rows(characterPlayers,characterAppearances,valid),equipment:rows(gearPlayers,gearAppearances,gearValid),
    combinations:[...combinations].map(([key,appearanceCount])=>{const [characterId,weaponId,armorId,accessoryId]=JSON.parse(key) as [string,string|null,string|null,string|null];return {characterId,weaponId,armorId,accessoryId,appearanceCount};}).sort((a,b)=>b.appearanceCount-a.appearanceCount),winRate:null};
}

async function context(snapshotId?:string,scope?:string){
  if(process.env.NODE_ENV!=='development')return null;
  const store=await readRankingStore();
  const documents=store.snapshots as RankingDocument[];
  if(!documents.length)return null;
  const current=store.current.filter(s=>activePvpScope(s.scope));
  const selectedId=snapshotId??current.find(s=>canonicalPvpScope(s.scope)===canonicalPvpScope(scope??'傳奇'))?.snapshotId??(scope?undefined:current[0]?.snapshotId);
  const original=documents.find(d=>d.snapshotId===selectedId);
  const document=original&&activePvpScope(original.scope.label)?{...original,scope:{...original.scope,label:canonicalPvpScope(original.scope.label)}}:null;
  if(!document||!['verified-native-pvp-ranking','verified-normal-pvp-league-ranking'].includes(document.sourceKind)||!Array.isArray(document.players))return null;
  const attempts=new Map<string,RankingAttempt>(),successes=new Map<string,RankingAttempt>();
  for(const row of store.attempts)if(row.snapshotId===document.snapshotId){const a=row.payload as RankingAttempt;attempts.set(row.playerId,a);if(a.status==='success'||a.status==='partial')successes.set(row.playerId,a);}
  const defense=JSON.parse(await readNormalizedText('defense-teams.private.json')) as {sourceKind:string;snapshots:RankingTeam[]};
  if(defense.sourceKind!=='validated-player-team-snapshots')throw new Error('防禦來源格式不正確');
  return {document,attempts,successes,teams:defense.snapshots,
    scopes:current.map(s=>canonicalPvpScope(s.scope)).sort((a,b)=>scopeOrder.indexOf(a)-scopeOrder.indexOf(b)),
    cohorts:summarizeRankingCoverage(current,documents,store.attempts,defense.snapshots),
    availableRankingPlayers:new Set(current.flatMap(c=>documents.find(d=>d.snapshotId===c.snapshotId)?.players.map(p=>p.playerId)??[])).size};
}

export async function getPvpRankings(scope?:string,top=100){
  const source=await context(undefined,scope);if(!source)return null;
  const {document,attempts,successes,teams}=source;
  const limit=Number.isSafeInteger(top)&&top>0?Math.min(top,1000):100;
  const players=document.players.filter(p=>p.rank<=limit).sort((a,b)=>a.rank-b.rank);
  const [characters,gear,lastUpdate]=await Promise.all([getCharacterReference(),getVerifiedEquipmentList(),readLatestPvpUpdate()]);
  const names=new Map(characters?.records.map(r=>[r.characterId,r.name??r.characterId])??[]);
  const gearNames=new Map(gear.map(r=>[r.itemCode,equipmentName(r)]));
  const stats=summarizeRankedDefense(players,attempts,teams);
  const linked=teams.filter(t=>t.purpose==='pvp_defense'&&t.status==='success'&&players.some(p=>p.playerId===t.playerId&&successes.get(p.playerId)?.defenseSnapshotIds.includes(t.snapshotId)));
  const linkedGear=linked.flatMap(t=>t.members?.flatMap(m=>Object.values(m.equipment))??[]).filter(e=>e.state==='equipped');
  const attributes=linkedGear.flatMap(g=>g.actualEffects?.entries??[]);
  const observationIds=linked.flatMap(t=>t.members?.flatMap(m=>m.memberIndex===undefined?[]:Object.keys(m.equipment).map(slot=>gearObservationId(t.snapshotId,t.playerId,m.memberIndex!,slot)))??[]);
  const rolls=await readNativeGearRolls(observationIds);
  const reconstructedValues=linked.reduce((total,t)=>total+(t.members?.reduce((n,m)=>n+Object.entries(m.equipment).reduce((sum,[slot,g])=>sum+(g.actualEffects?.entries.filter(a=>{
    if(a.valueVerified===true&&typeof a.value==='number'&&Number.isFinite(a.value))return false;
    if(m.memberIndex===undefined||a.index===undefined||a.attributeId===undefined||a.valueGradeRaw===undefined)return false;
    return !!reconstructedEffect(rolls.get(gearObservationId(t.snapshotId,t.playerId,m.memberIndex,slot)),g,{index:a.index,attributeId:a.attributeId,valueGradeRaw:a.valueGradeRaw,sourceField:a.sourceField},t.playerId);
  }).length??0),0),0)??0),0);
  const nativeValues=attributes.filter(e=>e.valueVerified===true&&typeof e.value==='number'&&Number.isFinite(e.value)).length;
  const attributeValues=nativeValues+reconstructedValues;
  return {snapshotId:document.snapshotId,scopeLabel:document.scope.label,scopes:source.scopes,capturedAt:document.capturedAt,rankingCheckedAt:document.lastCheckedAt??document.capturedAt,lastUpdate,
    availableRankingPlayers:source.availableRankingPlayers,cohorts:source.cohorts,teamsRetrieved:linked.length,equipmentRetrieved:linkedGear.length,equipmentMatched:linkedGear.filter(e=>e.equipmentId&&gearNames.has(e.equipmentId)).length,
    attributeEntries:attributes.length,attributeValues,attributeNativeValues:nativeValues,attributeReconstructedValues:reconstructedValues,attributeUnknown:attributes.length-attributeValues,
    unknownEquipmentIds:[...new Set(linkedGear.filter(e=>e.equipmentId&&!gearNames.has(e.equipmentId)).map(e=>e.equipmentId!))],
    loadedCount:document.loadedCount,retrievedPlayerCount:document.players.length,sourceStatus:document.status,top:limit,
    rankMinimum:players.length?Math.min(...players.map(p=>p.rank)):null,rankMaximum:players.length?Math.max(...players.map(p=>p.rank)):null,
    players:players.map(p=>{const a=attempts.get(p.playerId),old=successes.get(p.playerId);return {alias:alias(p.playerId),rank:p.rank,score:p.score,name:p.displayName?displaySourceText(p.displayName):'名稱尚未取得',
      defenseState:a?.status??'not_read',retrievedAt:old?.defenseRetrievedAt??null,lastCheckedAt:a?.lastCheckedAt??old?.lastCheckedAt??null,hasDefense:!!old,cacheState:old?.cacheState??null};}),
    stats:{...stats,characters:stats.characters.map(r=>({...r,name:names.get(r.id)??r.id,known:names.has(r.id)})),equipment:stats.equipment.map(r=>({...r,name:gearNames.get(r.id)??r.id,known:gearNames.has(r.id)})),
      combinations:stats.combinations.map(r=>({...r,characterName:names.get(r.characterId)??r.characterId,gearNames:[r.weaponId,r.armorId,r.accessoryId].map(id=>id?(gearNames.get(id)??id):'已確認空部位')}))}};
}

export async function getRankedDefense(playerAlias:string,snapshotId:string){
  if(!/^[a-f0-9]{12}$/.test(playerAlias)||!isRankingSnapshotId(snapshotId))return null;
  const source=await context(snapshotId);if(!source)return null;
  const player=source.document.players.find(p=>alias(p.playerId)===playerAlias);if(!player)return null;
  const a=source.successes.get(player.playerId);if(!a)return null;
  const teams=await getDefenseTeams('pvp_defense',player.playerId,{snapshotIds:new Set(a.defenseSnapshotIds)});
  if(!teams)return null;
    return {teams,rankingContext:{scopeLabel:source.document.scope.label,rank:player.rank,score:player.score,snapshotId:source.document.snapshotId,rankingCapturedAt:source.document.capturedAt,lastCheckedAt:a.lastCheckedAt??null,cacheState:a.cacheState??null,latestStatus:source.attempts.get(player.playerId)?.status??a.status}};
}
