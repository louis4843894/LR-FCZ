import { ModuleStatusPage } from "../_components/module-status-page";
import Link from "next/link";
import {CharacterPortrait} from "../_components/character-portrait";
import { getCharacterReference, roleName, elementName } from "../../lib/character-reference";
import { SiteHeader } from "../_components/site-header";
import { SiteFooter } from "../_components/site-footer";
import { ActiveCatalogFilters, CatalogPagination, CatalogResultCount, type CatalogFilterChip } from "../_components/catalog-navigation";
import type { CatalogQuery } from "../../lib/catalog-navigation";

export default async function CharactersPage({ searchParams }: { searchParams: Promise<CatalogQuery> }) {
  const source = await getCharacterReference();
  if (source) {
    const search = await searchParams;
    const first = (key: string) => { const value = search[key]; return (Array.isArray(value) ? value[0] : value) ?? ""; };
    const q = first("q"), requested = first("page"), category = first("category"), element = first("element"), star = first("star"), requestedDetails = first("details");
    const details=['skills','abilities','awakening','talents'].includes(requestedDetails)?requestedDetails:'';
    const sort = ['id','star-desc','name'].includes(first('sort')) ? first('sort') : 'id';
    const query = q.trim().toLocaleLowerCase();
    const rows = source.records.filter(r => [r.characterId, r.name ?? ""].some(s => s.toLocaleLowerCase().includes(query)) && (!category || r.roleType===category) && (!element || r.elementType===element) && (!star || r.starGrade===Number(star))&&
      (!details||(details==='skills'&&(r.skillCount??0)>0)||(details==='abilities'&&(r.abilityCount??0)>0)||(details==='awakening'&&(r.awakeningCount??0)>0)||(details==='talents'&&r.talentsAvailable))).sort((a,b)=>
        (sort==='star-desc' ? (b.starGrade??-1)-(a.starGrade??-1) : sort==='name' ? (a.name??a.characterId).localeCompare(b.name??b.characterId,'zh-Hant') : 0) || a.characterId.localeCompare(b.characterId,"en"));
    const pages = Math.max(1,Math.ceil(rows.length/24));
    const page = Number.isSafeInteger(Number(requested)) && Number(requested)>0 ? Math.min(Number(requested),pages) : 1;
    const navigation = {q,category,element,star,details,sort};
    const contentLabels:Record<string,string>={skills:'已有技能效果',abilities:'已有角色能力',awakening:'有覺醒候選',talents:'已有才能資料'};
    const filters:CatalogFilterChip[] = [
      ...(q?[{key:'q',label:`搜尋：${q}`}]:[]),
      ...(category?[{key:'category',label:roleName(category)}]:[]),
      ...(element?[{key:'element',label:`屬性：${elementName(element)}`}]:[]),
      ...(star?[{key:'star',label:`${star} 星`}]:[]),
      ...(details?[{key:'details',label:contentLabels[details]}]:[]),
    ];
    const categories=[...new Set(source.records.map(r=>r.roleType))].filter((v):v is string=>v!==null).sort();
    const elements=[...new Set(source.records.map(r=>r.elementType))].filter((v):v is string=>v!==null).sort();
    const stars=[...new Set(source.records.map(r=>r.starGrade))].filter((v):v is number=>v!==null).sort((a,b)=>a-b);
    return <div className="page-shell"><SiteHeader/><main className="page-main">
      <section className="page-intro"><p className="eyebrow">RANGERS</p><h1>角色與技能</h1><p className="page-lede">依名稱、星等、類型與屬性查詢 Rangers。</p></section>
      <details className="catalog-coverage"><summary>資料涵蓋範圍 <span>{source.records.length.toLocaleString('zh-TW')} 位角色 · {source.coverage.skillDetails.toLocaleString('zh-TW')} 位有技能詳情</span></summary>
      <p className="catalog-note">技能詳細資料 {source.coverage.skillDetails.toLocaleString('zh-TW')} 角色 · 能力 {source.coverage.abilityDetails.toLocaleString('zh-TW')} 角色 · 覺醒候選 {source.coverage.awakeningDetails.toLocaleString('zh-TW')} 角色 · 才能 {source.coverage.talentDetails.toLocaleString('zh-TW')} 角色</p>
      <p className="catalog-note">已對照 {source.coverage.matchedDetails.toLocaleString('zh-TW')} 個模板；目前詳細資料未收錄 {source.coverage.notInReference} 個模板，不據此判定有無能力。{source.coverage.skillsAbsent!==null&&<> 已確認無技能 {source.coverage.skillsAbsent}、無角色能力 {source.coverage.abilitiesAbsent}、無覺醒候選 {source.coverage.awakeningAbsent}。</>}{source.coverage.talentsAbsent!==null&&<> 本機確認未設定才能 {source.coverage.talentsAbsent}。</>}</p>
      </details>
      <form action="/characters" className="gear-filters catalog-search-form" role="search" aria-label="搜尋角色" key={JSON.stringify(navigation)}><label>名稱／角色 ID<input type="search" name="q" defaultValue={q} placeholder="輸入角色名稱或角色 ID"/></label>
        <label className="catalog-sort">排序<select name="sort" defaultValue={sort}><option value="id">角色 ID</option><option value="star-desc">星等由高至低</option><option value="name">中文名稱</option></select></label>
        <button className="button button-primary">搜尋</button><Link className="button" href="/characters">清除篩選</Link>
        <details className="catalog-advanced" open={!!category||!!element||!!star||!!details}><summary>進階篩選</summary><div className="catalog-advanced-fields">
        <label>類型<select name="category" defaultValue={category}><option value="">全部類型</option>{categories.map(v=><option key={v} value={v}>{roleName(v)}</option>)}</select></label>
        <label>屬性<select name="element" defaultValue={element}><option value="">全部屬性</option>{elements.map(v=><option key={v} value={v}>{elementName(v)}</option>)}</select></label>
        <label>星等<select name="star" defaultValue={star} disabled={!stars.length}><option value="">{stars.length ? "全部星等" : "尚未確認星等"}</option>{stars.map(v=><option key={v} value={v}>{v} 星</option>)}</select></label>
        <label>詳細內容<select name="details" defaultValue={details}><option value="">全部角色</option><option value="skills">已有技能效果</option><option value="abilities">已有角色能力</option><option value="awakening">有覺醒候選</option><option value="talents">已有才能資料</option></select></label>
        </div></details></form>
      <ActiveCatalogFilters path="/characters" query={navigation} filters={filters}/>
      <CatalogResultCount count={rows.length} total={source.records.length} page={page}/>
      <section className="verified-gear-grid catalog-grid character-catalog-grid" aria-label="角色列表">{rows.slice((page-1)*24,page*24).map(r=><Link className="verified-gear-card" key={r.characterId} href={`/characters/${encodeURIComponent(r.characterId)}`}><CharacterPortrait src={r.imageUrl} name={r.name??r.characterId}/><div><h2>{r.name ?? r.characterId}</h2><p>{r.starGrade === null ? "星等尚未確認" : `${r.starGrade} 星`} · {roleName(r.roleType)} · {elementName(r.elementType)}</p><code>{r.characterId}</code><p>{r.skillCount===null?'技能詳細資料尚未取得':r.skillCount===0?'本次模板未列技能':`${r.skillCount} 個技能 · ${r.abilityCount??'未知'} 個能力`}</p>{r.awakeningCount!==null&&r.awakeningCount>0&&<p>{r.awakeningCount} 個覺醒候選{r.talentsAvailable?' · 已有才能資料':''}</p>}</div></Link>)}</section>
      {!rows.length&&<div className="catalog-empty"><h2>沒有符合條件的角色</h2><p>試試其他名稱，或移除部分星等、屬性與內容篩選。</p><Link className="button" href="/characters">查看全部角色</Link></div>}
      <CatalogPagination path="/characters" query={navigation} page={page} pages={pages} label="角色分頁"/>
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
