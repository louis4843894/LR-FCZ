import type { ViewerTeam } from "./defense-viewer";

export type DisplayPlayer = { title: string; teams: ViewerTeam[] };
export type DisplayRankingContext = { scopeLabel: string; rank: number; score: number | null; snapshotId: string; rankingCapturedAt: string; lastCheckedAt: string | null; cacheState: string | null; latestStatus: string };
export type DisplayDefense = { displayPlayers: DisplayPlayer[]; rankingContext: DisplayRankingContext };

const forbiddenKeys = new Set(["playerId", "guildId", "characterInstanceId", "characterInstanceIdentity", "equipmentInstanceIdentity", "equipmentInstanceHash", "instanceHash", "owner", "sourceFile", "captureDirectory", "privateDirectory", "sourceField", "valueGradeRaw", "cookie", "token", "password", "secret", "LF_AC"]);
/** Fail closed before a display artifact can be written or published. */
export function assertSiteDisplaySafe(value: unknown, depth = 0): void {
  if (depth > 48) throw new Error("網站顯示資料巢狀層數過深");
  if (typeof value === "string") {
    if (/(?:^|[^A-Za-z0-9])[Uu][a-f0-9]{32}(?:$|[^A-Za-z0-9])/i.test(value) || /(?:LF_AC\s*=|eyJ[A-Za-z0-9_-]{20,}\.|runtime\.private|data[\\/]research|[A-Z]:[\\/])/i.test(value)) throw new Error("網站顯示資料包含私人值");
  } else if (Array.isArray(value)) {
    for (const item of value) assertSiteDisplaySafe(item, depth + 1);
  } else if (value && typeof value === "object") {
    for (const [key, item] of Object.entries(value)) {
      if (forbiddenKeys.has(key)) throw new Error("網站顯示資料包含非顯示欄位");
      assertSiteDisplaySafe(item, depth + 1);
    }
  } else if (typeof value === "number" && !Number.isFinite(value)) throw new Error("網站顯示資料包含無效數值");
}
