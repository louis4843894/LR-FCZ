import {createHash} from 'node:crypto';
const digest=(value:unknown)=>createHash('sha256').update(JSON.stringify(value)).digest('hex');
export const characterProgressKey=(scope:string,source:string,owner:string,team:string|number,position:number,tower:number|null=null)=>digest([scope,source,tower,owner,String(team),position]);
type Expected={characterId:string|null;owner:string;instance:string|undefined;retrievedAt:string};
const integer=(v:unknown,min=0)=>typeof v==='number'&&Number.isSafeInteger(v)&&v>=min&&v<=0xffffffff?v:null;
const text=(v:unknown)=>typeof v==='string'&&v.length>0&&v.length<=12000?v:null;
export function resolveCharacterProgress(value:unknown,expected:Expected){
 if(!value||typeof value!=='object'||Array.isArray(value)||!expected.instance)return null;
 const r=value as Record<string,unknown>;
 if(r.recordScope!=='player-character-instance'||r.templateTrainingSubstituted!==false||r.characterId!==expected.characterId||r.retrievedAt!==expected.retrievedAt||r.instanceHash!==digest([expected.owner,'player-owned-unit',expected.instance]))return null;
 const a=r.awakening&&typeof r.awakening==='object'&&!Array.isArray(r.awakening)?r.awakening as Record<string,unknown>:{};
 const state=a.state==='present'&&typeof a.abilityCode==='string'&&/^[A-Za-z0-9_-]{1,160}$/.test(a.abilityCode)?'present':a.state==='empty_observed'&&!a.abilityCode?'empty_observed':'not_returned';
 return {level:integer(r.level,1),maxLevel:integer(r.maxLevel,1),leonardPoints:integer(r.leonardPoints),talentGrade:integer(r.talentGrade),
  awakening:{state,name:state==='present'?text(a.name):null,description:state==='present'?text(a.description):null},
  retrievedAt:expected.retrievedAt,visuallyVerified:false as const,templateTrainingSubstituted:false as const};
}
export type CharacterInstanceProgress=NonNullable<ReturnType<typeof resolveCharacterProgress>>;
