import {describe,it,expect} from 'vitest';
import {publicCharacterDetails} from '../lib/character-details';
const ability={abilityCode:'aab_fixture',name:'測試覺醒',description:'測試描述',status:'matched-reference',candidateProbabilityRaw:10,probabilityMeaning:'unverified',triggerEffects:[{chancePercent:100,phase:'死亡時',effect:'測試效果',rawMemory:'private-sentinel'}]};
const base={characterId:'fixture',status:'matched-reference',skills:[],abilities:[ability],awakeningAbilities:[ability],talents:null,stats:{hp:0,rawMemory:'private-sentinel'},rawMemory:'private-sentinel'};
describe('character template detail whitelist',()=>{
 it('keeps native zero and candidates without exporting an unverified candidate probability',()=>{
  const d=publicCharacterDetails(base,'fixture')!;expect(d.stats?.find(s=>s.label==='體力')?.value).toBe(0);expect(d.skills).toEqual([]);
  expect(d.awakeningAbilities?.[0].triggerEffects?.[0].chancePercent).toBe(100);expect(d.awakeningCandidatesAreNotPlayerAwakening).toBe(true);
  const json=JSON.stringify(d);expect(json).not.toContain('candidateProbabilityRaw');expect(json).not.toContain('private-sentinel');expect(json).not.toContain('probabilityMeaning');
 });
 it('withholds wrong identities and leaves missing skills unknown',()=>{
  expect(publicCharacterDetails(base,'other')).toBeNull();expect(publicCharacterDetails({...base,status:'identity_conflict'},'fixture')).toBeNull();
  expect(publicCharacterDetails({...base,skills:null,awakeningAbilities:null},'fixture')?.skills).toBeNull();
 });
 it('never changes null or nonfinite rates into zero and rejects oversized effect arrays',()=>{
  const d=publicCharacterDetails({...base,skills:[{skillCode:'sk_fixture',status:'matched-reference',activationRatePercent:NaN,cooldownSeconds:null,effects:Array(129).fill({})}]},'fixture')!;
  expect(d.skills?.[0]).toMatchObject({activationRatePercent:null,cooldownSeconds:null,effects:null});
 });
});
