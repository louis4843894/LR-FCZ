import Link from "next/link";
import {notFound} from "next/navigation";
import {SiteHeader} from "../../_components/site-header";
import {SiteFooter} from "../../_components/site-footer";
import {getRankedGuild} from "../../../lib/guild-rankings";
import {GuildWarPanel} from "../../_components/guild-war-panel";
import {guildWarPanelView} from '../../../lib/guild-war';
import {requireGuildAccess} from "../../../lib/guild-access";
import {guildDetailPath} from "../../../lib/guild-access-path";
const time=(s:string)=>new Date(s).toLocaleString("zh-TW",{timeZone:"Asia/Taipei",hour12:false});
export default async function RankedGuildPage({params,searchParams}:{params:Promise<{guildAlias:string}>;searchParams:Promise<{q?:string;tower?:string}>}){
 const {guildAlias}=await params;const filters=await searchParams;
 const {client}=await requireGuildAccess(guildDetailPath(guildAlias,filters));
 const data=await getRankedGuild(guildAlias,client);if(!data)notFound();const {q="",tower}=filters;
 const members=data.roster?.members.filter(m=>m.name.toLocaleLowerCase().includes(q.trim().toLocaleLowerCase()))??[];
 const observedDefenders=new Map(data.war?.deployment?.towers.flatMap(t=>
   t.screenObservation?.defenders.map(d=>[d.memberAlias,{tower:t,level:d.playerLevel}] as const)??[]
 ));
 return <div className="page-shell"><SiteHeader/><main className="page-main"><Link className="back-link" href="/guild">← 公會排名</Link>
 <section className="page-intro"><p className="eyebrow">GUILD · 第 {data.guild.rank} 名</p><h1>{data.guild.name}</h1><p className="page-lede">{data.guild.grade} · 公會 Lv.{data.guild.level} · {data.guild.score.toLocaleString("zh-TW")} 分</p></section>
 <section className="catalog-summary"><div><span>成員數</span><strong>{data.guild.memberCount}／{data.guild.memberCapacity}</strong></div><div><span>國家／地區</span><strong>{data.guild.nation||"未知"}</strong></div><div><span>名單更新時間</span><strong>{data.roster?time(data.roster.capturedAt):"尚未取得"}</strong></div></section>
 <GuildWarPanel war={guildWarPanelView(data.war,tower)} towerCode={tower}/>
 <details className="reference-panel catalog-fold" open><summary><h2>成員名單</h2></summary>{data.roster?<><p>已取得 {data.roster.members.length} 位；當次公會顯示 {data.roster.observedTotal} 位。{data.roster.complete?"本次名單完整。":"名單仍有缺漏。"}名單與駐防取得時間分開，未在塔內觀察到的成員不能判定為沒有防禦。</p><form className="gear-filters" action={`/guild/${guildAlias}`}><label>搜尋成員<input name="q" type="search" defaultValue={q} placeholder="成員名稱"/></label><button className="button button-primary">搜尋</button></form><p role="status">{members.length} 位成員</p><div className="reference-table-wrap"><table className="ranking-table"><thead><tr><th>成員</th><th>職位</th><th>等級</th><th>公會戰防禦</th></tr></thead><tbody>{members.map(m=>{
   const observation=observedDefenders.get(m.alias);
   return <tr className="guild-member-row" key={m.alias}>
     <td>{m.name}</td><td>{m.role}</td>
     <td>{observation?`${observation.level.grade} Lv. ${observation.level.level}`:m.level??"尚未確認"}</td>
     <td>{m.defenseState==='captured'?m.defenseTowers.map(t=><Link key={t.code} href={`?tower=${t.number??t.code}#defender-${m.alias}`}>{t.label}防禦</Link>):
       observation?<Link href={`?tower=${observation.tower.number??observation.tower.code}#defender-${m.alias}`}>{observation.tower.label}駐防（畫面核對）</Link>:"尚未取得"}</td>
   </tr>;
 })}</tbody></table></div></>:<p>成員名單尚未取得，請稍後再查看。</p>}</details>
 </main><SiteFooter/></div>;
}
