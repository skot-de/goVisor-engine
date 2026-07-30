import { NextResponse, type NextRequest } from "next/server";
import { updateSession } from "@/lib/supabase/middleware";

/**
 * Baustellen-Sperre (Pre-Launch) VOR der Auth-Session-Middleware.
 *
 * Bis zum echten Start sieht jede:r Besucher:in nur die Coming-Soon-Seite — die eigentliche App
 * inklusive aller `/api`-Routen ist komplett dicht (HTTP 503). So kommt niemand auf govisor.eu rein.
 *
 * Owner-Bypass:  govisor.eu/?preview=<KEY>   (setzt ein Cookie, danach normal browsen)
 *   <KEY> = Vercel-Env-Var `PREVIEW_KEY`. Ist sie NICHT gesetzt, gibt es KEINEN Bypass → alles
 *   gesperrt (sicherer Default). Zum Freischalten in Vercel `PREVIEW_KEY` setzen und redeployen.
 *
 * Sperre wieder aufheben:  diese Datei auf die reine `updateSession`-Weiterleitung zurücksetzen
 *   (Git-Historie) + redeploy.
 */
const PREVIEW_KEY = process.env.PREVIEW_KEY || "";
const COOKIE = "gv_preview";

function isAllowed(req: NextRequest): boolean {
  if (!PREVIEW_KEY) return false; // kein Bypass konfiguriert → alles gesperrt (sicherer Default)
  if (req.nextUrl.searchParams.get("preview") === PREVIEW_KEY) return true;
  return req.cookies.get(COOKIE)?.value === PREVIEW_KEY;
}

export async function middleware(request: NextRequest) {
  // Gesperrt → Baustellenseite, harte Sperre (auch für /api). Kein Supabase-Aufruf nötig.
  if (!isAllowed(request)) {
    return new NextResponse(PAGE, {
      status: 503,
      headers: {
        "content-type": "text/html; charset=utf-8",
        "cache-control": "no-store",
        "retry-after": "86400",
        "x-robots-tag": "noindex, nofollow",
      },
    });
  }

  // Freigeschaltet → Auth-Session frisch halten wie gehabt.
  const res = await updateSession(request);
  // Wer über ?preview=<KEY> reinkommt, bekommt das Bypass-Cookie gesetzt.
  if (PREVIEW_KEY && request.nextUrl.searchParams.get("preview") === PREVIEW_KEY) {
    res.cookies.set(COOKIE, PREVIEW_KEY, {
      httpOnly: true, sameSite: "lax", path: "/", maxAge: 60 * 60 * 24 * 30,
    });
  }
  return res;
}

export const config = {
  // Alles außer statischen Assets — hält die Auth-Session frisch bzw. greift die Sperre. /api bleibt erfasst.
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)"],
};

const PAGE = `<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>goVisor — in Arbeit</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    min-height: 100vh; display: grid; place-items: center; padding: 24px;
    font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    background: radial-gradient(1200px 600px at 50% -10%, #0f2e24 0%, #07130f 55%, #050b09 100%);
    color: #e8f2ee;
  }
  .card { max-width: 560px; text-align: center; }
  .logo { font-size: 30px; font-weight: 800; letter-spacing: -0.02em; margin-bottom: 22px; }
  .logo b { color: #34d39a; }
  .badge {
    display: inline-block; font-size: 12px; font-weight: 600; letter-spacing: .12em;
    text-transform: uppercase; color: #7fe3c0; border: 1px solid #1f5344;
    background: #0c211a; padding: 6px 12px; border-radius: 999px; margin-bottom: 20px;
  }
  h1 { font-size: 26px; line-height: 1.25; font-weight: 700; margin-bottom: 12px; }
  p { font-size: 15px; line-height: 1.6; color: #9fb4ad; }
  .rule { width: 44px; height: 3px; background: #34d39a; border-radius: 2px; margin: 24px auto 0; opacity: .8; }
</style>
</head>
<body>
  <main class="card">
    <div class="logo">go<b>visor</b></div>
    <span class="badge">In Arbeit</span>
    <h1>Hier wird gerade etwas gebaut.</h1>
    <p>Die Plattform ist noch nicht öffentlich. Schau bald wieder vorbei.</p>
    <div class="rule"></div>
  </main>
</body>
</html>`;
