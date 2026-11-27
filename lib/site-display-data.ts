import "server-only";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { gunzipSync } from "node:zlib";

// These are explicitly generated display models, never a fallback to private captures.
const cache = new Map<string, Promise<unknown>>();
export async function readSiteDisplay<T>(name: string): Promise<T | null> {
  if (!/^(?:characters|character-details|equipment|gear-icons|status|pvp-index|pvp-[a-f0-9]{12}|defense-[a-f0-9]{12}-[a-f0-9]{24})$/.test(name)) throw new Error("不支援的網站顯示資料");
  let value = cache.get(name);
  if (!value) {
    value = readFile(path.join(process.cwd(), "data/site-display", `${name}.json.gz`)).then(bytes => {
      if (bytes.length > 12 * 1024 * 1024) throw new Error("網站顯示資料超過上限");
      const document = JSON.parse(gunzipSync(bytes, { maxOutputLength: 80 * 1024 * 1024 }).toString("utf8"));
      if (document.schemaVersion !== 1 || document.kind !== "lr-site-display" || document.name !== name) throw new Error("網站顯示資料版本不符");
      return document.data;
    }).catch((error: unknown) => {
      cache.delete(name);
      if (error instanceof Error && "code" in error && error.code === "ENOENT") return null;
      throw error;
    });
    // Bound caching when browsing many individual player pages.
    if (cache.size >= 80) cache.delete(cache.keys().next().value!);
    cache.set(name, value);
  }
  return await value as T | null;
}
