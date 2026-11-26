import Link from "next/link";
import type {guildWarPanelView} from "../../lib/guild-war";
import {CollapseControls} from './collapse-controls';
import {DefenseTeamViewer} from "./defense-team-viewer";
import {warViewerTeams} from "../../lib/defense-viewer-data";
type War=ReturnType<typeof guildWarPanelView>;
type Teams=NonNullable<War>['savedConfigurations'][number]['teams'];
const time=(s:string)=>new Date(s).toLocaleString("zh-TW",{timeZone:"Asia/Taipei",hour12:false});

function WarTeams({teams,scope,retrievedAt,title,subtitle}:{teams:Teams;scope:string;retrievedAt:string;title:string;subtitle:string}){
 return <DefenseTeamViewer title={title} subtitle={subtitle} teams={warViewerTeams(teams,scope,retrievedAt)} combinedLabel="全部已取得的公會戰隊伍"/>;
}
export function GuildWarPanel({war,towerCode}:{war:War;towerCode?:string}){
 if(!war)return <section className="reference-panel" id="defense"><h2>公會戰防禦</h2><p>此公會的十座塔配置尚未取得，無法判定哪些成員駐防。一般編隊與 PVP 防禦不列為公會戰防禦。</p></section>;
 const deployment=war.deployment;
 const selected=deployment?.towers.find(t=>t.number!==null&&String(t.number)===towerCode)??deployment?.towers.find(t=>String(t.code)===towerCode)??deployment?.towers[0];
 return <section className="reference-panel" id="defense" data-collapse-scope><h2>公會戰防禦</h2><CollapseControls/>
 {deployment?<><p>第 {deployment.seasonNo} 期 · 第 {deployment.battleNo} 場 · {deployment.historicalContext?"歷史對手":"防禦"}配置取得於 {time(deployment.capturedAt)}。非即時戰況，配置可能已變更。</p><p className="war-deployment-summary">已讀取 {deployment.towers.filter(t=>t.readState==='success').length}／{deployment.towers.length} 座塔 · {deployment.uniqueHumanDefenders} 位真人駐防 · {deployment.unitCount} 角色 · {deployment.equippedCount.toLocaleString("zh-TW")} 件裝備。</p>
 <nav className="war-tower-grid" aria-label="選擇防禦塔">{deployment.towers.map(t=><Link className="war-tower" aria-current={t.code===selected?.code?'page':undefined} key={t.code} href={`?tower=${t.number??t.code}#defense`}><strong>{t.label}</strong><span>{t.readState!=='success'?"尚未讀取":t.defenderCount!==null?`${t.defenderCount} 份防禦配置`:"內容未知"}</span></Link>)}</nav>
 {selected&&<section className="war-selected-tower"><h3>{selected.label}</h3>{selected.readState!=='success'?<p>此塔尚未讀取；不能判定為空塔。</p>:selected.defenders===null?<p>駐防內容未知。</p>:selected.defenders.length===0?<p>此次正常回應確認沒有駐防配置。</p>:selected.defenders.map((d,index)=><details open={index===0} className="war-defender" id={`defender-${d.memberAlias}`} key={d.memberAlias}><summary><h3>{d.name||"名稱未知"}{d.isAI?"（AI 配置）":""}</h3><small>{d.teams.reduce((n,t)=>n+t.units.length,0)} 角色</small></summary><p>取得於 {time(d.retrievedAt)}。{d.withdrawal===true?"回應標記此成員已退出；保留當次塔內配置。":""}角色、裝備與部位已解析，尚未逐件目視核對。</p><WarTeams teams={d.teams} scope={`${selected.code}/${d.memberAlias}`} retrievedAt={d.retrievedAt} title={d.name||"名稱未知"} subtitle={`${selected.label} · ${d.isAI?"AI 配置":"公會戰防禦"}`}/></details>)}</section>}
 </>:war.overview?<><p>第 {war.overview.seasonNo} 期{war.overview.battleNo!==null?` · 第 ${war.overview.battleNo} 場`:""} · 塔總覽取得於 {time(war.overview.capturedAt)}。{war.overview.ageHours>0?`資料距今 ${war.overview.ageHours} 小時，戰況可能已變更。`:""}</p><p>已取得 {war.overview.towers.length} 座塔的識別；塔內駐防尚未取得，不能判定為空塔。</p><div className="war-tower-grid">{war.overview.towers.map(t=><div className="war-tower" key={t.code}><strong>{t.label}</strong><span>駐防尚未取得</span></div>)}</div></>:null}
 {war.savedConfigurations.map(config=><details className="war-saved-configuration" key={config.alias}><summary>已儲存的個人防禦設定 · {config.teams.reduce((n,t)=>n+t.units.length,0)} 角色（部署未確認）</summary><p>取得於 {time(config.capturedAt)}。這份資料是個人已儲存設定，尚未核對實際駐防塔與成員，不計入已部署隊伍。</p><WarTeams teams={config.teams} scope={config.alias} retrievedAt={config.capturedAt} title="個人儲存的防禦設定" subtitle="部署尚未確認，不計入塔內駐防"/></details>)}
 </section>;
}
