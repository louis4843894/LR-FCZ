import "server-only";
import {readNativeGearLabels} from "./local-game-data";
import {displaySourceText} from "./display-text";
export type NativeGearLabel={attributeId:number;typeEnum:number;code:string;label:string};
type Entry={index:number;attributeId:number;attributeTypeRaw:number|null;attributeLabel?:string|null;sourceField?:string};

export function resolveGearLabel(entry:Entry,labels:ReadonlyMap<number,NativeGearLabel>){
  if(entry.attributeLabel&&entry.attributeTypeRaw!==null&&entry.attributeTypeRaw>=1&&entry.attributeTypeRaw<=45)
    return {label:displaySourceText(entry.attributeLabel),status:'native-instance' as const};
  if(entry.attributeTypeRaw!==null){
    const row=[...labels.values()].find(r=>r.typeEnum===entry.attributeTypeRaw);
    if(row)return {label:displaySourceText(row.label),status:'native-type' as const};
  }
  // skillPlusAttr1No may reference a different object namespace. Never resolve
  // it using an ordinary GearStat ID merely because the integer is identical.
  if(entry.sourceField&&/^attr[1-5]No$/.test(entry.sourceField)){
    const row=labels.get(entry.attributeId);
    if(row)return {label:displaySourceText(row.label),status:'native-id' as const};
  }
  return {label:entry.sourceField?.startsWith('skillPlus')?'技能追加詞條（種類尚未解析）':`詞條 ${entry.index+1}（種類尚未解析）`,status:'unknown' as const};
}

export async function getNativeGearLabelMap(){
  const source=await readNativeGearLabels();return new Map(source?.records.map(r=>[r.attributeId,r])??[]);
}
