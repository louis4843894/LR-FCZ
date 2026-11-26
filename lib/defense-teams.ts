import "server-only";
import { readNormalizedText,readRankedSnapshotKeys,readNativeGearRolls,readCharacterInstanceProgress,readCharacterNativeStore } from "./local-game-data";
import {publicNativeTalents,characterTalentStages} from './character-native';
import {characterProgressKey,resolveCharacterProgress} from './character-instance-progress';
import { createHash } from "node:crypto";
import { getCharacterReference } from "./character-reference";
import { getVerifiedEquipmentList } from "./verified-equipment";
import { displaySourceText } from "./display-text";
import { getEquipmentMappingMap } from "./equipment-mapping";
import {getNativeGearLabelMap,resolveGearLabel} from "./gear-attribute-labels";
import {getLocalGearIconUrl} from "./local-research-assets";
import {gearObservationId,reconstructedEffect} from './gear-instance-values';

type Slot = "weapon" | "armor" | "accessory";
type EffectIdentifiers = {status:"identifiers_only"|"partial_values";entries:{index:number;attributeId:number;valueGradeRaw:number;attributeTypeRaw:number|null;sourceField?:string;attributeCode?:string|null;attributeLabel?:string|null;value?:number|null;unit?:"PERCENT"|"FLAT"|null;valueVerified?:boolean;enhancementIncluded?:boolean;valueVisuallyVerified?:boolean}[];numericalValuesVerified:false;valueFactorRetrievedAt?:string|null};
type Team = { snapshotId: string; playerId: string; teamId: string | null; purpose: string; status: string; retrievedAt: string; guildId: string | null;
  playerDisplayName?:string|null;
  isSelected?:boolean|null;gameVersion?:string|null;unobservedPositionIndices?:number[]|null;
  verification?: {checkedAt:string;purposeConfirmed:boolean;visibleRangerCount:number;equipmentValuesVisuallyVerified:boolean} | null;
  members: null | { memberIndex: number; characterState: string; characterId: string | null;
    characterInstanceIdentity: { value:string;sourceField:string;namespace:string } | null;
    equipment: Record<Slot,{state:string;equipmentId:string|null;enhancement:number|null;instanceGrade?:number|null;equipmentInstanceIdentity?:{value:string;sourceField:string;namespace:string}|null;attributeReadState?:string;actualEffects:EffectIdentifiers|null}> }[] };
