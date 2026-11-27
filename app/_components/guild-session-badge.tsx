"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { AccessStatus, GuildSession } from "../../lib/guild-access";
import "./guild-session-badge.css";

const states: Record<AccessStatus, { label: string; href: string; action: string }> = {
  anonymous: { label: "未登入", href: "/guild/access", action: "前往登入" },
  pending: { label: "待審核", href: "/guild/access", action: "查看申請狀態" },
  approved: { label: "已核准", href: "/guild", action: "前往公會戰" },
  admin: { label: "管理員", href: "/guild/review", action: "前往審核後台" },
  rejected: { label: "未通過", href: "/guild/access", action: "查看申請狀態" },
  revoked: { label: "已撤銷", href: "/guild/access", action: "查看申請狀態" },
  unverified: { label: "待驗證", href: "/guild/access", action: "查看帳號狀態" },
  unregistered: { label: "尚未申請", href: "/guild/access", action: "查看帳號狀態" },
  unavailable: { label: "狀態暫不可用", href: "/guild/access", action: "前往公會戰權限頁" },
};
const unavailable: GuildSession = { status: "unavailable", username: null };

export function GuildSessionBadge({ pathname, initialSession }: { pathname: string; initialSession?: GuildSession }) {
  const [refreshResult, setRefreshResult] = useState<{
    pathname: string;
    initialSession?: GuildSession;
    session: GuildSession;
  }>();
  const session = refreshResult?.pathname === pathname && refreshResult.initialSession === initialSession
    ? refreshResult.session : initialSession;

  useEffect(() => {
    let request: AbortController | undefined;
    const refresh = async () => {
      request?.abort();
      const controller = new AbortController();
      request = controller;
      let result = unavailable;
      try {
        const response = await fetch("/api/guild-session", { cache: "no-store", signal: controller.signal });
        if (response.ok) {
          const data: GuildSession = await response.json();
          if (Object.hasOwn(states, data.status)) result = data;
        }
      } catch {
        // Keep canceled requests from replacing the current route's status.
      }
      if (!controller.signal.aborted) setRefreshResult({ pathname, initialSession, session: result });
    };
    const restore = (event: PageTransitionEvent) => {
      if (event.persisted) void refresh();
    };
    if (!initialSession) void refresh();
    window.addEventListener("focus", refresh);
    window.addEventListener("pageshow", restore);
    return () => {
      request?.abort();
      window.removeEventListener("focus", refresh);
      window.removeEventListener("pageshow", restore);
    };
  }, [pathname, initialSession]);

  if (!session) return <span className="guild-session-badge" role="status">讀取帳號狀態</span>;
  const { label, href, action } = states[session.status];
  const description = [session.username, label, action].filter(Boolean).join("，");
  return <Link href={href} prefetch={false} className="guild-session-badge" data-status={session.status}
    aria-label={description} title={description}>
    <span className="guild-session-dot" aria-hidden="true"/>
    {session.username && <bdi className="guild-session-name">{session.username}</bdi>}
    <span>{label}</span>
  </Link>;
}
