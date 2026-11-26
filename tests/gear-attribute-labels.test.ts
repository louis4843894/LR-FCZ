import {describe,it,expect,vi} from 'vitest';
vi.mock('server-only',()=>({}));
import {resolveGearLabel} from '../lib/gear-attribute-labels';
const labels=new Map([[40000,{attributeId:40000,typeEnum:34,code:'ALL_ATK_MUL',label:'總攻擊力 (%)'}]]);
const ordinary={index:0,attributeId:40000,attributeTypeRaw:null,sourceField:'attr1No'};
describe('native Chinese attribute kinds',()=>{
 it('resolves an ordinary ID to the native Chinese kind without adding a value',()=>{
  const result=resolveGearLabel(ordinary,labels);expect(result).toEqual({label:'總攻擊力 (%)',status:'native-id'});expect(result).not.toHaveProperty('value');
 });
 it('does not use an ordinary ID in the skill-plus namespace',()=>{
  const result=resolveGearLabel({...ordinary,sourceField:'skillPlusAttr1No'},labels);expect(result.status).toBe('unknown');expect(result.label).toContain('技能追加詞條');
 });
 it('uses proven instance types and preserves unknown identifiers as a Chinese unknown state',()=>{
  expect(resolveGearLabel({...ordinary,attributeId:999,attributeTypeRaw:34,sourceField:undefined},labels).status).toBe('native-type');
  expect(resolveGearLabel({...ordinary,attributeId:999},labels)).toEqual({label:'詞條 1（種類尚未解析）',status:'unknown'});
  expect(resolveGearLabel({...ordinary,sourceField:undefined},labels).status).toBe('unknown');
 });
});
