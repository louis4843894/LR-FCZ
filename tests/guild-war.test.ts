import {describe,it,expect,vi,beforeEach} from 'vitest';
import {createHash} from 'node:crypto';
vi.mock('server-only',()=>({}));
const store=vi.hoisted(()=>({records:[] as unknown[],rolls:new Map()}));
vi.mock('../lib/local-game-data',()=>({readGuildWarStore:async()=>store.records,readCharacterInstanceProgress:async()=>new Map(),readNativeGearRolls:async(_keys:string[],scope:string)=>scope==='guildwar'?store.rolls:new Map(),readNativeGearLabels:async()=>({records:[{attributeId:5,typeEnum:2,code:'fixture',label:'體力'}]})}));
vi.mock('../lib/character-reference',()=>({getCharacterReference:async()=>({records:[{characterId:'fixture-unit',name:'測試角色',starGrade:6}]})}));
vi.mock('../lib/verified-equipment',()=>({getVerifiedEquipmentList:async()=>[{itemCode:'eq_fixture',dataCode:'eq_fixture_nm',names:{'zh-Hant':'測試防具'},starCount:6,equipType:'ARMOR',reference:{itemCode:'eq_fixture',normalOptions:[{optionKey:'fixture_attack',name:'攻擊力',category:'NORMAL',range:{min:1,max:2,unit:'PERCENT'},upgradeStep:null,attributeId:99}],advanced:null,skillPlus:[],specPlus:null}}]}));
import {getGuildWar,guildGearObservationId,guildWarPanelView} from '../lib/guild-war';
import {warViewerTeams} from '../lib/defense-viewer-data';
const gid='fixture-private-guild';const alias=createHash('sha256').update(gid).digest('hex').slice(0,20);
beforeEach(()=>{store.rolls.clear();store.records=[{sourceKind:'verified-guildwar-overview',kind:'overview',guildId:gid,seasonNo:1,battleNo:1,capturedAt:'2026-11-25T00:00:00Z',towers:[{code:11,countersRaw:[0,0],defendersState:'not_read',defenders:null}]},
 {sourceKind:'verified-guildwar-saved-configuration',kind:'saved_configuration',deploymentState:'unconfirmed',sourceId:'fixture-source',guildId:gid,playerId:'fixture-private-player',capturedAt:'2026-11-25T00:00:00Z',configuredTeamNo:1,
 teams:[{teamNo:1,units:[{position:19,characterId:'fixture-unit',characterInstanceId:'fixture-private-instance',level:180,equipment:{weapon:{state:'unknown',equipmentId:null},armor:{state:'equipped',equipmentId:'eq_fixture',enhancement:2,instanceGrade:9,ownerAssociationStatus:'verified-native',equipmentInstanceIdentity:{namespace:'player-owned-equipment',value:'fixture-private-gear'},actualEffects:{entries:[{index:0,attributeId:5,valueGradeRaw:3,attributeTypeRaw:null,sourceField:'attr1No'}]}},accessory:{state:'not_equipped',equipmentId:null}}}]}]}];});
