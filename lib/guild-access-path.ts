export function guildReturnPath(value: unknown): string {
  if (typeof value !== "string" || value.length > 1200 || !value.startsWith("/") ||
    value.startsWith("//") || /[\\\x00-\x20\x7f]/.test(value)) return "/guild";
  const url = new URL(value, "https://navigation.invalid");
  if (!/^\/guild(?:\/[a-f0-9]{20}|\/members\/[a-f0-9]{20}|\/review)?$/.test(url.pathname)) return "/guild";
  return url.pathname + url.search + url.hash;
}

export function guildAccessUrl(next: unknown, notice?: string, register = false) {
  const params = new URLSearchParams({ next: guildReturnPath(next) });
  if (notice) params.set("notice", notice);
  if (register) params.set("mode", "register");
  return `/guild/access?${params}`;
}

export function guildDetailPath(identifier: string, query: Record<string, unknown>) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (typeof value === "string" && value.length <= 200) params.set(key, value);
  }
  return `/guild${identifier ? `/${identifier}` : ""}${params.size ? `?${params}` : ""}`;
}
