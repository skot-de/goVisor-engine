import { NextRequest, NextResponse } from "next/server";
import { createAdminClient } from "@/lib/supabase/admin";
import { feeApplies, feeForBand, bandForValue, type Band } from "@/lib/billing";
import { requireCronSecret } from "@/lib/cronAuth";

/* Success-Fee-Rechnung vorbereiten (Ticket #6) — HITL: erzeugt nur ENTWÜRFE, bucht nie ab.
 * Getriggert wenn ein TED-Zuschlag zu einem bestätigten Kunden-Entity matcht (Award-Stream =
 * Integrationspunkt; hier per POST-Payload für Test/Anbindung). Ablauf: Gruppen-Match →
 * Attribution (Ausschreibung VOR Zuschlag geklickt, ≤12 Mon) → Wert-Waterfall → Entwurf.
 * CRON_SECRET-geschützt. */
type Award = {
  winner_entity_id: string; lead_id: string; tender_publication_number?: string;
  award_date: string; value_eur?: number | null; anchor_band?: Band | null;
};

export async function POST(req: NextRequest) {
  const deny = requireCronSecret(req);   // fail-closed (ohne CRON_SECRET deaktiviert)
  if (deny) return deny;

  const awards: Award[] = await req.json().catch(() => []);
  const list = Array.isArray(awards) ? awards : [awards];
  const admin = createAdminClient();
  const drafted: string[] = [];

  for (const a of list) {
    // Gruppen-Match: welche Nutzer führen dieses Gewinner-Entity als bestätigte Identität?
    const { data: users } = await admin.from("user_profiles")
      .select("id,plan,grace_until,entity_confidence,confirmed_entities")
      .contains("confirmed_entities", [a.winner_entity_id]);
    for (const u of users || []) {
      // Attribution: hat der Nutzer die Ausschreibung vor dem Zuschlag angesehen?
      const { data: inter } = await admin.from("user_lead_interactions")
        .select("first_click_at").eq("user_id", u.id).eq("lead_id", a.lead_id).single();
      const gate = feeApplies({
        plan: u.plan, graceUntil: u.grace_until, entityConfidence: u.entity_confidence,
        clickedAt: inter?.first_click_at ?? null, awardDate: a.award_date,
      });
      if (!gate.ok) continue;

      // Wert-Waterfall: echter Wert → Entwurf; sonst Kunden-Bestätigung nötig (mit Anker).
      const hatWert = a.value_eur != null && a.value_eur > 0;
      const band = hatWert ? bandForValue(a.value_eur!) : null;
      const { data: ins } = await admin.from("success_fee_charges").insert({
        user_id: u.id, lead_id: a.lead_id, tender_publication_number: a.tender_publication_number ?? null,
        award_date: a.award_date,
        value_source: hatWert ? "echt" : "kunde_offen",
        award_value_band: band, anchor_band: a.anchor_band ?? null,
        fee_amount: hatWert ? feeForBand(band as Band, "echt") : null,
        status: hatWert ? "draft" : "needs_confirmation",
      }).select("id").single();
      if (ins) drafted.push(ins.id);
    }
  }
  return NextResponse.json({ ok: true, drafted: drafted.length });
}
