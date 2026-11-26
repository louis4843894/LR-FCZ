const obj=(v:unknown):Record<string,unknown>|null=>v!==null&&typeof v==='object'&&!Array.isArray(v)?v as Record<string,unknown>:null;
const text=(v:unknown)=>typeof v==='string'&&v.length>0&&v.length<=12000?v:null;
export function publicNativeTalents(value:unknown,id:string){
 const r=obj(value),t=obj(r?.talents);if(!r||r.characterId!==id||!t)return null;
 if(t.status==='not_configured')return {status:'not_configured' as const,steps:[]};
 if(t.status!=='verified-native-group'||!Array.isArray(t.steps)||t.steps.length!==4)return null;
 const steps=t.steps.map((v,i)=>{
  const s=obj(v);if(!s||s.stage!==i+1||!['major','enhancement'].includes(String(s.kind)))return null;
  return {stage:i+1,kind:s.kind as 'major'|'enhancement',name:text(s.name),description:text(s.description)};
 });
 if(steps.some(s=>s===null))return null;
 return {status:'verified-native-group' as const,steps:steps.filter((s):s is NonNullable<typeof s>=>s!==null)};
}
export type NativeCharacterTalents=NonNullable<ReturnType<typeof publicNativeTalents>>;
export function characterTalentStages(talents:NativeCharacterTalents|null,grade:number|null){
 if(!talents)return null;
 const known=grade!==null&&Number.isInteger(grade)&&grade>=0&&grade<=4;
 return {status:talents.status,grade:known?grade:null,steps:talents.steps.map(s=>({...s,state:known?(s.stage<=grade!?'reached':'locked'):'unknown'}))};
}
