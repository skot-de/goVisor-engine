"use client";

/**
 * Client-Seite des Vorgangs-Kontingents (Preismodell v1.9 §4.3). Serverseite:
 * lib/kontingent.ts + /api/kontingent. Ein Vorgang ist ein aufgeschlossener Lead (erstes
 * Oeffnen Unterlagen/Bewertung) oder ein einzeln aufgerufenes Firmenprofil.
 *
 * `pruefeVorgang` schaltet den Vorgang frei UND sagt, ob er offen oder (fuer Free ueber dem
 * Monatslimit) gesperrt ist — darauf baut das Gating (Blur + CTA) auf.
 *
 * ⚠ Folgenlos, solange die Paywall aus ist: der Server liefert dann Limit null → immer
 * `offen`. ⚠ FAIL-OPEN: bei einem Fehler nie sperren (lieber einmal zu viel zeigen, als einen
 * Zahlenden aussperren). Je (art, ref) wird der Status gecacht — ein aufgeschlossener Vorgang
 * bleibt offen; ein zweiter Rundlauf entfaellt.
 */

export type VorgangGate = "offen" | "gesperrt";
const cache = new Map<string, VorgangGate>();

export async function pruefeVorgang(art: "lead" | "firma", ref: string): Promise<VorgangGate> {
  if (!ref) return "offen";
  const schluessel = `${art}:${ref}`;
  const bekannt = cache.get(schluessel);
  if (bekannt) return bekannt;
  try {
    const r = await fetch("/api/kontingent", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ art, ref }),
    });
    const j = r.ok ? await r.json() : null;
    const gate: VorgangGate = j?.status === "limit_erreicht" ? "gesperrt" : "offen";
    cache.set(schluessel, gate);
    try { window.dispatchEvent(new Event("kontingent:changed")); } catch { /* SSR */ }
    return gate;
  } catch {
    return "offen";   // fail-open
  }
}
