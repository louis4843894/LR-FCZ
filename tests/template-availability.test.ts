import {describe,it,expect} from 'vitest';
import {characterAvailability,equipmentAvailability,explicitAvailability} from '../lib/template-availability';
import {publicCharacterDetails} from '../lib/character-details';
describe('template absence versus missing acquisition',()=>{
 it('only accepts an explicit empty list or null configuration as absence',()=>{
  expect(equipmentAvailability(null)).toEqual({normal:'unknown',advanced:'unknown',skillPlus:'unknown',specPlus:'unknown'});
  expect(equipmentAvailability({normalOptions:[{name:'體力'}],advanced:null,skillPlus:[],specPlus:null})).toEqual({normal:'present',advanced:'absent',skillPlus:'absent',specPlus:'absent'});
  for(const value of [undefined,null,false,0,{},''])expect(explicitAvailability({skills:value},'skills')).toBe('unknown');
  expect(explicitAvailability({},'talents','object')).toBe('unknown');
 });
 it('keeps omitted optional fields unknown even when a legacy parser wrote null or an empty list',()=>{
  const row={skills:[],abilities:[],awakeningAbilities:[],talents:null,availability:{skills:'absent',abilities:'absent',awakening:'unknown',talents:'unknown'}};
  expect(characterAvailability(row)).toEqual({skills:'absent',abilities:'absent',awakening:'unknown',talents:'unknown'});
  expect(characterAvailability({talents:null}).talents).toBe('unknown');
 });
 it('withholds contradictory absence and strips arbitrary availability metadata',()=>{
  const d=publicCharacterDetails({characterId:'fixture',status:'matched-reference',skills:[{}],abilities:[],awakeningAbilities:[],talents:null,availability:{skills:'absent',talents:'absent',rawMemory:'private-sentinel'}},'fixture')!;
  expect(d.availability.skills).toBe('unknown');expect(d.availability.talents).toBe('absent');
  expect(JSON.stringify(d)).not.toContain('private-sentinel');
  expect(publicCharacterDetails({characterId:'fixture',status:'not_in_reference',skills:[]},'fixture')).toBeNull();
 });
});
