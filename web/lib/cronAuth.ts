import "server-only";
import { NextRequest, NextResponse } from "next/server";

/**
 * Fail-closed Auth für cron-/scheduler-getriggerte Server-Endpunkte (Alerts, Billing-Draft).
 *
 * Sicherheits-Härtung: FRÜHER wurde die Prüfung übersprungen, wenn `CRON_SECRET` nicht gesetzt
 * war (`if (secret) {…}`) — dann konnte JEDER den Endpunkt auslösen (E-Mail-Versand, Fee-Drafts).
 * Jetzt fail-closed: ohne gesetztes Secret ist der Endpunkt deaktiviert (503), mit Secret nur bei
 * passendem Header (Vercel-Cron sendet `Authorization: Bearer $CRON_SECRET`; manuell `x-cron-secret`).
 *
 * Gibt eine Fehler-Response zurück, wenn der Aufruf abzulehnen ist — sonst `null` (durchlassen).
 */
export function requireCronSecret(req: NextRequest): NextResponse | null {
  const secret = process.env.CRON_SECRET;
  if (!secret) return NextResponse.json({ ok: false, error: "CRON_SECRET nicht konfiguriert" }, { status: 503 });
  const ok = req.headers.get("x-cron-secret") === secret ||
    req.headers.get("authorization") === `Bearer ${secret}`;
  return ok ? null : NextResponse.json({ ok: false, error: "forbidden" }, { status: 403 });
}
