import Image from "next/image";
import Link from "next/link";
import { getVerifiedEquipmentList } from "../../lib/verified-equipment";
import { filterEquipment, equipmentName } from "../../lib/equipment-filters";
import { getLocalGearIconUrl } from "../../lib/local-research-assets";
import { SiteHeader } from "../_components/site-header";
import { SiteFooter } from "../_components/site-footer";
import { referenceFilterOptions } from "../../lib/reference-filters";
type Search = Record<string, string | string[] | undefined>;
const first = (x: string | string[] | undefined) => Array.isArray(x) ? x[0] ?? "" : x ?? "";
export default async function GearPage({ searchParams }: { searchParams: Promise<Search> }) {
  const search = await searchParams;
  const rows = await getVerifiedEquipmentList();
  const q = first(search.q), star = Number(first(search.star)) || undefined;
  const type = ["ARMOR", "WEAPON", "ACC"].includes(first(search.type)) ? first(search.type) : "";
  const sort = ["id", "star-desc", "name"].includes(first(search.sort)) ? first(search.sort) : "id";
  const many = (value: string | string[] | undefined) => value === undefined ? [] : Array.isArray(value) ? value : [value];
  const effectIds = many(search.effect), conditionIds = many(search.condition), mode = first(search.mode) === "OR" ? "OR" : "AND";
  const effectOptions = new Map<string,string>(), conditionOptions = new Map<string,string>();
  for (const row of rows) {
    if (!row.reference) continue;
    for (const e of referenceFilterOptions(row.reference)) {
      effectOptions.set(e.effectId, e.name);
      if (e.conditionId && e.conditionName) conditionOptions.set(e.conditionId, e.conditionName);
    }
  }
  const selected = filterEquipment(rows, { q, star, type, sort, effectIds, conditionIds, mode });
  const size = 24, pages = Math.max(1, Math.ceil(selected.length / size));
  const requested = Number(first(search.page));
  const page = Number.isSafeInteger(requested) && requested > 0 ? Math.min(requested, pages) : 1;
  const items = await Promise.all(selected.slice((page - 1) * size, page * size).map(async row => ({ ...row, icon: await getLocalGearIconUrl(row.dataCode) })));
  const href = (next: number) => { const p = new URLSearchParams({ q, star: star ? String(star) : "", type, sort, page: String(next) }); effectIds.forEach(id=>p.append("effect",id)); conditionIds.forEach(id=>p.append("condition",id)); p.set("mode",mode); return `/gear?${p}`; };
  return <div className="page-shell"><SiteHeader /><main className="page-main">
    <section className="page-intro"><p className="eyebrow">EQUIPMENT</p><h1>裝備圖鑑</h1><p className="page-lede">查詢武器、防具與飾品的星等、效果及強化範圍。</p></section>
    <form action="/gear" className="gear-filters" key={JSON.stringify({q,star,type,sort,effectIds,conditionIds,mode})}>
      <label>名稱／ID<input type="search" name="q" defaultValue={q} placeholder="裝備名稱或 itemCode" /></label>
      <button className="button button-primary" type="submit">套用篩選</button><Link className="button" href="/gear">清除篩選</Link>
      <details className="catalog-advanced" open={!!star||!!type||sort!=='id'||effectIds.length>0||conditionIds.length>0}><summary>進階篩選</summary><div className="catalog-advanced-fields">
      <label>星等<select name="star" defaultValue={star ?? ""}><option value="">全部星等</option>{[...new Set(rows.map(r=>r.starCount))].sort((a,b)=>a-b).map(n=><option key={n} value={n}>{n} 星</option>)}</select></label>
      <label>類型<select name="type" defaultValue={type}><option value="">全部類型</option><option value="WEAPON">武器</option><option value="ARMOR">防具</option><option value="ACC">飾品</option></select></label>
      <label>排序<select name="sort" defaultValue={sort}><option value="id">ID</option><option value="star-desc">星等由高至低</option><option value="name">名稱</option></select></label>
      <fieldset disabled={!effectOptions.size} className="gear-effects-filter"><legend>效果與觸發條件</legend>
        {effectOptions.size ? <><label>效果<select name="effect" multiple size={4} defaultValue={effectIds}>{[...effectOptions].sort((a,b)=>a[1].localeCompare(b[1],"zh-Hant")).map(([id,name])=><option key={id} value={id}>{name}</option>)}</select></label>
        <label>觸發條件<select name="condition" multiple size={4} defaultValue={conditionIds}>{[...conditionOptions].map(([id,name])=><option key={id} value={id}>{name}</option>)}</select></label>
        <div><p>可複選；以所選效果及條件比對裝備。</p><label><input type="radio" name="mode" value="AND" defaultChecked={mode==="AND"}/> AND（全部符合）</label><label><input type="radio" name="mode" value="OR" defaultChecked={mode==="OR"}/> OR（任一符合）</label></div></>
        : <span>效果尚未解析，暫無可用篩選。</span>}
      </fieldset>
      </div></details>
    </form><p role="status">{selected.length} 筆結果 · 第 {page}／{pages} 頁</p>
    <section className="verified-gear-grid catalog-grid equipment-catalog-grid" aria-label="裝備列表">{items.map(row=><Link className="verified-gear-card" key={row.itemCode} href={`/gear/${row.dataCode}`}>
      {row.icon ? <span className="gear-icon-candidate"><Image src={row.icon} width={72} height={72} alt="" unoptimized /><small>圖示對應待確認</small></span> : <span className="gear-image-fallback" aria-label="圖片尚未取得">◇</span>}
      <div><h2>{equipmentName(row)}</h2><p>{row.starCount} 星 · {({ARMOR:"防具",WEAPON:"武器",ACC:"飾品"})[row.equipType]}</p><code>{row.itemCode}</code><p>{row.reference ? `基本效果 ${row.reference.normalOptions.length} 項` : "效果：尚未解析"}</p></div>
    </Link>)}</section>
    {!items.length&&<p className="empty-panel">沒有符合條件的已驗證裝備，請調整篩選。</p>}
    <nav className="gear-pagination" aria-label="裝備分頁">{page>1&&<Link className="button" href={href(page-1)}>上一頁</Link>}<span>{page}／{pages}</span>{page<pages&&<Link className="button" href={href(page+1)}>下一頁</Link>}</nav>
  </main><SiteFooter /></div>;
}
