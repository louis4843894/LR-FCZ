import { displaySourceText } from "./display-text";
export type EquipmentEffect = { effectId: string; conditionId: string | null };
export type FilterableEquipment = { itemCode: string; starCount: number; equipType: string; names: Partial<Record<string, string>>; effects: EquipmentEffect[] | null; referenceEffects?: EquipmentEffect[] | null };
export type EquipmentFilters = { q?: string; star?: number; type?: string; effectIds?: string[]; conditionIds?: string[]; mode?: "AND" | "OR"; sort?: string };
export function equipmentName(row: FilterableEquipment): string {
  return displaySourceText(row.names["zh-Hant"] ?? row.names.en ?? row.itemCode);
}
export function filterEquipment<T extends FilterableEquipment>(rows: T[], filters: EquipmentFilters): T[] {
  const query = (filters.q ?? "").trim().toLocaleLowerCase();
  const selected = rows.filter(row => {
    if (query && ![row.itemCode, ...Object.values(row.names).filter((s): s is string => typeof s === "string").map(displaySourceText)].some(s => s.toLocaleLowerCase().includes(query))) return false;
    if (filters.star && row.starCount !== filters.star) return false;
    if (filters.type && row.equipType !== filters.type) return false;
    const effectIds = filters.effectIds ?? [], conditionIds = filters.conditionIds ?? [];
    if ((effectIds.length || conditionIds.length) && row.effects === null && !row.referenceEffects) return false;
    const effects = row.effects ?? row.referenceEffects ?? [];
    const tests = [...effectIds.map(id => effects.some(e => e.effectId === id)), ...conditionIds.map(id => effects.some(e => e.conditionId === id))];
    return !tests.length || (filters.mode === "OR" ? tests.some(Boolean) : tests.every(Boolean));
  });
  return selected.sort((a, b) => {
    const first = filters.sort === "star-desc" ? b.starCount - a.starCount : filters.sort === "name" ? equipmentName(a).localeCompare(equipmentName(b), "zh-Hant") : 0;
    return first || a.itemCode.localeCompare(b.itemCode, "en");
  });
}
