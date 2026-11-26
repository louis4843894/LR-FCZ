import Image from "next/image";
import Link from "next/link";
import {
  getPublishedVersion,
  searchPublishedLocalizations,
  SupabaseDataError,
  type PublishedVersion,
  type SearchResult,
} from "../../lib/ranger-supabase";
import { getLocalGearIconUrl } from "../../lib/local-research-assets";
import { DataState } from "../_components/data-state";
import { SiteFooter } from "../_components/site-footer";
import { SiteHeader } from "../_components/site-header";

const PAGE_SIZE = 10;
const LANGUAGE = "zh-Hant";

type SearchParams = {
  q?: string | string[];
  page?: string | string[];
};

function firstValue(value: string | string[] | undefined): string {
  return Array.isArray(value) ? (value[0] ?? "") : (value ?? "");
}

function parsePage(value: string): number {
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed > 0 && parsed <= 1_000_000
    ? parsed
    : 1;
}

function buildPageHref(page: number, query: string): string {
  const params = new URLSearchParams({ page: String(page) });
  if (query) params.set("q", query);
  return `/translations?${params.toString()}`;
}

async function Listing({
  result,
  query,
  page,
}: {
  result: SearchResult;
  query: string;
  page: number;
}) {
  const pageCount = Math.max(1, Math.ceil(result.totalCount / PAGE_SIZE));
  const firstItem = result.totalCount === 0 ? 0 : (page - 1) * PAGE_SIZE + 1;
  const lastItem = Math.min(page * PAGE_SIZE, result.totalCount);

  if (result.totalCount === 0) {
    return (
      <section className="empty-panel">
        <span className="empty-panel-icon" aria-hidden="true">
          ◇
        </span>
        <h2>沒有符合的文字記錄</h2>
        <p>請調整關鍵字，或清除搜尋條件後再試。</p>
      </section>
    );
  }

  if (page > pageCount) {
    return (
      <section className="empty-panel">
        <h2>這一頁沒有資料</h2>
        <p>目前共有 {result.totalCount} 筆符合條件的文字記錄。</p>
        <Link className="button button-primary" href={buildPageHref(1, query)}>
          回到第一頁
        </Link>
      </section>
    );
  }

  const items = await Promise.all(
    result.items.map(async (item) => ({
      item,
      iconUrl: await getLocalGearIconUrl(item.dataCode),
    })),
  );

  return (
    <>
      <ul className="localization-list" aria-label="裝備相關文字記錄">
        {items.map(({ item, iconUrl }) => (
          <li key={`${item.dataCode}:${item.language}`}>
            <Link
              className="localization-card"
              href={`/gear/${encodeURIComponent(item.dataCode)}`}
            >
              {iconUrl ? (
                <span className="gear-icon-candidate">
                  <Image
                    src={iconUrl}
                    alt=""
                    width={52}
                    height={52}
                    unoptimized
                  />
                  <small>候選圖示</small>
                </span>
              ) : null}
              <span className="localization-copy">
                <span className="localization-message">
                  {item.displayMessage || "（此記錄沒有可顯示的文字）"}
                </span>
                <span className="localization-code">
                  原始代碼：{item.dataCode}
                </span>
              </span>
              <span className="localization-arrow" aria-hidden="true">
                →
              </span>
            </Link>
          </li>
        ))}
      </ul>

      <nav className="pagination" aria-label="列表分頁">
        <span>
          顯示第 {firstItem}–{lastItem} 筆，共 {result.totalCount} 筆
        </span>
        <span className="pagination-controls">
          {page > 1 ? (
            <Link
              className="button"
              href={buildPageHref(page - 1, query)}
              aria-label="上一頁"
            >
              上一頁
            </Link>
          ) : (
            <span className="button button-disabled" aria-disabled="true">
              上一頁
            </span>
          )}
          <span className="page-number">
            {page} / {pageCount}
          </span>
          {page < pageCount ? (
            <Link
              className="button"
              href={buildPageHref(page + 1, query)}
              aria-label="下一頁"
            >
              下一頁
            </Link>
          ) : (
            <span className="button button-disabled" aria-disabled="true">
              下一頁
            </span>
          )}
        </span>
      </nav>
    </>
  );
}

export default async function HomePage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  const query = firstValue(params.q).trim();
  const page = parsePage(firstValue(params.page));

  let version: PublishedVersion | null = null;
  let result: SearchResult | null = null;
  let errorMessage: string | null = null;

  if (Array.from(query).length > 100) {
    errorMessage = "搜尋關鍵字最多 100 個字元。";
  } else {
    try {
      version = await getPublishedVersion();
      if (version) {
        result = await searchPublishedLocalizations(
          version.snapshotId,
          query,
          page,
          PAGE_SIZE,
          LANGUAGE,
        );
      }
    } catch (error: unknown) {
      errorMessage =
        error instanceof SupabaseDataError
          ? error.message
          : "讀取資料時發生未預期錯誤，請稍後再試。";
    }
  }

  return (
    <div className="page-shell">
      <SiteHeader />
      <main className="page-main">
        <section className="page-intro">
          <p className="eyebrow">目前可查：裝備翻譯</p>
          <h1>裝備名稱與效果文字</h1>
          <p className="page-lede">
            這裡只有遊戲內的翻譯文字，不是完整裝備圖鑑。角色、PvP 與公會資料的範圍及核對狀態，
            請從上方導覽查看各模組的實際狀態。
          </p>
          <p className="local-asset-note">
            本機開發模式會預覽檔名同主幹相符的 APK 圖示候選；尚未核實裝備映射或公開使用權，正式環境不提供。
          </p>
        </section>

        {errorMessage ? (
          <DataState title="目前無法讀取資料" description={errorMessage} />
        ) : !version ? (
          <DataState
            title="目前沒有已發布的資料版本"
            description="資料庫尚未提供已發布版本。完成 Supabase migration、匯入並發布資料後，列表才會顯示真實記錄。"
          />
        ) : result ? (
          <>
            <section className="dataset-banner" aria-label="資料版本資訊">
              <span className="dataset-dot" aria-hidden="true" />
              <span>
                <strong>資料版本 {version.sourceVersion}</strong>
              </span>
              <span className="dataset-count">
                共 {version.recordCount} 筆翻譯文字
              </span>
            </section>

            <form className="search-panel" action="/" method="get">
              <label className="search-input-wrap">
                <span aria-hidden="true">⌕</span>
                <span className="sr-only">搜尋翻譯文字或原始代碼</span>
                <input
                  type="search"
                  name="q"
                  defaultValue={query}
                  placeholder="搜尋翻譯文字或原始代碼"
                  maxLength={100}
                />
              </label>
              <button className="button button-primary" type="submit">
                搜尋
              </button>
              <span className="search-result-count">
                符合 <strong>{result.totalCount}</strong> 筆
              </span>
            </form>

            <section className="list-panel" aria-label="搜尋結果">
              <div className="list-panel-heading">
                <div>
                  <h2>遊戲內翻譯文字</h2>
                  <p>依原始代碼排序；資料由 Supabase 伺服器端搜尋及分頁。</p>
                </div>
              </div>
              <Listing result={result} query={query} page={page} />
            </section>
          </>
        ) : null}
      </main>
      <SiteFooter />
    </div>
  );
}