export async function getDefenseTeams(purpose: "pvp_defense" | "guild_battle_defense", ownerPlayerId?:string,filter?:{snapshotIds?:ReadonlySet<string>;excludeRanked?:boolean}) {
  if (process.env.NODE_ENV !== "development") return null;
  let teams: Team[];
  try {
    const data = JSON.parse(await readNormalizedText("defense-teams.private.json"));
    if (data.sourceKind !== "validated-player-team-snapshots" || data.recordScope !== "player-team" || !Array.isArray(data.snapshots)) throw new Error("防禦快照格式不正確");
    const ranked=filter?.excludeRanked ? await readRankedSnapshotKeys() : new Set<string>();
    teams = data.snapshots.filter((s:Team)=>s.purpose===purpose && (ownerPlayerId===undefined || s.playerId===ownerPlayerId) && (!filter?.snapshotIds||filter.snapshotIds.has(s.snapshotId)) && !ranked.has(JSON.stringify([s.playerId,s.snapshotId])));
  } catch (error: unknown) {
    if (error instanceof Error && "code" in error && error.code === "ENOENT") return null;
    throw error;
  }
  if (!teams.length) return null;
  const latest = new Map<string,Team>();
  for (const team of teams) {
    const key = JSON.stringify([team.guildId,team.playerId,team.teamId]);
    const previous = latest.get(key);
    if (!previous || Date.parse(team.retrievedAt)>Date.parse(previous.retrievedAt)) latest.set(key,team);
  }
  const observationIds=[...latest.values()].flatMap(t=>t.members?.flatMap(m=>['weapon','armor','accessory'].map(slot=>gearObservationId(t.snapshotId,t.playerId,m.memberIndex,slot)))??[]);
  const progressIds=[...latest.values()].flatMap(t=>t.members?.map(m=>characterProgressKey('pvp',t.snapshotId,t.playerId,t.teamId?.split('/').at(-1)??'',m.memberIndex))??[]);
  const [characters,equipment,mappings,labels,rolls,progress] = await Promise.all([getCharacterReference(),getVerifiedEquipmentList(),getEquipmentMappingMap(),getNativeGearLabelMap(),readNativeGearRolls(observationIds),readCharacterInstanceProgress(progressIds)]);
  const names = new Map(characters?.records.map(r=>[r.characterId,r]) ?? []);
  const native=characters?.nativeSha?await readCharacterNativeStore(characters.nativeSha,[...new Set([...latest.values()].flatMap(t=>t.members?.flatMap(m=>m.characterId?[m.characterId]:[])??[]))]):null;
  const progressFor=(t:Team,m:NonNullable<Team['members']>[number])=>resolveCharacterProgress(progress.get(characterProgressKey('pvp',t.snapshotId,t.playerId,t.teamId?.split('/').at(-1)??'',m.memberIndex)),{characterId:m.characterId,owner:t.playerId,instance:m.characterInstanceIdentity?.value,retrievedAt:t.retrievedAt});
  const gear = new Map(equipment.map(r=>[r.itemCode,r]));
  const used=new Set([...latest.values()].flatMap(t=>t.members?.flatMap(m=>Object.values(m.equipment).flatMap(e=>e.equipmentId?[e.equipmentId]:[]))??[]));
  const icons=new Map(await Promise.all([...used].map(async id=>[id,await getLocalGearIconUrl(id+'_nm')] as const)));
  return [...latest.values()].sort((a,b)=>a.playerId.localeCompare(b.playerId)).map(t=>({snapshotId:t.snapshotId,playerId:`本機玩家-${createHash("sha256").update(t.playerId).digest("hex").slice(0,12)}`,playerDisplayName:t.playerDisplayName ? displaySourceText(t.playerDisplayName) : null,teamId:t.teamId,purpose:t.purpose,status:t.status,retrievedAt:t.retrievedAt,guildId:t.guildId,
    isSelected:t.isSelected ?? null,gameVersion:t.gameVersion ?? null,unobservedPositionIndices:t.unobservedPositionIndices ?? null,
    ageHours:Math.max(0,Math.floor((Date.now()-Date.parse(t.retrievedAt))/3600000)),
    attributeFactorTimes:[...new Set(t.members?.flatMap(m=>Object.entries(m.equipment).flatMap(([slot,e])=>{
      const roll=rolls.get(gearObservationId(t.snapshotId,t.playerId,m.memberIndex,slot));
      const derived=e.actualEffects?.entries.some(a=>reconstructedEffect(roll,e,a,t.playerId));
      return [e.actualEffects?.valueFactorRetrievedAt,derived?roll?.factorCapturedAt:null].filter((v):v is string=>typeof v==='string');
    })) ?? [])],
    verification:t.verification ? {checkedAt:t.verification.checkedAt,purposeConfirmed:t.verification.purposeConfirmed,visibleRangerCount:t.verification.visibleRangerCount,equipmentValuesVisuallyVerified:t.verification.equipmentValuesVisuallyVerified} : null,
    members:t.members?.map(m=>({memberIndex:m.memberIndex,characterState:m.characterState,characterId:m.characterId,
    characterInstanceIdentity:m.characterInstanceIdentity ? {value:m.characterInstanceIdentity.value,sourceField:m.characterInstanceIdentity.sourceField,namespace:m.characterInstanceIdentity.namespace} : null,
    characterName:m.characterId ? names.get(m.characterId)?.name ?? m.characterId : null,
    imageUrl:m.characterId?names.get(m.characterId)?.imageUrl??null:null,
    starCount:m.characterId?names.get(m.characterId)?.starGrade??null:null,
    elementType:m.characterId?names.get(m.characterId)?.elementType??null:null,
    roleType:m.characterId?names.get(m.characterId)?.roleType??null:null,
    characterProgress:progressFor(t,m),
    talentProgress:m.characterId?characterTalentStages(publicNativeTalents(native?.details.get(m.characterId),m.characterId),progressFor(t,m)?.talentGrade??null):null,
    slots:(["weapon","armor","accessory"] as const).map(slot=>{const e=m.equipment[slot];const template=e.equipmentId ? gear.get(e.equipmentId) : null;return {slot,state:e.state,equipmentId:e.equipmentId,enhancement:e.enhancement ?? null,instanceGrade:e.instanceGrade ?? null,attributeReadState:e.attributeReadState ?? "not_captured",
      actualEffects:e.actualEffects ? {status:e.actualEffects.status,numericalValuesVerified:false,entries:e.actualEffects.entries.map(a=>{
        const verified=e.actualEffects?.status==="partial_values" && a.valueVerified===true && a.enhancementIncluded===true && typeof a.value==="number" && Number.isFinite(a.value) && (a.unit==="PERCENT" || a.unit==="FLAT");
        const derived=verified?null:reconstructedEffect(rolls.get(gearObservationId(t.snapshotId,t.playerId,m.memberIndex,slot)),e,a,t.playerId);
        const observation=createHash('sha256').update(JSON.stringify([t.snapshotId,t.playerId,m.memberIndex,slot])).digest('hex');
        const linked=mappings.get(`${observation}:${a.index}`);const externalMapping=!verified&&linked?.itemCode===e.equipmentId&&linked.attributeId===a.attributeId ? linked.mapping : null;
        const translated=resolveGearLabel(a,labels);
        return {index:a.index,attributeId:a.attributeId,valueGradeRaw:a.valueGradeRaw,attributeTypeRaw:a.attributeTypeRaw,attributeCode:a.attributeCode ?? null,attributeLabel:a.attributeLabel ? displaySourceText(a.attributeLabel) : null,displayLabel:translated.label,labelStatus:translated.status,value:verified ? a.value! : derived?.value??null,unit:verified ? a.unit! : derived?.unit??null,enhancementIncluded:verified||!!derived,valueVisuallyVerified:verified && a.valueVisuallyVerified===true,valueSource:derived?'native-definition-reconstruction':'native-instance',externalMapping};
      })} : null,
      equipmentInstanceIdentity:e.equipmentInstanceIdentity ? {value:e.equipmentInstanceIdentity.value,sourceField:e.equipmentInstanceIdentity.sourceField,namespace:e.equipmentInstanceIdentity.namespace} : null,
      template:template ? {itemCode:template.itemCode,dataCode:template.dataCode,names:template.names,starCount:template.starCount,equipType:template.equipType,effects:null,reference:template.reference,iconUrl:icons.get(template.itemCode)??null} : null};})
  })) ?? null}));
}
