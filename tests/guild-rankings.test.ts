import {describe,it,expect,vi,beforeEach} from 'vitest';
vi.mock('server-only',()=>({}));
const store=vi.hoisted(()=>({value:null as unknown,war:[] as unknown[]}));
vi.mock('../lib/local-game-data',()=>({readRankedGuildStore:async()=>store.value,readGuildWarStore:async()=>store.war}));
import {getGuildRankings,getRankedGuild} from '../lib/guild-rankings';

beforeEach(()=>{store.war=[];store.value={ranking:{sourceKind:'verified-normal-guildwar-top-ranking',status:'success',snapshotId:'fixture-ranking',capturedAt:'2026-11-25T00:00:00Z',top:100,observedTotal:500,
 guilds:[{guildId:'fixture-private-guild-a',rank:1,score:100,name:'fixture guild A',gradeId:1,gradeLabel:'傳奇',memberCount:1,memberCapacity:50,level:10,nationalFlag:'TW'},{guildId:'fixture-private-guild-b',rank:51,score:50,name:'fixture guild B',gradeId:2,gradeLabel:'大師',memberCount:48,memberCapacity:50,level:10,nationalFlag:'JP'}]},
 rosters:[{guildId:'fixture-private-guild-a',name:'fixture guild A',level:10,capturedAt:'2026-11-25T01:00:00Z',observedMemberTotal:1,memberCapacity:50,membersRetrieved:1,membershipComplete:true,members:[{playerId:'fixture-private-player',name:'fixture member',level:532,role:'MASTER'}]}],attempts:[{guildId:'fixture-private-guild-a',part:'roster',checkedAt:'2026-11-25T02:00:00Z',status:'failed',reason:'fixture_failure'}]};});

describe('ranked guild display boundaries',()=>{
 it('shows a partially acquired ranked guild as partial defense with its own acquisition time',async()=>{
  store.war=[{sourceKind:'verified-guildwar-tower-deployments',kind:'deployed_defense',guildId:'fixture-private-guild-a',status:'partial',capturedAt:'2026-11-26T15:34:00Z',towers:[{code:11,readState:'success',defenders:[{teams:[{}]}]},{code:12,readState:'not_read',defenders:null}]}];
  expect((await getGuildRankings())?.guilds[0]).toMatchObject({defenseState:'partial',defenseCheckedAt:'2026-11-26T15:34:00Z',defenseTowersRead:1,defenseTowersObserved:2});
 });
 it('counts actual deployment teams only within the accepted ranked guild scope',async()=>{
  store.war=[{sourceKind:'verified-guildwar-tower-deployments',kind:'deployed_defense',guildId:'fixture-private-guild-a',status:'success',towers:[{defenders:[{teams:[{}]}]}]},
   {sourceKind:'verified-guildwar-tower-deployments',kind:'deployed_defense',guildId:'fixture-private-outside-ranking',status:'success',towers:[{defenders:[{teams:[{},{}]}]}]}];
  const result=await getGuildRankings();expect(result?.defenseGuilds).toBe(1);expect(result?.defenseTeams).toBe(1);
 });
 it('preserves actual global ranks, independent roster failure and unknown defense',async()=>{
  const result=await getGuildRankings();expect(result?.guilds.map(g=>g.rank)).toEqual([1,51]);
  expect(result?.completeRosters).toBe(1);expect(result?.membersRetrieved).toBe(1);
  expect(result?.guilds[0]).toMatchObject({rosterState:'failed',membershipComplete:true,defenseState:'not_read'});
  expect(result?.guilds[1]).toMatchObject({rosterState:'not_read',membersRetrieved:null,defenseState:'not_read'});
  expect(JSON.stringify(result)).not.toContain('fixture-private');
 });
 it('resolves only the selected guild, never treats the raw level code or PVP team as guild defense',async()=>{
  const result=await getGuildRankings();const detail=await getRankedGuild(result!.guilds[0].alias);
  expect(detail?.roster?.members[0]).toMatchObject({name:'fixture member',level:null,role:'會長',defenseState:'not_read'});
  expect(JSON.stringify(detail)).not.toContain('fixture-private');
  expect(await getRankedGuild('a'.repeat(20))).toBeNull();expect(await getRankedGuild('../invalid')).toBeNull();
 });
});
