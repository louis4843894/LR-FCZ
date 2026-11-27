import {describe,it,expect} from 'vitest';
import {guildWarTowerNumber,guildWarTowerLabel,guildWarTowerElements} from '../lib/guild-war-towers';
describe('game fortress display numbers',()=>{
 it('matches native 00858314 zero-based indexes plus one for all ten actual codes',()=>{
  const codes=[11,12,13,14,15,16,21,22,23,31];
  expect(codes.map(guildWarTowerNumber)).toEqual([1,2,3,4,5,6,7,8,9,10]);
  expect(guildWarTowerLabel(16)).toBe('第 6 塔');expect(guildWarTowerLabel(31)).toBe('第 10 塔');
 });
 it('shows the observed element for each tower and both elements for tower ten',()=>{
  const codes=[11,12,13,14,15,16,21,22,23,31];
  expect(codes.map(guildWarTowerElements)).toEqual([
   ['FIRE'],['WATER'],['TREE'],['FIRE'],['WATER'],['TREE'],['FIRE'],['WATER'],['TREE'],['LIGHT','DARK'],
  ]);
  expect(guildWarTowerElements(99)).toEqual([]);
 });
 it('does not label an unknown code by its array position or the native table zero fallback',()=>{
  for(const code of [0,17,24,99]){expect(guildWarTowerNumber(code)).toBeNull();expect(guildWarTowerLabel(code)).toBe('塔號尚未確認');}
 });
});
