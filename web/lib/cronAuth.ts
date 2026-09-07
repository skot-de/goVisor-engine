import "server-only";
import { NextRequest, NextResponse } from "next/server";
import { cronUrteil, DURCH, UNKONFIGURIERT } from "@/lib/cronWache.js";

/**
 * Fail-closed Auth für cron-/scheduler-getriggerte Server-Endpunkte (Alerts, Billing-Draft).
 *
 * Sicherheits-Härtung: FRÜHER wurde die Prüfung übersprungen, wenn `CRON_SECRET` nicht gesetzt
 * war (`if (secret) {…}`) — dann konnte JEDER den Endpunkt auslösen (E-Mail-Versand, Fee-Drafts).
 * Jetzt fail-closed: ohne gesetztes Secret ist der Endpunkt deaktiviert (503), mit Secret nur bei
 * passendem Header (Vercel-Cron sendet `Authorization: Bearer $CRON_SECRET`; manuell `x-cron-secret`).
 *
 * Die ENTSCHEIDUNG steht in `lib/cronWache.js` — Plain JS, damit `node` sie ohne Next-Laufzeit
 * prüfen kann. Hier bleibt nur die Übersetzung in HTTP.
 *
 * Gibt eine Fehler-Response zurück, wenn der Aufruf abzulehnen ist — sonst `null` (durchlassen).
 */
export function requireCronSecret(req: NextRequest): NextResponse | null {
  const urteil = cronUrteil(process.env.CRON_SECRET, (n) => req.headers.get(n));
  if (urteil === DURCH) return null;
  if (urteil === UNKONFIGURIERT) {
    return NextResponse.json({ ok: false, error: "CRON_SECRET nicht konfiguriert" }, { status: 503 });
  }
  return NextResponse.json({ ok: false, error: "forbidden" }, { status: 403 });
}
