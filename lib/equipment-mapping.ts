import "server-only";
import { readLatestEquipmentChecks } from "./local-game-data";
import { displaySourceText } from "./display-text";

export type DisplayEquipmentMapping={status:"exact_attribute_id"|"same_equipment_key_and_base_range"|"template_candidates_only";category:string|null;conditionLabel:string|null;actualValueVerified:false;candidates:{name:string;range:{min:number;max:number;unit:string}|null;upgradeStep:number|null}[]};
const object=(x:unknown):x is Record<string,unknown>=>typeof x==="object"&&x!==null&&!Array.isArray(x);
export function mappingDisplay(input:unknown):DisplayEquipmentMapping|null{
  if(!object(input)||input.sourceKind!=="external-reference"||input.actualValueVerified!==false||!['exact_attribute_id','same_equipment_key_and_base_range','template_candidates_only'].includes(String(input.status))||!Array.isArray(input.candidates)||input.candidates.length>64)return null;
  const candidates=input.candidates.filter(object).map(c=>{
    const r=c.range;
    const range=object(r)&&typeof r.min==="number"&&Number.isFinite(r.min)&&typeof r.max==="number"&&Number.isFinite(r.max)&&typeof r.unit==="string" ? {min:r.min,max:r.max,unit:r.unit} : null;
    return {name:displaySourceText(String(c.name ?? c.effectName ?? c.description ?? c.effectCode ?? "特殊效果（名稱待確認）")),range,upgradeStep:typeof c.upgradeStep==="number"&&Number.isFinite(c.upgradeStep) ? c.upgradeStep : null};
  });
  return {status:input.status as DisplayEquipmentMapping['status'],category:typeof input.category==="string" ? input.category : null,
    conditionLabel:object(input.condition)&&typeof input.condition.label==="string" ? displaySourceText(input.condition.label) : null,actualValueVerified:false,candidates};
}
export async function getEquipmentMappingMap(){
  const result=new Map<string,{itemCode:string;attributeId:number;mapping:DisplayEquipmentMapping}>();
  for(const row of await readLatestEquipmentChecks()){
    if(!object(row)||typeof row.observationId!=="string"||typeof row.itemCode!=="string"||!Number.isInteger(row.index)||!Number.isInteger(row.attributeId))continue;
    const mapping=mappingDisplay(row.externalMapping);
    if(mapping)result.set(`${row.observationId}:${row.index}`,{itemCode:row.itemCode,attributeId:Number(row.attributeId),mapping});
  }
  return result;
}
