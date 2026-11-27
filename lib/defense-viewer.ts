import type {CharacterInstanceProgress} from './character-instance-progress';
import type {characterTalentStages} from './character-native';
import type {ReferenceEquipment} from './equipment-reference';

/** Display-only contract. Account IDs, instance IDs and research paths stay on the server. */
export type ViewerGear = {
  slot:'weapon'|'armor'|'accessory'; state:string; name:string; dataCode:string|null;
  imageUrl:string|null; stars:number|null; enhancement:number|null;
  effects:{label:string;value:string;note:string|null}[]|null; effectStatus:string;
  special:{name:string;description:string;note:string}|null;
  reference:ReferenceEquipment|null;
};
export type ViewerUnit = {
  key:string;position:number;state:string;characterId:string|null;name:string;
  imageUrl:string|null;stars:number|null;element:string|null;role:string|null;
  progress:CharacterInstanceProgress|null;talents:ReturnType<typeof characterTalentStages>;
  gear:ViewerGear[];
};
export type ViewerTeam = {
  key:string;label:string;status:string;retrievedAt:string;
  note:string;unobservedPositions:number[];units:ViewerUnit[];
};
export const viewerTeams=(teams:ViewerTeam[],key:string)=>key==='all'?teams:teams.filter(t=>t.key===key);
export const viewerSelectedUnit=(teams:ViewerTeam[],teamKey:string,unitKey:string|null)=>
  viewerTeams(teams,teamKey).flatMap(t=>t.units).find(u=>u.key===unitKey)??null;
// Explicit parts avoid Node/Chromium ICU whitespace differences during hydration.
export function viewerTime(s:string){
  const parts=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Taipei',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'}).formatToParts(new Date(s));
  const part=(type:string)=>parts.find(p=>p.type===type)?.value??'';
  return `${part('year')}/${part('month')}/${part('day')} ${part('hour')}:${part('minute')}:${part('second')}`;
}
export const viewerSlotName={weapon:'武器',armor:'防具',accessory:'飾品'};
export const viewerElementName=(s:string|null)=>({FIRE:'火',WATER:'水',TREE:'木',LIGHT:'光',DARK:'暗',NONE:'無'} as Record<string,string>)[s?.toUpperCase()??'']??'未知';
export function actualEffectText(value:number|null,unit:string|null,operator?:string|null){
  if(value===null||!Number.isFinite(value))return '數值尚未解析';
  const n=operator?Math.abs(value):value;
  const formatted=Number(n.toFixed(3)).toLocaleString('zh-TW',{maximumFractionDigits:3});
  return `${operator??(n>0?'+':'')}${formatted}${unit==='PERCENT'?'%':unit==='SECOND'?' 秒':unit==='POINT'?' 點':''}`;
}
