import {describe,it,expect} from 'vitest';
import {createHash} from 'node:crypto';
import {gearObservationId,reconstructedEffect,reconstructedSpecial,type GearRoll} from '../lib/gear-instance-values';
const hash=(x:unknown)=>createHash('sha256').update(JSON.stringify(x)).digest('hex');
const owner='isolated-owner';
const gear={equipmentId:'eq_fixture',enhancement:5,instanceGrade:9,equipmentInstanceIdentity:{namespace:'player-owned-equipment',value:'101'}};
const entry={index:0,attributeId:1011,valueGradeRaw:5,sourceField:'attr1No'};
const roll:GearRoll={observationId:gearObservationId('snapshot',owner,0,'weapon'),equipmentId:gear.equipmentId,enhancement:5,instanceGrade:9,equipmentInstanceHash:hash([owner,'player-owned-equipment','101']),factorCapturedAt:'2026-11-26T00:00:00Z',entries:[{...entry,value:-30,unit:'PERCENT',enhancementIncluded:true,valueVerified:true,valueVisuallyVerified:false}]};
describe('native ordinary reconstructions stay bound to actual instances',()=>{
 it('binds special descriptions to this owner and instance without another multiplier',()=>{
  const extra={name:'光之盔甲',normalText:'降低傷害 +23.9%',description:'反射26.7%的物理傷害',specialEnhancement:5,valueVisuallyVerified:false as const,activationState:'not_verified' as const};
  const special={...roll,extraSpecial:extra};expect(reconstructedSpecial(special,gear,owner)).toEqual(extra);
  expect(reconstructedSpecial(special,gear,'other-owner')).toBeNull();
  expect(reconstructedSpecial(special,{...gear,equipmentInstanceIdentity:{namespace:'player-owned-equipment',value:'102'}},owner)).toBeNull();
  expect(reconstructedSpecial(special,{...gear,enhancement:4},owner)).toBeNull();
  expect(reconstructedSpecial(roll,gear,owner)).toBeNull();
 });
 it('preserves the signed result without another enhancement multiplier or visual claim',()=>{
  expect(reconstructedEffect(roll,gear,entry,owner)).toMatchObject({value:-30,unit:'PERCENT',enhancementIncluded:true,valueVisuallyVerified:false,valueSource:'native-definition-reconstruction'});
 });
 it('rejects other owners, repeated templates on other instances and changed enhancement or rolls',()=>{
  expect(reconstructedEffect(roll,gear,entry,'other-owner')).toBeNull();
  expect(reconstructedEffect(roll,{...gear,equipmentInstanceIdentity:{namespace:'player-owned-equipment',value:'102'}},entry,owner)).toBeNull();
  expect(reconstructedEffect(roll,{...gear,enhancement:2},entry,owner)).toBeNull();
  expect(reconstructedEffect(roll,gear,{...entry,valueGradeRaw:4},owner)).toBeNull();
  expect(reconstructedEffect(roll,gear,{...entry,attributeId:1012},owner)).toBeNull();
 });
 it('never maps ordinary IDs into Skill+ or accepts nonfinite/unverified values',()=>{
  expect(reconstructedEffect(roll,gear,{...entry,sourceField:'skillPlusAttr1No'},owner)).toBeNull();
  for(const changed of [{value:NaN},{valueVerified:false},{enhancementIncluded:false}])expect(reconstructedEffect({...roll,entries:[{...roll.entries[0],...changed}]},gear,entry,owner)).toBeNull();
  expect(gearObservationId('snapshot',owner,0,'weapon')).not.toBe(gearObservationId('snapshot',owner,1,'weapon'));
 });
 it('accepts separately proved guild Skill+ seconds only through the explicit guild branch',()=>{
  const skillEntry={...entry,sourceField:'skillPlusAttr1No'};
  const skill:GearRoll={...roll,entries:[{...roll.entries[0],...skillEntry,value:1.5,unit:'SECOND',calculationKind:'native-skillplus',modifierOperator:'+',conditionState:'skill_activation_not_verified'}]};
  expect(reconstructedEffect(skill,gear,skillEntry,owner)).toBeNull();
  expect(reconstructedEffect(skill,gear,skillEntry,owner,true)).toMatchObject({value:1.5,unit:'SECOND',valueVisuallyVerified:false});
  expect(reconstructedEffect(skill,gear,entry,owner,true)).toBeNull();
  expect(reconstructedEffect(roll,gear,skillEntry,owner,true)).toBeNull();
 });
});
