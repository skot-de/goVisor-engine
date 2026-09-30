import { NextResponse } from "next/server";
import { stripeEnabled } from "@/lib/stripe";
// erfuelleKauf (lib/kauf.ts) verbucht idempotent — hier eingebunden, damit der Pfad steht.
import { erfuelleKauf } from "@/lib/kauf";

/**
 * Zahlungs-Webhook (Stripe) → Kontingent gutschreiben. ⚠ EHRLICH STUB bis Stripe scharf ist.
 *
 * Wenn scharf: Signatur gegen STRIPE_WEBHOOK_SECRET pruefen, bei `checkout.session.completed`
 * die metadata { org_id, art, menge } lesen und `erfuelleKauf(...)` mit der Session-ID als
 * Referenz rufen — idempotent (0027), also gegen Webhook-Retries sicher.
 */
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST() {
  if (!stripeEnabled) {
    return NextResponse.json({ error: "Zahlung nicht konfiguriert" }, { status: 503 });
  }
  // TODO(Integration): const sig = req.headers.get('stripe-signature');
  //   const evt = stripe.webhooks.constructEvent(rawBody, sig, STRIPE_WEBHOOK_SECRET);
  //   if (evt.type === 'checkout.session.completed') {
  //     const s = evt.data.object; const { org_id, art, menge } = s.metadata;
  //     await erfuelleKauf(org_id, art, Number(menge), s.id, s.amount_total);
  //   }
  void erfuelleKauf;   // haelt den Import bis zur Umsetzung
  return NextResponse.json({ error: "Webhook noch nicht implementiert." }, { status: 503 });
}
