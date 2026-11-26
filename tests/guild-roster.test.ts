import { beforeEach,afterEach,it,expect,vi } from "vitest";
vi.mock("server-only",()=>({}));
vi.mock("node:fs/promises",()=>({readFile:vi.fn()}));
vi.mock("../lib/defense-teams",()=>({getDefenseTeams:vi.fn()}));
import { readFile } from "node:fs/promises";
import { getGuildRoster,getGuildMemberPvpDefense } from "../lib/guild-roster";
import { getDefenseTeams } from "../lib/defense-teams";
// Contract fixture only. Never exported as real game data.
const fixture={sourceKind:"validated-native-guild-roster",guildId:"private-guild",name:"測試公會",capturedAt:"2026-11-23T03:39:22Z",gameVersion:"fixture",observedMemberTotal:3,memberCapacity:50,membersRetrieved:2,membershipComplete:false,rawMemory:"private-sentinel",members:[{playerId:"private-player",name:"測試成員",level:null,retrievedAt:"2026-11-23T03:39:22Z",defenseStatus:"not_read",defenseFailureReason:null},{playerId:"private-player-2",name:"另一成員",level:null,retrievedAt:"2026-11-23T03:39:22Z",defenseStatus:"failed",defenseFailureReason:"private-address-sentinel"}]};
function files(roster:unknown=fixture,snapshots:unknown[]=[]){vi.mocked(readFile).mockImplementation(async p=>JSON.stringify(String(p).endsWith("defense-teams.private.json") ? {sourceKind:"validated-player-team-snapshots",recordScope:"player-team",snapshots} : roster));}
beforeEach(()=>{vi.stubEnv("NODE_ENV","development");vi.mocked(readFile).mockReset();vi.mocked(getDefenseTeams).mockReset();vi.mocked(getDefenseTeams).mockResolvedValue([]);files();});
afterEach(()=>vi.unstubAllEnvs());
it("preserves partial membership, failed and unread states without leaking IDs or errors",async()=>{
 const r=(await getGuildRoster())!;expect(r.membershipComplete).toBe(false);expect(r.observedMemberTotal).toBe(3);expect(r.members).toHaveLength(2);expect(r.members[0].defenseStatus).toBe("not_read");expect(r.members[1].defenseStatus).toBe("failed");
 const s=JSON.stringify(r);for(const word of ['private-player','private-guild','private-sentinel','private-address-sentinel'])expect(s).not.toContain(word);
 expect(r.members[0].level).toBeNull();expect(r.members[0].memberId).toMatch(/^[a-f0-9]{20}$/);
});
it("scopes member aliases to the guild",async()=>{
 const first=(await getGuildRoster())!.members[0].memberId;files({...fixture,guildId:"other-guild"});expect((await getGuildRoster())!.members[0].memberId).not.toBe(first);
});
it("rejects malformed counts and external data sources",async()=>{
 vi.mocked(readFile).mockResolvedValue(JSON.stringify({...fixture,membersRetrieved:3}));await expect(getGuildRoster()).rejects.toThrow();
 vi.mocked(readFile).mockResolvedValue(JSON.stringify({...fixture,sourceKind:"external"}));await expect(getGuildRoster()).rejects.toThrow();
});
it("does not read private guild data in production",async()=>{vi.stubEnv("NODE_ENV","production");expect(await getGuildRoster()).toBeNull();expect(readFile).not.toHaveBeenCalled();});
it("joins PVP by exact player identity and leaves other guild members unread",async()=>{
 files(fixture,[{playerId:"private-player",teamId:"pvpteam/1",purpose:"pvp_defense",status:"success",retrievedAt:"2026-11-25T00:00:00Z"},{playerId:"unrelated-own-player",teamId:"pvpteam/1",purpose:"pvp_defense",status:"success",retrievedAt:"2026-11-25T00:00:00Z"}]);
 const r=(await getGuildRoster())!;expect(r.members[0].pvp.successfulTeams).toBe(1);expect(r.members[1].pvp.status).toBe("not_read");expect(JSON.stringify(r)).not.toContain("unrelated-own-player");
 const detail=await getGuildMemberPvpDefense(r.members[0].memberId);expect(getDefenseTeams).toHaveBeenCalledWith("pvp_defense","private-player");expect(detail?.teams).toEqual([]);expect(JSON.stringify(detail)).not.toContain("private-player");
});
it("retains a new failed team attempt separately from another successful team",async()=>{
 files(fixture,[{playerId:"private-player",teamId:"pvpteam/1",purpose:"pvp_defense",status:"success",retrievedAt:"2026-11-23T00:00:00Z"},{playerId:"private-player",teamId:"pvpteam/1",purpose:"pvp_defense",status:"failed",retrievedAt:"2026-11-25T00:00:00Z"},{playerId:"private-player",teamId:"pvpteam/2",purpose:"pvp_defense",status:"success",retrievedAt:"2026-11-25T00:00:00Z"}]);
 const r=(await getGuildRoster())!;expect(r.members[0].pvp.status).toBe("partial");expect(r.members[0].pvp.successfulTeams).toBe(1);
});
it("does not count guild battle teams as member PVP defense",async()=>{
 files(fixture,[{playerId:"private-player",teamId:"tower-fixture",purpose:"guild_battle_defense",status:"success",retrievedAt:"2026-11-25T00:00:00Z"}]);expect((await getGuildRoster())!.members[0].pvp.status).toBe("not_read");
});
it("does not count a team with unread positions as a completely acquired team",async()=>{
 files(fixture,[{playerId:"private-player",teamId:"pvpteam/1",purpose:"pvp_defense",status:"success",unobservedPositionIndices:[4],retrievedAt:"2026-11-25T00:00:00Z"}]);
 const r=(await getGuildRoster())!;expect(r.members[0].pvp.status).toBe("partial");expect(r.members[0].pvp.successfulTeams).toBe(0);
});
