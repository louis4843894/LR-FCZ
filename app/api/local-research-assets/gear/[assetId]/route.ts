import { realpath, readFile, stat } from "node:fs/promises";
import path from "node:path";
import {
  getGearIconDirectory,
  isGearIconAssetId,
} from "../../../../../lib/local-research-assets";

export const dynamic = "force-dynamic";

const PNG_SIGNATURE = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);

function isMissingFileError(error: unknown): boolean {
  return (
    error instanceof Error &&
    "code" in error &&
    error.code === "ENOENT"
  );
}

function isLoopbackRequest(request: Request): boolean {
  const hostname = new URL(request.url).hostname.toLowerCase();
  return (
    hostname === "localhost" ||
    hostname === "127.0.0.1" ||
    hostname === "[::1]"
  );
}

export async function GET(
  request: Request,
  { params }: { params: Promise<{ assetId: string }> },
) {
  if (process.env.NODE_ENV !== "development" || !isLoopbackRequest(request)) {
    return new Response(null, { status: 404 });
  }

  const { assetId } = await params;
  if (!isGearIconAssetId(assetId)) {
    return new Response(null, { status: 404 });
  }

  let iconPath: string;
  try {
    const root = await realpath(getGearIconDirectory());
    iconPath = await realpath(path.join(root, `${assetId}_icon.png`));
    const relativePath = path.relative(root, iconPath);
    if (
      relativePath.length === 0 ||
      relativePath === ".." ||
      relativePath.startsWith(`..${path.sep}`) ||
      path.isAbsolute(relativePath)
    ) {
      return new Response(null, { status: 404 });
    }
    const file = await stat(iconPath);
    if (!file.isFile()) return new Response(null, { status: 404 });
  } catch (error: unknown) {
    if (isMissingFileError(error)) {
      return new Response(null, { status: 404 });
    }
    throw error;
  }

  const image = await readFile(iconPath);
  if (!image.subarray(0, PNG_SIGNATURE.length).equals(PNG_SIGNATURE)) {
    return new Response(null, { status: 404 });
  }

  return new Response(new Uint8Array(image), {
    headers: {
      "Content-Type": "image/png",
      "Cache-Control": "private, no-store",
      "X-Content-Type-Options": "nosniff",
    },
  });
}
