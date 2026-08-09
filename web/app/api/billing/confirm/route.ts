import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { createAdminClient } from "@/lib/supabase/admin";
import { feeForBand, anchorFlag, type Band } from "@/lib/billing";
import { identitaetBestaetigt, GESPERRT } from "@/lib/identityGate";

/* Kunde bestätigt das Auftragsband einer 'needs_confirmation'-Rechnung (Ticket #6). Läuft
 * serverseitig (success_fee_charges hat keine update-Policy — Schreiben nur über Admin-Client),
 * verifiziert aber die Session-Ownership. Anker-Wächter: ≥2 Bänder unter dem Anker → 'disputed'
 * (Beleg-Pflicht/HITL), sonst 'draft' (HITL-Freigabe → Versand). */
export async function POST(req: NextRequest) {
  const { chargeId, band } = await req.json().catch(() => ({}));
  if (!chargeId || !band) return NextResponse.json({ ok: false, error: "bad-request" }, { status: 400 });

  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ ok: false, error: "not-authenticated" }, { status: 401 });

  // Sperre: hier bestätigt der Kunde ein Auftragsband und löst damit eine Rechnung aus.
  // Das darf nur, wer die beanspruchte Firma auch belegt hat — `prepare` prüft dasselbe
  // über feeApplies(), aber diese Route ist ein zweiter, direkt aufrufbarer Eingang.
  const ident = await identitaetBestaetigt(user.id);
  if (!ident.bestaetigt) return NextResponse.json(GESPERRT, { status: 403 });

  const admin = createAdminClient();
  const { data: charge } = await admin.from("success_fee_charges").select("*").eq("id", chargeId).single();
  if (!charge || charge.user_id !== user.id) return NextResponse.json({ ok: false, error: "forbidden" }, { status: 403 });
  if (charge.status !== "needs_confirmation") return NextResponse.json({ ok: false, error: "not-open" }, { status: 409 });

  const flagged = anchorFlag(band as Band, (charge.anchor_band as Band) ?? null);
  const fee = feeForBand(band as Band, "kunde_bestaetigt");
  const { error } = await admin.from("success_fee_charges").update({
    award_value_band: band,
    value_source: "kunde_bestaetigt",
    fee_amount: fee,
    status: flagged ? "disputed" : "draft",   // disputed → Beleg/HITL; draft → HITL-Freigabe
  }).eq("id", chargeId);

  if (error) return NextResponse.json({ ok: false, error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true, fee, flagged, status: flagged ? "disputed" : "draft" });
}
