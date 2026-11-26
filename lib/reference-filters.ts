import type { ReferenceEquipment } from "./equipment-reference";

/** Preserve external option keys, skill codes and structured condition identities. */
export function referenceFilterOptions(row: ReferenceEquipment) {
  const result: { effectId: string; name: string; conditionId: string | null; conditionName: string | null }[] = [];
  for (const e of row.normalOptions) result.push({ effectId: e.optionKey, name: e.name, conditionId: null, conditionName: null });
  if (row.advanced) {
    const { condition, defaultOption, switchOptions } = row.advanced;
    for (const e of [defaultOption, ...switchOptions]) result.push({ effectId: e.optionKey, name: e.name, conditionId: condition.key, conditionName: condition.label });
  }
  for (const e of row.skillPlus) result.push({ effectId: e.effectCode, name: `Skill+ · ${e.name}`, conditionId: null, conditionName: null });
  if (row.specPlus) {
    for (const e of row.specPlus.basicOptions) result.push({ effectId: e.optionKey, name: e.name, conditionId: null, conditionName: null });
    for (const e of row.specPlus.specialOptions) {
      if (!e.effectCode) continue;
      for (const c of e.conditions.length ? e.conditions : [null]) result.push({ effectId: e.effectCode, name: `Skill / Spec+ · ${e.effectName ?? e.effectCode}`, conditionId: c?.key ?? null, conditionName: c?.label ?? null });
    }
  }
  return result;
}
