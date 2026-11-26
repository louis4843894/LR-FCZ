import { expect,it,vi } from "vitest";
vi.mock("server-only",()=>({}));
import { summarizeDefense } from "../lib/acquisition-progress";

const base={playerId:"private-owner",purpose:"pvp_defense",teamId:"A",status:"success",retrievedAt:"2026-11-25T00:00:00Z",members:[{characterId:"fixture",equipment:{weapon:{state:"equipped",equipmentId:"eq_known",enhancement:5,actualEffects:{entries:[{value:444,valueVerified:true},{value:null}]}},armor:{state:"equipped",equipmentId:"eq_missing"},accessory:{state:"unknown",equipmentId:null}}}]};
it("uses latest per-owner teams without treating unknown equipment as empty",()=>{
 const result=summarizeDefense([base,{...base,retrievedAt:"2026-11-24T00:00:00Z"}],new Set([base.playerId,"unread"]),new Set(["eq_known"]));
 expect(result).toMatchObject({pvpPlayers:1,pvpTeams:1,guildPlayers:1,guildUnread:1,equipment:2,equipmentMatched:1,enhancementKnown:1,attributeValues:1,attributeUnknown:1,unknownEquipmentIds:["eq_missing"]});
 expect(JSON.stringify(result)).not.toContain("private-owner");
});
it("separates guild war from PVP and partial/failed snapshots from complete data",()=>{
 const result=summarizeDefense([base,{...base,playerId:"other",unobservedPositionIndices:[4]},{...base,teamId:"B",status:"failed",members:null},{...base,purpose:"guild_battle_defense",teamId:"tower"}],new Set(["other"]),new Set());
 expect(result).toMatchObject({pvpPlayers:2,pvpTeams:2,partialTeams:1,failedTeams:1,guildPlayers:1,guildBattleTeams:1});
});
