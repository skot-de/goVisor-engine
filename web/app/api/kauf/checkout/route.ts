import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { stripeEnabled } from "@/lib/stripe";
import { preisOk } from "@/lib/preise";

/**
 * Kauf starten: zusaetzliche Seats/Profile (Mehrfachprofile, Phase 2b).
 *
 * ⚠ EHRLICH STUB, solange Stripe nicht scharf ist (lib/stripe.ts, UMGESETZT=false) und das
 * Kostenmodell keine Preise gesetzt hat. Es wird KEIN Erfolg vorgetaeuscht — der Endpunkt
 * sagt klar, was fehlt (Preis bzw. Zahlungsanbindung). Der geld-sichere Teil ist die
 * idempotente Gutschrift (0027 kauf_gutschreiben), die der Webhook nach echter Zahlung ruft.
 */
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  const sb = await createClient();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return NextResponse.json({ error: "Anmeldung erforderlich" }, { status: 401 });
  const { data } = await sb.from("user_profiles").select("org_id, role").eq("id", user.id).single();
  const d = (data ?? {}) as { org_id?: string | null; role?: string | null };
  if (!d.org_id || !(d.role === "owner" || d.role === "admin")) {
    return NextResponse.json({ error: "Nur Inhaber/Admins können kaufen." }, { status: 403 });
  }
  let body: { art?: string; menge?: number };
  try { body = await req.json(); } catch { return NextResponse.json({ error: "ungültig" }, { status: 400 }); }
  const art = body.art === "profile" ? "profile" : body.art === "seat" ? "seat" : null;
  const menge = Math.floor(Number(body.menge ?? 1));
  if (!art || !(menge > 0 && menge <= 100)) return NextResponse.json({ error: "art/menge ungültig" }, { status: 400 });

  if (!preisOk(art)) {
    return NextResponse.json({ error: "Preis noch nicht gesetzt — das Kostenmodell ist offen." }, { status: 503 });
  }
  if (!stripeEnabled) {
    return NextResponse.json({ error: "Zahlung noch nicht konfiguriert (Stripe).", stub: true }, { status: 503 });
  }
  // TODO(Integration): Stripe Checkout Session mit metadata { org_id, art, menge } anlegen und
  // deren URL zurueckgeben; der Webhook verbucht nach Zahlung ueber erfuelleKauf (lib/kauf.ts).
  return NextResponse.json({ error: "Checkout noch nicht implementiert." }, { status: 503 });
}
