import Link from "next/link";
import { redirect } from "next/navigation";
import { SiteHeader } from "../../../_components/site-header";
import { SiteFooter } from "../../../_components/site-footer";
import { getGuildAccess } from "../../../../lib/guild-access";
import { activateGuildOwner } from "../actions";
import "../access.css";

export default async function GuildOwnerPage({ searchParams }: { searchParams: Promise<{ invalid?: string }> }) {
  const { status } = await getGuildAccess();
  if (status === "admin") redirect("/guild/review");
  const { invalid } = await searchParams;
  return <div className="page-shell"><SiteHeader/><main className="page-main">
    <section className="page-intro"><h1>啟用公會戰管理員</h1></section>
    <section className="reference-panel guild-access-card">
      {status === "anonymous" || status === "unavailable" ? <>
        <p>{status === "anonymous" ? "請先使用指定的管理員 Email 註冊或登入，再回到此頁。" : "帳號服務暫時無法使用。"}</p>
        <Link className="button" href="/guild/access">前往登入</Link>
      </> : <form action={activateGuildOwner} className="guild-access-form">
        {invalid === "1" && <p className="guild-access-notice" role="alert">無法啟用。請核對帳號與啟用碼，或確認啟用碼是否已過期。</p>}
        <label>一次性啟用碼<input name="code" type="password" autoComplete="off" minLength={64} maxLength={64} required/></label>
        <button className="button button-primary">啟用管理員權限</button>
      </form>}
    </section>
  </main><SiteFooter/></div>;
}
