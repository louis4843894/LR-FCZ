import Link from "next/link";
import { catalogHref, catalogPageNumbers, catalogParams, removeCatalogFilter, type CatalogQuery } from "../../lib/catalog-navigation";

export type CatalogFilterChip = { key: string; value?: string; label: string };

export function ActiveCatalogFilters({ path, query, filters }: { path: string; query: CatalogQuery; filters: CatalogFilterChip[] }) {
  if (!filters.length) return null;
  return <div className="catalog-active-filters" aria-label="已套用篩選">
    <span>已套用</span>
    <ul>{filters.map(filter => <li key={`${filter.key}:${filter.value ?? ""}`}>
      <Link className="catalog-filter-chip" href={catalogHref(path, removeCatalogFilter(query, filter.key, filter.value))} aria-label={`移除篩選：${filter.label}`}>
        {filter.label}<span aria-hidden="true">×</span>
      </Link>
    </li>)}</ul>
    <Link className="catalog-clear" href={path}>清除全部</Link>
  </div>;
}

export function CatalogResultCount({ count, total, page, size = 24 }: { count: number; total: number; page: number; size?: number }) {
  return <div className="catalog-result-bar" id="catalog-results">
    <p role="status"><strong>{count.toLocaleString("zh-TW")}</strong> 筆結果<span> / 共 {total.toLocaleString("zh-TW")} 筆</span></p>
    <span>{count ? `顯示 ${(page - 1) * size + 1}–${Math.min(page * size, count)} 筆` : "試試減少篩選條件"}</span>
  </div>;
}

export function CatalogPagination({ path, query, page, pages, label }: { path: string; query: CatalogQuery; page: number; pages: number; label: string }) {
  if (pages <= 1) return null;
  const href = (n: number) => `${catalogHref(path, query, { page: String(n) })}#catalog-results`;
  return <nav className="catalog-pagination" aria-label={label}>
    <div className="catalog-page-links">
      {page > 1 ? <Link className="button catalog-page-prev" href={href(page - 1)}>上一頁</Link> : <span className="button catalog-page-prev" aria-disabled="true">上一頁</span>}
      {catalogPageNumbers(page, pages).map((n, index) => n === "gap" ? <span className="catalog-page-gap" key={`gap-${index}`} aria-hidden="true">…</span> :
        <Link className="button catalog-page-number" key={n} href={href(n)} aria-label={`第 ${n} 頁`} aria-current={n === page ? "page" : undefined}>{n}</Link>)}
      {page < pages ? <Link className="button catalog-page-next" href={href(page + 1)}>下一頁</Link> : <span className="button catalog-page-next" aria-disabled="true">下一頁</span>}
    </div>
    <form action={`${path}#catalog-results`} className="catalog-page-jump">
      {[...catalogParams({ ...query, page: undefined })].map(([name, value], i) => <input key={`${name}-${i}`} type="hidden" name={name} value={value} />)}
      <label>跳至第 <input type="number" name="page" aria-label="頁碼" min={1} max={pages} defaultValue={page} key={page} required /> / {pages} 頁</label>
      <button className="button" type="submit">前往</button>
    </form>
  </nav>;
}
