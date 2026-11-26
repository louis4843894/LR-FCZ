/** Display whitelist. Template candidates never become player awakening state. */
import {characterAvailability} from './template-availability';
type Dict=Record<string,unknown>;
const obj=(v:unknown):Dict|null=>v!==null&&typeof v==='object'&&!Array.isArray(v)?v as Dict:null;
const text=(v:unknown)=>typeof v==='string'&&v.length>0&&v.length<=12000?v:null;
const number=(v:unknown)=>typeof v==='number'&&Number.isFinite(v)?v:null;
const chance=(v:unknown)=>number(v)!==null&&Number(v)>=0&&Number(v)<=100?Number(v):null;
const bool=(v:unknown)=>typeof v==='boolean'?v:null;
const code=(v:unknown)=>typeof v==='string'&&/^[A-Za-z0-9_-]{1,160}$/.test(v)?v:null;
function rows<T>(v:unknown,map:(row:Dict)=>T,limit=128):T[]|null{
 if(!Array.isArray(v)||v.length>limit||v.some(r=>!obj(r)))return null;
 return v.map(r=>map(obj(r)!));
}
function effect(r:Dict){return {name:text(r.name),magnitudeText:text(r.magnitudeText),durationText:text(r.durationText),rangePoints:number(r.rangePoints),
 triggerChancePercent:chance(r.triggerChancePercent),targetLimitText:text(r.targetLimitText),availableEvents:bool(r.availableEvents),availableGuardian:bool(r.availableGuardian)};}
function skill(r:Dict){return {skillCode:code(r.skillCode),name:text(r.name),description:text(r.description),status:r.status==='matched-reference'?'matched-reference':'unresolved',
 activationRatePercent:chance(r.activationRatePercent),cooldownSeconds:number(r.cooldownSeconds),startupSeconds:number(r.startupSeconds)!==null&&Number(r.startupSeconds)>=0?Number(r.startupSeconds):null,triggerLabel:text(r.triggerLabel),searchRatio:number(r.searchRatio),effects:rows(r.effects,effect)};}
function ability(r:Dict){return {abilityCode:code(r.abilityCode),name:text(r.name),description:text(r.description),status:r.status==='matched-reference'?'matched-reference':'unresolved',
 triggerEffects:rows(r.triggerEffects,t=>({chancePercent:chance(t.chancePercent),phase:text(t.phase),battleMode:text(t.battleMode),condition:text(t.condition),additionalCondition:text(t.additionalCondition),effect:text(t.effect)}))};}
function talent(r:Dict){
 const m=obj(r.major);return {major:m?{talentCode:code(m.talentCode),description:text(m.description),activationChancePercent:chance(m.activationChancePercent),condition:text(m.condition),
  additionalConditions:Array.isArray(m.additionalConditions)?m.additionalConditions.map(text).filter((s):s is string=>s!==null):[],
  effects:rows(m.effects,e=>({description:text(e.description),durationSeconds:number(e.durationSeconds),activationChancePercent:chance(e.activationChancePercent)}))}:null,
  enhancements:rows(r.enhancements,e=>({talentCode:code(e.talentCode),description:text(e.description)}))};
}
function stats(r:Dict){
 const nested=(parent:string,key:string)=>number(obj(r[parent])?.[key]);
 return [
  {label:'體力',value:number(r.hp),unit:''},{label:'物理攻擊力',value:nested('attack','physical'),unit:''},{label:'魔法攻擊力',value:nested('attack','magical'),unit:''},
  {label:'物理防禦力',value:nested('defense','physical'),unit:''},{label:'魔法防禦力',value:nested('defense','magical'),unit:''},
  {label:'生產礦物費用',value:number(r.mineralCost),unit:''},{label:'再出動時間',value:number(r.respawnSeconds),unit:'秒'},
  {label:'攻擊範圍',value:number(r.attackRange),unit:'點'},{label:'濺射範圍',value:number(r.splashRange),unit:'點'},
  {label:'移動速度',value:nested('moveSpeed','pointsPerSecond'),unit:'點／秒'},{label:'攻擊間隔',value:nested('attackSpeed','secondsPerAttack'),unit:'秒／次'},
  ...[['criticalChancePercent','爆擊機率'],['criticalDamagePercent','爆擊傷害'],['dodgeChancePercent','閃避機率'],['skillDodgeChancePercent','技能閃避機率'],
      ['skillResistancePercent','技能抗性'],['hitChancePercent','命中率'],['skillHitChancePercent','技能命中率']].map(([key,label])=>({label,value:number(r[key]),unit:'%'})),
 ];
}
export function publicCharacterDetails(value:unknown,characterId:string){
 const r=obj(value);if(!r||r.characterId!==characterId||r.status!=='matched-reference')return null;
 const t=obj(r.talents),s=obj(r.stats);
 return {skills:rows(r.skills,skill,8),abilities:rows(r.abilities,ability,32),awakeningAbilities:rows(r.awakeningAbilities,ability,32),
  talents:t?talent(t):null,stats:s?stats(s):null,availability:characterAvailability(r),evolution:code(r.evolution),releaseDate:typeof r.releaseDate==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(r.releaseDate)?r.releaseDate:null,
  templateOnly:true as const,playerTrainingOrEquipmentApplied:false as const,awakeningCandidatesAreNotPlayerAwakening:true as const};
}
export type CharacterDetails=NonNullable<ReturnType<typeof publicCharacterDetails>>;
