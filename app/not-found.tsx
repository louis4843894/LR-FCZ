import Link from "next/link";
import { SiteFooter } from "./_components/site-footer";
import { SiteHeader } from "./_components/site-header";

export default function NotFound() {
  return (
    <div className="page-shell">
      <SiteHeader />
      <main className="page-main">
        <section className="data-state">
          <span className="data-state-mark" aria-hidden="true">
            ?
          </span>
          <h1>找不到這筆文字記錄</h1>
          <p>此代碼不存在於目前已發布的資料版本中。</p>
          <Link className="text-link" href="/">
            回到列表
          </Link>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}