describe('guild-war saved configuration display',()=>{
 it('does not turn tower counters or saved settings into actual deployed defenses',async()=>{
  const data=await getGuildWar(alias);expect(data?.deployedTeams).toBe(0);expect(data?.overview?.towers[0]).toEqual({code:11,number:1,label:'第 1 塔',defendersState:'not_read'});
  expect(data?.savedConfigurations[0].deploymentState).toBe('unconfirmed');expect(data?.savedConfigurations[0].teams[0].units[0].position).toBe(19);
 });
 it('links actual template IDs, keeps +2 and unknown slots, strips private identities',async()=>{
  const data=await getGuildWar(alias);const slots=data!.savedConfigurations[0].teams[0].units[0].slots;
  expect(slots[0].state).toBe('unknown');expect(slots[2].state).toBe('not_equipped');expect(slots[1]).toMatchObject({enhancement:2,template:{dataCode:'eq_fixture_nm'},effectIdentifiers:[{id:5,valueGradeRaw:3}]});
  expect(JSON.stringify(data)).not.toContain('fixture-private');expect(await getGuildWar('f'.repeat(20))).toBeNull();
  const display=warViewerTeams(data!.savedConfigurations[0].teams,'fixture-public-scope','2026-11-25T00:00:00Z');
  expect(display[0].units[0]).toMatchObject({position:19,stars:6,progress:null});
  expect(display[0].units[0].gear[1]).toMatchObject({name:'測試防具',enhancement:2});
  expect(display[0].units[0].gear.map(g=>g.state)).toEqual(['unknown','equipped','not_equipped']);
  expect(JSON.stringify(display)).not.toMatch(/fixture-private|characterInstanceId|valueGradeRaw/);
  expect(warViewerTeams(data!.savedConfigurations[0].teams,'different-member','2026-11-25T00:00:00Z')[0].units[0].key).not.toBe(display[0].units[0].key);
 });
 it('uses the catalogue Chinese name and keeps reference ranges separate from unknown instance values',async()=>{
  const data=await getGuildWar(alias);const gear=data!.savedConfigurations[0].teams[0].units[0].slots[1];
  expect(gear.template?.name).toBe('測試防具');expect(gear.enhancement).toBe(2);expect(gear.effectIdentifiers).toEqual([{id:5,valueGradeRaw:3}]);
  expect(gear.template?.reference?.normalOptions[0].name).toBe('攻擊力');expect(gear.effectIdentifiers?.[0]).not.toHaveProperty('value');
 });
 it('accepts actual fortress deployments independently of saved settings and missing towers',async()=>{
  const saved=store.records[1] as {teams:unknown[]};store.records.push({sourceKind:'verified-guildwar-tower-deployments',kind:'deployed_defense',guildId:gid,seasonNo:1,battleNo:2,capturedAt:'2026-11-26T00:00:00Z',status:'partial',
   towers:[{code:11,readState:'success',defenders:[{playerId:'fixture-private-player',playerName:'測試駐防',isAI:false,withdrawal:false,retrievedAt:'2026-11-26T00:00:00Z',teams:saved.teams}]},{code:12,readState:'not_read',defenders:null},{code:13,readState:'success',defenders:[]}]});
  const data=await getGuildWar(alias);expect(data?.deployedTeams).toBe(1);expect(data?.deployment).toMatchObject({battleNo:2,uniqueHumanDefenders:1,unitCount:1,equippedCount:1});
  expect(data?.deployment?.towers[1].defenders).toBeNull();expect(data?.deployment?.towers[2].defenders).toEqual([]);expect(JSON.stringify(data)).not.toContain('fixture-private');
  const view=guildWarPanelView(data,'3');expect(view?.deployment?.unitCount).toBe(data?.deployment?.unitCount);
  expect(view?.deployment?.towers[0].defenders).toBeNull();expect(view?.deployment?.towers[0].defenderCount).toBe(1);
  expect(view?.deployment?.towers[1].defenderCount).toBeNull();expect(view?.deployment?.towers[2].defenders).toEqual([]);
  expect(data?.deployment?.towers[0].defenders).toHaveLength(1);
  expect(guildWarPanelView(data,'invalid')?.deployment?.towers[0].defenders).toHaveLength(1);
 });
 it('binds real values to owner, source, tower, twenty-slot position and actual instance grade',async()=>{
  const key=guildGearObservationId('fixture-source',null,'fixture-private-player',1,19,'armor');
  store.rolls.set(key,{observationId:key,equipmentId:'eq_fixture',enhancement:2,instanceGrade:9,equipmentInstanceHash:createHash('sha256').update(JSON.stringify(['fixture-private-player','player-owned-equipment','fixture-private-gear'])).digest('hex'),factorCapturedAt:'2026-11-26T00:00:00Z',entries:[{index:0,attributeId:5,valueGradeRaw:3,sourceField:'attr1No',value:30,unit:'PERCENT',enhancementIncluded:true,valueVerified:true,valueVisuallyVerified:false}]});
  const data=await getGuildWar(alias);expect(data!.savedConfigurations[0].teams[0].units[0].slots[1].actualEffects?.[0]).toMatchObject({label:'體力',value:30,unit:'PERCENT',valueVisuallyVerified:false});
  const display=warViewerTeams(data!.savedConfigurations[0].teams,'fixture-public-scope','2026-11-25T00:00:00Z');
  expect(display[0].units[0].gear[1].effects?.[0].value).toBe('+30%');
  expect(display[0].units[0].gear[1].reference?.normalOptions[0].range).toEqual({min:1,max:2,unit:'PERCENT'});
  expect(key).not.toBe(guildGearObservationId('fixture-source',11,'fixture-private-player',1,19,'armor'));
  expect(key).not.toBe(guildGearObservationId('other-source',null,'fixture-private-player',1,19,'armor'));
  store.rolls.get(key).instanceGrade=8;
  expect((await getGuildWar(alias))!.savedConfigurations[0].teams[0].units[0].slots[1].actualEffects?.[0].value).toBeNull();
 });
});
