import "server-only";
import {createHash} from "node:crypto";
import {readGuildWarStore,readNativeGearRolls,readCharacterInstanceProgress,readCharacterNativeStore} from "./local-game-data";
import {publicNativeTalents,characterTalentStages} from './character-native';
import {characterProgressKey,resolveCharacterProgress} from './character-instance-progress';
import {getCharacterReference} from "./character-reference";
import {getVerifiedEquipmentList} from "./verified-equipment";
import {displaySourceText} from "./display-text";
import {equipmentName} from "./equipment-filters";
import {getLocalGearIconUrl} from "./local-research-assets";
import {guildWarTowerNumber,guildWarTowerLabel} from "./guild-war-towers";
import {guildDefenderLevel} from './guild-defender-level';
import {getNativeGearLabelMap,resolveGearLabel} from "./gear-attribute-labels";
import {reconstructedEffect,reconstructedSpecial} from "./gear-instance-values";

type Gear={state:string;equipmentId:string|null;enhancement?:number;instanceGrade?:number;ownerAssociationStatus?:string;equipmentInstanceIdentity?:{namespace:string;value:string}|null;
 actualEffects?:{entries:{index:number;attributeId:number;valueGradeRaw:number;attributeTypeRaw:number|null;sourceField?:string}[]}|null};
type Unit={position:number;characterId:string;characterInstanceId:string;level:number;equipment:Record<string,Gear>};
type Defender={playerId:string;playerName:string;retrievedAt:string;isAI:boolean;withdrawal:boolean|null;teams:{teamNo:number;units:Unit[]}[]};
export type WarRecord={sourceKind:string;kind:string;sourceId:string;guildId:string;seasonNo:number;battleNo:number|null;seasonStatus:string;capturedAt:string;status:string;side?:string;
  towers?:{code:number;countersRaw?:number[];defendersState?:string;readState?:string;defenders:Defender[]|null}[];
  playerId?:string;configuredTeamNo?:number;deploymentState?:string;teams?:{teamNo:number;units:Unit[]}[]};
const alias=(id:string)=>createHash('sha256').update(id).digest('hex').slice(0,20);
export const guildGearObservationId=(source:string,tower:number|null,owner:string,team:number,position:number,slot:string)=>
 createHash('sha256').update(JSON.stringify(['guildwar',source,tower,owner,team,position,slot])).digest('hex');

