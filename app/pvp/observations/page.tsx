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
      title="尚無可驗證的排行榜資料"
      description="排行榜、玩家防守隊伍與配裝分析目前尚未串接。"
      evidence="目前沒有取得任何真實 PvP 排行、段位或玩家防守隊伍記錄。"
      missing="已授權且可重現的排行榜來源、有效樣本、玩家隊伍快照、角色與裝備配對，以及取得失敗紀錄。"
      nextStep="取得資料後會標示排名玩家範圍與取樣時間；使用率以有效樣本玩家為分母，勝率則需要戰鬥結果資料。"
    />
  );
}
