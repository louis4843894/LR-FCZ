import { describe, it, expect } from "vitest";
import { filterEquipment } from "../lib/equipment-filters";
import { displaySourceText } from "../lib/display-text";
import data from "../data/normalized/verified-equipment.json";
describe("verified equipment filtering", () => {
  it("finds actual target by ID and name with type and stars", () => {
    expect(filterEquipment(data.records, { q: "eq_2202_amr_06", star: 6, type: "ARMOR" }).map(r => r.itemCode)).toEqual(["eq_2202_amr_06"]);
    expect(filterEquipment(data.records, { q: "日暮永遠" }).some(r => r.itemCode === "eq_2202_amr_06")).toBe(true);
  });
  it("never matches unknown effects to a known condition", () => {
    expect(filterEquipment(data.records, { effectIds: ["fixture-only"] })).toEqual([]);
  });
  it("implements AND and OR on isolated test-only effect associations", () => {
    const fixture = [{ ...data.records[0], itemCode: "test-only-a", effects: [{ effectId: "test-only-effect", conditionId: "test-only-water" }] }];
    expect(filterEquipment(fixture, { effectIds: ["test-only-effect", "absent"], mode: "AND" })).toHaveLength(0);
    expect(filterEquipment(fixture, { effectIds: ["test-only-effect", "absent"], mode: "OR" })).toHaveLength(1);
    expect(filterEquipment(fixture, { effectIds: ["test-only-effect"], conditionIds: ["absent"], mode: "AND" })).toHaveLength(0);
  });
  it("sorts stably regardless of source order", () => {
    expect(filterEquipment([...data.records].reverse(), {}).map(r => r.itemCode)).toEqual(filterEquipment(data.records, {}).map(r => r.itemCode));
  });
  it("decodes exactly one source newline boundary", () => {
    const slash = String.fromCharCode(92), lf = String.fromCharCode(10);
    expect(displaySourceText("[YSH]" + slash + "nUniform")).toBe("[YSH]" + lf + "Uniform");
    expect(displaySourceText("a" + lf + "b")).toBe("a" + lf + "b");
    const escaped = "a" + slash.repeat(2) + "nb";
    expect(displaySourceText(escaped)).toBe(escaped);
    expect(displaySourceText(displaySourceText("[YSH]" + slash + "nUniform"))).toBe("[YSH]" + lf + "Uniform");
  });
});
