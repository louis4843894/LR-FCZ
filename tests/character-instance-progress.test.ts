import {describe,it,expect} from 'vitest';
import {createHash} from 'node:crypto';
import {characterProgressKey,resolveCharacterProgress} from '../lib/character-instance-progress';
import {publicCharacterDetails} from '../lib/character-details';
const expected={characterId:'u1',owner:'owner-a',instance:'10',retrievedAt:'2026-11-26T00:00:00Z'};
const raw={...expected,recordScope:'player-character-instance',templateTrainingSubstituted:false,instanceHash:createHash('sha256').update(JSON.stringify(['owner-a','player-owned-unit','10'])).digest('hex'),level:180,maxLevel:180,leonardPoints:0,talentGrade:4,awakening:{state:'present',abilityCode:'aab223_guts5',name:'毅力+',description:'說明'},sourceFile:'private',token:'never'};
describe('actual character observation whitelist',()=>{
 it('keeps actual zero and Chinese awakening, strips private fields',()=>{
  const p=resolveCharacterProgress(raw,expected)!;expect(p.leonardPoints).toBe(0);expect(p.awakening.name).toBe('毅力+');
  expect(JSON.stringify(p)).not.toMatch(/instanceHash|sourceFile|owner-a|never|aab223/);
 });
 it('rejects another owner, instance, time or template',()=>{
  for(const e of [{...expected,owner:'other'},{...expected,instance:'11'},{...expected,retrievedAt:'later'},{...expected,characterId:'other'}])expect(resolveCharacterProgress(raw,e)).toBeNull();
  expect(resolveCharacterProgress({...raw,templateTrainingSubstituted:true},expected)).toBeNull();
 });
 it('keeps unknown separate from zero, empty and present awakening',()=>{
  const p=resolveCharacterProgress({...raw,level:true,leonardPoints:undefined,talentGrade:NaN,awakening:{state:'not_returned'}},expected)!;
  expect(p.level).toBeNull();expect(p.leonardPoints).toBeNull();expect(p.talentGrade).toBeNull();expect(p.awakening.state).toBe('not_returned');
  expect(characterProgressKey('guildwar','s','a',1,0,11)).not.toBe(characterProgressKey('guildwar','s','a',1,0,12));
 });
 it('retains zero startup seconds, treats absent/invalid timing as unknown',()=>{
  const row={characterId:'u1',status:'matched-reference',skills:[{startupSeconds:0},{},{startupSeconds:NaN},{startupSeconds:-1}]};
  expect(publicCharacterDetails(row,'u1')!.skills!.map(s=>s.startupSeconds)).toEqual([0,null,null,null]);
 });
});