export async function getGuildWar(guildAlias:string, memberLevels?: ReadonlyMap<string, number>){
 const records=(await readGuildWarStore() as WarRecord[]).filter(r=>alias(r.guildId)===guildAlias);
 const overview=records.find(r=>r.sourceKind==='verified-guildwar-overview'&&r.kind==='overview');
 const deployment=records.find(r=>r.sourceKind==='verified-guildwar-tower-deployments'&&r.kind==='deployed_defense');
 const configured=records.filter(r=>r.sourceKind==='verified-guildwar-saved-configuration'&&r.kind==='saved_configuration'&&r.deploymentState==='unconfirmed');
 if(!overview&&!configured.length&&!deployment)return null;
 const observations:string[]=[];
 const collectKeys=(teams:{teamNo:number;units:Unit[]}[],source:string,tower:number|null,owner:string)=>{
  for(const team of teams)for(const unit of team.units)for(const slot of Object.keys(unit.equipment))
   observations.push(guildGearObservationId(source,tower,owner,team.teamNo,unit.position,slot));
 };
 for(const r of configured)collectKeys(r.teams??[],r.sourceId,null,r.playerId!);
 for(const t of deployment?.towers??[])for(const d of t.defenders??[])collectKeys(d.teams,deployment!.sourceId,t.code,d.playerId);
 const progressKeys:string[]=[];
 for(const r of configured)for(const t of r.teams??[])for(const u of t.units)progressKeys.push(characterProgressKey('guildwar-saved',r.sourceId,r.playerId!,t.teamNo,u.position));
 for(const tower of deployment?.towers??[])for(const d of tower.defenders??[])for(const t of d.teams)for(const u of t.units)progressKeys.push(characterProgressKey('guildwar',deployment!.sourceId,d.playerId,t.teamNo,u.position,tower.code));
 const [rolls,labels,progress]=await Promise.all([readNativeGearRolls(observations,'guildwar'),getNativeGearLabelMap(),readCharacterInstanceProgress(progressKeys)]);
 const [characters,gear]=configured.length||deployment?await Promise.all([getCharacterReference(),getVerifiedEquipmentList()]):[null,[]];
 const names=new Map(characters?.records.map(r=>[r.characterId,r])??[]);const equipment=new Map(gear.map(r=>[r.itemCode,r]));
 const allUnits=records.flatMap(r=>[...(r.teams??[]),...(r.towers??[]).flatMap(t=>(t.defenders??[]).flatMap(d=>d.teams))]).flatMap(t=>t.units);
 const native=characters?.nativeSha?await readCharacterNativeStore(characters.nativeSha,[...new Set(allUnits.map(u=>u.characterId))]):null;
 const usedCodes=new Set(allUnits.flatMap(u=>Object.values(u.equipment).flatMap(e=>e.equipmentId?[e.equipmentId]:[])));
 const displayEquipment=new Map(await Promise.all([...usedCodes].map(async code=>{
   const template=equipment.get(code);
   return [code,template?{dataCode:template.dataCode,name:equipmentName(template)||'裝備名稱尚未取得',starCount:template.starCount,
     equipType:template.equipType,iconUrl:await getLocalGearIconUrl(template.dataCode),reference:template.reference??null}:null] as const;
 })));
 const progressFor=(u:Unit,teamNo:number,source:string,tower:number|null,owner:string,retrievedAt:string)=>resolveCharacterProgress(progress.get(characterProgressKey(tower===null?'guildwar-saved':'guildwar',source,owner,teamNo,u.position,tower)),{characterId:u.characterId,owner,instance:u.characterInstanceId,retrievedAt});
 const displayTeams=(teams:{teamNo:number;units:Unit[]}[],source:string,tower:number|null,owner:string,retrievedAt:string)=>teams.map(t=>({teamNo:t.teamNo,units:t.units.map(u=>({position:u.position,characterId:u.characterId,
   characterName:names.get(u.characterId)?.name??u.characterId,starCount:names.get(u.characterId)?.starGrade??null,level:u.level,
   imageUrl:names.get(u.characterId)?.imageUrl??null,elementType:names.get(u.characterId)?.elementType??null,roleType:names.get(u.characterId)?.roleType??null,
   characterProgress:progressFor(u,t.teamNo,source,tower,owner,retrievedAt),
   talentProgress:characterTalentStages(publicNativeTalents(native?.details.get(u.characterId),u.characterId),progressFor(u,t.teamNo,source,tower,owner,retrievedAt)?.talentGrade??null),
   slots:(['weapon','armor','accessory'] as const).map(slot=>{const e=u.equipment[slot];const template=e.equipmentId?displayEquipment.get(e.equipmentId)??null:null;
     const roll=rolls.get(guildGearObservationId(source,tower,owner,t.teamNo,u.position,slot));
     const bound=e.ownerAssociationStatus==='verified-native'&&(e.actualEffects?.entries.some(a=>reconstructedEffect(roll,e,a,owner,true)!==null)??false);
     const special=e.ownerAssociationStatus==='verified-native'?reconstructedSpecial(roll,e,owner):null;
     return {slot,state:e.state,equipmentId:e.equipmentId,enhancement:e.enhancement??null,
       extraSpecialObserved:bound&&roll?.extraSpecialObserved===true,
       extraSpecial:special?{name:displaySourceText(special.name),normalText:displaySourceText(special.normalText),description:displaySourceText(special.description),
         specialEnhancement:special.specialEnhancement,valueVisuallyVerified:false,activationState:'not_verified' as const}:null,
       template,
       effectIdentifiers:e.actualEffects?.entries.map(a=>({id:a.attributeId,valueGradeRaw:a.valueGradeRaw}))??null,
       actualEffects:e.actualEffects?.entries.map(a=>{const name=resolveGearLabel(a,labels);
        const result=e.ownerAssociationStatus==='verified-native'?reconstructedEffect(roll,e,a,owner,true):null;
        const label=result?.calculationKind==='native-skillplus'&&result.labelTemplate?displaySourceText(result.labelTemplate)+'（技能追加參數變化）':name.label;
        return {index:a.index,label,labelStatus:result?.labelTemplate?'native-skillplus':name.status,value:result?.value??null,unit:result?.unit??null,
         valueSource:result?.valueSource??null,factorCapturedAt:result?.factorCapturedAt??null,valueVisuallyVerified:false,
         calculationKind:result?.calculationKind??null,appliedEnhancementLevel:result?.appliedEnhancementLevel??null,conditionState:result?.conditionState??null,modifierOperator:result?.modifierOperator??null};})??null};})}))}));
 const allDefenders=deployment?.towers?.flatMap(t=>t.defenders??[])??[];
 return {overview:overview?{seasonNo:overview.seasonNo,battleNo:overview.battleNo,seasonStatus:overview.seasonStatus,capturedAt:overview.capturedAt,
   ageHours:Math.max(0,Math.floor((Date.now()-Date.parse(overview.capturedAt))/3600000)),
   towers:overview.towers?.map(t=>({code:t.code,number:guildWarTowerNumber(t.code),label:guildWarTowerLabel(t.code),defendersState:'not_read' as const}))??[]}:null,
   // Saved deck is deliberately not returned as a deployed tower/member team.
   savedConfigurations:configured.map(r=>({alias:alias(r.sourceId),playerAlias:alias(JSON.stringify([r.guildId,r.playerId])),capturedAt:r.capturedAt,
     deploymentState:'unconfirmed' as const,configuredTeamNo:r.configuredTeamNo,
     teams:displayTeams(r.teams??[],r.sourceId,null,r.playerId!,r.capturedAt)})),
   deployment:deployment?{seasonNo:deployment.seasonNo,battleNo:deployment.battleNo,seasonStatus:deployment.seasonStatus,status:deployment.status,capturedAt:deployment.capturedAt,historicalContext:(deployment as WarRecord&{historicalContext?:boolean}).historicalContext===true,
     uniqueHumanDefenders:new Set(allDefenders.filter(d=>!d.isAI).map(d=>d.playerId)).size,
     unitCount:allDefenders.reduce((n,d)=>n+d.teams.reduce((m,t)=>m+t.units.length,0),0),
     equippedCount:allDefenders.reduce((n,d)=>n+d.teams.reduce((m,t)=>m+t.units.reduce((k,u)=>k+Object.values(u.equipment).filter(e=>e.state==='equipped').length,0),0),0),
     towers:deployment.towers?.map(t=>({code:t.code,number:guildWarTowerNumber(t.code),label:guildWarTowerLabel(t.code),readState:t.readState??'not_read',defenders:t.defenders?.map(d=>({
       memberAlias:alias(JSON.stringify([deployment.guildId,d.playerId])),name:displaySourceText(d.playerName),retrievedAt:d.retrievedAt,isAI:d.isAI,withdrawal:d.withdrawal,
       playerLevel:d.isAI?null:guildDefenderLevel(memberLevels?.get(d.playerId)),
       teams:displayTeams(d.teams,deployment.sourceId,t.code,d.playerId,d.retrievedAt)}))??null}))??[]}:null,
   deployedTeams:allDefenders.reduce((n,d)=>n+d.teams.length,0)};
}

/** Keep the ten-tower summary; pass only the selected tower's large team data. */
export function guildWarPanelView(war:Awaited<ReturnType<typeof getGuildWar>>,towerCode?:string){
 if(!war||!war.deployment)return war?{...war,deployment:null}:null;
 const d=war.deployment;const selected=d.towers.find(t=>t.number!==null&&String(t.number)===towerCode)??d.towers.find(t=>String(t.code)===towerCode)??d.towers[0];
 return {...war,deployment:{...d,towers:d.towers.map(t=>({...t,defenderCount:t.defenders===null?null:t.defenders.length,defenders:t.code===selected?.code?t.defenders:null}))}};
}
