import { getGuildAccess } from "../../../lib/guild-access";

export async function GET() {
  const { status, username } = await getGuildAccess();
  return Response.json({ status, username }, {
    headers: { "Cache-Control": "private, no-store" },
  });
}
