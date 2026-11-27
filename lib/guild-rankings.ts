import "server-only";
import {readSiteDisplay} from './site-display-data';
import {createHash} from "node:crypto";
import {readRankedGuildStore,readGuildWarStore} from "./local-game-data";
import {getGuildWar,type WarRecord} from "./guild-war";
import {displaySourceText} from "./display-text";

type Guild={guildId:string;rank:number;score:number;name:string;gradeId:number;gradeLabel:string;memberCount:number;memberCapacity:number;level:number;nationalFlag:string;retrievedAt:string};
type Roster={guildId:string;name:string;level:number;capturedAt:string;observedMemberTotal:number;memberCapacity:number;membersRetrieved:number;membershipComplete:boolean;members:{playerId:string;name:string;level:number;role:string}[]};
type Ranking={sourceKind:string;snapshotId:string;capturedAt:string;lastCheckedAt?:string;top:number;observedTotal:number;status:string;guilds:Guild[]};
const alias=(id:string)=>createHash('sha256').update(id).digest('hex').slice(0,20);
const role=(r:string)=>({MASTER:'會長',SUBMASTER:'副會長',NORMAL:'成員'} as Record<string,string>)[r]??'職位未知';

export async function getGuildRankings():Promise<Awaited<ReturnType<typeof getLocalGuildRankings>>>{
  return process.env.NODE_ENV==='production'?readSiteDisplay('guilds'):getLocalGuildRankings();
}
async function getLocalGuildRankings(){
  const store=await readRankedGuildStore();if(!store)return null;
  const ranking=store.ranking as Ranking;
  if(ranking.sourceKind!=='verified-normal-guildwar-top-ranking'||ranking.status!=='success')return null;
  const rosters=new Map((store.rosters as Roster[]).map(r=>[r.guildId,r]));
  const attempts=new Map(store.attempts.map(r=>[JSON.stringify([r.guildId,r.part]),r]));
  const warRecords=await readGuildWarStore() as WarRecord[];
  const rankedGuildIds=new Set(ranking.guilds.map(g=>g.guildId));
  const guilds=ranking.guilds.map(g=>{
    const roster=rosters.get(g.guildId);const last=attempts.get(JSON.stringify([g.guildId,'roster']));const defense=attempts.get(JSON.stringify([g.guildId,'defense']));
    const deployment=warRecords.find(r=>r.guildId===g.guildId&&r.kind==='deployed_defense'&&r.sourceKind==='verified-guildwar-tower-deployments');
    return {alias:alias(g.guildId),name:displaySourceText(g.name),rank:g.rank,score:g.score,grade:g.gradeLabel,
      level:g.level,nation:g.nationalFlag,memberCount:g.memberCount,memberCapacity:g.memberCapacity,
      rosterRetrievedAt:roster?.capturedAt??null,rosterState:last?.status??(roster?'success':'not_read'),
      membersRetrieved:roster?.membersRetrieved??null,membershipComplete:roster?.membershipComplete??false,
      defenseState:deployment?.status??defense?.status??'not_read',defenseCheckedAt:deployment?.capturedAt??defense?.checkedAt??null,
      defenseTowersRead:deployment?.towers?.filter(t=>t.readState==='success').length??null,defenseTowersObserved:deployment?.towers?.length??null,
      warOverviewAvailable:warRecords.some(r=>r.guildId===g.guildId&&r.kind==='overview'&&r.sourceKind==='verified-guildwar-overview'),
      savedWarConfigurationAvailable:warRecords.some(r=>r.guildId===g.guildId&&r.kind==='saved_configuration'&&r.sourceKind==='verified-guildwar-saved-configuration')};
  });
  return {capturedAt:ranking.lastCheckedAt??ranking.capturedAt,top:ranking.top,totalGuilds:ranking.observedTotal,guilds,
    completeRosters:guilds.filter(g=>g.membershipComplete).length,
    membersRetrieved:guilds.reduce((n,g)=>n+(g.membersRetrieved??0),0),
    defenseGuilds:guilds.filter(g=>g.defenseState==='success').length,
    partialDefenseGuilds:guilds.filter(g=>g.defenseState==='partial').length,
    defenseNotAcquiredGuilds:guilds.filter(g=>g.defenseState!=='success'&&g.defenseState!=='partial').length,
    defenseTeams:warRecords.filter(r=>rankedGuildIds.has(r.guildId)&&r.kind==='deployed_defense').reduce((n,r)=>n+(r.towers??[]).reduce((m,t)=>m+(t.defenders??[]).reduce((k,d)=>k+d.teams.length,0),0),0)};
}

export async function getRankedGuild(guildAlias:string):Promise<Awaited<ReturnType<typeof getLocalRankedGuild>>>{
  if(!/^[a-f0-9]{20}$/.test(guildAlias))return null;
  if(process.env.NODE_ENV!=='production')return getLocalRankedGuild(guildAlias);
  const data=await readSiteDisplay<Awaited<ReturnType<typeof getLocalRankedGuild>>>(`guild-${guildAlias}`);
  if(!data?.war?.overview)return data;
  return {...data,war:{...data.war,overview:{...data.war.overview,ageHours:Math.max(0,Math.floor((Date.now()-Date.parse(data.war.overview.capturedAt))/3600000))}}};
}
async function getLocalRankedGuild(guildAlias:string){
  if(!/^[a-f0-9]{20}$/.test(guildAlias))return null;
  const summary=await getGuildRankings();const guild=summary?.guilds.find(g=>g.alias===guildAlias);if(!guild)return null;
  const store=await readRankedGuildStore();const roster=(store?.rosters as Roster[]).find(r=>alias(r.guildId)===guildAlias);
  const war=await getGuildWar(guildAlias,new Map(roster?.members.map(m=>[m.playerId,m.level])));
  return {guild,rankingCapturedAt:summary!.capturedAt,war,roster:roster?{
    capturedAt:roster.capturedAt,observedTotal:roster.observedMemberTotal,capacity:roster.memberCapacity,
    complete:roster.membershipComplete,members:roster.members.map(m=>({alias:alias(JSON.stringify([roster.guildId,m.playerId])),name:displaySourceText(m.name),role:role(m.role),
      // The native level code still needs its displayed-rank conversion.
      // It is kept in the private source rather than shown as a verified level.
      level:null as number|null,defenseState:war?.deployment?.towers.some(t=>t.defenders?.some(d=>d.memberAlias===alias(JSON.stringify([roster.guildId,m.playerId]))))?'captured':'not_read',
      defenseTowers:war?.deployment?.towers.filter(t=>t.defenders?.some(d=>d.memberAlias===alias(JSON.stringify([roster.guildId,m.playerId])))).map(t=>({code:t.code,number:t.number,label:t.label}))??[],
      towerCodes:war?.deployment?.towers.filter(t=>t.defenders?.some(d=>d.memberAlias===alias(JSON.stringify([roster.guildId,m.playerId])))).map(t=>t.code)??[]}))}:null};
}
