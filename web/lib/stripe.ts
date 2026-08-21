import "server-only";

/* Stripe (Ticket #6) — INTEGRATIONS-STUB. Ohne STRIPE_SECRET_KEY passiert nichts Echtes.
 * Zum Scharfschalten: `stripe`-SDK anbinden und die TODOs füllen. Bewusst kein harter
 * Dependency, damit der Build ohne Stripe-Account läuft.
 * Stripe dient der Karten-Hinterlegung und der Abo-Zahlung. Die Erfolgsprämie, für die
 * dieser Stub urspruenglich mitgedacht war, ist am 2026-08-21 gestrichen. */

const KEY = process.env.STRIPE_SECRET_KEY;
export const stripeEnabled = !!KEY;

// Karte hinterlegen (SetupIntent) — für spätere Abo-Rechnung.
export async function createSetupIntent(userId: string): Promise<{ clientSecret: string | null; stub: boolean }> {
  if (!KEY) return { clientSecret: null, stub: true };
  // TODO(Integration): const si = await stripe.setupIntents.create({ metadata: { userId } }); return { clientSecret: si.client_secret, stub:false }
  return { clientSecret: null, stub: false };
}

// Abo-Rechnung (kein Auto-Charge bei Success-Fee — das läuft über HITL + Rechnung).
export async function chargeSubscription(_userId: string, _amount: number): Promise<{ ok: boolean; stub: boolean }> {
  if (!KEY) return { ok: false, stub: true };
  // TODO(Integration): stripe.invoices / paymentIntents …
  return { ok: true, stub: false };
}
