import { ModuleStatusPage } from "../_components/module-status-page";
import Link from "next/link";
import {CharacterPortrait} from "../_components/character-portrait";
import { getCharacterReference, roleName, elementName } from "../../lib/character-reference";
import { SiteHeader } from "../_components/site-header";
import { SiteFooter } from "../_components/site-footer";

export default async function CharactersPage({ searchParams }: { searchParams: Promise<{ q?: string; page?: string; category?:string; element?:string; star?:string; details?:string }> }) {
  const source = await getCharacterReference();
  if (source) {
    const { q = "", page: requested, category="", element="", star="",details:requestedDetails="" } = await searchParams;
    const details=['skills','abilities','awakening','talents'].includes(requestedDetails)?requestedDetails:'';
    const query = q.trim().toLocaleLowerCase();
    const rows = source.records.filter(r => [r.characterId, r.name ?? ""].some(s => s.toLocaleLowerCase().includes(query)) && (!category || r.roleType===category) && (!element || r.elementType===element) && (!star || r.starGrade===Number(star))&&
      (!details||(details==='skills'&&(r.skillCount??0)>0)||(details==='abilities'&&(r.abilityCount??0)>0)||(details==='awakening'&&(r.awakeningCount??0)>0)||(details==='talents'&&r.talentsAvailable))).sort((a,b)=>a.characterId.localeCompare(b.characterId,"en"));
    const pages = Math.max(1,Math.ceil(rows.length/24));
    const page = Number.isSafeInteger(Number(requested)) && Number(requested)>0 ? Math.min(Number(requested),pages) : 1;
    const href = (n:number)=>`/characters?${new URLSearchParams({q,category,element,star,details,page:String(n)})}`;
    const categories=[...new Set(source.records.map(r=>r.roleType))].filter((v):v is string=>v!==null).sort();
    const elements=[...new Set(source.records.map(r=>r.elementType))].filter((v):v is string=>v!==null).sort();
    const stars=[...new Set(source.records.map(r=>r.starGrade))].filter((v):v is number=>v!==null).sort((a,b)=>a-b);
    return <div className="page-shell"><SiteHeader/><main className="page-main">
      <section className="page-intro"><p className="eyebrow">RANGERS</p><h1>角色與技能</h1><p className="page-lede">依名稱、星等、類型與屬性查詢 Rangers。</p></section>
      <p className="catalog-note">技能詳細資料 {source.coverage.skillDetails.toLocaleString('zh-TW')} 角色 · 能力 {source.coverage.abilityDetails.toLocaleString('zh-TW')} 角色 · 覺醒候選 {source.coverage.awakeningDetails.toLocaleString('zh-TW')} 角色 · 才能 {source.coverage.talentDetails.toLocaleString('zh-TW')} 角色</p>
      <p className="catalog-note">已對照 {source.coverage.matchedDetails.toLocaleString('zh-TW')} 個模板；目前詳細資料未收錄 {source.coverage.notInReference} 個模板，不據此判定有無能力。{source.coverage.skillsAbsent!==null&&<> 已確認無技能 {source.coverage.skillsAbsent}、無角色能力 {source.coverage.abilitiesAbsent}、無覺醒候選 {source.coverage.awakeningAbsent}。</>}{source.coverage.talentsAbsent!==null&&<> 本機確認未設定才能 {source.coverage.talentsAbsent}。</>}</p>
      <form action="/characters" className="gear-filters" key={JSON.stringify({q,category,element,star,details})}><label>名稱／角色 ID<input type="search" name="q" defaultValue={q}/></label>
        <button className="button button-primary">搜尋</button><Link className="button" href="/characters">清除</Link>
        <details className="catalog-advanced" open={!!category||!!element||!!star||!!details}><summary>進階篩選</summary><div className="catalog-advanced-fields">
        <label>類型<select name="category" defaultValue={category}><option value="">全部類型</option>{categories.map(v=><option key={v} value={v}>{roleName(v)}</option>)}</select></label>
        <label>屬性<select name="element" defaultValue={element}><option value="">全部屬性</option>{elements.map(v=><option key={v} value={v}>{elementName(v)}</option>)}</select></label>
        <label>星等<select name="star" defaultValue={star} disabled={!stars.length}><option value="">{stars.length ? "全部星等" : "尚未確認星等"}</option>{stars.map(v=><option key={v} value={v}>{v} 星</option>)}</select></label>
        <label>詳細內容<select name="details" defaultValue={details}><option value="">全部角色</option><option value="skills">已有技能效果</option><option value="abilities">已有角色能力</option><option value="awakening">有覺醒候選</option><option value="talents">已有才能資料</option></select></label>
        </div></details></form>
      <p role="status">{rows.length} 筆結果 · 第 {page}／{pages} 頁</p>
      <section className="verified-gear-grid catalog-grid character-catalog-grid" aria-label="角色列表">{rows.slice((page-1)*24,page*24).map(r=><Link className="verified-gear-card" key={r.characterId} href={`/characters/${encodeURIComponent(r.characterId)}`}><CharacterPortrait src={r.imageUrl} name={r.name??r.characterId}/><div><h2>{r.name ?? r.characterId}</h2><p>{r.starGrade === null ? "星等尚未確認" : `${r.starGrade} 星`} · {roleName(r.roleType)} · {elementName(r.elementType)}</p><code>{r.characterId}</code><p>{r.skillCount===null?'技能詳細資料尚未取得':r.skillCount===0?'本次模板未列技能':`${r.skillCount} 個技能 · ${r.abilityCount??'未知'} 個能力`}</p>{r.awakeningCount!==null&&r.awakeningCount>0&&<p>{r.awakeningCount} 個覺醒候選{r.talentsAvailable?' · 已有才能資料':''}</p>}</div></Link>)}</section>
      {!rows.length&&<p className="empty-panel">沒有符合條件的角色。</p>}
      <nav className="gear-pagination" aria-label="角色分頁">{page>1&&<Link className="button" href={href(page-1)}>上一頁</Link>}<span>{page}／{pages}</span>{page<pages&&<Link className="button" href={href(page+1)}>下一頁</Link>}</nav>
      <p className="catalog-note">資料更新：{new Date(source.retrievedAt).toLocaleString("zh-TW",{timeZone:"Asia/Taipei",hour12:false})}。星等為角色圖鑑資料，玩家角色的等級與配置另計。</p>
    </main><SiteFooter/></div>;
  }
  return (
    <ModuleStatusPage
      eyebrow="角色圖鑑"
      title="角色資料尚未開放"
      description="目前無法可靠地列出角色名稱、能力或養成數值。"
      evidence="角色頁目前還沒有通過驗證的資料集。"
      missing="可查詢的角色 ID、名稱、類型、技能、進化數值，以及可核對的角色圖片對應。"
      nextStep="目前可先查看裝備圖鑑；角色基本資料、技能與圖片將在資料確認後提供。"
    />
  );
}
