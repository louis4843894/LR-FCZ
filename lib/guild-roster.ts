import "server-only";
import { readNormalizedText } from "./local-game-data";
import { createHash } from "node:crypto";
import { displaySourceText } from "./display-text";
import { getDefenseTeams } from "./defense-teams";

type PvpSummary={status:"not_read"|"success"|"partial"|"failed"|"unavailable";successfulTeams:number;retrievedAt:string|null};
export type GuildMember = { memberId:string;name:string;level:number|null;retrievedAt:string;defenseObservedAt:string|null;defenseStatus:"not_read"|"failed"|"unavailable";defenseFailureReason:string|null;pvp:PvpSummary };
export type GuildRoster = { name:string;level:number|null;capturedAt:string;gameVersion:string;observedMemberTotal:number;memberCapacity:number;membersRetrieved:number;membershipComplete:boolean;ageHours:number;members:GuildMember[];guildBattleAvailability:{status:"unavailable";reasonCode:"not_registered";confirmedAt:string}|null };
const memberAlias=(guildId:string,playerId:string)=>createHash("sha256").update(JSON.stringify([guildId,playerId])).digest("hex").slice(0,20);
async function pvpSummaries():Promise<Map<string,PvpSummary>> {
  let data;
  try{data=JSON.parse(await readNormalizedText("defense-teams.private.json"));}
  catch(error:unknown){if(error instanceof Error && "code" in error && error.code==="ENOENT")return new Map();throw error;}
  if(data.sourceKind!=="validated-player-team-snapshots" || data.recordScope!=="player-team" || !Array.isArray(data.snapshots))throw new Error("防禦快照格式不正確");
  type Observation={playerId:string;teamId:string;purpose:string;retrievedAt:string;status:string;unobservedPositionIndices?:number[]};
  const latest=new Map<string,Observation>();
  for(const t of data.snapshots as Observation[]){
    if(t.purpose!=="pvp_defense")continue;
    const key=JSON.stringify([t.playerId,t.teamId]);const before=latest.get(key);
    if(!before || Date.parse(t.retrievedAt)>Date.parse(before.retrievedAt))latest.set(key,t);
  }
  const result=new Map<string,PvpSummary>();
  for(const t of latest.values()){
    const before=result.get(t.playerId);const partial=t.status==="success" && !!t.unobservedPositionIndices?.length;
    const success=t.status==="success" && !partial;const failed=t.status==="failed";
    const current=partial ? "partial" : success ? "success" : failed ? "failed" : "unavailable";
    const status=before && before.status!==current ? "partial" : current;
    result.set(t.playerId,{status,successfulTeams:(before?.successfulTeams ?? 0)+(success ? 1 : 0),retrievedAt:before?.retrievedAt && Date.parse(before.retrievedAt)>Date.parse(t.retrievedAt) ? before.retrievedAt : t.retrievedAt});
  }
  return result;
}
export async function getGuildRoster():Promise<GuildRoster|null> {
  if(process.env.NODE_ENV!=="development")return null;
  try {
    const data=JSON.parse(await readNormalizedText("guild-roster.private.json"));
    if(data.sourceKind!=="validated-native-guild-roster" || !Array.isArray(data.members) || typeof data.guildId!=="string" || data.membersRetrieved!==data.members.length || !Number.isInteger(data.observedMemberTotal) || data.membersRetrieved>data.observedMemberTotal || data.observedMemberTotal>data.memberCapacity || (data.membershipComplete===true && data.membersRetrieved!==data.observedMemberTotal))throw new Error("公會名單格式不正確");
    const pvp=await pvpSummaries();
    const members:GuildMember[]=data.members.map((m:{playerId:string;name:string;level:number|null;retrievedAt:string;defenseObservedAt?:string;defenseStatus:string;defenseFailureReason:string|null})=>({
      memberId:memberAlias(data.guildId,m.playerId),name:displaySourceText(m.name),level:m.level,retrievedAt:m.retrievedAt,defenseObservedAt:m.defenseObservedAt ?? null,pvp:pvp.get(m.playerId) ?? {status:"not_read",successfulTeams:0,retrievedAt:null},
      defenseStatus:m.defenseStatus==="failed" ? "failed" : m.defenseStatus==="unavailable" ? "unavailable" : "not_read",defenseFailureReason:m.defenseFailureReason==="only_general_team_visible" ? "此筆名單的原始觀察只有一般編隊，PVP 防禦資料另行取得。" : m.defenseStatus==="failed" ? "此次讀取未完成，內容未知。" : m.defenseStatus==="unavailable" ? "目前可見來源未提供防禦資料。" : null,
    }));
    const war=data.guildBattleAvailability;
    const guildBattleAvailability=war?.guildId===data.guildId && war.source==="user-confirmed" && war.status==="unavailable" && war.reasonCode==="not_registered" && Number.isFinite(Date.parse(war.confirmedAt)) ? {status:"unavailable" as const,reasonCode:"not_registered" as const,confirmedAt:war.confirmedAt} : null;
    return {name:displaySourceText(data.name),level:Number.isInteger(data.level) ? data.level : null,capturedAt:data.capturedAt,gameVersion:data.gameVersion,observedMemberTotal:data.observedMemberTotal,memberCapacity:data.memberCapacity,membersRetrieved:members.length,membershipComplete:data.membershipComplete===true,ageHours:Math.max(0,Math.floor((Date.now()-Date.parse(data.capturedAt))/3600000)),members,guildBattleAvailability};
  }catch(error:unknown){
    if(error instanceof Error && "code" in error && error.code==="ENOENT")return null;
    throw error;
  }
}

export async function getGuildMemberPvpDefense(memberId:string){
  const roster=await getGuildRoster();const member=roster?.members.find(m=>m.memberId===memberId);
  if(!roster || !member)return null;
  // Resolve the actual owner on the server, before any display alias is created.
  const raw=JSON.parse(await readNormalizedText("guild-roster.private.json"));
  const owner=raw.members.find((m:{playerId:string})=>memberAlias(raw.guildId,m.playerId)===memberId);
  if(!owner)return null;
  const teams=await getDefenseTeams("pvp_defense",owner.playerId);
  return {guildName:roster.name,memberName:member.name,teams:teams ?? []};
}
