import {describe,it,expect,vi} from 'vitest';
vi.mock('server-only',()=>({}));
import {summarizeRankedDefense,summarizeRankingCoverage,isRankingSnapshotId,type RankingPlayer,type RankingAttempt,type RankingTeam} from '../lib/pvp-rankings';

const player=(id:string):RankingPlayer=>({playerId:id,rank:1,score:1,displayName:'isolated fixture'});
const member=(id:string,w:string|null,a:string|null,x:string|null)=>({characterState:'present',characterId:id,equipment:{weapon:{state:w===null?'not_equipped':'equipped',equipmentId:w},armor:{state:a===null?'not_equipped':'equipped',equipmentId:a},accessory:{state:x===null?'not_equipped':'equipped',equipmentId:x}}});
const team=(uid:string,id:string,members:ReturnType<typeof member>[],selected=true):RankingTeam=>({playerId:uid,snapshotId:id,purpose:'pvp_defense',teamId:id,status:'success',isSelected:selected,unobservedPositionIndices:[],members});
const attempt=(ids:string[]):RankingAttempt=>({status:'success',defenseSnapshotIds:ids,defenseRetrievedAt:'2026-11-25T00:00:00Z',failureReason:null});

describe('real ranking statistics boundaries (isolated fixtures)',()=>{
 it('opens both native and normal HTTP sources while rejecting malformed source IDs',()=>{
  expect(isRankingSnapshotId('pvp-ranking-'+'a'.repeat(24))).toBe(true);
  expect(isRankingSnapshotId('pvp-ranking-http-'+'b'.repeat(24))).toBe(true);
  for(const value of [null,'pvp-ranking-http-'+'c'.repeat(23),'pvp-ranking-other-'+'d'.repeat(24),'../pvp-ranking-'+'e'.repeat(24),'pvp-ranking-'+'f'.repeat(24)+'?x=1'])expect(isRankingSnapshotId(value)).toBe(false);
 });
 it('keeps league coverage, unavailable responses and unread players separate',()=>{
  const doc=(scope:string,id:string,players:RankingPlayer[])=>({sourceKind:'verified-normal-pvp-league-ranking',snapshotId:id,capturedAt:'2026-11-25T00:00:00Z',status:'success',loadedCount:players.length,retrievedPlayerCount:players.length,scope:{label:scope,wholeRankingComplete:false as const},players});
  const sources=[doc('大師','master',[player('fixture-a'),player('fixture-b'),player('fixture-b')]),doc('黃金2','silver',[player('fixture-c'),player('fixture-d')]),doc('白銀','legacy-silver',[player('fixture-lower-tier')])];
  const rows=[{snapshotId:'master',playerId:'fixture-a',payload:attempt(['a','wrong-owner'])},{snapshotId:'master',playerId:'fixture-b',payload:{...attempt([]),status:'unavailable'}},{snapshotId:'silver',playerId:'fixture-c',payload:{...attempt(['c']),status:'partial'}},{snapshotId:'old-source',playerId:'fixture-d',payload:attempt(['old'])}];
  const coverage=summarizeRankingCoverage([{scope:'白銀',snapshotId:'legacy-silver'},{scope:'黃金2',snapshotId:'silver'},{scope:'大師',snapshotId:'master'}],sources,rows,[team('fixture-a','a',[]),team('other-owner','wrong-owner',[]),team('fixture-c','c',[]),team('fixture-d','old',[])]);
  expect(coverage.map(c=>c.scope)).toEqual(['大師3','黃金2']);
  expect(coverage[0]).toMatchObject({players:2,success:1,unavailable:1,partial:0,failed:0,notRead:0,teams:1});
  expect(coverage[1]).toMatchObject({players:2,success:0,unavailable:0,partial:1,notRead:1,teams:1});
 });
 it('deduplicates players but counts repeated appearances, excludes backups and splits denominators',()=>{
  const first=team('fixture-a','a',[member('c1','w1','a1','x1'),member('c1','w2','a2','x2')]);
  const second=team('fixture-b','b',[member('c2','w3','a3','x3')]);second.members![0].equipment.armor={state:'unknown',equipmentId:null};
  const backup=team('fixture-a','backup',[member('backup-only','w9','a9','x9')],false);
  const stats=summarizeRankedDefense([player('fixture-a'),player('fixture-a'),player('fixture-b')],new Map([['fixture-a',attempt(['a','backup'])],['fixture-b',attempt(['b'])]]),[first,second,backup]);
  expect(stats.validPlayers).toBe(2);expect(stats.equipmentValidPlayers).toBe(1);expect(stats.unknownEquipmentSlots).toBe(1);
  expect(stats.characters.find(r=>r.id==='c1')).toEqual({id:'c1',playerCount:1,appearanceCount:2,rate:.5});
  expect(stats.characters.some(r=>r.id==='backup-only')).toBe(false);
  expect(stats.combinations).toHaveLength(2);expect(stats.combinations.some(r=>r.weaponId==='w1'&&r.armorId==='a2')).toBe(false);
  expect(stats.winRate).toBeNull();
 });
 it('does not replace failed updates with older successes or unrelated player snapshots in statistics',()=>{
  const bad={...attempt(['old']),status:'failed',failureReason:'fixture_failure'};
  const stats=summarizeRankedDefense([player('fixture-a'),player('fixture-b')],new Map([['fixture-a',bad]]),[team('fixture-a','old',[member('c1','w1','a1','x1')]),team('unranked','extra',[member('c2','w2','a2','x2')])]);
  expect(stats.validPlayers).toBe(0);expect(stats.failedPlayers).toBe(1);expect(stats.notReadPlayers).toBe(1);expect(stats.characters).toEqual([]);
 });
 it('requires matching player ownership, one selected team and observed positions',()=>{
  const a=attempt(['a','b']);const left=team('fixture-a','a',[member('c1',null,null,null)]);const right=team('fixture-a','b',[member('c2',null,null,null)]);
  expect(summarizeRankedDefense([player('fixture-a')],new Map([['fixture-a',a]]),[left,right]).validPlayers).toBe(0);
  right.isSelected=false;left.unobservedPositionIndices=[3];
  expect(summarizeRankedDefense([player('fixture-a')],new Map([['fixture-a',a]]),[left,right]).partialPlayers).toBe(1);
  left.unobservedPositionIndices=[];left.playerId='different-owner';
  expect(summarizeRankedDefense([player('fixture-a')],new Map([['fixture-a',a]]),[left,right]).validPlayers).toBe(0);
 });
 it('preserves confirmed empty equipment instead of treating it as unknown',()=>{
  const stats=summarizeRankedDefense([player('fixture-a')],new Map([['fixture-a',attempt(['a'])]]),[team('fixture-a','a',[member('c1',null,null,null)])]);
  expect(stats.equipmentValidPlayers).toBe(1);expect(stats.unknownEquipmentSlots).toBe(0);expect(stats.equipment).toEqual([]);
  expect(stats.combinations[0]).toMatchObject({weaponId:null,armorId:null,accessoryId:null});
 });
});
