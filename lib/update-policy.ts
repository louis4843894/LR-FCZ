// Taiwan time has a fixed UTC+8 offset. Use UTC arithmetic independent of host time zone.
const offset = 8 * 60 * 60 * 1000;
const week = 7 * 24 * 60 * 60 * 1000;
export function guildRefreshWindow(capturedAt: string, now = new Date()) {
  const local = new Date(now.getTime()+offset);
  const boundary = Date.UTC(local.getUTCFullYear(), local.getUTCMonth(), local.getUTCDate() - (local.getUTCDay()+5)%7, 12) - offset;
  const last = now.getTime() >= boundary ? boundary : boundary-week;
  return { due: Date.parse(capturedAt) < last, nextUpdateAt: new Date(last+week).toISOString() };
}
