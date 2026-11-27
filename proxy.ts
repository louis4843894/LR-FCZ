import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";
import { guildAuthConfig, guildCookieOptions } from "./lib/guild-auth-client";
import { guildAccessUrl } from "./lib/guild-access-path";

export async function proxy(request: NextRequest) {
  const hasSession = request.cookies.getAll().some(({ name }) => /^sb-.*-auth-token(?:\.\d+)?$/.test(name));
  const { pathname } = request.nextUrl;
  if (!hasSession && pathname !== "/api/guild-session" && pathname !== "/guild/access" && pathname !== "/guild/access/owner") {
    const destination = request.nextUrl.clone();
    destination.searchParams.delete("_rsc");
    return NextResponse.redirect(new URL(guildAccessUrl(pathname + destination.search), request.url), {
      status: request.method === "POST" ? 303 : 307,
      headers: { "Cache-Control": "private, no-store" },
    });
  }

  let response = NextResponse.next({ request });
  const config = guildAuthConfig();
  if (config && hasSession) {
    const auth = createServerClient(config.url, config.key, {
      cookieOptions: guildCookieOptions,
      cookies: {
        getAll: () => request.cookies.getAll(),
        setAll(changes) {
          for (const { name, value } of changes) request.cookies.set(name, value);
          response = NextResponse.next({ request });
          for (const { name, value, options } of changes) response.cookies.set(name, value, options);
        },
      },
      global: { fetch: (input, init) => fetch(input, { ...init, cache: "no-store" }) },
    });
    await auth.auth.getClaims();
  }
  response.headers.set("Cache-Control", "private, no-store");
  return response;
}

export const config = { matcher: ["/guild/:path*", "/api/guild-session"] };
