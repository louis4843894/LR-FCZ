import "server-only";

import { access } from "node:fs/promises";
import path from "node:path";

const SNAPSHOT_ID = "lr_20261116T212608096_7b99bdd0";
const GEAR_ICON_DIRECTORY = path.join(
  process.cwd(),
  "data",
  "extracted",
  SNAPSHOT_ID,
  "apk_contents",
  "base",
  "assets",
  "res",
  "tutorial_res",
  "hd",
  "gear_icon",
);

export function getGearIconAssetId(dataCode: string): string | null {
  const match = /^(eq_[A-Za-z0-9_]+)_nm$/.exec(dataCode);
  return match?.[1] ?? null;
}

export function isGearIconAssetId(assetId: string): boolean {
  return /^eq_[A-Za-z0-9_]+$/.test(assetId);
}

export async function getLocalGearIconUrl(
  dataCode: string,
): Promise<string | null> {
  if (process.env.NODE_ENV !== "development") return null;

  const assetId = getGearIconAssetId(dataCode);
  if (!assetId) return null;

  try {
    await access(path.join(GEAR_ICON_DIRECTORY, `${assetId}_icon.png`));
  } catch (error: unknown) {
    if (
      error instanceof Error &&
      "code" in error &&
      error.code === "ENOENT"
    ) {
      return null;
    }
    throw error;
  }

  return `/api/local-research-assets/gear/${encodeURIComponent(assetId)}`;
}

export function getGearIconDirectory(): string {
  return GEAR_ICON_DIRECTORY;
}
