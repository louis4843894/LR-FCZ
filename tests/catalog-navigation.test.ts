import { describe, expect, it } from "vitest";
import { catalogHref, catalogPageNumbers, catalogParams, removeCatalogFilter } from "../lib/catalog-navigation";

describe("catalogue navigation preserves the selected dataset", () => {
  it("removes one effect without losing other repeated filters or OR mode", () => {
    const source = { q: "制服", effect: ["hp", "skill"], condition: ['{"args":[1]}'], mode: "OR", page: "9" };
    const next = removeCatalogFilter(source, "effect", "hp");
    const params = new URL(catalogHref("/gear", next), "https://local.invalid").searchParams;
    expect(params.getAll("effect")).toEqual(["skill"]);
    expect(params.getAll("condition")).toEqual(['{"args":[1]}']);
    expect(params.get("q")).toBe("制服");
    expect(params.get("mode")).toBe("OR");
    expect(params.has("page")).toBe(false);
    expect(source.page).toBe("9");
    expect(source.effect).toEqual(["hp", "skill"]);
  });
  it("changes page while retaining every filter and safely encoding text", () => {
    const params = new URL(catalogHref("/characters", { q: "熊 & 兔", star: "9", element: "FIRE", sort: "star-desc" }, { page: "3" }), "https://local.invalid").searchParams;
    expect(Object.fromEntries(params)).toEqual({ q: "熊 & 兔", star: "9", element: "FIRE", sort: "star-desc", page: "3" });
    expect([...catalogParams({ q: "", page: undefined, effect: ["a", "b"] })]).toEqual([["effect", "a"], ["effect", "b"]]);
  });
  it("keeps first, last and adjacent pages without duplicate pages or false gaps", () => {
    expect(catalogPageNumbers(1, 101)).toEqual([1, 2, "gap", 101]);
    expect(catalogPageNumbers(50, 101)).toEqual([1, "gap", 49, 50, 51, "gap", 101]);
    expect(catalogPageNumbers(4, 6)).toEqual([1, 2, 3, 4, 5, 6]);
    expect(catalogPageNumbers(1, 1)).toEqual([1]);
  });
});
