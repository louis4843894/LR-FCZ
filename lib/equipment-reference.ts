import "server-only";
import { readNormalizedText } from "./local-game-data";
export type ReferenceRange = { min: number | null; max: number | null; unit: string };
export type ReferenceOption = { optionKey: string; name: string; category: string; range: ReferenceRange | null; upgradeStep: number | null; attributeId: number | null };
export type ReferenceEquipment = {
  itemCode: string; normalOptions: ReferenceOption[];
  advanced: null | { condition: { key: string; label: string }; defaultOption: ReferenceOption; switchOptions: ReferenceOption[] };
  skillPlus: { effectCode: string; name: string; dimension: string; range: ReferenceRange | null; upgradeStep: number | null }[];
  specPlus: null | { name: string; basicOptions: ReferenceOption[]; specialOptions: { description: string | null; conditions: {key:string;label:string}[]; triggerChance: ReferenceRange | null; effectCode: string | null; effectName: string | null; chance: ReferenceRange | null; chanceUpgrade: number | null; magnitudeRange: ReferenceRange | null; magnitudeUpgrade: number | null; durationRange: ReferenceRange | null; durationUpgradeSeconds: number | null }[] };
};
export async function getEquipmentReferenceMap(): Promise<Map<string, ReferenceEquipment>> {
  // Research comparison is deliberately unavailable to production pending publication rights.
  if (process.env.NODE_ENV !== "development") return new Map();
  try {
    const data = JSON.parse(await readNormalizedText("equipment-reference-preview.json"));
    if (data.sourceKind !== "external-user-confirmed" || data.publicationAllowed !== false || !Array.isArray(data.records)) throw new Error("Invalid reference preview");
    return new Map(data.records.map((r: ReferenceEquipment) => [r.itemCode, r]));
  } catch (error: unknown) {
    if (error instanceof Error && "code" in error && error.code === "ENOENT") return new Map();
    throw error;
  }
}
