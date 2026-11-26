import {describe,it,expect} from 'vitest';
import {publicNativeTalents,characterTalentStages} from '../lib/character-native';
const raw={characterId:'fixture',talents:{status:'verified-native-group',steps:Array.from({length:4},(_,i)=>({stage:i+1,kind:i===0?'major':'enhancement',name:'才能',description:'說明',enhanceValueRaw:999,abilityCode:'private',sourcePath:'private'}))}};
describe('native talent order and actual training',()=>{
 it('whitelists native relationships without leaking raw scalars/IDs/paths',()=>{
  const t=publicNativeTalents(raw,'fixture');expect(t?.steps).toHaveLength(4);expect(JSON.stringify(t)).not.toMatch(/enhanceValueRaw|abilityCode|sourcePath|private/);
  expect(publicNativeTalents(raw,'another')).toBeNull();
 });
 it('uses the real grade prefix and leaves unknown/out-of-range grades unknown',()=>{
  const t=publicNativeTalents(raw,'fixture');
  expect(characterTalentStages(t,0)?.steps.map(s=>s.state)).toEqual(['locked','locked','locked','locked']);
  expect(characterTalentStages(t,2)?.steps.map(s=>s.state)).toEqual(['reached','reached','locked','locked']);
  expect(characterTalentStages(t,4)?.steps.every(s=>s.state==='reached')).toBe(true);
  for(const g of [null,NaN,-1,5])expect(characterTalentStages(t,g)?.steps.every(s=>s.state==='unknown')).toBe(true);
 });
 it('rejects malformed vectors, preserves not configured separately from unknown',()=>{
  expect(publicNativeTalents({...raw,talents:{...raw.talents,steps:raw.talents.steps.slice(0,3)}},'fixture')).toBeNull();
  expect(publicNativeTalents({characterId:'fixture',talents:{status:'not_configured'}},'fixture')?.steps).toEqual([]);
  expect(publicNativeTalents({characterId:'fixture',talents:{status:'definition_missing'}},'fixture')).toBeNull();
 });
});
