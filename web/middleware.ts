import { NextResponse, type NextRequest } from "next/server";
import { updateSession } from "@/lib/supabase/middleware";

/**
 * Pre-Launch-Blackout — FAIL-CLOSED.
 *
 * Jedes Production-Deployment liefert NUR eine leere schwarze Seite (auch /api), SOLANGE nicht
 * explizit `LAUNCH_LIVE=1` gesetzt ist. Lokale Entwicklung (`next dev`, NODE_ENV≠production) läuft
 * immer voll — dort ist der Blackout nie aktiv.
 *
 * Wichtig (Härtung): der Schutz hängt NICHT mehr an einer plattform-gesetzten Var (`VERCEL`),
 * deren Fehlen früher die volle App öffentlich machte (fail-open auf fremdem Host/Klon/Preview).
 * Default ist jetzt schwarz; Freischalten = aktives Setzen von `LAUNCH_LIVE=1` in der Deploy-Umgebung
 * (kein Code-Change nötig).
 *
 * VORSCHAU-BYPASS (privat deployen, ohne öffentlich zu sein): ist der Blackout aktiv, kommt man mit
 * dem geheimen Schlüssel `?preview=<PREVIEW_KEY>` (oder gesetztem Cookie) trotzdem in die volle App;
 * die Öffentlichkeit sieht weiter Schwarz. FAIL-CLOSED: ist `PREVIEW_KEY` leer/ungesetzt, gibt es
 * KEINEN Bypass. So bleibt LAUNCH_LIVE ungesetzt (public = schwarz), und nur Sven kommt rein.
 */
const BLACKOUT = process.env.NODE_ENV === "production" && process.env.LAUNCH_LIVE !== "1";
const PREVIEW_KEY = process.env.PREVIEW_KEY ?? "";
const PREVIEW_COOKIE = "gv_preview";

function blackPage() {
  return new NextResponse(BLACK_PAGE, {
    status: 200,
    headers: {
      "content-type": "text/html; charset=utf-8",
      "cache-control": "no-store",
      "x-robots-tag": "noindex, nofollow",
    },
  });
}

export async function middleware(request: NextRequest) {
  if (BLACKOUT) {
    // Bypass nur, wenn ein PREVIEW_KEY gesetzt ist UND per Query/Cookie exakt getroffen wird.
    const q = new URL(request.url).searchParams.get("preview");
    const cookie = request.cookies.get(PREVIEW_COOKIE)?.value;
    const unlocked = PREVIEW_KEY.length > 0 && (q === PREVIEW_KEY || cookie === PREVIEW_KEY);
    if (!unlocked) return blackPage();
    // Schlüssel gültig → volle App; bei frischem ?preview den Cookie setzen (Folgeseiten ohne Query).
    const res = await updateSession(request);
    if (q === PREVIEW_KEY) {
      res.cookies.set(PREVIEW_COOKIE, PREVIEW_KEY, {
        httpOnly: true, sameSite: "lax", secure: true, path: "/", maxAge: 60 * 60 * 24 * 30,
      });
    }
    return res;
  }
  // Lokal: Auth-Session frisch halten wie gehabt, volle App.
  return await updateSession(request);
}

export const config = {
  // Alles außer statischen Assets — greift den Blackout bzw. hält die Auth-Session frisch. /api erfasst.
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)"],
};

// Reine schwarze Seite — kein Text, kein Logo.
const BLACK_PAGE = `<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex, nofollow"><title></title><style>html,body{margin:0;height:100%;background:#000}</style></head><body></body></html>`;
