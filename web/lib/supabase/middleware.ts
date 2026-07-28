import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

/* Session-Refresh in der Middleware (Supabase-SSR-Standard): hält das Auth-Cookie frisch,
 * damit Server Components eine gültige Session sehen. Kein Route-Gating hier — der
 * Explorer ist bewusst auch anonym nutzbar (Free-Tier), Gating erfolgt pro Feature. */
export async function updateSession(request: NextRequest) {
  let response = NextResponse.next({ request });

  // Ohne konfigurierten Anon-Key nichts tun (bis der Key in .env.local steht).
  if (!process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY) return response;

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
          response = NextResponse.next({ request });
          cookiesToSet.forEach(({ name, value, options }) => response.cookies.set(name, value, options));
        },
      },
    },
  );

  // WICHTIG (Supabase-Doku): getClaims/getUser aufrufen, damit die Session refresht wird.
  await supabase.auth.getUser();
  return response;
}
