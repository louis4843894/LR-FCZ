import type { ReferenceRange } from "./equipment-reference";
/** Rules transcribed from the user-confirmed reference's gear-detail.js, not local game proofs. */
export function referenceRange(range: ReferenceRange | null, level = 0, mode: "base" | "multiply" | "increment" = "base", step: number | null = null): string {
  if (!range || range.min === null || range.max === null) return "尚無對照數值";
  if (!Number.isInteger(level) || level < 0 || level > 5) throw new Error("Unsupported reference level");
  if (level > 0 && mode === "increment" && step === null) return "該等級尚無對照規則";
  const change = (n: number) => mode === "multiply" ? n * (level + 1) : mode === "increment" ? n + level * (step ?? 0) : n;
  const format = (n: number) => { const value = Math.abs(n) < 1e-10 ? 0 : n; return `${value > 0 ? "+" : ""}${range.unit === "PERCENT" ? value.toFixed(1) : Number(value.toFixed(3))}`; };
  const a = change(range.min), b = change(range.max), suffix = ({PERCENT:"%",SECOND:" 秒",NUMBER:"",FLAT:"",POINT:" 點"} as Record<string,string>)[range.unit] ?? ` ${range.unit}`;
  return (a === b ? format(a) : `${format(a)} ～ ${format(b)}`) + suffix;
}
