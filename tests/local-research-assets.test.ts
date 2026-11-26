import { describe, expect, it, vi } from "vitest";

vi.mock("server-only", () => ({}));

import {
  getGearIconAssetId,
  isGearIconAssetId,
} from "../lib/local-research-assets";

describe("local gear icon candidate mapping", () => {
  it("maps only equipment name codes to their exact filename stem", () => {
    expect(getGearIconAssetId("eq_2202_acc_06_nm")).toBe("eq_2202_acc_06");
    expect(getGearIconAssetId("FIX_AVD_PROB_MUL_nm")).toBeNull();
    expect(getGearIconAssetId("eq_2202_acc_06")).toBeNull();
  });

  it("rejects path syntax in asset identifiers", () => {
    expect(isGearIconAssetId("eq_2202_acc_06")).toBe(true);
    expect(isGearIconAssetId("../secret")).toBe(false);
    expect(isGearIconAssetId("eq_2202/../../secret")).toBe(false);
    expect(isGearIconAssetId("eq_2202.acc_06")).toBe(false);
  });
});
