import { beforeEach, describe, expect, it, vi } from "vitest";
vi.mock("server-only", () => ({}));
vi.mock("node:fs/promises", () => ({ readFile: vi.fn() }));
import { readFile } from "node:fs/promises";
import { getVerifiedEquipment } from "../lib/verified-equipment";
import data from "../data/normalized/verified-equipment.json";
describe("equipment website allowlist", () => {
  beforeEach(() => vi.mocked(readFile).mockResolvedValue(JSON.stringify(data)));
  it("returns 6 stars while retaining unknown effects as null", async () => {
    const row = await getVerifiedEquipment("eq_2202_amr_06_nm");
    expect(row?.starCount).toBe(6); expect(row?.effects).toBeNull(); expect(row?.effectsStatus).toBe("unparsed");
  });
  it("does not pass research fields to rendering", async () => {
    const document = { ...data, records: data.records.map(r => ({ ...r, objectAddress: "must-not-leak", rawMemory: "must-not-leak" })) };
    vi.mocked(readFile).mockResolvedValue(JSON.stringify(document));
    expect(JSON.stringify(await getVerifiedEquipment("eq_2202_amr_06_nm"))).not.toContain("must-not-leak");
  });
  it("rejects an empty array masquerading as unparsed effects", async () => {
    vi.mocked(readFile).mockResolvedValue(JSON.stringify({records:[{...data.records[0],effects:[]}]}));
    await expect(getVerifiedEquipment(data.records[0].dataCode)).rejects.toThrow();
  });
  it("rejects arbitrary identifiers before reading disk", async () => {
    expect(await getVerifiedEquipment("../../runtime.private/objects")).toBeNull();
  });
});
