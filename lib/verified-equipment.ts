import "server-only";
import { getEquipmentReferenceMap, type ReferenceEquipment } from "./equipment-reference";
import { referenceFilterOptions } from "./reference-filters";

import { readNormalizedText } from "./local-game-data";

export type VerifiedEquipment = {
  itemCode: string;
  dataCode: string;
  equipType: "ARMOR" | "WEAPON" | "ACC";
  starCount: number;
  maxEnchant: number;
  minAttributeCount: number;
  maxAttributeCount: number;
  names: Record<string, string>;
  effects: null;
  effectsStatus: "unparsed";
  recordScope: "equipment-template";
  updatedAt: string | null;
  sourceVersion: string;
  reference: ReferenceEquipment | null;
  referenceEffects: { effectId: string; conditionId: string | null }[] | null;
};

export async function getVerifiedEquipmentList(): Promise<VerifiedEquipment[]> {
  let text: string;
  try {
    text = await readNormalizedText("verified-equipment.json");
  } catch (error: unknown) {
    if (error instanceof Error && "code" in error && error.code === "ENOENT") return [];
    throw error;
  }
  const data: unknown = JSON.parse(text);
  if (!data || typeof data !== "object" || !("records" in data) || !Array.isArray(data.records)) throw new Error("裝備資料格式不正確");
  const references = await getEquipmentReferenceMap();
  return data.records.map((row): VerifiedEquipment => {
    if (row.recordScope !== "equipment-template" || row.effects !== null || row.effectsStatus !== "unparsed" ||
      !["ARMOR", "WEAPON", "ACC"].includes(row.equipType) || !Number.isInteger(row.starCount) || row.starCount < 1 || row.starCount > 9 ||
      !/^eq_[A-Za-z0-9_]+$/.test(row.itemCode) || row.dataCode !== row.itemCode + "_nm" || !row.names || typeof row.names !== "object" ||
      ![row.maxEnchant, row.minAttributeCount, row.maxAttributeCount].every((value: unknown) => Number.isInteger(value) && Number(value) >= 0)) throw new Error("裝備模板欄位驗證失敗");
    const reference = references.get(row.itemCode) ?? null;
    const referenceEffects = reference ? referenceFilterOptions(reference).map(({ effectId, conditionId }) => ({ effectId, conditionId })) : null;
    return { reference, referenceEffects, itemCode: row.itemCode, dataCode: row.dataCode, equipType: row.equipType, starCount: row.starCount,
      maxEnchant: row.maxEnchant, minAttributeCount: row.minAttributeCount, maxAttributeCount: row.maxAttributeCount,
      names: Object.fromEntries(Object.entries(row.names).filter((entry): entry is [string, string] => typeof entry[1] === "string")),
      effects: null, effectsStatus: "unparsed", recordScope: "equipment-template",
      updatedAt: typeof row.provenance?.capturedAt === "string" ? row.provenance.capturedAt : null,
      sourceVersion: typeof row.provenance?.gameVersion === "string" ? row.provenance.gameVersion : "未知" };
  });
}
export async function getVerifiedEquipment(dataCode: string): Promise<VerifiedEquipment | null> {
  if (!/^eq_[A-Za-z0-9_]+_nm$/.test(dataCode)) return null;
  return (await getVerifiedEquipmentList()).find((row) => row.dataCode === dataCode) ?? null;
}
