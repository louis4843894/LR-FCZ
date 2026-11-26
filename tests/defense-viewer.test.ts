import {describe,it,expect} from 'vitest';
import {actualEffectText,viewerSelectedUnit,viewerTeams,viewerTime,viewerElementName,type ViewerTeam,type ViewerUnit} from '../lib/defense-viewer';
const unit=(key:string):ViewerUnit=>({key,position:0,state:'present',characterId:'same-template',name:'測試角色',imageUrl:null,stars:8,element:'WATER',role:'STR',progress:null,talents:null,gear:[]});
const teams:ViewerTeam[]=[{key:'A',label:'A',status:'success',retrievedAt:'2026-11-26T00:00:00Z',note:'',unobservedPositions:[],units:[unit('first-instance')]},{key:'B',label:'B',status:'success',retrievedAt:'2026-11-26T01:00:00Z',note:'',unobservedPositions:[2],units:[unit('second-instance')]}];
describe('display selection and actual effect formatting',()=>{
 it('uses deterministic Taiwan timestamps and native lowercase element codes',()=>{
  expect(viewerTime('2026-11-26T00:00:01Z')).toBe('2026/11/26 08:00:01');
  expect(viewerElementName('water')).toBe('水');expect(viewerElementName('TREE')).toBe('木');expect(viewerElementName(null)).toBe('未知');
 });
 it('keeps repeated templates separate and never selects the other team by template ID',()=>{
  expect(viewerSelectedUnit(teams,'all','first-instance')?.key).toBe('first-instance');
  expect(viewerSelectedUnit(teams,'B','first-instance')).toBeNull();
  expect(viewerSelectedUnit(teams,'B','second-instance')?.key).toBe('second-instance');
  expect(viewerSelectedUnit(teams,'all','same-template')).toBeNull();
 });
 it('does not invent missing teams or fill unobserved positions',()=>{
  expect(viewerTeams(teams,'all')).toHaveLength(2);
  expect(viewerTeams(teams,'missing')).toEqual([]);
  expect(viewerTeams(teams,'B')[0].unobservedPositions).toEqual([2]);
  expect(viewerTeams(teams,'B')[0].units).toHaveLength(1);
 });
 it('keeps zero distinct from missing and preserves signs, seconds and explicit operators',()=>{
  expect(actualEffectText(null,'PERCENT')).toBe('數值尚未解析');
  expect(actualEffectText(NaN,'PERCENT')).toBe('數值尚未解析');
  expect(actualEffectText(0,'PERCENT')).toBe('0%');
  expect(actualEffectText(-17.8,'PERCENT')).toBe('-17.8%');
  expect(actualEffectText(2.25,'SECOND')).toBe('+2.25 秒');
  expect(actualEffectText(-5,'PERCENT','×')).toBe('×5%');
 });
});
