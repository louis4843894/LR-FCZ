import { describe, expect, it } from "vitest";
import { assertSiteDisplaySafe } from "../lib/site-display-contract";

describe("production display boundary", () => {
  it("rejects nested account and instance identifiers without printing their values", () => {
    for (const key of ["playerId", "guildId", "characterInstanceIdentity", "equipmentInstanceIdentity", "sourceFile", "valueGradeRaw"]) {
      expect(() => assertSiteDisplaySafe({ teams: [{ slots: [{ [key]: "test-only" }] }] })).toThrow("非顯示欄位");
    }
    const account = "U"+"a".repeat(32);
    expect(() => assertSiteDisplaySafe({ note: account })).toThrow("私人值");
    expect(() => assertSiteDisplaySafe({ note: "data/research/runtime.private/test" })).toThrow("私人值");
  });
  it("retains observed zero values, unknown fields and explicit absence separately", () => {
    const data = { progress: { leonardPoints: 0, awakening: { state: "not_returned", name: null } }, template: { availability: { skills: "absent" }, skills: [] }, unit: { position: 1, stars: 6, actualEffects: null } };
    const original = JSON.stringify(data);
    expect(() => assertSiteDisplaySafe(data)).not.toThrow();
    expect(JSON.stringify(data)).toBe(original);
  });
});
