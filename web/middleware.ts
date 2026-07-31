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
 */
const BLACKOUT = process.env.NODE_ENV === "production" && process.env.LAUNCH_LIVE !== "1";

export async function middleware(request: NextRequest) {
  if (BLACKOUT) {
    return new NextResponse(BLACK_PAGE, {
      status: 200,
      headers: {
        "content-type": "text/html; charset=utf-8",
        "cache-control": "no-store",
        "x-robots-tag": "noindex, nofollow",
      },
    });
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
