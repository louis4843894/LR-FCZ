import { getDefenseTeams } from "../../lib/defense-teams";
import { SiteHeader } from "./site-header";
import { SiteFooter } from "./site-footer";
import Link from "next/link";
import {PvpAutoUpdateStatus} from './pvp-auto-update-status';
import {DefenseTeamViewer} from './defense-team-viewer';
import {pvpViewerTeams} from '../../lib/defense-viewer-data';
import type {DisplayPlayer} from '../../lib/site-display-contract';

type Browse={basePath?:string;page:number;totalPages:number;totalTeams:number;totalPlayers:number;players:{key:string;label:string}[];selectedKey:string};
type RankingContext={scopeLabel:string;rank:number;score?:number|null;snapshotId:string;rankingCapturedAt:string;lastCheckedAt?:string|null;cacheState:string|null;latestStatus:string};
export function DefenseTeamsPanel({teams,purpose,contextLabel,browse,rankingContext,displayPlayers}:{teams:NonNullable<Awaited<ReturnType<typeof getDefenseTeams>>>;purpose:"pvp_defense"|"guild_battle_defense";contextLabel?:string;browse?:Browse;rankingContext?:RankingContext;displayPlayers?:DisplayPlayer[]}) {
  const players=new Set(teams.map(t=>t.playerId)).size;
  const browsePath=browse?.basePath ?? "/pvp/observations";
  return <div className="page-shell"><SiteHeader/><main className="page-main"><section className="page-intro"><p className={contextLabel ? "page-lede" : "eyebrow"}>{contextLabel ?? (rankingContext ? "玩家防禦資料" : "玩家防禦")}</p><h1>{purpose==="pvp_defense" ? "PVP 防禦隊伍" : "公會戰防禦隊伍"}</h1><p className="page-lede">顯示每位玩家最新取得狀態。角色名稱及裝備模板資訊不代表實際能力或詞條數值。</p>{contextLabel&&<p><Link href="/guild">返回公會成員名單</Link></p>}</section>
    {browse&&<><p>已取得 {browse.totalPlayers} 位玩家、{browse.totalTeams} 組防禦快照；目前顯示第 {browse.page}／{browse.totalPages} 位玩家。這是快照索引，不是排行榜。</p><form action={browsePath} className="gear-filters"><label>選擇已取得的玩家<select name="player" defaultValue={browse.selectedKey}>{browse.players.map(p=><option value={p.key} key={p.key}>{p.label}</option>)}</select></label><button className="button button-primary">查看防禦</button></form></>}
    {purpose==="pvp_defense"&&<><p>PVP 防禦可隨時重新擷取並更新資料庫，不受公會每週更新時間限制。頁面顯示各隊實際取得時間，重新整理頁面不會自動擷取遊戲。</p><PvpAutoUpdateStatus/></>}
    {!teams.length&&!displayPlayers?.length&&<p className="empty-panel">尚無此用途的隊伍快照；不代表玩家沒有隊伍。</p>}
    {displayPlayers?.map((player,index)=><section className="defense-player-view" key={index}><DefenseTeamViewer title={player.title} subtitle={rankingContext?`${rankingContext.scopeLabel} · 排名 #${rankingContext.rank}`:'PVP 防禦 · 已取得的玩家配置'} teams={player.teams} combinedLabel="全部 PVP 防禦（含備用）"/></section>)}
    {rankingContext?<section className="reference-panel"><h2>{rankingContext.scopeLabel}排行榜第 {rankingContext.rank} 名</h2><p>排行榜時間：{new Date(rankingContext.rankingCapturedAt).toLocaleString('zh-TW',{timeZone:'Asia/Taipei',hour12:false})}；已按同一玩家身分關聯此份防禦。</p><p>統計僅使用採集時選用的隊伍，備用隊伍另外保留。{rankingContext.cacheState==='verified-earlier-session-copy'?'此處沿用同次工作中較早取得的有效副本，防禦時間另列。':''}</p>{rankingContext.lastCheckedAt&&<p>防禦最近核對：{new Date(rankingContext.lastCheckedAt).toLocaleString('zh-TW',{timeZone:'Asia/Taipei',hour12:false})}。配置未變時保留原取得時間。</p>}{(rankingContext.latestStatus==='failed'||rankingContext.latestStatus==='unavailable')&&<p>本次來源無法更新防禦，保留先前成功資料供核對，不計入本次有效統計。</p>}<Link href={`/pvp?scope=${encodeURIComponent(rankingContext.scopeLabel)}`}>返回排行榜</Link></section>:teams.length>0&&<p>{players===1 ? "目前為單一玩家樣本展示" : `目前為 ${players} 位玩家的防禦快照展示`}；本頁為非排名歷史觀察，不納入排行統計。</p>}
    {[...new Set(teams.map(t=>t.playerId))].map(playerId=>{
      const playerTeams=teams.filter(t=>t.playerId===playerId);const first=playerTeams[0];
      return <section className="defense-player-view" key={playerId}>
        <DefenseTeamViewer title={first.playerDisplayName??first.playerId} subtitle={rankingContext?`${rankingContext.scopeLabel} · 排名 #${rankingContext.rank}${rankingContext.score!=null?` · ${rankingContext.score.toLocaleString('zh-TW')} 分`:''}`:purpose==='pvp_defense'?'PVP 防禦 · 已取得的玩家配置':'公會戰防禦 · 已取得的玩家配置'} teams={pvpViewerTeams(playerTeams)} combinedLabel={purpose==='pvp_defense'?'全部 PVP 防禦（含備用）':'全部已取得的公會戰防禦'}/>
        <details className="defense-capture-notes"><summary>資料時間與核對狀態</summary>{playerTeams.map(t=><div key={t.snapshotId}><p>{t.teamId==='pvpteam/1'?'防禦 A 隊':t.teamId==='pvpteam/2'?'防禦 B 隊':'防禦隊伍'} · 取得於 {new Date(t.retrievedAt).toLocaleString('zh-TW',{timeZone:'Asia/Taipei',hour12:false})} · 遊戲版本 {t.gameVersion??'未知'}</p><p>約 {t.ageHours} 小時前取得，配置可能已有變更。{t.verification?.purposeConfirmed?`防禦用途於 ${new Date(t.verification.checkedAt).toLocaleString('zh-TW',{timeZone:'Asia/Taipei',hour12:false})} 核對；數值尚未逐項目視核對。`:'尚未目視核對。'}</p>{t.attributeFactorTimes.length>0&&<p>詞條係數取得時間：{t.attributeFactorTimes.map(v=>new Date(v).toLocaleString('zh-TW',{timeZone:'Asia/Taipei',hour12:false})).join('、')}。已還原值包含實際強化，不再次套用倍率。</p>}</div>)}</details>
      </section>;
    })}
    {browse&&<nav className="gear-pagination" aria-label="PVP 快照分頁">{browse.page>1&&<Link className="button" href={`${browsePath}?page=${browse.page-1}`}>上一位玩家</Link>}<span>{browse.page}／{browse.totalPages}（非排名）</span>{browse.page<browse.totalPages&&<Link className="button" href={`${browsePath}?page=${browse.page+1}`}>下一位玩家</Link>}</nav>}
  </main><SiteFooter/></div>;
}
