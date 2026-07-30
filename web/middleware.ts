import { NextResponse, type NextRequest } from "next/server";
import { updateSession } from "@/lib/supabase/middleware";

/**
 * Pre-Launch-Blackout.
 *
 * Auf Vercel (öffentlich, govisor.eu) liefert die App NUR eine leere schwarze Seite — niemand
 * sieht Inhalt oder erreicht /api. LOKAL (Dev, kein VERCEL-Env) läuft die volle App normal weiter.
 * So ist die Seite „vom Netz", aber lokal voll zugänglich.
 *
 * Blackout aufheben (echter Launch): diese Datei auf die reine `updateSession`-Weiterleitung
 * zurücksetzen (Git-Historie) + neu deployen.
 */
const BLACKOUT = process.env.VERCEL === "1"; // auf jedem Vercel-Deployment aktiv, lokal nie

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
