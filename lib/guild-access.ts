import "server-only";
import { cache } from "react";
import { redirect } from "next/navigation";
import { guildAuthClient } from "./guild-auth-client";
import { guildAccessUrl } from "./guild-access-path";

export const reviewStatuses = ["pending", "approved", "rejected", "revoked"] as const;
export type ReviewStatus = typeof reviewStatuses[number];
export type AccessStatus = ReviewStatus | "admin" | "unverified" | "unregistered" | "anonymous" | "unavailable";
export type GuildSession = { status: AccessStatus; username: string | null };

export type GuildApplication = {
  user_id: string;
  username: string;
  email: string;
  status: ReviewStatus;
  requested_at: string;
  reviewed_at: string | null;
};

export const getGuildAccess = cache(async (): Promise<GuildSession & {
  client: Awaited<ReturnType<typeof guildAuthClient>>;
}> => {
  const client = await guildAuthClient();
  if (!client) return { client, status: "unavailable", username: null };

  const { data: verified, error: identityError } = await client.auth.getClaims();
  if (identityError || !verified?.claims.sub) {
    const status: AccessStatus = identityError && (identityError.status ?? 0) >= 500 ? "unavailable" : "anonymous";
    return { client, status, username: null };
  }

  const name = verified.claims.user_metadata?.guild_username;
  const username = typeof name === "string" && !/\p{Cc}/u.test(name)
    ? [...name.trim()].slice(0, 40).join("") || null
    : null;
  const { data, error } = await client.rpc("guild_access_current");
  if (!error && (reviewStatuses.includes(data) || ["admin", "unverified", "unregistered"].includes(data))) {
    return { client, status: data as AccessStatus, username };
  }
  return { client, status: "unavailable", username };
});

export async function requireGuildAccess(path: string) {
  const { client, status } = await getGuildAccess();
  if (!client || (status !== "approved" && status !== "admin")) redirect(guildAccessUrl(path));
  return { client, status };
}

export async function requireGuildAdmin(path = "/guild/review") {
  const { client, status } = await getGuildAccess();
  if (status !== "admin" || !client) redirect(guildAccessUrl(path, status === "approved" ? "admin-only" : undefined));
  return client;
}
