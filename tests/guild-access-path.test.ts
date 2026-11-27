import { describe, expect, it } from "vitest";
import { guildAccessUrl, guildDetailPath, guildReturnPath } from "../lib/guild-access-path";

describe("guild access return paths", () => {
  it("preserves a guild tower and filters through the sign-in flow", () => {
    const target = guildDetailPath("c0ae8c24042b277ceb3f", { tower: "7", q: "銀刀" });
    const url = new URL(guildAccessUrl(target, undefined, true), "https://ranger.example");
    expect(url.searchParams.get("mode")).toBe("register");
    expect(url.searchParams.get("next")).toBe(target);
  });

  it.each(["//outside.example", "/\\outside.example", "https://outside.example", "/guild/access",
    "/guild/../gear", "/guild/%2e%2e/gear", "/guild/review/extra", "/guild/%2foutside.example",
    "/guild\n/review"])("rejects an invalid destination %j", (target) => {
    expect(guildReturnPath(target)).toBe("/guild");
  });

  it("allows the review page as a destination without granting access", () => {
    expect(guildReturnPath("/guild/review?status=pending")).toBe("/guild/review?status=pending");
  });
});
