import { beforeEach,afterEach,describe,it,expect,vi } from "vitest";
vi.mock("server-only",()=>({}));
vi.mock("node:fs/promises",()=>({readFile:vi.fn()}));
vi.mock("../lib/verified-equipment",()=>({getVerifiedEquipmentList:async()=>[{itemCode:"eq_2202_wpn_17",names:{"zh-Hant":"測試用對應名稱"},starCount:7,equipType:"WEAPON",effects:null}]}));
import { readFile } from "node:fs/promises";
import { getCharacterReference } from "../lib/character-reference";
import { getDefenseTeams } from "../lib/defense-teams";

// These are contract fixtures, not captured player observations or production data.
const character={sourceKind:"verified-character-template",localVerification:true,capturedAt:1795017600,records:[{characterId:"fixture-unit",name:"測試用角色",description:null,starCount:null,unitCategory:"STR",unitElement:"fire",rawMemory:"private-sentinel"}]};
const success={snapshotId:"fixture-snapshot",teamId:"fixture-team",playerId:"fixture-player",purpose:"pvp_defense",status:"success",retrievedAt:"2026-11-19T00:00:00+08:00",guildId:null,rawMemory:"private-sentinel",members:[{memberIndex:0,characterState:"present",characterId:"fixture-unit",characterInstanceIdentity:{value:"9007199254740993",sourceField:"invenId",namespace:"unknown"},rawMemory:"private-sentinel",equipment:{weapon:{state:"equipped",equipmentId:"eq_2202_wpn_17",rawMemory:"private-sentinel"},armor:{state:"equipped",equipmentId:"unmatched-fixture-id"},accessory:{state:"unknown",equipmentId:null}}}]};
function source(snapshots:unknown[]){return {sourceKind:"validated-player-team-snapshots",recordScope:"player-team",snapshots};}
function files(teams:unknown=source([success])){vi.mocked(readFile).mockImplementation(async p=>JSON.stringify(String(p).endsWith("defense-teams.private.json") ? teams : character));}
beforeEach(()=>{vi.stubEnv("NODE_ENV","development");vi.mocked(readFile).mockReset();files();});
afterEach(()=>vi.unstubAllEnvs());
describe("native character and private defense data boundaries",()=>{
 it("keeps unknown star and skill values unknown and excludes raw fields",async()=>{
  const result=await getCharacterReference();expect(result?.records[0].starGrade).toBeNull();expect(result?.records[0].skills).toBeNull();expect(JSON.stringify(result)).not.toContain("private-sentinel");
 });
 it("does not promote an external character reference to native data",async()=>{
  vi.mocked(readFile).mockResolvedValue(JSON.stringify({...character,sourceKind:"external-user-confirmed"}));await expect(getCharacterReference()).rejects.toThrow();
 });
 it("joins supported equipment and preserves unknown IDs and three slots",async()=>{
  const result=await getDefenseTeams("pvp_defense");const member=result![0].members![0];
  expect(member.slots).toHaveLength(3);expect(member.slots[0].template?.starCount).toBe(7);expect(member.slots[1].equipmentId).toBe("unmatched-fixture-id");expect(member.slots[1].template).toBeNull();expect(member.slots[2].state).toBe("unknown");
  expect(member.characterInstanceIdentity?.value).toBe("9007199254740993");expect(JSON.stringify(result)).not.toContain("private-sentinel");
 });
 it("does not fall back to an old successful team after a newer failure",async()=>{
  files(source([success,{...success,snapshotId:"failure",status:"failed",retrievedAt:"2026-11-19T01:00:00+08:00",members:null}]));const result=await getDefenseTeams("pvp_defense");expect(result).toHaveLength(1);expect(result![0].status).toBe("failed");expect(result![0].members).toBeNull();
 });
 it("does not merge identical instance values belonging to different players",async()=>{
  files(source([success,{...success,snapshotId:"other",playerId:"other-player"}]));expect(await getDefenseTeams("pvp_defense")).toHaveLength(2);
 });
 it("filters a member detail by actual owner before creating public aliases",async()=>{
  files(source([success,{...success,snapshotId:"other",playerId:"other-player"}]));
  expect(await getDefenseTeams("pvp_defense","fixture-player")).toHaveLength(1);expect(await getDefenseTeams("pvp_defense","not-observed")).toBeNull();
 });
 it("keeps raw account identifiers off the page and preserves proven instance enhancement",async()=>{
  const row=structuredClone(success);row.playerId="private-account-sentinel";
  Object.assign(row.members[0].equipment.weapon,{enhancement:5,equipmentInstanceIdentity:{value:"9007199254740997",sourceField:"invenId",namespace:"player-owned-equipment"}});
  files(source([row]));const result=await getDefenseTeams("pvp_defense");
  expect(result![0].playerId).toMatch(/^本機玩家-[a-f0-9]{12}$/);expect(JSON.stringify(result)).not.toContain("private-account-sentinel");
  expect(result![0].members![0].slots[0].enhancement).toBe(5);expect(result![0].members![0].slots[0].actualEffects).toBeNull();
 });
 it("keeps separate team identifiers for the same owner",async()=>{
  files(source([success,{...success,snapshotId:"second-team",teamId:"another-team"}]));expect(await getDefenseTeams("pvp_defense")).toHaveLength(2);
 });
 it("does not read private previews in production",async()=>{
  vi.stubEnv("NODE_ENV","production");expect(await getDefenseTeams("pvp_defense")).toBeNull();expect(await getCharacterReference()).toBeNull();expect(readFile).not.toHaveBeenCalled();
 });
});
