import Link from "next/link";
import { SiteHeader } from "../../_components/site-header";
import { SiteFooter } from "../../_components/site-footer";
import { requireGuildAdmin, reviewStatuses, type GuildApplication, type ReviewStatus } from "../../../lib/guild-access";
import { logoutGuildAccount } from "../access/actions";
import { reviewGuildApplication } from "./actions";
import "../access/access.css";

const pagesize = 25;
const statusLabels = { pending: "待審核", approved: "已核准", rejected: "未通過", revoked: "已撤銷" };
const messages: Record<string, string> = {
  updated: "已更新權限。",
  invalid: "無法識別這項申請。",
  stale: "申請狀態已變更。請確認清單後再操作。",
  unavailable: "暫時無法更新權限，請稍後再試。",
};
const time = (value: string | null) => value ? new Date(value).toLocaleString("zh-TW", {
  timeZone: "Asia/Taipei", hour12: false,
}) : "—";

export default async function GuildReviewPage({ searchParams }: {
  searchParams: Promise<{ status?: string; page?: string; notice?: string }>;
}) {
  const auth = await requireGuildAdmin();
  const params = await searchParams;
  const requestedStatus = params.status as ReviewStatus;
  const status = reviewStatuses.includes(requestedStatus) ? requestedStatus : "pending";
  const requestedPage = Number(params.page);
  const page = Number.isSafeInteger(requestedPage) && requestedPage > 0 && requestedPage <= 10000 ? requestedPage : 1;
  const { data, error } = await auth.rpc("guild_access_review_queue", { p_status: status, p_offset: (page - 1) * pagesize });
  const rows = (data ?? []) as GuildApplication[];
  const message = typeof params.notice === "string" && Object.hasOwn(messages, params.notice) ? messages[params.notice] : null;

  return <div className="page-shell"><SiteHeader/><main className="page-main">
    <Link className="back-link" href="/guild">← 公會排名</Link>
    <section className="page-intro"><h1>公會戰權限審核</h1><p className="page-lede">管理使用者的公會戰存取權限。</p></section>
    <section className="reference-panel">
      <nav className="guild-access-actions" aria-label="篩選申請狀態">
        {reviewStatuses.map(item => <Link key={item} className={item === status ? "button button-primary" : "button"}
          aria-current={item === status ? "page" : undefined} href={`/guild/review?status=${item}`}>{statusLabels[item]}</Link>)}
        <form action={logoutGuildAccount}><button className="button">登出</button></form>
      </nav>
      {message && <p className="guild-access-notice" role="status">{message}</p>}
      {error ? <p role="alert">暫時無法讀取申請清單，請稍後再試。</p> : rows.length ? <>
        <div className="reference-table-wrap"><table className="ranking-table" aria-label="公會戰權限申請">
          <thead><tr><th>使用者名稱</th><th>Email</th><th>申請時間</th><th>審核時間</th><th>操作</th></tr></thead>
          <tbody>{rows.slice(0, pagesize).map(row => <tr key={row.user_id}>
            <td>{row.username}</td><td>{row.email}</td><td>{time(row.requested_at)}</td><td>{time(row.reviewed_at)}</td>
            <td><form className="guild-access-actions" action={reviewGuildApplication}>
              <input type="hidden" name="user" value={row.user_id}/>
              <input type="hidden" name="expected" value={row.status}/>
              {row.status === "approved" ?
                <button className="button" name="decision" value="revoked">撤銷權限</button> :
                <button className="button button-primary" name="decision" value="approved">{row.status === "pending" ? "核准" : "恢復權限"}</button>}
              {row.status === "pending" && <button className="button" name="decision" value="rejected">拒絕</button>}
            </form></td>
          </tr>)}</tbody>
        </table></div>
        <nav className="guild-access-actions" aria-label="申請清單分頁">
          {page > 1 && <Link className="button" href={`?status=${status}&page=${page - 1}`}>上一頁</Link>}
          {rows.length > pagesize && <Link className="button" href={`?status=${status}&page=${page + 1}`}>下一頁</Link>}
        </nav>
      </> : <p>沒有{statusLabels[status]}的申請。{page > 1 && <> <Link href={`?status=${status}`}>回到第一頁</Link></>}</p>}
    </section>
  </main><SiteFooter/></div>;
}
