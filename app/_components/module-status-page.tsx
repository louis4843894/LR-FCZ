import Link from "next/link";
import { SiteFooter } from "./site-footer";
import { SiteHeader } from "./site-header";

type ModuleStatusPageProps = {
  eyebrow: string;
  title: string;
  description: string;
  evidence: string;
  missing: string;
  nextStep: string;
};

export function ModuleStatusPage({
  eyebrow,
  title,
  description,
  evidence,
  missing,
  nextStep,
}: ModuleStatusPageProps) {
  return (
    <div className="page-shell">
      <SiteHeader />
      <main className="page-main">
        <section className="page-intro">
          <p className="eyebrow">{eyebrow}</p>
          <h1>{title}</h1>
          <p className="page-lede">{description}</p>
        </section>

        <section className="module-status-card" aria-label="模組資料狀態">
          <p className="module-status-label">目前沒有可發布的真實資料</p>
          <div className="module-status-grid">
            <section>
              <h2>已確認</h2>
              <p>{evidence}</p>
            </section>
            <section>
              <h2>缺少資料</h2>
              <p>{missing}</p>
            </section>
          </div>
          <section className="module-status-next">
            <h2>資料說明</h2>
            <p>{nextStep}</p>
          </section>
          <p className="module-status-note">
            不以測試資料或推測內容填補；取得並驗證真實來源後才會開放查詢。
          </p>
        </section>

        <Link className="back-link" href="/">
          ← 前往裝備圖鑑
        </Link>
      </main>
      <SiteFooter />
    </div>
  );
}
