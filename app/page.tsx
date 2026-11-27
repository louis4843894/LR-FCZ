import Link from "next/link";
import {SiteHeader} from "./_components/site-header";
import {SiteFooter} from "./_components/site-footer";
import {getVerifiedEquipmentList} from "../lib/verified-equipment";
import {getCharacterReference} from "../lib/character-reference";
import {getPvpRankings} from "../lib/pvp-rankings";
import {HomeSearch} from "./_components/home-search";

export default async function HomePage(){
  const [gear,characters,ranking]=await Promise.all([getVerifiedEquipmentList(),getCharacterReference(),getPvpRankings()]);
  const players=ranking?.availableRankingPlayers??0;
  const modules=[{title:"Rangers 角色",description:"依名稱、星等、類型與屬性查詢角色，查看技能及能力關聯。",href:"/characters",symbol:"◇",count:characters?`${characters.records.length.toLocaleString('zh-TW')} 位角色`:"資料準備中"},
    {title:"裝備圖鑑",description:"搜尋武器、防具與飾品，查看基本效果、觸發條件與強化範圍。",href:"/gear",symbol:"✧",count:`${gear.length.toLocaleString('zh-TW')} 件裝備`},
    {title:"PvP 排行與防禦",description:"查看各段位排行榜、玩家防禦角色與配裝，以及樣本內使用率。",href:"/pvp",symbol:"⚔",count:players?`${players.toLocaleString('zh-TW')} 位排名玩家`:"資料準備中"},
    {title:"公會排名與防禦",description:"查詢前 100 名公會、成員名單及公會戰防禦的取得狀態。",href:"/guild",symbol:"♜",count:"需登入並通過審核"}];
  return <div className="page-shell"><SiteHeader/><main className="page-main"><section className="page-intro home-intro"><p className="eyebrow">LINE RANGERS DATABASE</p><h1>LINE Rangers 資料站</h1><p className="page-lede">角色、裝備、PvP 與公會戰資料，一站查詢。</p><HomeSearch/></section>
    <section className="home-modules" aria-label="資料查詢">{modules.map(m=><Link href={m.href} className="home-module" key={m.href}><span className="home-module-icon" aria-hidden="true">{m.symbol}</span><div><span className="home-module-count">{m.count}</span><h2>{m.title}</h2><p>{m.description}</p><span className="home-module-action">開始查詢</span></div></Link>)}</section>
    <section className="catalog-summary"><div><span>角色圖鑑</span><strong>{characters?.records.length.toLocaleString('zh-TW')??"尚未取得"}</strong></div><div><span>裝備圖鑑</span><strong>{gear.length.toLocaleString('zh-TW')}</strong></div><div><span>PvP 段位</span><strong>{ranking?.scopes.length||"尚未取得"}</strong></div></section>
  </main><SiteFooter/></div>;
}
