"use client";

/**
 * Client-Ausloeser fuers Vorgangs-Kontingent (Preismodell v1.9 §4.3). Serverseite:
 * lib/kontingent.ts + /api/kontingent. Ruft der Ausloeser (erstes Oeffnen Unterlagen/
 * Bewertung je Lead, bzw. Einzelaufruf eines Firmenprofils), schaltet das den Vorgang frei.
 *
 * ⚠ Folgenlos, solange die Paywall aus ist: der Server liefert dann Limit null (unbegrenzt)
 * und zaehlt nichts. Erst mit scharfer Paywall + Free-Stufe greift das Limit.
 *
 * Idempotent und doppelklick-fest: je (art, ref) wird pro Seitenaufenthalt nur einmal gerufen
 * (die Route ist ohnehin idempotent — das spart nur den ueberfluessigen Rundlauf).
 */

const gesehen = new Set<string>();

export function vorgangOeffnen(art: "lead" | "firma", ref: string): void {
  if (!ref) return;
  const schluessel = `${art}:${ref}`;
  if (gesehen.has(schluessel)) return;
  gesehen.add(schluessel);
  fetch("/api/kontingent", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ art, ref }),
  })
    .then((r) => (r.ok ? r.json() : null))
    .then(() => { try { window.dispatchEvent(new Event("kontingent:changed")); } catch { /* SSR */ } })
    .catch(() => { gesehen.delete(schluessel); });   // beim naechsten Mal erneut versuchen
}
