import Link from "next/link";
import { redirect } from "next/navigation";
import { SiteHeader } from "../../_components/site-header";
import { SiteFooter } from "../../_components/site-footer";
import { getGuildAccess } from "../../../lib/guild-access";
import { guildAccessUrl, guildReturnPath } from "../../../lib/guild-access-path";
import { loginGuildAccount, logoutGuildAccount, registerGuildAccount } from "./actions";
import "./access.css";

const notices: Record<string, string> = {
  "try-login": "請使用 Email 和密碼登入，查看申請狀態。",
  "email-unverified": "請先開啟信箱中的驗證連結，再重新登入。",
  "invalid-login": "登入失敗。請核對 Email 和密碼後再試。",
  "invalid-registration": "請填寫有效的 Email、1～40 字的使用者名稱，以及符合長度的密碼。",
  "registration-failed": "暫時無法註冊。請稍後再試。",
  "unavailable": "帳號服務暫時無法使用，請稍後再試。",
  "admin-only": "審核後台僅供管理員使用。",
};

const statusText = {
  pending: ["等待審核", "申請已送出。管理員核准後即可查看公會戰資料。"],
  rejected: ["申請未通過", "如需重新審核，請聯絡管理員。"],
  revoked: ["權限已撤銷", "如需恢復存取，請聯絡管理員。"],
  unverified: ["等待 Email 驗證", "請先完成 Email 驗證，再登入查看審核狀態。"],
  unregistered: ["尚無公會戰申請", "請聯絡管理員確認此帳號的註冊資料。"],
  unavailable: ["帳號服務暫時無法使用", "請稍後再試。"],
} as const;

export default async function GuildAccessPage({ searchParams }: {
  searchParams: Promise<{ next?: string; mode?: string; notice?: string }>;
}) {
  const { next, mode, notice } = await searchParams;
  const returnPath = guildReturnPath(next);
  const { status, username } = await getGuildAccess();
  const approvedButNotAdmin = status === "approved" && returnPath.startsWith("/guild/review");
  if (status === "admin" || (status === "approved" && !approvedButNotAdmin)) redirect(returnPath);
  const registering = mode === "register";
  const message = typeof notice === "string" && Object.hasOwn(notices, notice) ? notices[notice] : null;
  const state = Object.hasOwn(statusText, status) ? statusText[status as keyof typeof statusText] : null;

  return <div className="page-shell"><SiteHeader guildSession={{ status, username }}/><main className="page-main">
    <section className="page-intro"><h1>公會戰權限</h1><p className="page-lede">註冊並通過管理員審核後，即可查看公會排名、十塔防禦與成員名單。</p></section>
    <section className="reference-panel guild-access-card">
      {message && <p className="guild-access-notice" role="status">{message}</p>}
      {status === "anonymous" ? <>
        <nav className="guild-access-actions" aria-label="帳號操作">
          <Link className={registering ? "button" : "button button-primary"} aria-current={!registering ? "page" : undefined} href={guildAccessUrl(returnPath)}>登入</Link>
          <Link className={registering ? "button button-primary" : "button"} aria-current={registering ? "page" : undefined} href={guildAccessUrl(returnPath, undefined, true)}>註冊</Link>
        </nav>
        <form className="guild-access-form" action={registering ? registerGuildAccount : loginGuildAccount}>
          <input type="hidden" name="next" value={returnPath}/>
          {registering && <label>使用者名稱<input name="username" autoComplete="nickname" maxLength={40} required/></label>}
          <label>Email<input type="email" name="email" autoComplete="email" maxLength={254} required/></label>
          <label>密碼<input type="password" name="password" autoComplete={registering ? "new-password" : "current-password"} minLength={registering ? 8 : undefined} maxLength={registering ? 72 : 1024} required/></label>
          {registering && <p className="catalog-note">密碼至少 8 個字元。註冊後會送交管理員審核。</p>}
          <button className="button button-primary">{registering ? "註冊並申請權限" : "登入公會戰"}</button>
        </form>
      </> : <>
        {state && <><h2>{state[0]}</h2><p>{state[1]}</p></>}
        <div className="guild-access-actions">
          {approvedButNotAdmin && <Link className="button button-primary" href="/guild">前往公會戰</Link>}
          {status === "pending" && <form action="/guild/access"><input type="hidden" name="next" value={returnPath}/><button className="button">重新查看狀態</button></form>}
          {status !== "unavailable" && <form action={logoutGuildAccount}><button className="button">登出</button></form>}
        </div>
      </>}
    </section>
  </main><SiteFooter/></div>;
}
