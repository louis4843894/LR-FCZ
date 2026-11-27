"use server";

import { redirect } from "next/navigation";
import { guildAuthClient } from "../../../lib/guild-auth-client";
import { getGuildAccess } from "../../../lib/guild-access";
import { guildAccessUrl, guildReturnPath } from "../../../lib/guild-access-path";

export async function registerGuildAccount(form: FormData) {
  const next = guildReturnPath(form.get("next"));
  const email = String(form.get("email") ?? "").trim().toLowerCase();
  const username = String(form.get("username") ?? "").trim();
  const password = String(form.get("password") ?? "");
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) || email.length > 254 ||
    !username || [...username].length > 40 || /\p{Cc}/u.test(username) ||
    password.length < 8 || Buffer.byteLength(password, "utf8") > 72) {
    redirect(guildAccessUrl(next, "invalid-registration", true));
  }
  const auth = await guildAuthClient();
  if (!auth) redirect(guildAccessUrl(next, "unavailable", true));
  const { data, error } = await auth.auth.signUp({
    email, password,
    options: { data: { guild_username: username } },
  });
  if (error && error.code !== "user_already_exists") {
    redirect(guildAccessUrl(next, "registration-failed", true));
  }
  if (data.session) redirect(guildAccessUrl(next));
  redirect(guildAccessUrl(next, "try-login"));
}

export async function loginGuildAccount(form: FormData) {
  const next = guildReturnPath(form.get("next"));
  const email = String(form.get("email") ?? "").trim().toLowerCase();
  const password = String(form.get("password") ?? "");
  if (!email || email.length > 254 || !password || password.length > 1024) {
    redirect(guildAccessUrl(next, "invalid-login"));
  }
  const auth = await guildAuthClient();
  if (!auth) redirect(guildAccessUrl(next, "unavailable"));
  const { error } = await auth.auth.signInWithPassword({ email, password });
  if (error) redirect(guildAccessUrl(next, error.code === "email_not_confirmed" ? "email-unverified" : "invalid-login"));
  redirect(guildAccessUrl(next));
}

export async function logoutGuildAccount() {
  const auth = await guildAuthClient();
  if (auth) await auth.auth.signOut({ scope: "local" });
  redirect("/guild/access");
}

export async function activateGuildOwner(form: FormData) {
  const { client, status } = await getGuildAccess();
  if (status === "admin") redirect("/guild/review");
  if (!client || status === "anonymous" || status === "unavailable") redirect("/guild/access");
  const code = String(form.get("code") ?? "").trim();
  if (/^[a-f0-9]{64}$/.test(code)) {
    const { data } = await client.rpc("guild_access_activate", { p_code: code });
    if (data === true) redirect("/guild/review");
  }
  redirect("/guild/access/owner?invalid=1");
}
