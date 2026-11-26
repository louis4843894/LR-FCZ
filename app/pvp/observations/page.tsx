import { ModuleStatusPage } from "../../_components/module-status-page";
import { getDefenseTeams } from "../../../lib/defense-teams";
import { DefenseTeamsPanel } from "../../_components/defense-teams-panel";
import { notFound } from "next/navigation";

export default async function PvpObservationsPage({searchParams}:{searchParams:Promise<{page?:string;player?:string}>}) {
  const teams = await getDefenseTeams("pvp_defense",undefined,{excludeRanked:true});
  if (teams){
    const query=await searchParams;
    const players=[...new Map(teams.map(t=>[t.playerId,{key:t.playerId.slice(-12),label:t.playerDisplayName ?? t.playerId}])).values()];
    const requested=Number(query.page);let page=Number.isSafeInteger(requested) && requested>0 ? Math.min(requested,players.length) : 1;
    if(query.player){const index=players.findIndex(p=>p.key===query.player);if(index<0)notFound();page=index+1;}
    const selected=players[page-1];const visible=teams.filter(t=>t.playerId.endsWith('-'+selected.key));
    return <DefenseTeamsPanel teams={visible} purpose="pvp_defense" browse={{basePath:"/pvp/observations",page,totalPages:players.length,totalTeams:teams.length,totalPlayers:players.length,players,selectedKey:selected.key}}/>;
  }
  return (
    <ModuleStatusPage
      eyebrow="PvP"
      title="非排名歷史觀察未公開"
      description="此頁保留給本機歷史資料；排行榜與已公開的玩家防禦請由 PVP 排行進入。"
      evidence="沒有將個人歷史觀察與原始快照放入公開網站。"
      missing="這不影響目前已取得的排名樣本與防禦展示。"
      nextStep="前往 PVP 排行選擇段位，再點選已取得的玩家防禦；統計僅使用對應排名樣本。"
    />
  );
}
