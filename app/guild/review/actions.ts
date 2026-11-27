"use server";

import { redirect } from "next/navigation";
import { requireGuildAdmin, reviewStatuses, type ReviewStatus } from "../../../lib/guild-access";

export async function reviewGuildApplication(form: FormData) {
  const auth = await requireGuildAdmin();
  const user = form.get("user");
  const expected = form.get("expected") as ReviewStatus;
  const decision = form.get("decision") as ReviewStatus;
  if (typeof user !== "string" || !/^[a-f0-9-]{36}$/.test(user) ||
    !reviewStatuses.includes(expected) || !reviewStatuses.includes(decision)) {
    redirect("/guild/review?notice=invalid");
  }
  const { data, error } = await auth.rpc("guild_access_review", {
    p_user: user, p_expected: expected, p_decision: decision,
  });
  const notice = error ? "unavailable" : data === true ? "updated" : "stale";
  redirect(`/guild/review?status=${expected}&notice=${notice}`);
}
