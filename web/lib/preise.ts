import "server-only";
/* Preise fuer Seats/Profile — ⚠ PLATZHALTER. Das Kostenmodell ist offen (Sven, 2026-09-30).
 * Endpreise kommen entweder hierher (Cent-Betraege per Env) oder spaeter als Stripe-Price-IDs.
 * 0 = unkonfiguriert → der Checkout weist den Kauf freundlich ab, statt 0 € zu buchen. */
export const PREIS_CENTS: Record<"seat" | "profile", number> = {
  seat:    Number(process.env.PREIS_SEAT_CENTS ?? 0),
  profile: Number(process.env.PREIS_PROFILE_CENTS ?? 0),
};
export function preisOk(art: "seat" | "profile"): boolean { return PREIS_CENTS[art] > 0; }
