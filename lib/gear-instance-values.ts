import {createHash} from 'node:crypto';
const digest=(v:unknown)=>createHash('sha256').update(JSON.stringify(v)).digest('hex');
export const gearObservationId=(snapshot:string,owner:string,position:number,slot:string)=>digest([snapshot,owner,position,slot]);
export type RollEntry={index:number;attributeId:number;valueGradeRaw:number;sourceField:string;value:number;unit:'PERCENT'|'FLAT'|'SECOND';enhancementIncluded:boolean;valueVerified:boolean;valueVisuallyVerified:false;calculationKind?:'native-conditional'|'native-skillplus';appliedEnhancementLevel?:number;conditionState?:'applicability_not_verified'|'skill_activation_not_verified';labelTemplate?:string|null;modifierOperator?:'+'|'-'|'/'};
export type GearSpecialOption={name:string;normalText:string;description:string;specialEnhancement:number;valueVisuallyVerified:false;activationState:'not_verified'};
export type GearRoll={observationId:string;equipmentId:string;enhancement:number;instanceGrade:number|null;equipmentInstanceHash:string;factorCapturedAt:string;entries:RollEntry[];extraSpecialObserved?:boolean;extraSpecial?:GearSpecialOption};
type Gear={equipmentId:string|null;enhancement?:number|null;instanceGrade?:number|null;equipmentInstanceIdentity?:{namespace:string;value:string}|null};
type Entry={index:number;attributeId:number;valueGradeRaw:number;sourceField?:string};
export function reconstructedSpecial(roll:GearRoll|undefined,gear:Gear,owner:string){
 if(!roll?.extraSpecial||!gear.equipmentInstanceIdentity||roll.equipmentId!==gear.equipmentId||roll.enhancement!==gear.enhancement||roll.instanceGrade!==(gear.instanceGrade??null)||roll.equipmentInstanceHash!==digest([owner,gear.equipmentInstanceIdentity.namespace,gear.equipmentInstanceIdentity.value]))return null;
 return roll.extraSpecial;
}
export function reconstructedEffect(roll:GearRoll|undefined,gear:Gear,entry:Entry,owner:string,allowGuildSkillPlus=false){
 if(!roll||!gear.equipmentInstanceIdentity||roll.equipmentId!==gear.equipmentId||roll.enhancement!==gear.enhancement||roll.instanceGrade!==(gear.instanceGrade??null)||roll.equipmentInstanceHash!==digest([owner,gear.equipmentInstanceIdentity.namespace,gear.equipmentInstanceIdentity.value]))return null;
 const skill=allowGuildSkillPlus&&entry.sourceField==='skillPlusAttr1No';
 if(!entry.sourceField||(!/^attr[1-5]No$/.test(entry.sourceField)&&!skill))return null;
 const found=roll.entries.find(r=>r.index===entry.index&&r.attributeId===entry.attributeId&&r.valueGradeRaw===entry.valueGradeRaw&&r.sourceField===entry.sourceField);
 if(!found||found.valueVerified!==true||found.enhancementIncluded!==true||!Number.isFinite(found.value)||!(skill?['PERCENT','FLAT','SECOND']:['PERCENT','FLAT']).includes(found.unit))return null;
 if(skill?found.calculationKind!=='native-skillplus':found.calculationKind==='native-skillplus')return null;
 return {...found,valueSource:'native-definition-reconstruction' as const,factorCapturedAt:roll.factorCapturedAt};
}
