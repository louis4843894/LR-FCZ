import { notFound } from "next/navigation";
import { getGuildMemberPvpDefense } from "../../../../lib/guild-roster";
import { DefenseTeamsPanel } from "../../../_components/defense-teams-panel";
import { requireGuildAccess } from "../../../../lib/guild-access";

export default async function GuildMemberPage({params}:{params:Promise<{memberId:string}>}){
  const {memberId}=await params;
  await requireGuildAccess(`/guild/members/${memberId}`);
  if(!/^[a-f0-9]{20}$/.test(memberId))notFound();
  const data=await getGuildMemberPvpDefense(memberId);
  if(!data)notFound();
  return <DefenseTeamsPanel teams={data.teams} purpose="pvp_defense" contextLabel={`${data.guildName} · ${data.memberName} 的 PVP 防禦`}/>;
}
